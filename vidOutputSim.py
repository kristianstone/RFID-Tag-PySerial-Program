import serial
import datetime as dt
import time
from rfidClasses import *

'''
Serial Port Allocations
2809 is the current tag i have "in scope"

'''
# VID detector input - port 3 - /dev/ttyUSB2 on Linux or COM15 on Windows
ser3 = serial.Serial('COM17', baudrate=9600)
line = "1-BBT2809,12344321" + '\r\n' # CR and LF as per VID 800
line2 = "2-BBT2809,00000000" + '\r\n'

while True:
    for i in range(10):
        ser3.write(line.encode('utf-8')) 
        ser3.write(line2.encode('utf-8'))
        time.sleep(1)
    time.sleep(5)  # wait for 5 seconds before sending again
    for i in range(3):
        ser3.write(line2.encode('utf-8')) # test to break
        time.sleep(1)
    for i in range(3):
        ser3.write(line.encode('utf-8'))
        time.sleep(1)
