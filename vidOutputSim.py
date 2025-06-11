import serial
import datetime as dt
import time
from rfidClasses import *

'''
Serial Port Allocations
'''
# VID detector input - port 3 - /dev/ttyUSB2 on Linux or COM15 on Windows
ser3 = serial.Serial('COM16', baudrate=9600)
line = "1-BBT6969,00000000" + '\r\n' # CR and LF as per VID 800
#line2 = "2-BBT2809,00000000" + '\r\n'

while True:
    ser3.write(line.encode('utf-8'))
    #ser3.write(line2.encode('utf-8'))
    time.sleep(1)
