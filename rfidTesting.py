import serial
import datetime as dt
import threading
import queue
import csv
import time
import os
import revpimodio2
import sys

from rfidClasses import *
#from rfidUtil import *

# CSV file for fleet list
csvFleetList = 'fleet_list.csv' 

# UPS Variables
shutdown_countdown = 10  # seconds before shutdown
rpi = revpimodio2.RevPiModIO(autorefresh=True)  # initialize RevPiModIO 

# Relay Output Value
rpi.io.RevPiOutput.value = 0 # default relay open/ LED Off 

# current RFID and VID values
vid1Msg = "init"
vid2Msg = "init"
rfid1FuelScanMsg = "init"
rfid2FuelScanMsg = "init"

# previous RFID and VID values for counting
prevFuelScanMsgFromRFID1 = "init" # previous RFID for lane 1
prevFuelScanMsgFromRFID2 = "init" # previous RFID for lane 2

# RFID Reader Counters
seqNumFuelScanMsgFromRFID1 = 0 # counter for RFID reader 1
seqNumFuelScanMsgFromRFID2 = 0 # counter for RFID reader 2

emptyCounter1 = 0 # counter for empty reads on RFID reader 1
emptyCounter2 = 0 # counter for empty reads on RFID reader 2

NO_READ_LIMIT = 3 # number of empty reads before resetting the counter

# RFID Read Counts - Each lane may require different read counts
readCount1 = 5 # required read count for RFID reader 1
readCount2 = 5 # required read count for RFID reader 2

# create reader - this should make it easier having two readers
rfidReader1 = Reader(False, "empty") # initalize first reader
rfidReader2 = Reader(False, "empty") # second reader

# may eventually use this properly, but for now just using global variables
vidLane1 = Reader(False, "empty") # VID detector lane 1
vidLane2 = Reader(False, "empty") # VID detector lane 2

# queue creation
queue1 = queue.Queue() # queue for reader 1
queue2 = queue.Queue() # queue for reader 2
queue3 = queue.Queue() # queue for VID detector

'''
Serial Port Allocations
'''
# reader 1 - port 1 - COM11 on Windows - /dev/ttyUSB0 on Linux assumed
try:
    ser1 = serial.Serial('/dev/ttyUSB0', baudrate=9600) #open serial port default 8N1
except serial.SerialException as e:
    print(f"Error opening serial port for reader 1: {e}")
    rpi.io.RevPiOutput.value = 1 # turn on LED
    sys.exit()

# reader 2 - port 2 - COM7 on Windows - /dev/ttyUSB1 on Linux
try:
    ser2 = serial.Serial('/dev/ttyUSB1', baudrate=9600) #open serial port default 8N1
except serial.SerialException as e:
    print(f"Error opening serial port for reader 2: {e}")
    rpi.io.RevPiOutput.value = 1 # turn on LED
    sys.exit()

# VID detector input - port 3 - /dev/ttyUSB2 on Linux
try:
    ser3 = serial.Serial('/dev/ttyUSB2', baudrate=9600)
except serial.SerialException as e:
    print(f"Error opening serial port for VID detector: {e}")
    rpi.io.RevPiOutput.value = 1 # turn on LED
    sys.exit()

# output serial port - port 4 - /dev/ttyUSB3 on linux
try:
    ser4 = serial.Serial('/dev/ttyUSB3', baudrate=9600)
except serial.SerialException as e:
    print(f"Error opening serial port for output: {e}")
    rpi.io.RevPiOutput.value = 1 # turn on LED
    sys.exit()

# create serial read lines
def serial_read(s, readerName):
    while 1:
        try:
            sline = s.readline()
            if readerName == "R1:": # add to reader 1 queue
                queue1.put(sline.decode('utf-8'))
            elif readerName == "R2:": # add to reader 2 queue
                queue2.put(sline.decode('utf-8')) # may consider bringing readerName back
            else: # add to VID queue
                queue3.put(sline.decode('utf-8'))
        except Exception as e:
            print(f"Error reading from {readerName}: {e}")
            rpi.io.RevPiOutput.value = 1 # turn on LED
            sys.exit() # this may not work

# checks what the current results filename is
def get_results_filename():
    return f"results_{dt.datetime.now().strftime('%Y%m%d')}.csv"

resultsFile = get_results_filename()  # initialize results file name
current_log_date = dt.datetime.now().date()  # initialize current log date

# this function logs the results to a CSV file
# considering another column which has flags that describe the mismatch issue
def log_result(now, lane, vid, rfid, rfidNum, match):
    global resultsFile, current_log_date
    # check if the date has changed
    if now.date() != current_log_date:
        resultsFile = get_results_filename()  # update results file name
        current_log_date = now.date()  # update current log date

    # create headers for csv file
    write_header = not os.path.exists(resultsFile) or os.stat(resultsFile).st_size == 0

    try:
        with open(resultsFile, 'a', newline='') as csvfile:
            fieldnames = ['timestamp', 'lane', 'vid', 'rfid', 'rfidNum', 'match']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if write_header: # write header only if the file is new or has changed date
                writer.writeheader()
            writer.writerow({
                'timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
                'lane': lane,
                'vid': repr(vid),
                'rfid': repr(rfid),
                'rfidNum': rfidNum,
                'match': match
            })
    except Exception as e:
        print(f"Error writing to results file {resultsFile}: {e}")
        rpi.io.RevPiOutput.value = 1 # turn on LED
        sys.exit()

# extract fleet number from VID String
def msg2BusNum(vid_string):
    # assuming the VID string is formatted as "1-BBT<fleet_number>,00000000"
    try:
        return vid_string.split(',')[0][5:]
    except Exception as e: #Might make index error
        # might include more logic here to handle different formats
        print(f"Error extracting fleet number: '{vid_string}': {e}")
        return None

# function to check if VID string is in scope
def is_vid_in_scope(fleet_number):
    with open(csvFleetList, mode='r') as file:
        for row in csv.reader(file):
            if fleet_number == row[0]:
                return True
    return False

# function to check battery health of RFID tag
def tag_battery_check(tagString):
    if tagString.startswith('n'):
        return "Low Battery Detected: " + tagString

# UPS Shutdown Function
def shutdown_countdown_func(): 
    while 1: # loop this thread to constantly monitor UPS status
        if rpi.io.RevPiStatus.value & (1<<6):
            for i in range(shutdown_countdown, 0, -1):
                time.sleep(1)
                if (rpi.io.RevPiStatus.value & (1<<6)):
                    print("Shutdown aborted!")
                    time.sleep(1)
                    break
                print(f"Shutting down in {i} seconds...")
            else:
                print("Shutting down now...")
                os.system("sudo shutdown now")
        else:
            time.sleep(0.5)  # sleep for a short time to avoid busy waiting

# UPS Shutdown Thread
shutdown_thread = threading.Thread(target=shutdown_countdown_func).start() 

# creating each thread to receive data from readers
r1 = threading.Thread(target=serial_read, args=(ser1, "R1:",)).start() # reader 1 thread
r2 = threading.Thread(target=serial_read, args=(ser2, "R2:",)).start() # reader 2 thread
vid = threading.Thread(target=serial_read, args=(ser3, "VID",)).start() # VID detector thread

'''
Main Loop - this will run continuously to read from queues and process data
'''
while True:
    # time of event
    now = dt.datetime.now()

    # lane 1 RFID reader queue
    if queue1.empty():
        rfidReader1.change_tag("empty")
        rfid1FuelScanMsg = "empty" # this variable shouldnt be used, should use class get_tag
        emptyCounter1 += 1 # increment the empty counter for RFID reader 1
        
        if emptyCounter1 >= NO_READ_LIMIT: # seqNumFuelScanMsgFromRFID resets if too many empty reads
            seqNumFuelScanMsgFromRFID1 = 0 

    else:
        emptyCounter1 = 0 # reset empty counter if queue is not empty
        rfidReader1.change_tag(queue1.get(True))
        # conversion to the proper string, look up table handled inside of reader class
        rfid1FuelScanMsg = "1-BBT" + rfidReader1.get_fleetNumber(csvFleetList) + ",00000000" + '\r\n' # not sure if new line required for final build
        seqNumFuelScanMsgFromRFID1 += 1
        if rfid1FuelScanMsg != prevFuelScanMsgFromRFID1:
            seqNumFuelScanMsgFromRFID1 = 0 # reset the counter to 0 if different tag is read
        
        prevFuelScanMsgFromRFID1 = rfid1FuelScanMsg  # update previous RFID for lane 1
        print("RFID Lane 1 Read: " + repr(rfid1FuelScanMsg)) # print the current RFID for testing purposes

    # lane 2 RFID reader queue
    if queue2.empty():
        rfidReader2.change_tag("empty")
        rfid2FuelScanMsg = "empty"
        emptyCounter2 += 1

        if emptyCounter2 >= NO_READ_LIMIT: # seqNumFuelScanMsgFromRFID resets if too many empty reads
            seqNumFuelScanMsgFromRFID2 = 0
        
    else:
        emptyCounter2 = 0
        rfidReader2.change_tag(queue2.get(True))
        rfid2FuelScanMsg = "2-BBT" + rfidReader2.get_fleetNumber(csvFleetList) + ",00000000" + '\r\n' #VID 800 outputs \r and \n
        seqNumFuelScanMsgFromRFID2 += 1 # increment the counter for RFID reader 2
        if rfid2FuelScanMsg != prevFuelScanMsgFromRFID2:
            seqNumFuelScanMsgFromRFID2 = 0
        
        prevFuelScanMsgFromRFID2 = rfid2FuelScanMsg  # update previous RFID for lane 2
        print("RFID Lane 2 Read: " + repr(rfid2FuelScanMsg)) # repr to show escape characters like \n
    
    # VID detector queue
    vid_input = None # ensure no freezing
    try:
        vid_input = queue3.get_nowait() # non-blocking get from queue
    except queue.Empty: # if queue is empty
        vid_input = None 

    if vid_input is None: # if no input from VID detector
        vid1Msg = "empty" # might be issues here if one lane has a VID and the other does not
        vid2Msg = "empty"
    elif vid_input[0] == "1":
        vid1Msg = vid_input
        print("VID Lane 1 Read: " + repr(vid1Msg))
        ser4.write(vid1Msg.encode('utf-8'))  # send to serial port 4
    elif vid_input[0] == "2":
        vid2Msg = vid_input
        print("VID Lane 2 Read: " + repr(vid2Msg))
        ser4.write(vid2Msg.encode('utf-8'))  # send to serial port 4

    
    # true or false if results match for lane 1
    vid1MatchesRfid1 = msg2BusNum(vid1Msg) == msg2BusNum(rfid1FuelScanMsg) and vid1Msg != "empty" and rfid1FuelScanMsg != "empty"
    vid2MatchesRfid2 = msg2BusNum(vid2Msg) == msg2BusNum(rfid2FuelScanMsg) and vid2Msg != "empty" and rfid2FuelScanMsg != "empty"
    
    # RFID data only recorded if certain read conditions are met

    # lane 1 comparison - ser4 should be writing the VID anyway
    if seqNumFuelScanMsgFromRFID1 > readCount1: #and vid1Msg == rfid1FuelScanMsg: added after trial
        # in future, this will be written to plc, for now just record
        log_result(now, '1', vid1Msg, rfid1FuelScanMsg, rfidReader1.get_tag(), vid1MatchesRfid1)
    # record regardless of RFID, but only if VID is in scope
    elif vid1Msg != "empty" and is_vid_in_scope(msg2BusNum(vid1Msg)):
        log_result(now, '1', vid1Msg, rfid1FuelScanMsg, rfidReader1.get_tag(), vid1MatchesRfid1)
        #ser4.write(vid1Msg.encode('utf-8')) # send to serial port 4
    
    # lane 2 comparison
    if seqNumFuelScanMsgFromRFID2 > readCount2: #and vid2Msg == rfid2FuelScanMsg:
        log_result(now, '2', vid2Msg, rfid2FuelScanMsg, rfidReader2.get_tag(), vid2MatchesRfid2)
    elif vid2Msg != "empty" and is_vid_in_scope(msg2BusNum(vid2Msg)):
        log_result(now, '2', vid2Msg, rfid2FuelScanMsg, rfidReader2.get_tag(), vid2MatchesRfid2)
        #ser4.write(vid2Msg.encode('utf-8')) # send to serial port 4
    
    # this doesnt allow both lanes to handle at the same time effectively 

    time.sleep(1)  # sleep for a second before next iteration