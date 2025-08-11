import serial
import datetime as dt
import threading
import queue
import csv
import time
import os
import revpimodio2
import sys
import tkinter as tk

from rfidClasses import *
from rfidUtil import *
from rfidGui import RfidGui

# CSV file for fleet list
csvFleetList = 'fleet_list.csv' 

# UPS Variables
shutdown_countdown = 10  # seconds before shutdown
rpi = revpimodio2.RevPiModIO(autorefresh=True)  # initialize RevPiModIO 

# Relay Output Value
rpi.io.RevPiOutput.value = 0 # default relay open/ LED Off 

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

emptyCounter1 = 0 # counter for empty reads on RFID reader 1
emptyCounter2 = 0 # counter for empty reads on RFID reader 2

noReadLimit = 3 # number of empty reads before resetting the counter

# RFID Read Counts - Each lane may require different read counts
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


resultsFile = get_results_filename()  # initialize results file name
current_log_date = dt.datetime.now().date()  # initialize current log date

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


def serial_read(s, readerName):
    """
    Read strings received from an RFID reader or VID 800 and organizes them into the correct queue.
    Strings are UTF-8 decoded.

    Args:
        readerName: String which indicates which reader the string is from: R1, R2 else VID 800.

    Raises:
        Exception: An error occured when communicating with the reader. The LED while turn on.
    """
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
            print(f"[{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error reading from {readerName}: {e}")
            rpi.io.RevPiOutput.value = 1 # turn on LED 


# considering another column which has flags that describe the mismatch issue
def log_result(now, lane, vid, rfid, rfidNum, match):
    """
    Stores the results of the program into a CSV file for data analysis. 
    Data is placed into columns: timestamp, lane, vid, rfid, rfidNum, match

    Args:
        now: The current date and time
        lane: Which lane the RFID/ VID reading occured
        vid: String received by the VID
        rfid: String converted from the RFID string
        rfidNum: String received by the RFID reader
        match: Bool if vid == rfid
    
    Raises:
        Exception: An error occured writing to the CSV file.
    """
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



# creating each thread to receive data from readers
r1 = threading.Thread(target=serial_read, args=(ser1, "R1:",)).start() # reader 1 thread
r2 = threading.Thread(target=serial_read, args=(ser2, "R2:",)).start() # reader 2 thread
vid = threading.Thread(target=serial_read, args=(ser3, "VID",)).start() # VID detector thread


'''
Main Loop - this will run continuously to read from queues and process data
'''
while True:
    # gui stuff
    #root = tk.Tk()
    #appGui = RfidGui(root)  # create the GUI instance
    #root.mainloop()  # start the GUI event loop
    # time of event
    now = dt.datetime.now()

    # lane 1 RFID reader queue
    if queue1.empty():
        #appGui.update_lane(1, 'blue')  
        reader1.change_tag("empty")
        currentRFID1 = "empty" # this variable shouldnt be used, should use class get_tag
        emptyCounter1 += 1 # increment the empty counter for RFID reader 1
        
        if emptyCounter1 >= noReadLimit: # counterRFID resets if too many empty reads
            counterRFID1 = 0 

    else:
        emptyCounter1 = 0 # reset empty counter if queue is not empty
        reader1.change_tag(queue1.get(True))
        # conversion to the proper string, look up table handled inside of reader class
        currentRFID1 = "1-BBT" + reader1.get_fleetNumber(csvFleetList) + ",00000000" + '\r\n' # not sure if new line required for final build
        counterRFID1 += 1
        if currentRFID1 != prevRFID1:
            counterRFID1 = 0 # reset the counter to 0 if different tag is read
        
        prevRFID1 = currentRFID1  # update previous RFID for lane 1
        #print("RFID Lane 1 Read: " + repr(currentRFID1)) # print the current RFID for testing purposes

        # testing gui stuff
        #appGui.update_lane(1, 'green')  # update lane 1 status to green in GUI

    # lane 2 RFID reader queue
    if queue2.empty():
        reader2.change_tag("empty")
        currentRFID2 = "empty"
        emptyCounter2 += 1

        if emptyCounter2 >= noReadLimit: # counterRFID resets if too many empty reads
            counterRFID2 = 0
        
    else:
        emptyCounter2 = 0
        reader2.change_tag(queue2.get(True))
        currentRFID2 = "2-BBT" + reader2.get_fleetNumber(csvFleetList) + ",00000000" + '\r\n' #VID 800 outputs \r and \n
        counterRFID2 += 1 # increment the counter for RFID reader 2
        if currentRFID2 != prevRFID2:
            counterRFID2 = 0
        
        prevRFID2 = currentRFID2  # update previous RFID for lane 2
        #print("RFID Lane 2 Read: " + repr(currentRFID2)) # repr to show escape characters like \n
    

    # VID detector queue
    vidsList = []
    while True:
        try:
            vid_input = queue3.get_nowait()
            vidsList.append(vid_input)
        except queue.Empty:
            break

    currentVID1 = "empty"  # default value for VID lane 1
    currentVID2 = "empty"  # default value for VID lane 2

    for vidIn in vidsList:
        if vidIn.startswith("1"): # VID for lane 1
            currentVID1 = vidIn
        elif vidIn.startswith("2"): # VID for lane 2
            currentVID2 = vidIn


    # these are to be removed in the final build
    if currentVID1 != "empty":
        #print("VID Lane 1 Read: " + repr(currentVID1))
        ser4.write(currentVID1.encode('utf-8'))  # send to serial port 4
    
    if currentVID2 != "empty":
        #print("VID Lane 2 Read: " + repr(currentVID2))
        ser4.write(currentVID2.encode('utf-8'))  # send to serial port 4

    # true or false if results match for lane 1
    matchresult1 = vid_to_fleet_number(currentVID1) == vid_to_fleet_number(currentRFID1) and currentVID1 != "empty" and currentRFID1 != "empty"
    matchresult2 = vid_to_fleet_number(currentVID2) == vid_to_fleet_number(currentRFID2) and currentVID2 != "empty" and currentRFID2 != "empty"
    
    # RFID data only recorded if certain read conditions are met

    # lane 1 comparison - ser4 should be writing the VID anyway
    if counterRFID1 > readCount1: #and currentVID1 == currentRFID1: added after trial
        # in future, this will be written to plc, for now just record
        log_result(now, '1', currentVID1, currentRFID1, reader1.get_tag(), matchresult1)
    # record regardless of RFID, but only if VID is in scope
    elif currentVID1 != "empty" and is_vid_in_scope(vid_to_fleet_number(currentVID1), csvFleetList):
        log_result(now, '1', currentVID1, currentRFID1, reader1.get_tag(), matchresult1)
        #ser4.write(currentVID1.encode('utf-8')) # send to serial port 4
    
    # lane 2 comparison
    if counterRFID2 > readCount2: #and currentVID2 == currentRFID2:
        log_result(now, '2', currentVID2, currentRFID2, reader2.get_tag(), matchresult2)
    elif currentVID2 != "empty" and is_vid_in_scope(vid_to_fleet_number(currentVID2), csvFleetList):
        log_result(now, '2', currentVID2, currentRFID2, reader2.get_tag(), matchresult2)
        #ser4.write(currentVID2.encode('utf-8')) # send to serial port 4

    time.sleep(1)  # sleep for a second before next iteration