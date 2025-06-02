import serial
import datetime as dt
import time
from rfidClasses import *

'''
Serial Port Allocations
'''
# VID detector input - port 3 - /dev/ttyUSB2 on Linux or COM15 on Windows
ser3 = serial.Serial('COM16', baudrate=9600)
line = "1-BBT3809,00000000" + '\n' # new line is temp
#line2 = "2-BBT2809,00000000" + '\n'

while True:
    ser3.write(line.encode('utf-8'))
    #ser3.write(line2.encode('utf-8'))
    time.sleep(1)
