import serial
import datetime as dt
import threading
import queue
import csv
from rfidClasses import *

# create text file for logging data
logFileName = "data log " + str(dt.datetime.now().strftime("%d-%b %H%M%S")) + ".txt" # should be the same for linux
f = open(logFileName, 'a') # creates the text file

# declare csv file
csvFleetList = 'fleet_list.csv' 

# testing only
currentVID = "test"
currentRFID1 = "test"

# create reader - this should make it easier having two readers
reader1 = Reader(False, "empty") # initalize first reader
#reader2 = Reader(False, "empty") # second reader

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
        else:
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
        # include logic here for comparison with vid
        reader1.change_tag("empty")
        currentRFID1 = "empty"
    else:
        reader1.change_tag(queue1.get(True))
        # conversion to the proper string, look up table handled inside of reader class
        muxString = "1-BBT" + reader1.get_fleetNumber(csvFleetList) + ",00000000" + '\n' # not sure if new line required for final build
        f.write(now.strftime("%H:%M:%S ") + muxString) # save converted tag read to data file 
        currentRFID1 = muxString
        #ser3.write(muxString.encode('utf-8')) # testing string to transmit from port 4 over rs232

    # for reader 2 - need to basically duplicate reader 1 
    '''
    # reader 2 processing

    2-BBT 
    '''
    
    # VID detector reads
    if queue3.empty():
        # include log here for comparison with readers
        # will require more logic to compare with correct fuel bay etc.
        currentVID = "empty"
        #pass
    else:
        muxString = queue3.get(True) # sets the string to whatever is in the queue
        f.write(now.strftime("%H:%M:%S ") + muxString)
        currentVID = muxString
        #print(muxString)


    # output handling - this should just skip to parse the VID reading


    # test purpose code - comparison of strings
    
    # store both RFID and VID detector strings in a txt file
    # compare RFID and VID strings and update a JSON file
    # may need to add everything into another queue but hopefully not

    if currentVID == currentRFID1:
        print("yes")
    else:
        print("no")

    # output VID detector string

    f.close() # close after writing
    f = open(logFileName, 'a') # reopen for next iteration

