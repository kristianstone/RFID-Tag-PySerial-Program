import serial
import datetime as dt
import time
from rfidClasses import *

'''
Serial Port Allocations
2809 is the current tag i have "in scope"

'''
# VID detector input - port 3 - /dev/ttyUSB2 on Linux or COM15 on Windows
vid_In = serial.Serial('COM18', baudrate=9600)
line = "1-BBT4321,12344321" + '\r\n' # CR and LF as per VID 800
line2 = "2-BBT2809,00000000" + '\r\n'
line4 = "1-BBT1234,0000000"
line5 = "1-BBT9999,12344321" + '\r\n'
prefix = "1-BBT"

while True:
    #for i in range(9):
        #lineSend = line4 + str(i) + '\r\n'  # Simulate VID data for lane 1
        #lineSend = prefix + "290" + str(i) + ",00000000\r\n"  # Simulate VID data for lane 1    
        #vid_In.write(lineSend.encode('utf-8'))
        #time.sleep(1)
    vid_In.write(line.encode('utf-8'))
    vid_In.write(line2.encode('utf-8'))  
    time.sleep(1)
    vid_In.write(line.encode('utf-8'))  
    time.sleep(1) 
    vid_In.write(line.encode('utf-8'))
    vid_In.write(line2.encode('utf-8'))    
    time.sleep(1)
    vid_In.write(line.encode('utf-8'))  
    time.sleep(2) 
    vid_In.write(line5.encode('utf-8'))
    time.sleep(1)
    vid_In.write(line5.encode('utf-8'))
    time.sleep(1)
    vid_In.write(line5.encode('utf-8'))
    time.sleep(1)
    vid_In.write(line5.encode('utf-8'))
    time.sleep(1)
    vid_In.write(line5.encode('utf-8'))
    time.sleep(1)
