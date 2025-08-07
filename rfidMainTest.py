"""
Attempting to resolve VID thread and queue issues

Trying to also resolve RFID tag logging issues

This includes bare minimum RS232 connections:
    Reader 1
    VID Input
"""

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
from rfidUtil import *

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
"""
try:
    ser1 = serial.Serial('/dev/ttyUSB0', baudrate=9600) #open serial port default 8N1
except serial.SerialException as e:
    print(f"Error opening serial port for reader 1: {e}")
    rpi.io.RevPiOutput.value = 1 # turn on LED
    sys.exit()
"""


# VID detector input - port 3 - /dev/ttyUSB2 on Linux
try:
    ser3 = serial.Serial('/dev/ttyUSB0', baudrate=9600)
except serial.SerialException as e:
    print(f"Error opening serial port for VID detector: {e}")
    rpi.io.RevPiOutput.value = 1 # turn on LED
    #sys.exit()


resultsFile = get_results_filename()  # initialize results file name
current_log_date = dt.datetime.now().date()  # initialize current log date


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



# creating each thread to receive data from readers
#r1 = threading.Thread(target=serial_read, args=(ser1, "R1:",)).start() # reader 1 thread

vid = threading.Thread(target=serial_read, args=(ser3, "VID",)).start() # VID detector thread

'''
Main Loop - this will run continuously to read from queues and process data
'''
while True:
    # time of event
    now = dt.datetime.now()

    # lane 1 RFID reader queue
    if queue1.empty():
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
        print("RFID Lane 1 Read: " + repr(currentRFID1)) # print the current RFID for testing purposes

    
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

    if currentVID1 != "empty":
        print("VID Lane 1 Read: " + repr(currentVID1))
        # serial write
    
    if currentVID2 != "empty":
        print("VID Lane 2 Read: " + repr(currentVID2))
        # serial write


    """
    if vid_input is None: # if no input from VID detector
        currentVID1 = "empty" # might be issues here if one lane has a VID and the other does not
        currentVID2 = "empty"
    elif vid_input[0] == "1":
        currentVID1 = vid_input
        print("VID Lane 1 Read: " + repr(currentVID1))
    elif vid_input[0] == "2":
        currentVID2 = vid_input
        print("VID Lane 2 Read: " + repr(currentVID2))
    """

    
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
    
    # this doesnt allow both lanes to handle at the same time effectively 

    time.sleep(1)  # sleep for a second before next iteration