"""
RFID utility functions for reading and writing RFID data.
"""

import serial
import datetime as dt
import threading
import queue
import csv
import time
import os
import revpimodio2
import sys

from rfidClasses import *


# checks what the current results filename is
def get_results_filename():
    return f"results_{dt.datetime.now().strftime('%Y%m%d')}.csv"

# extract fleet number from VID String
def vid_to_fleet_number(vid_string):
    # assuming the VID string is formatted as "1-BBT<fleet_number>,00000000"
    try:
        return vid_string.split(',')[0][5:]
    except Exception as e: #Might make index error
        # might include more logic here to handle different formats
        print(f"Error extracting fleet number: '{vid_string}': {e}")
        return None

# function to check if VID string is in scope
def is_vid_in_scope(fleet_number, fleetList):
    with open(fleetList, mode='r') as file:
        for row in csv.reader(file):
            if fleet_number == row[0]:
                return True
    return False

# function to check battery health of RFID tag
def tag_battery_check(tagString):
    if tagString.startswith('n'):
        return "Low Battery Detected: " + tagString
