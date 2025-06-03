import serial
import datetime as dt
import threading
import queue
import csv
from rfidClasses import *


# queue creation
queue3 = queue.Queue() # queue for VID detector

'''
Serial Port Allocations
'''
# VID detector input - port 3 - /dev/ttyUSB2 on Linux
ser3 = serial.Serial('COM15', baudrate=9600)

# output serial port - port 4 - /dev/ttyUSB3 on linux
#ser4 = serial.Serial('/dev/ttyUSB3', baudrate=9600)


# create serial read lines
def serial_read(s, readerName):
    while 1:
        sline = s.readline()
        queue3.put(sline.decode('utf-8'))

# creating each thread to receive data from readers
vid = threading.Thread(target=serial_read, args=(ser3, "VID",)).start() # VID detector thread

print("Ready") # This indicates that the software is ready to begin

while True:
    # serial reading stuff
    
    # VID detector reads
    if queue3.empty():
        # include log here for comparison with readers
        # will require more logic to compare with correct fuel bay etc.
        currentVID = "empty"
        #pass
    else:
        muxString = queue3.get(True) # sets the string to whatever is in the queue
        currentVID = muxString


    if currentVID != "empty":
        # if the current VID is not empty, print it
        print("Current VID: " + repr(currentVID))
    #print("Current VID: " + repr(currentVID)) # print the current VID for testing purposes
