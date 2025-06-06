import serial
import datetime as dt
import threading
import queue
import csv
import time
import os
from rfidClasses import *


# CSV file for fleet list
csvFleetList = 'fleet_list.csv' 

# current RFID and VID values
currentVID1 = "init"
currentVID2 = "init"
currentRFID1 = "init"
currentRFID2 = "init"

# previous RFID and VID values for counting
prevRFID1 = "init" # previous RFID for lane 1
prevRFID2 = "init" # previous RFID for lane 2

# RFID Reader Counters
counterRFID1 = 0 # counter for RFID reader 1
counterRFID2 = 0 # counter for RFID reader 2

# RFID Read Counts
readCount1 = 5 # required read count for RFID reader 1
readCount2 = 5 # required read count for RFID reader 2

# create reader - this should make it easier having two readers
reader1 = Reader(False, "empty") # initalize first reader
reader2 = Reader(False, "empty") # second reader

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
ser1 = serial.Serial('/dev/ttyUSB0', baudrate=9600) #open serial port default 8N1

# reader 2 - port 2 - COM7 on Windows - /dev/ttyUSB1 on Linux
ser2 = serial.Serial('/dev/ttyUSB1', baudrate=9600) #open serial port default 8N1

# VID detector input - port 3 - /dev/ttyUSB2 on Linux
ser3 = serial.Serial('/dev/ttyUSB2', baudrate=9600)

# output serial port - port 4 - /dev/ttyUSB3 on linux
ser4 = serial.Serial('/dev/ttyUSB3', baudrate=9600)


# create serial read lines
def serial_read(s, readerName):
    while 1:
        sline = s.readline()
        if readerName == "R1:": # add to reader 1 queue
            queue1.put(sline.decode('utf-8'))
        elif readerName == "R2:": # add to reader 2 queue
            queue2.put(sline.decode('utf-8')) # may consider bringing readerName back
        else: # add to VID queue
            queue3.put(sline.decode('utf-8'))

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

# extract fleet number from VID String
def vid_to_fleet_number(vid_string):
    # assuming the VID string is formatted as "1-BBT<fleet_number>,00000000"
    return vid_string.split(',')[0][5:]

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

# creating each thread to receive data from readers
r1 = threading.Thread(target=serial_read, args=(ser1, "R1:",)).start() # reader 1 thread
r2 = threading.Thread(target=serial_read, args=(ser2, "R2:",)).start() # reader 2 thread
vid = threading.Thread(target=serial_read, args=(ser3, "VID",)).start() # VID detector thread

while True:
    # time of event
    now = dt.datetime.now()

    # lane 1 RFID reader queue
    if queue1.empty():
        reader1.change_tag("empty")
        currentRFID1 = "empty" # this variable shouldnt be used, should use class get_tag
        counterRFID1 = 0 # reset the counter to 0 if queue is empty
    else:
        reader1.change_tag(queue1.get(True))
        # conversion to the proper string, look up table handled inside of reader class
        currentRFID1 = "1-BBT" + reader1.get_fleetNumber(csvFleetList) + ",00000000" + '\r\n' # not sure if new line required for final build
        if currentRFID1 == prevRFID1: 
            counterRFID1 += 1 # increment the counter for RFID reader 1
        else: # need to reset too if a reasonable amount of time has passed maybe
            counterRFID1 = 0 # reset the counter to 0 if different tag is read
        prevRFID1 = currentRFID1  # update previous RFID for lane 1
        print("RFID Lane 1 Read: " + repr(currentRFID1)) # print the current RFID for testing purposes

    # lane 2 RFID reader queue
    if queue2.empty():
        reader2.change_tag("empty")
        currentRFID2 = "empty"
        counterRFID2 = 0 # reset the counter to 0 if queue is empty
    else:
        reader2.change_tag(queue2.get(True))
        currentRFID2 = "2-BBT" + reader2.get_fleetNumber(csvFleetList) + ",00000000" + '\r\n' #VID 800 outputs \r and \n
        if currentRFID2 == prevRFID2:
            counterRFID2 += 1
        else: 
            counterRFID2 = 0 # reset the counter to 0 if different tag is read
        prevRFID2 = currentRFID2  # update previous RFID for lane 2
        print("RFID Lane 2 Read: " + repr(currentRFID2)) # repr to show escape characters like \n
    
    # VID detector queue
    vid_input = None # ensure no freezing
    try:
        vid_input = queue3.get_nowait() # non-blocking get from queue
    except queue.Empty: # if queue is empty
        vid_input = None 

    if vid_input is None: # if no input from VID detector
        currentVID1 = "empty" # might be issues here if one lane has a VID and the other does not
        currentVID2 = "empty"
    elif vid_input[0] == "1":
        currentVID1 = vid_input
        print("VID Lane 1 Read: " + repr(currentVID1))
    elif vid_input[0] == "2":
        currentVID2 = vid_input
        print("VID Lane 2 Read: " + repr(currentVID2))

    # lane 1 comparison 
    if counterRFID1 > readCount1 and currentVID1 == currentRFID1 and currentVID1 != "empty" and currentRFID1 != "empty": # ensure not empty so that nothing is printed either
        print("Output to PLC: " + repr(currentVID1)) # output only VID detector string
        ser4.write(currentVID1.encode('utf-8')) # send to serial port 4
    
    # lane 2 comparison
    if counterRFID2 > readCount2 and currentVID2 == currentRFID2 and currentVID2 != "empty" and currentRFID2 != "empty": # ensure not empty so that nothing is printed either
        print("Output to PLC: " + repr(currentVID2)) # output only VID detector string
        ser4.write(currentVID2.encode('utf-8')) # send to serial port 4
    
    # true or false if results match for lane 1
    matchresult1 = currentVID1 == currentRFID1 and currentVID1 != "empty" and currentRFID1 != "empty"
    matchresult2 = currentVID2 == currentRFID2 and currentVID2 != "empty" and currentRFID2 != "empty"

    # lane 1 logging
    if currentRFID1 != "empty": # ensure there is an RFID tag read
        log_result(now, '1', currentVID1, currentRFID1, reader1.get_tag(), matchresult1)
    # record regardless of RFID, but only if VID is in scope
    elif currentVID1 != "empty" and is_vid_in_scope(vid_to_fleet_number(currentVID1)):
        log_result(now, '1', currentVID1, currentRFID1, reader1.get_tag(), matchresult1)

    # lane 2 logging
    if currentRFID2 != "empty":
        log_result(now, '2', currentVID2, currentRFID2, reader2.get_tag(), matchresult2)
    elif currentVID2 != "empty" and is_vid_in_scope(vid_to_fleet_number(currentVID2)):
        log_result(now, '2', currentVID2, currentRFID2, reader2.get_tag(), matchresult2)

    time.sleep(1)  # sleep for a second before next iteration