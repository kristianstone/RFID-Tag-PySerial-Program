import serial
import datetime as dt
import threading
import queue
import csv
import time
import os
import revpimodio2
import sys
import sqlite3

from rfidClasses import *
from rfidUtil import *


# CSV file for fleet list
csvFleetList = 'fleet_list.csv' 

# UPS Variables
shutdown_countdown = 10  # seconds before shutdown
rpi = revpimodio2.RevPiModIO(autorefresh=True)  # initialize RevPiModIO 

# Relay Output Value
rpi.io.RevPiOutput.value = 0 # default relay open/ LED Off 

# VID values
vid1Msg = "EMPTY"
vid2Msg = "EMPTY"
vid1MsgCnt = 0
vid2MsgCnt = 0
vidsListSize = 0

# RFID values
rfid1FuelScanMsg = "EMPTY"
rfid2FuelScanMsg = "EMPTY"
# previous RFID and VID values for counting
rfid1PrevFuelScanMsg = "INIT" # initial RFID for lane 1
rfid2PrevFuelScanMsg = "INIT" # initial previous RFID for lane 2
# RFID Reader Counters
rfid1SeqNumFuelScanMsg = 0 # counter for RFID reader 1
rfid2SeqNumFuelScanMsg = 0 # counter for RFID reader 2
rfid1NullPolls = 0 # counter for empty reads on RFID reader 1
rfid2NullPolls = 0 # counter for empty reads on RFID reader 2

NO_READ_LIMIT = 3 # number of empty reads before resetting the counter
# RFID Read Counts - Each lane may require different read counts
RFID_READS_TO_TRUST = 5 # required read count for RFID reader


# create reader - this should make it easier having two readers
rfid1Reader = Reader(False, "EMPTY") # initalize first reader
rfid2Reader = Reader(False, "EMPTY") # second reader

# may eventually use this properly, but for now just using global variables
vidLane1 = Reader(False, "EMPTY") # VID detector lane 1
vidLane2 = Reader(False, "EMPTY") # VID detector lane 2

# queue creation
rfid1Queue = queue.Queue() # queue for reader 1
rfid2Queue = queue.Queue() # queue for reader 2
vidQueue = queue.Queue() # queue for VID detector

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
                rfid1Queue.put(sline.decode('utf-8'))
            elif readerName == "R2:": # add to reader 2 queue
                rfid2Queue.put(sline.decode('utf-8')) # may consider bringing readerName back
            else: # add to VID queue
                vidQueue.put(sline.decode('utf-8'))
        except Exception as e:
            print(f"[{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error reading from {readerName}: {e}")
            rpi.io.RevPiOutput.value = 1 # turn on LED 


def batteryStatus(tagId) -> str:

    status = "NO_BATT"

    if tagId[0] == 'N':
        status = "CHARGED_BATT" 
    elif tagId[0] == 'n':
        status = "REPLACE_BATT"

    return status
        

# considering another column which has flags that describe the mismatch issue
def log_result(when, tagOrigin, vidMsg, rfidMsg, rfidNum, prevRfidNum, seqNum, nullPolls, batteryStatus, match, rfidInBothLanes):
    """
    Stores the results of the program into a CSV file for data analysis. 
    Data is placed into columns: timestamp, lane, vidMsg, rfidMsg, rfidNum, seqNum, rfidNullPolls, batteryStatus, match, rfidInBothLanes

    Args:
        when            : The current date and time
        tagOrigin       : Which lane the RFID/ VID reading occured
        vidMsg          : String received by the VID
        rfidMsg         : String converted from the RFID string
        rfidNum         : String received by the RFID reader
        seqNum      : seconds this rfid has been continuously seen
        nullPolls   : count of polls when queue was empty
        batteryStatus   : battery status        
        match           : True if vidMsg == rfidMsg
        rfidInBothLanes : rfid detected by both readers
    
    Raises:
        Exception: An error occured writing to the CSV file.
    """
    global resultsFile, current_log_date
    # check if the date has changed
    if when.date() != current_log_date:
        resultsFile = get_results_filename()  # create next results file name
        current_log_date = when.date()  # update current log date

    # create headers for csv file
    write_header = not os.path.exists(resultsFile) or os.stat(resultsFile).st_size == 0

    try:
        with open(resultsFile, 'a', newline='') as csvfile:
            fieldnames = ['timestamp', 'tagOrigin', 'vidMsg', 'rfidMsg', 'rfidNum', 'prevRfidNum','seqNum', 'nullPolls', 'batteryStatus', 'match', 'rfidInBothLanes']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if write_header: # write header only if the file is new or has changed date
                writer.writeheader()
            writer.writerow({
                'timestamp'         : when.strftime('%Y-%m-%d, %H:%M:%S.%f')[:-3],
                'tagOrigin'         : tagOrigin,
                'vidMsg'            : repr(vidMsg),
                'rfidMsg'           : repr(rfidMsg),
                'rfidNum'           : rfidNum,
                'prevRfidNum'       : prevRfidNum,
                'seqNum'            : seqNum,
                'nullPolls'         : nullPolls,
                'batteryStatus'     : batteryStatus,
                'match'             : match,
                'rfidInBothLanes'   : rfidInBothLanes

            })
    except Exception as e:
        print(f"Error writing to results file {resultsFile}: {e}")
        rpi.io.RevPiOutput.value = 1 # turn on LED



# creating each thread to receive data from readers
r1  = threading.Thread(target=serial_read, args=(ser1, "R1:",)).start() # reader 1 thread
r2  = threading.Thread(target=serial_read, args=(ser2, "R2:",)).start() # reader 2 thread
vid = threading.Thread(target=serial_read, args=(ser3, "VID",)).start() # VID detector thread

# database initialization
conn = sqlite3.connect('vid_data.db', check_same_thread = False) # create or connect to the database
# MAKE SURE ONLY THIS SCRIPT WRITES, TO AVOID CONFLICTS
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
    # time of event
    now = dt.datetime.now()

    # lane 1 RFID reader queue
    if rfid1Queue.empty():  
        rfid1NullPolls += 1 # increment the empty counter for RFID reader 1
        rfid1Reader.update_tag("T1_POLLING_" + str(rfid1NullPolls))
        rfid1FuelScanMsg = "R1_POLLING"        

        if rfid1NullPolls >= NO_READ_LIMIT: # seqNumFuelScanMsgsFromRFID resets if too many empty reads
            rfid1SeqNumFuelScanMsg = 0 
            rfid1Reader.update_tag("EMPTY")
            rfid1FuelScanMsg = "EMPTY" # this variable shouldnt be used, should use class get_tag            
    else:
        rfid1NullPolls = 0 # reset empty counter if queue is not empty
        rfid1Reader.update_tag(rfid1Queue.get(True))
        # conversion to the proper string, look up table handled inside of reader class
        rfid1FuelScanMsg = "1-BBT" + rfid1Reader.get_fleetNumber(csvFleetList) + ",00000000" + '\r\n' # VID 800 outputs \r\n in the msg
        rfid1SeqNumFuelScanMsg += 1
        if rfid1FuelScanMsg != rfid1PrevFuelScanMsg:
            rfid1SeqNumFuelScanMsg = 0 # reset the counter to 0 if different tag is read
        
        rfid1PrevFuelScanMsg = rfid1FuelScanMsg  # update previous RFID for lane 1
        #print("RFID Lane 1 Read: " + repr(rfid1FuelScanMsg)) # print the current RFID for testing purposes

    # lane 2 RFID reader queue
    if rfid2Queue.empty():
        rfid2NullPolls += 1
        rfid2Reader.update_tag("T2_POLLING_" + str(rfid2NullPolls))
        rfid2FuelScanMsg = "R2_POLLING" 

        if rfid2NullPolls >= NO_READ_LIMIT: # seqNumFuelScanMsgsFromRFID resets if too many empty reads
            rfid2SeqNumFuelScanMsg = 0
            rfid2Reader.update_tag("EMPTY")
            rfid2FuelScanMsg = "EMPTY"                   
    else:
        rfid2NullPolls = 0
        rfid2Reader.update_tag(rfid2Queue.get(True))
        rfid2FuelScanMsg = "2-BBT" + rfid2Reader.get_fleetNumber(csvFleetList) + ",00000000" + '\r\n' # VID 800 outputs \r\n in the msg
        rfid2SeqNumFuelScanMsg += 1 # increment the counter for RFID reader 2
        if rfid2FuelScanMsg != rfid2PrevFuelScanMsg:
            rfid2SeqNumFuelScanMsg = 0
        
        rfid2PrevFuelScanMsg = rfid2FuelScanMsg  # update previous RFID for lane 2
        #print("RFID Lane 2 Read: " + repr(rfid2FuelScanMsg)) # repr to show escape characters like \n
    

    # Flush VID detector queue
    vidsList = []

    while True:
        try:
            vid_input = vidQueue.get_nowait()
            vidsList.append(vid_input)
        except queue.Empty:
            break

    vid1Msg = "EMPTY"   # default value for VID lane 1
    vid1MsgCnt = 0      # more than 1 will indicate falling behind
    vid2Msg = "EMPTY"   # default value for VID lane 2
    vid2MsgCnt = 0      # more than 1 will indicate falling behind

    vidsListSize = len(vidsList)

    for vidIn in vidsList:
        if vidIn.startswith("1"):   # VID msgs for lane 1            
            vid1Msg = vidIn
            vid1MsgCnt += 1
        elif vidIn.startswith("2"): # VID msgs for lane 2
            vid2Msg = vidIn
            vid2MsgCnt += 1

    # forward the VID msgs 
    # WAB ?? are to be removed for production build
    if vid1Msg != "EMPTY":
        #print("VID Lane 1 Read: " + repr(vid1Msg))
        ser4.write(vid1Msg.encode('utf-8'))  # send to serial port 4
           
    if vid2Msg != "EMPTY":
        #print("VID Lane 2 Read: " + repr(vid2Msg))
        ser4.write(vid2Msg.encode('utf-8'))  # send to serial port 4


    # Update SQL Database
    # WAB what use is the SQL put to ?
    update_lane_data(cursor, 1, vid1Msg, rfid1FuelScanMsg)  # update lane 1 data in the database
    update_lane_data(cursor, 2, vid2Msg, rfid2FuelScanMsg)  # update lane 2 data in the database
    conn.commit()  # commit the changes to the database


    # Flags so if VID and RFID give same BUS Id
    vid1MatchesRfid1 = "V1!=R1"
    #if (vid1Msg != "EMPTY" and rfid1FuelScanMsg != "EMPTY" and 
    if (msg2BusNum(vid1Msg) == msg2BusNum(rfid1FuelScanMsg)):
        vid1MatchesRfid1 = "V1==R1"        

    vid2MatchesRfid2 = "V2!=R2"
    #if (vid2Msg != "EMPTY" and rfid2FuelScanMsg != "EMPTY" and 
    if (msg2BusNum(vid2Msg) == msg2BusNum(rfid2FuelScanMsg)):
        vid2MatchesRfid2 = "V2==R2"


    # Flag if the RFID is seen in both lanes

    if(rfid1FuelScanMsg == "EMPTY" and rfid1FuelScanMsg == "EMPTY") :
        rfidInBothLanes = "R_IN_NONE"
    else :
        if(rfid1FuelScanMsg[2:9] == rfid2FuelScanMsg[2:9]):
            rfidInBothLanes = "R_IN_BOTH"
        else :
            rfidInBothLanes = "R_IN_ONE"


    # RFID data only logged if:
    #   enough consecutive identical reads

    # lane 1 rfid_1   
    tagId = rfid1Reader.get_tag() 
    lastTagId =  rfid1Reader.get_last_tag()  
    if rfid1SeqNumFuelScanMsg > RFID_READS_TO_TRUST: #get RFID_READS_TO_TRUST consecutive reads to trust the data
        # in future, rfid1FuelScanMsg will be written to plc, for now just record
        log_result(now, 'rfid1', vid1Msg, rfid1FuelScanMsg, tagId, lastTagId, rfid1SeqNumFuelScanMsg, rfid1NullPolls, batteryStatus(tagId), vid1MatchesRfid1, rfidInBothLanes)
    
    # record regardless of RFID, but only if VID is in scope
    elif vid1Msg != "EMPTY" and is_vid_in_scope(msg2BusNum(vid1Msg), csvFleetList):
        log_result(now, 'vid1', vid1Msg, rfid1FuelScanMsg, tagId, lastTagId, vid1MsgCnt,               vidsListSize,   batteryStatus(tagId), vid1MatchesRfid1, rfidInBothLanes)
        #ser4.write(vid1Msg.encode('utf-8')) # send to serial port 4
    
    # lane 2 rfid_2
    tagId = rfid2Reader.get_tag() 
    lastTagId =  rfid2Reader.get_last_tag()      
    if rfid2SeqNumFuelScanMsg > RFID_READS_TO_TRUST: #and vid2Msg == rfid2FuelScanMsg:  
        log_result(now, 'rfid2', vid2Msg, rfid2FuelScanMsg, tagId, lastTagId, rfid2SeqNumFuelScanMsg, rfid2NullPolls, batteryStatus(tagId), vid2MatchesRfid2, rfidInBothLanes)

    # record regardless of RFID, but only if VID is in scope    
    elif vid2Msg != "EMPTY" and is_vid_in_scope(msg2BusNum(vid2Msg), csvFleetList):
        log_result(now, 'vid2', vid2Msg, rfid2FuelScanMsg, tagId, lastTagId, vid2MsgCnt,               vidsListSize,   batteryStatus(tagId), vid2MatchesRfid2, rfidInBothLanes)
        #ser4.write(vid2Msg.encode('utf-8')) # send to serial port 4


    time.sleep(0.9)  # sleep 
    # RFID Reader and VID are on 1 sec period 
    # slightly over sample to ensure keeping up
    # allow for empty buffers occasionally