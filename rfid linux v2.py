import serial
import datetime as dt
import threading
import queue
import csv
import time
from rfidClasses import *

# CSV file for logging results
resultsFile = 'results.csv'

# CSV file for fleet list
csvFleetList = 'fleet_list.csv' 

# testing only
currentVID1 = "test"
currentVID2 = "test"
currentRFID1 = "test"
currentRFID2 = "test"

# create reader - this should make it easier having two readers
reader1 = Reader(False, "empty") # initalize first reader
#reader2 = Reader(False, "empty") # second reader
vidLane1 = Reader(False, "empty") # VID detector lane 1
vidLane2 = Reader(False, "empty") # VID detector lane 2

# queue creation
queue1 = queue.Queue() # queue for reader 1
#queue2 = queue.Queue() # queue for reader 2
queue3 = queue.Queue() # queue for VID detector

'''
Serial Port Allocations
'''
# reader 1 - port 1 - COM11 on Windows - /dev/ttyUSB0 on Linux assumed
ser1 = serial.Serial('/dev/ttyUSB0', baudrate=9600) #open serial port default 8N1

# reader 2 - port 2 - COM7 on Windows - /dev/ttyUSB1 on Linux
#ser2 = serial.Serial('/dev/ttyUSB1', baudrate=9600) #open serial port default 8N1

# VID detector input - port 3 - /dev/ttyUSB2 on Linux
ser3 = serial.Serial('/dev/ttyUSB2', baudrate=9600)

# output serial port - port 4 - /dev/ttyUSB3 on linux
#ser4 = serial.Serial('/dev/ttyUSB3', baudrate=9600)


# create serial read lines
def serial_read(s, readerName):
    while 1:
        sline = s.readline()
        if readerName == "R1:": # add to reader 1 queue
            queue1.put(sline.decode('utf-8'))
        #else: # add to reader 2 queue
            #queue2.put(readerName + sline.decode('utf-8')) # may consider bringing readerName back
        else: # add to VID queue
            queue3.put(sline.decode('utf-8'))


# creating each thread to receive data from readers
r1 = threading.Thread(target=serial_read, args=(ser1, "R1:",)).start() # reader 1 thread
#r2 = threading.Thread(target=serial_read, args=(ser2, "R2:",)).start() # reader 2 thread
vid = threading.Thread(target=serial_read, args=(ser3, "VID",)).start() # VID detector thread

print("Ready") # This indicates that the software is ready to begin

# need to create out text file too

while True:
    # time of event
    now = dt.datetime.now()

    # serial reading stuff

    # Reader 1 Check Tag
    if queue1.empty():
        reader1.change_tag("empty")
        currentRFID1 = "empty" # this variable shouldnt be used, should use class get_tag
    else:
        reader1.change_tag(queue1.get(True))
        # conversion to the proper string, look up table handled inside of reader class
        currentRFID1 = "1-BBT" + reader1.get_fleetNumber(csvFleetList) + ",00000000" + '\n' # not sure if new line required for final build
        #ser3.write(muxString.encode('utf-8')) # testing string to transmit from port 4 over rs232
        print("RFID Read: " + repr(currentRFID1)) # print the current RFID for testing purposes

    # for reader 2 - need to basically duplicate reader 1 
    '''
    # reader 2 processing 

    2-BBT 
    '''

    
    # VID detector reads for each lane
    vid_input = None
    try:
        vid_input = queue3.get_nowait()
    except queue.Empty:
        vid_input = None

    if vid_input is None:
        currentVID1 = "empty"
        currentVID2 = "empty"
    elif vid_input[0] == "1":
        currentVID1 = vid_input
        print("VID1 Read: " + repr(currentVID1))
    elif vid_input[0] == "2":
        currentVID2 = vid_input
        print("VID2 Read: " + repr(currentVID2))


    # need to determine a method if one lane is empty and the other is not

    # test purpose code - comparison of strings
    
    # store both RFID and VID detector strings in a txt file
    # compare RFID and VID strings and update a CSV
    # need comparison for each lane

    # lane 1 comparison - should use get tag for this too
    if currentVID1 == currentRFID1 and currentVID1 != "empty" and currentRFID1 != "empty": # ensure not empty so that nothing is printed either
        print("yes") 
        print("Output to PLC: " + repr(currentVID1)) # for trial, output only VID detector string
        time.sleep(1)  # sleep for 1 second to allow for output to PLC
    else:
        print("no")
        time.sleep(1)
    
    # lane 2 comparison

    # logic for storing data to analyse later

# need to parse VID no matter what

    # true or false if results match for lane 1
    matchresult1 = currentVID1 == currentRFID1 and currentVID1 != "empty" and currentRFID1 != "empty"

    # want to store entire string with repr
    # only write when there is a read from RFID or VID
    if currentVID1 != "empty" or currentRFID1 != "empty":
        with open(resultsFile, 'a', newline='') as csvfile:
            fieldnames = ['timestamp', 'lane', 'vid', 'rfid', 'rfidNum', 'match']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            # write header if file is empty
            if csvfile.tell() == 0:
                writer.writeheader()

            # write the current results
            writer.writerow({
                'timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
                'lane': '1',
                'vid': repr(currentVID1),
                'rfid': repr(currentRFID1),
                'rfidNum': reader1.get_tag(),
                'match': matchresult1
            })

