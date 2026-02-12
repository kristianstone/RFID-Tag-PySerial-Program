import cv2
import serial
import datetime as dt
import threading
import os
import queue
import time
from rfidClasses import *

# create text file for logging data
logFileName = "data log " + str(dt.datetime.now().strftime("%d-%b %H%M%S")) + ".txt" # should be the same for linux
f = open(logFileName, 'a') # creates the text file

# serial com RFID stuff

# global variable for state if RFID present or not
reader1Text = "No Read" # for reader 1
reader2Text = "No Read" # for reader 2
rfid1NullPolls = 0 # for reader 1
rfid2NullPolls = 0 # for reader 2

# create reader - this should make it easier having two readers
rfid1Reader = Reader(False, "EMPTY") # initalize first reader
rfid2Reader = Reader(False, "EMPTY") # second reader

# queue creation
rfid1Queue = queue.Queue() # queue for reader 1
rfid2Queue = queue.Queue() # queue for reader 2

# reader 1
rfid1_In = serial.Serial('COM9', baudrate=9600) # change COM depending on device

# reader 2
rfid2_In = serial.Serial('COM8', baudrate=9600)

# create serial read lines
def serial_read(s, readerName):
    while 1:
        sline = s.readline()
        if readerName == "RFRD1:": # add to reader 1 queue
            rfid1Queue.put(readerName + sline.decode('utf-8'))
        else: # add to reader 2 queue
            rfid2Queue.put(readerName + sline.decode('utf-8'))

# creating each thread to receive data from readers
r1 = threading.Thread(target=serial_read, args=(rfid1_In, "RFRD1:",)).start() # reader 1 thread
r2 = threading.Thread(target=serial_read, args=(rfid2_In, "RFRD2:",)).start() # reader 2 thread

# webcam init

# Open webcam plugged into laptop (1), (0) to use default
cam = cv2.VideoCapture(0)
cam.set(cv2.CAP_PROP_EXPOSURE,-4)

# RGB values for colours
colour_dict = {"red":(0,0,255),
               "green":(0,255,0)}

# font for text
font = cv2.FONT_HERSHEY_SIMPLEX

# get default height and width for frames - 640 x 480
frame_width = int(cam.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cam.get(cv2.CAP_PROP_FRAME_HEIGHT))
print("Ready") # This indicates that the software is ready to begin

# define the codec and create VideoWriter object
fourcc = cv2.VideoWriter_fourcc(*'MJPG')
videoFile = "video" + str(dt.datetime.now().strftime("%d-%b %H%M%S"))
out = cv2.VideoWriter(videoFile + ".mp4", fourcc, 25.0, (frame_width, frame_height))

# need to create out text file too

while True:
    # camera stuff 
    ret, frame = cam.read()

    # time of event
    now = dt.datetime.now()
    # timestamp string for video
    dtime = str(now.strftime("%H:%M:%S"))

    # could turn this into a for loop too
    # change colour for reader 1
    if rfid1Reader.get_status() == True:
        line_colour1 = colour_dict["green"] 
    else: 
        line_colour1 = colour_dict["red"]

    # change colour for reader 2
    if rfid2Reader.get_status() == True:
        line_colour2 = colour_dict["green"]
    else:
        line_colour2 = colour_dict["red"]

    # rectangle for lane 1        
    cv2.rectangle(frame, (10,10), (300,470), line_colour1, 10)
    cv2.putText(frame,reader1Text,(100,400),font,1,(0,0,255),2,cv2.LINE_AA)

    # rectangle for lane 2
    cv2.rectangle(frame, (330,10), (630,470), line_colour2, 10)
    cv2.putText(frame,reader2Text,(400,400),font,1,(0,0,255),2,cv2.LINE_AA)

    # time stamp for video
    cv2.putText(frame, dtime, (30,50), font, 1, (0,0,255), 2, cv2.LINE_AA)

    # write the frame to the output file
    out.write(frame)

    # display the captured frame
    cv2.imshow('Camera', frame)

    # press 'q' to exist the loop
    if cv2.waitKey(1) == ord('q'):
        break
    
    # serial reading stuff

    # check reader communication

    # for reader 1
    if rfid1Queue.empty():
        rfid1Reader.update_tag("EMPTY")
        rfid1NullPolls += 1 # increment for each empty print
    else:
        rfid1Reader.update_tag(rfid1Queue.get(True))
        f.write(now.strftime("%H:%M:%S ") + rfid1Reader.get_tag()) # save tag read to data file

    # for reader 2
    if rfid2Queue.empty():
        rfid2Reader.update_tag("EMPTY")
        rfid2NullPolls += 1 # increment for each empty print
    else:
        rfid2Reader.update_tag(rfid2Queue.get(True))
        f.write(now.strftime("%H:%M:%S ") + rfid2Reader.get_tag()) # save tag read to data file
                    
    # reader 1 checks 
    if rfid1Reader.get_tag() == "EMPTY" and rfid1NullPolls > 30:
        rfid1Reader.change_status(False)
        reader1Text = "No Read" # update video text

    if rfid1Reader.get_tag()[0] == "R":
        rfid1Reader.change_status(True)
        reader1Text = rfid1Reader.get_tag().rstrip()
        rfid1NullPolls = 0

    # reader 2 checks
    if rfid2Reader.get_tag() == "EMPTY" and rfid2NullPolls > 30:
        rfid2Reader.change_status(False)
        reader2Text = "No Read" # update video text

    if rfid2Reader.get_tag()[0] == "R":
        rfid2Reader.change_status(True)
        reader2Text = rfid2Reader.get_tag().rstrip()
        rfid2NullPolls = 0
    
    f.close() # close after writing
    f = open(logFileName, 'a') # reopen for next iteration

# release the capture and writer objects
cam.release()
out.release()
cv2.destroyAllWindows()
