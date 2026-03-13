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
f = open(logFileName, mode='a', encoding="utf-8") # creates the text file

# serial com RFID stuff

# global variable for state if RFID present or not
reader1Text = "No Read" # for reader 1
reader2Text = "No Read" # for reader 2
rfid_1_NullPolls = 0 # for reader 1
rfid_2_NullPolls = 0 # for reader 2

# create reader - this should make it easier having two readers
rfid_1_Reader = Reader(False, "EMPTY") # initalize first reader
rfid_2_Reader = Reader(False, "EMPTY") # second reader

# queue creation
lane1Q = queue.Queue() # queue for reader 1
lane2Q = queue.Queue() # queue for reader 2

# reader 1
lane1Serial_In = serial.Serial('COM9', baudrate=9600) # change COM depending on device

# reader 2
lane2Serial_In = serial.Serial('COM8', baudrate=9600)

# create serial read lines
def serial_read(s, readerName):
    while 1:
        sline = s.readline()
        if readerName == "Lane1:": # add to reader 1 queue
            lane1Q.put(readerName + sline.decode('utf-8'))
        else: # add to reader 2 queue
            lane2Q.put(readerName + sline.decode('utf-8'))

# creating each thread to receive data from readers
r1 = threading.Thread(target=serial_read, args=(lane1Serial_In, "Lane1:",)).start() # reader 1 thread
r2 = threading.Thread(target=serial_read, args=(lane2Serial_In, "Lane2:",)).start() # reader 2 thread

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
    if rfid_1_Reader.get_status() == True:
        line_colour1 = colour_dict["green"]
    else:
        line_colour1 = colour_dict["red"]

    # change colour for reader 2
    if rfid_2_Reader.get_status() == True:
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
    if lane1Q.empty():
        rfid_1_Reader.updateTag("EMPTY")
        rfid_1_NullPolls += 1 # increment for each empty print
    else:
        rfid_1_Reader.updateTag(lane1Q.get(True))
        f.write(now.strftime("%H:%M:%S ") + rfid_1_Reader.getTag()) # save tag read to data file

    # for reader 2
    if lane2Q.empty():
        rfid_2_Reader.updateTag("EMPTY")
        rfid_2_NullPolls += 1 # increment for each empty print
    else:
        rfid_2_Reader.updateTag(lane2Q.get(True))
        f.write(now.strftime("%H:%M:%S ") + rfid_2_Reader.getTag()) # save tag read to data file

    # reader 1 checks
    if rfid_1_Reader.getTag() == "EMPTY" and rfid_1_NullPolls > 30:
        rfid_1_Reader.change_status(False)
        reader1Text = "No Read" # update video text

    if rfid_1_Reader.getTag()[0] == "R":
        rfid_1_Reader.change_status(True)
        reader1Text = rfid_1_Reader.getTag().rstrip()
        rfid_1_NullPolls = 0

    # reader 2 checks
    if rfid_2_Reader.getTag() == "EMPTY" and rfid_2_NullPolls > 30:
        rfid_2_Reader.change_status(False)
        reader2Text = "No Read" # update video text

    if rfid_2_Reader.getTag()[0] == "R":
        rfid_2_Reader.change_status(True)
        reader2Text = rfid_2_Reader.getTag().rstrip()
        rfid_2_NullPolls = 0

    f.close() # close after writing
    f = open(logFileName, mode='a', encoding="utf-8") # reopen for next iteration

# release the capture and writer objects
cam.release()
out.release()
cv2.destroyAllWindows()
