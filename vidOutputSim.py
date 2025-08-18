import serial
import datetime as dt
import time
from rfidClasses import *

'''
Serial Port Allocations
2809 is the current tag i have "in scope"

'''
# VID detector input - port 3 - /dev/ttyUSB2 on Linux or COM15 on Windows
ser3 = serial.Serial('COM18', baudrate=9600)
line = "1-BBT2809,12344321" + '\r\n' # CR and LF as per VID 800
line2 = "2-BBT2809,00000000" + '\r\n'
line4 = "1-BBT2899,0000000"

while True:
    for i in range(10):
        lineSend = line4 + str(i) + '\r\n'  # Simulate VID data for lane 1
        ser3.write(lineSend.encode('utf-8')) 
        time.sleep(1)
