"""
RFID utility functions for reading and writing RFID data.
"""

import datetime as dt
import csv

#import threading
#import queue
#import time
#import os
#import sys
#import serial
#import revpimodio2

from rfidClasses import *


# checks what the current results filename is
def get_results_filename():
    """
    Generates a data log file name based on the current date.
    The format is 'results_YYYYMMDD.csv'.
    """
    #return f"results_{dt.datetime.now().strftime('%Y%m%d')}.csv"
    return "logs/log.csv"

# extract fleet number from VID String
def msg2BusNum(msg):
    # assuming the VID string is formatted as "1-BBT<fleet_number>,00000000"
    try:
        return msg.split(',')[0][5:]
    except Exception as e: #Might make index error
        # might include more logic here to handle different formats
        print(f"Error extracting fleet number: '{msg}': {e}")
        return None

# function to check if VID string is in scope
def is_vid_in_scope(fleet_number, fleetList):
    with open(fleetList, mode='r', encoding="utf-8") as file:
        for row in csv.reader(file):
            if fleet_number == row[0]:
                return True
    return False

# function to check battery health of RFID tag
def tag_battery_check(tagString):
    if tagString.startswith('n'):
        return "Low Battery Detected: " + tagString

# function to update lane data in the database
def update_lane_data(cursor, lane, vid, rfid):
    cursor.execute('UPDATE vid_data SET vid=?, rfid=? WHERE lane=?', (vid, rfid, lane))
    #conn.commit()  # commit the changes to the database

# function to read data from the database
def read_lane_data(cursor, lane):
    cursor.execute('SELECT vid, rfid FROM vid_data WHERE lane=?', (lane,))
    row = cursor.fetchone() # retreives info for the specified lane
    if row:
        vid, rfid = row
        return vid, rfid
    else:
        return None, None