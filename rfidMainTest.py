"""
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
#import revpimodio2
import sys
from dash import Dash, html, dcc, callback, Output, Input
import sqlite3

from rfidClasses import *
from rfidUtilTesting import *


# CSV file for fleet list
csvFleetList = 'fleet_list.csv'

# UPS Variables
shutdown_countdown = 10  # seconds before shutdown
#rpi = revpimodio2.RevPiModIO(autorefresh=True)  # initialize RevPiModIO

# Relay Output Value
#rpi.io.RevPiOutput.value = 0 # default relay open/ LED Off

# current RFID and VID values
vid_1_Msg = "EMPTY"
vid_2_Msg = "EMPTY"
rfid_1_FuelScanMsg = "EMPTY"
rfid_2_FuelScanMsg = "EMPTY"

# previous RFID and VID values for counting
prevFuelScanMsgFromRFID1 = "INIT" # previous RFID for lane 1
prevFuelScanMsgFromRFID2 = "INIT" # previous RFID for lane 2

# RFID Reader Counters
seqNumFuelScanMsgFromRFID1 = 0 # counter for RFID reader 1
seqNumFuelScanMsgFromRFID2 = 0 # counter for RFID reader 2

rfid_1_NullPolls = 0 # counter for empty reads on RFID reader 1
rfid_2_NullPolls = 0 # counter for empty reads on RFID reader 2

NO_READ_LIMIT = 3 # number of empty reads before resetting the counter

# RFID Read Counts - Each lane may require different read counts
readCount1 = 5 # required read count for RFID reader 1
readCount2 = 5 # required read count for RFID reader 2

# create reader - this should make it easier having two readers
rfid_1_Reader = Reader(False, "EMPTY") # initalize first reader
rfid_2_Reader = Reader(False, "EMPTY") # second reader

# may eventually use this properly, but for now just using global variables
vid_Reader = Reader(False, "EMPTY") # VID detector lane 1


# queue creation
rfid_1_Queue = queue.Queue() # queue for reader 1
rfid_2_Queue = queue.Queue() # queue for reader 2
vidQueue = queue.Queue() # queue for VID detector

'''
Serial Port Allocations
'''
# reader 1 - port 1 - COM11 on Windows - /dev/ttyUSB0 on Linux assumed

try:
    rfid_1_In = serial.Serial('COM19', baudrate=9600) #open serial port default 8N1
except serial.SerialException as e:
    print(f"Error opening serial port for reader 1: {e}")
    #rpi.io.RevPiOutput.value = 1 # turn on LED




# VID detector input - port 3 - /dev/ttyUSB2 on Linux
try:
    vid_In = serial.Serial('COM21', baudrate=9600)
except serial.SerialException as e:
    print(f"Error opening serial port for VID detector: {e}")
    #rpi.io.RevPiOutput.value = 1 # turn on LED
    #sys.exit()


resultsFile = get_results_filename()  # initialize results file name
current_log_date = dt.datetime.now().date()  # initialize current log date


# create serial read lines
def serial_read(s, readerName):
    while 1:
        try:
            sline = s.readline()
            if readerName == "RFRD1:": # add to reader 1 queue
                rfid_1_Queue.put(sline.decode('utf-8'))
            elif readerName == "RFRD2:": # add to reader 2 queue
                rfid_2_Queue.put(sline.decode('utf-8')) # may consider bringing readerName back
            else: # add to VID queue
                vidQueue.put(sline.decode('utf-8'))
        except Exception as e:
            print(f"Error reading from {readerName}: {e}")
            #rpi.io.RevPiOutput.value = 1 # turn on LED

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
        with open(resultsFile, mode='a', encoding="utf-8", newline='') as csvfile:
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
        #rpi.io.RevPiOutput.value = 1 # turn on LED
        sys.exit()


# creating each thread to receive data from readers
r1 = threading.Thread(target=serial_read, args=(rfid_1_In, "RFRD1:",)).start() # reader 1 thread

vid = threading.Thread(target=serial_read, args=(vid_In, "VID",)).start() # VID detector thread

# testing database stuff
conn = sqlite3.connect('vid_data.db', check_same_thread = False) # create or connect to the database
# MAKE SURE ONLY THIS SCRIPT WRITES, NOTHING ELSE TO AVOID CONFLICTS
cursor = conn.cursor() # create a cursor object to execute SQL commands

cursor.execute('''
    CREATE TABLE IF NOT EXISTS vid_data (
            lane INTEGER PRIMARY KEY,
            vid TEXT,
            rfid TEXT
    )
''')  # creates table with limited columns

conn.commit()  # commit the changes to the database

# initialize a column for each lane
for lane in [1, 2]:
    cursor.execute('INSERT OR IGNORE INTO vid_data (lane, vid, rfid) VALUES (?, ?, ?)', (lane, '', ''))
conn.commit()  # commit the changes to the database



'''
Main Loop - this will run continuously to read from queues and process data
'''
while True:
    now = dt.datetime.now()  # get current time for logging

    # lane 1 RFID reader queue
    if rfid_1_Queue.empty():
        rfid_1_Reader.update_tag("EMPTY")
        rfid_1_FuelScanMsg = "EMPTY" # this variable shouldnt be used, should use class get_tag
        rfid_1_NullPolls += 1 # increment the empty counter for RFID reader 1

        if rfid_1_NullPolls >= NO_READ_LIMIT: # seqNumFuelScanMsgFromRFID resets if too many empty reads
            seqNumFuelScanMsgFromRFID1 = 0

    else:
        rfid_1_NullPolls = 0 # reset empty counter if queue is not empty
        rfid_1_Reader.update_tag(rfid_1_Queue.get(True))
        # conversion to the proper string, look up table handled inside of reader class
        rfid_1_FuelScanMsg = "1-BBT" + rfid_1_Reader.get_fleetNumber(csvFleetList) + ",00000000" + '\r\n'
        seqNumFuelScanMsgFromRFID1 += 1
        if rfid_1_FuelScanMsg != prevFuelScanMsgFromRFID1:
            seqNumFuelScanMsgFromRFID1 = 0 # reset the counter to 0 if different tag is read

        prevFuelScanMsgFromRFID1 = rfid_1_FuelScanMsg  # update previous RFID for lane 1
        print("RFID Lane 1 Read: " + repr(rfid_1_FuelScanMsg)) # print the current RFID for testing purposes


    # VID detector queue
    vidsList = []
    while True:
        try:
            vid_input = vidQueue.get_nowait()
            vidsList.append(vid_input)
        except queue.Empty:
            break

    vid_1_Msg = "EMPTY"  # default value for VID lane 1 this is pretty dumb looking at it now
    vid_2_Msg = "EMPTY"  # default value for VID lane 2

    for vidIn in vidsList:
        if vidIn.startswith("1"): # VID for lane 1
            vid_1_Msg = vidIn
        elif vidIn.startswith("2"): # VID for lane 2
            vid_2_Msg = vidIn

    # testing RFID stuff
    #rfid_1_FuelScanMsg = "1-BBT9999,12344321"
    #rfid_2_FuelScanMsg = "2-BBT2809,00000000"  # testing RFID for lane 2

    # testing database update
    update_lane_data(cursor, 1, vid_1_Msg, rfid_1_FuelScanMsg)  # update lane 1 data in the database
    update_lane_data(cursor, 2, vid_2_Msg, rfid_2_FuelScanMsg)  # update lane 2 data in the database
    conn.commit()  # commit the changes to the database

    #print("lane 1: " + str(read_lane_data(cursor, 1)))  # print lane 1 data for testing
    #print("lane 2: " + str(read_lane_data(cursor, 2)))  # print lane 2 data for testing

    # true or false if results match for lane 1
    vid_1_MatchesRfid1 = msg2BusNum(vid_1_Msg) == msg2BusNum(rfid_1_FuelScanMsg) and vid_1_Msg != "EMPTY" and rfid_1_FuelScanMsg != "EMPTY"
    vid_2_MatchesRfid2 = msg2BusNum(vid_2_Msg) == msg2BusNum(rfid_2_FuelScanMsg) and vid_2_Msg != "EMPTY" and rfid_2_FuelScanMsg != "EMPTY"

    #if vid_1_Msg != "EMPTY":
        #print("VID Lane 1 Read: " + repr(vid_1_Msg))
        #pass
        # serial write

    #if vid_2_Msg != "EMPTY":
        #print("VID Lane 2 Read: " + repr(vid_2_Msg))
        # serial write


    # RFID data only recorded if certain read conditions are met

    # lane 1 comparison - plc_Out should be writing the VID anyway
    #if seqNumFuelScanMsgFromRFID1 > readCount1: #and vid_1_Msg == rfid_1_FuelScanMsg: added after trial
        # in future, this will be written to plc_Out, for now just record
        #log_result(now, '1', vid_1_Msg, rfid_1_FuelScanMsg, rfid_1_Reader.get_tag(), vid_1_MatchesRfid1)
    # record regardless of RFID, but only if VID is in scope
    #elif vid_1_Msg != "EMPTY" and is_vid_in_scope(msg2BusNum(vid_1_Msg), csvFleetList):
        #log_result(now, '1', vid_1_Msg, rfid_1_FuelScanMsg, rfid_1_Reader.get_tag(), vid_1_MatchesRfid1)
        #plc_Out.write(vid_1_Msg.encode('utf-8')) # send to serial port 4

    if seqNumFuelScanMsgFromRFID1 > readCount1:
        print("Lane 1 RFID Read Confirmed: " + repr(rfid_1_FuelScanMsg))
        # log etc
        # serial write
    elif vid_1_Msg != "EMPTY" and is_vid_in_scope(msg2BusNum(vid_1_Msg), csvFleetList) and rfid_1_FuelScanMsg == "EMPTY":
        print("Lane 1 VID Read Confirmed without RFID: " + repr(vid_1_Msg))
        # raise a flag "Issue Bus #### RFID Failure"
        # log
        # serial write
    elif vid_1_Msg != "EMPTY":
        print("Lane 1: " + repr(vid_1_Msg))

    time.sleep(1)  # sleep for a second before next iteration