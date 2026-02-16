import serial
import datetime as dt
import threading
import queue
import csv
import time
import os
import revpimodio2
import sys
import sqlite3
import argparse
import logging

from cysystemd.journal import JournaldLogHandler

from rfidClasses import *
from rfidUtil import *


if __name__ == '__main__':
    ### https://docs.python.org/3/library/logging.html
    # get an instance of the logger object this module will use
    log2journal = logging.getLogger(__name__)
    # instantiate the JournaldLogHandler to hook into systemd
    journald_handler = JournaldLogHandler()
    # set a formatter to include the level name
    journald_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    # add the journald handler to the current logger
    log2journal.addHandler(journald_handler)
    # optionally set the logging level
    log2journal.setLevel(logging.DEBUG)


    # CSV file for fleet list
    csvFleetList = 'fleet_list.csv'

    # UPS Variables
    SHUTDOWN_COUNT_DOWN = 10                                                                                # seconds before shutdown
    rpi = revpimodio2.RevPiModIO(autorefresh=True)                                                          # initialize RevPiModIO

    # Relay Output Value
    LED_OFF:int = 0
    LED_ON:int  = 1
    rpiRelay = rpi.io.RevPiOutput.value
    rpiRelay = LED_OFF                                                                            # default relay open/ LED Off

    ### WAB ToDo There are a lot of variables differing by the digit in the name "1" or "2"
    ###     This would sugest that the can be moved inside a class and made instance variables not global
    #

    # VID values
    vid_L1_Msg:                  str = "EMPTY"
    vid_L1_MsgCnt:               int = 0

    vid_L2_Msg:                  str = "EMPTY"
    vid_L2_MsgCnt:               int = 0

    vidsListSize:               int = 0
    vidQueue:       queue.Queue[str]  = queue.Queue()   # queue for VID detector
    vid_Reader:     Reader = Reader(False, "EMPTY")     # VID detector lane 1

    # RFID values
    NO_READ_LIMIT: int = 3                              # number of empty reads before resetting the counter

    # RFID Read Counts - Each lane may require different read counts
    RFID_READS_TO_TRUST: int = 5                        # required read count for RFID reader

    rfid_1_FuelScanMsg:         str  = "EMPTY"
    rfid_1_PrevFuelScanMsg:     str = "INIT"            # initial RFID for lane 1
    rfid_1_SequentialReads:   int = 0                 # counter for RFID reader 1
    rfid_1_NullPolls:           int = 0                 # counter for empty reads on RFID reader 1
    rfid_1_Queue:   queue.Queue[str]  = queue.Queue()   # queue for reader 1
    rfid_1_Reader:  Reader = Reader(False, "EMPTY")     # initalize first reader


    rfid_2_FuelScanMsg:         str = "EMPTY"
    rfid_2_PrevFuelScanMsg:     str = "INIT"            # initial previous RFID for lane 2
    rfid_2_SequentialReads:   int = 0                 # counter for RFID reader 2
    rfid_2_NullPolls:           int = 0                 # counter for empty reads on RFID reader 2
    rfid_2_Queue:   queue.Queue[str]  = queue.Queue()   # queue for reader 2
    rfid_2_Reader:  Reader = Reader(False, "EMPTY")     # second reader


    # Collect commandline args

    cmdLineParser = argparse.ArgumentParser()
    cmdLineParser.add_argument("-o", "--Output", help="Show output message")
    cmdLineArgs = cmdLineParser.parse_args()

    if cmdLineArgs.Output:
        log2journal.info("Output: <%s>", cmdLineArgs.Output)


    ###########################
    ### Serial Port Allocations
    ###########################

    #connect reader 1 - port 1 - COM11 on Windows - /dev/ttyUSB0 on Linux assumed
    try:
        rfid_1_In = serial.Serial('/dev/ttyUSB0', baudrate=9600)                                             #open serial port default 8N1
    except serial.SerialException as e:
        log2journal.error("Error opening serial port for: reader 1: {%s}",e)
        rpiRelay = LED_ON                                                                        # turn on LED
        sys.exit()

    # connect reader 2 - port 2 - COM7 on Windows - /dev/ttyUSB1 on Linux
    try:
        rfid_2_In = serial.Serial('/dev/ttyUSB1', baudrate=9600)                                             #open serial port default 8N1
    except serial.SerialException as e:
        log2journal.error("Error opening serial port for: reader 2: {%s}",e)
        rpiRelay = LED_ON                                                                        # turn on LED
        sys.exit()

    # connect VID detector input - port 3 - /dev/ttyUSB2 on Linux
    try:
        vid_In = serial.Serial('/dev/ttyUSB2', baudrate=9600)
    except serial.SerialException as e:
        log2journal.error("Error opening serial port for: VID detector: {%s}",e)
        rpiRelay = LED_ON                                                                        # turn on LED
        sys.exit()

    # connect output serial port - port 4 - /dev/ttyUSB3 on linux
    try:
        plc_Out = serial.Serial('/dev/ttyUSB3', baudrate=9600)
    except serial.SerialException as e:
        log2journal.error("Error opening serial port for: output: {%s}",e)
        rpiRelay = LED_ON                                                                        # turn on LED
        sys.exit()

    resultsFile = get_results_filename()                                                                    # initialize results file name
    current_log_date = dt.datetime.now().date()                                                             # initialize current log date

    # UPS Shutdown Function
    def shutdown_countdown_func():
        while 1:                                                                                            # loop this thread to constantly monitor UPS status
            if rpi.io.RevPiStatus.value & (1<<6):
                for i in range(SHUTDOWN_COUNT_DOWN, 0, -1):
                    time.sleep(1)
                    if (rpi.io.RevPiStatus.value & (1<<6)):
                        log2journal.warning("Shutdown aborted!")
                        time.sleep(1)
                        break
                    log2journal.critical("Shutting down in {%d} seconds...",i)
                else:
                    log2journal.critical("Shutting down now...")
                    os.system("sudo shutdown now")
            else:
                time.sleep(0.5)                                                                             # sleep for a short time to avoid busy waiting
    #_#end def shutdown_countdown_func(


    # UPS Shutdown Thread
    threading.Thread(target=shutdown_countdown_func).start()


    def serial_read(s, readerName):
        """
        Read strings received from an RFID reader or VID 800 and organizes them into the correct queue.
        Strings are UTF-8 decoded.

        Args:
            readerName: String which indicates which reader the string is from: R1, R2 else VID 800.

        Raises:
            Exception: An error occured when communicating with the reader. The LED while turn on.
        """
        while 1:
            try:
                sline = s.readline()
                if readerName == "RFRD1:":                                                                  # add to reader 1 queue
                    rfid_1_Queue.put(sline.decode('utf-8'))
                elif readerName == "RFRD2:":                                                                # add to reader 2 queue
                    rfid_2_Queue.put(sline.decode('utf-8'))                                                   # may consider bringing readerName back
                else:                                                                                       # add to VID queue
                    vidQueue.put(sline.decode('utf-8'))
            except Exception as e:
                log2journal.error("%s %s Serial Read Error : %s ", [{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}], readerName, e)
                rpiRelay = LED_ON                                                                # turn on LED
        #_#end while 1
    #_#end def serial_read(


    def batteryStatus(tagId) -> str:
        status = "NO_BATT"

        if tagId[0] == 'N':
            status = "CHARGED_BATT"
        elif tagId[0] == 'n':
            status = "REPLACE_BATT"

        return status
    #_#end def batteryStatus(


    # considering another column which has flags that describe the mismatch issue
    def log_result( when,   tagOrigin,  vidMsg, rfidMsg,    rfidNum,    prevRfidNum,   seqNum,  nullPolls,      batteryStatus, match, rfidLanes):
        """
        Stores the results of the program into a CSV file for data analysis.
        Data is placed into columns:
                    when,   lane,       vidMsg, rfidMsg,    rfidNum,   prevRfidNum,    seqNum,  rfidNullPolls,  batteryStatus, match, rfidLanes

        Args:
            when            : The current date and time
            tagOrigin       : Which lane the RFID/ VID reading occured
            vidMsg          : String received by the VID
            rfidMsg         : String converted from the RFID string
            rfidNum         : String received by the RFID reader
            prevRfidNum     : String previously received by the RFID reader
            seqNum          : seconds this rfid has been continuously seen
            nullPolls       : count of polls when queue was empty
            batteryStatus   : battery status
            match           : True if vidMsg == rfidMsg
            rfidLanes       : rfid detected by both readers

        Raises:
            Exception: An error occured writing to the CSV file.
        """
        global resultsFile, current_log_date
        # check if the date has changed
        if when.date() != current_log_date:
            resultsFile = get_results_filename()                                                            # create next results file name
            current_log_date = when.date()                                                                  # update current log date

        # create headers for csv file
        write_header = not os.path.exists(resultsFile) or os.stat(resultsFile).st_size == 0

        try:
            with open(resultsFile, mode='a', encoding="utf-8", newline='') as csvfile:
                fieldnames = ['timestamp', 'tagOrigin', 'vidMsg', 'rfidMsg', 'rfidNum', 'prevRfidNum','seqNum', 'nullPolls', 'batteryStatus', 'match', 'rfidLanes']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                if write_header:                                                                            # write header only if the file is new or has changed date
                    writer.writeheader()
                writer.writerow({
                    'timestamp'         : when.strftime('%Y-%m-%d, %H:%M:%S.%f')[:-3],
                    'tagOrigin'         : tagOrigin,
                    'vidMsg'            : repr(vidMsg),
                    'rfidMsg'           : repr(rfidMsg),
                    'rfidNum'           : rfidNum,
                    'prevRfidNum'       : prevRfidNum,
                    'seqNum'            : seqNum,
                    'nullPolls'         : nullPolls,
                    'batteryStatus'     : batteryStatus,
                    'match'             : match,
                    'rfidLanes'         : rfidLanes
                })
        except Exception as e:
            log2journal.error("Error writing to results file {resultsFile}: {%s}",e)
            rpiRelay = LED_ON                                # turn on LED
    #_#end def log_result


    # creating each thread to receive data from readers
    threading.Thread(target=serial_read, args=(rfid_1_In, "RFRD1:",)).start()                                # reader 1 thread
    threading.Thread(target=serial_read, args=(rfid_2_In, "RFRD2:",)).start()                                # reader 2 thread
    threading.Thread(target=serial_read, args=(vid_In,    "VIDRD:",)).start()                                # VID detector thread


    """
        WAB ToDo
        What was the intent of the DB ??

        # database initialization
        conn = sqlite3.connect('vid_data.db', check_same_thread = False)                                        # create or connect to the database
        # MAKE SURE ONLY THIS SCRIPT WRITES, TO AVOID CONFLICTS
        cursor = conn.cursor()                                                                                  # create a cursor object to execute SQL commands

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vid_data (
                    lane INTEGER PRIMARY KEY,
                    vid TEXT,
                    rfid TEXT
            )
        ''')                                                                                                    # creates table with limited columns

        conn.commit()

                                                                                                                                                                                    # commit the changes to the database

        # initialize a column for each lane
        for lane in [1, 2]:
            cursor.execute('INSERT OR IGNORE INTO vid_data (lane, vid, rfid) VALUES (?, ?, ?)', (lane, '', ''))
        conn.commit()                                                                                           # commit the changes to the database
    """

    ##############################################################################
    ## Main Loop - this will run continuously to read from queues and process data
    ##############################################################################

    log2journal.info("RFID Reader ready to enter Main Loop")

    while True:
        # time of event
        now = dt.datetime.now()

        # lane 1 RFID reader queue
        if rfid_1_Queue.empty():
            rfid_1_NullPolls += 1

            if rfid_1_NullPolls > NO_READ_LIMIT:                                                             # seqNumFuelScanMsgsFromRFID resets if too many empty reads
                if (rfid_1_SequentialReads != 0) :
                    log2journal.info("RFID_L1_Q_Empty : <%s><%d>", repr(rfid_1_FuelScanMsg), rfid_1_SequentialReads)
                    rfid_1_SequentialReads = 0
                    rfid_1_Reader.update_tag("EMPTY")
                    rfid_1_FuelScanMsg = "EMPTY"
                else :
                    rfid_1_Reader.update_tag("Polling")
                    rfid_1_FuelScanMsg = "Polling" + str(rfid_2_NullPolls)
                    log2journal.info("Polling : <%s><%d>", repr(rfid_1_FuelScanMsg), rfid_1_NullPolls)  # increment the empty counter for RFID reader 1
        else:
            rfid_1_NullPolls = 0                                                                              # reset empty counter if queue is not empty
            rfid_1_Reader.update_tag(rfid_1_Queue.get(True))
            # conversion to the proper string, look up table handled inside of reader class
            rfid_1_FuelScanMsg = "1-BBT" + rfid_1_Reader.get_fleetNumber(csvFleetList) + ",00000000" + '\r\n'   # VID 800 outputs \r\n in the msg
            rfid_1_SequentialReads += 1

            if rfid_1_FuelScanMsg != rfid_1_PrevFuelScanMsg:
                rfid_1_SequentialReads = 1                                                                  # reset the counter to 1 if different tag is read

            rfid_1_PrevFuelScanMsg = rfid_1_FuelScanMsg                                                       # update previous RFID for lane 1

            log2journal.info("RFID_L1_Q Read : <%s><%d>", repr(rfid_1_FuelScanMsg), rfid_1_SequentialReads) # log the current RFID


        # lane 2 RFID reader queue
        if rfid_2_Queue.empty():
            rfid_2_NullPolls += 1

            if rfid_2_NullPolls > NO_READ_LIMIT:                                                             # seqNumFuelScanMsgsFromRFID resets if too many empty reads
                if (rfid_2_SequentialReads != 0) :
                    log2journal.info("RFID_L2_Q_Empty : <%s><%d>", repr(rfid_2_FuelScanMsg), rfid_2_SequentialReads)
                    rfid_2_SequentialReads = 0
                    rfid_2_Reader.update_tag("EMPTY")
                    rfid_2_FuelScanMsg = "EMPTY"
                else :
                    rfid_2_Reader.update_tag("Polling")
                    rfid_2_FuelScanMsg = "Polling" + str(rfid_2_NullPolls)
                    log2journal.info("Polling : <%s><%d>", repr(rfid_2_FuelScanMsg), rfid_2_NullPolls)
        else:
            rfid_2_NullPolls = 0
            rfid_2_Reader.update_tag(rfid_2_Queue.get(True))
            rfid_2_FuelScanMsg = "2-BBT" + rfid_2_Reader.get_fleetNumber(csvFleetList) + ",00000000" + '\r\n'   # VID 800 outputs \r\n in the msg
            rfid_2_SequentialReads += 1
                                                                     # increment the counter for RFID reader 2
            if rfid_2_FuelScanMsg != rfid_2_PrevFuelScanMsg:
                rfid_2_SequentialReads = 1

            rfid_2_PrevFuelScanMsg = rfid_2_FuelScanMsg                                                         # update previous RFID for lane 2

            log2journal.info("RFID_L2_Q Read : <%s><%d>", repr(rfid_2_FuelScanMsg), rfid_2_SequentialReads)   # repr to show escape characters like \n


        # Flush VID detector queue
        vidsList = []

        while True:
            try:
                vid_input = vidQueue.get_nowait()
                vidsList.append(vid_input)
            except queue.Empty:
                break

        vid_L1_Msg = "EMPTY"                                                                                   # default value for VID lane 1
        vid_L1_MsgCnt = 0                                                                                      # more than 1 will indicate falling behind

        vid_L2_Msg = "EMPTY"                                                                                   # default value for VID lane 2
        vid_L2_MsgCnt = 0                                                                                      # more than 1 will indicate falling behind

        vidQEmpty:bool = True

        vidsListSize = len(vidsList)

        for vidIn in vidsList:
            if vidIn.startswith("1"):                                                                       # VID msgs for lane 1
                vid_L1_Msg = vidIn
                vid_L1_MsgCnt += 1
                vidQEmpty = False
            elif vidIn.startswith("2"):                                                                     # VID msgs for lane 2
                vid_L2_Msg = vidIn
                vid_L2_MsgCnt += 1
                vidQEmpty = False


        #_#end for

        """
            # Update SQL Database
            ## WAB_?? what use is the SQL put to ?
            update_lane_data(cursor, 1, vid_L1_Msg, rfid_1_FuelScanMsg)                                              # update lane 1 data in the database
            update_lane_data(cursor, 2, vid_L2_Msg, rfid_2_FuelScanMsg)                                              # update lane 2 data in the database
            conn.commit()                                                                                       # commit the changes to the database
        """
        # RFID data only logged if:
        # enough consecutive identical reads

        # lane 1 rfid_1
        # Flags to identify if VID and RFID give same BUS Id
        vid_1_MatchesRfid1 = "V1!=R1"
        #if (vid_L1_Msg != "EMPTY" and rfid_1_FuelScanMsg != "EMPTY" and
        if (msg2BusNum(vid_L1_Msg) == msg2BusNum(rfid_1_FuelScanMsg)):
            vid_1_MatchesRfid1 = "V1==R1"  #

        tagId = rfid_1_Reader.get_tag()
        lastTagId =  rfid_1_Reader.get_last_tag()

        if (rfid_1_SequentialReads > RFID_READS_TO_TRUST) :                                                 # get RFID_READS_TO_TRUST consecutive reads to trust the data
            rfidLanes = "R_IN_L1"
            if(rfid_1_FuelScanMsg[2:9] == rfid_2_FuelScanMsg[2:9]):                                             # Flag if the RFID is seen in both lanes
                rfidLanes = "R1_IN_BOTH"
                log2journal.info("R1_IN_BOTH : <%s>", repr(rfid_1_FuelScanMsg))

            log2journal.debug("RFID_L1 Log : <%s>", repr(rfid_1_FuelScanMsg))
            #plc_Out.write(rfid_1_FuelScanMsg.encode('utf-8'))
            log_result(now, 'RFID_L1', vid_L1_Msg, rfid_1_FuelScanMsg, tagId, lastTagId, rfid_1_SequentialReads, rfid_1_NullPolls, batteryStatus(tagId), vid_1_MatchesRfid1, rfidLanes)

        # record regardless of RFID, but only if VID is in scope
        elif (vid_L1_Msg != "EMPTY" and is_vid_in_scope(msg2BusNum(vid_L1_Msg), csvFleetList)) :
            rfidLanes = "R_NONE"
            log2journal.debug("VID_L1 Log : <%s>", repr(vid_L1_Msg))
            #plc_Out.write(vid_L1_Msg.encode('utf-8')) # send to serial port 4
            log_result(now, 'VID_L1', vid_L1_Msg, rfid_1_FuelScanMsg, tagId, lastTagId, vid_L1_MsgCnt,               vidsListSize,   batteryStatus(tagId), vid_1_MatchesRfid1, rfidLanes)
        else :
        ## WAB_TODO use a runtime command arg to switch on or off
            if vid_L1_Msg != "EMPTY":
                log2journal.debug("VID_L1 FWD : <%s>", repr(vid_L1_Msg))
                #plc_Out.write(vid_L1_Msg.encode('utf-8'))         # send to serial port 4


        # lane 2 rfid_2
        # Flags to identify if VID and RFID give same BUS Id
        vid_2_MatchesRfid2 = "V2!=R2"
        #if (vid_L2_Msg != "EMPTY" and rfid_2_FuelScanMsg != "EMPTY" and
        if (msg2BusNum(vid_L2_Msg) == msg2BusNum(rfid_2_FuelScanMsg)):
            vid_2_MatchesRfid2 = "V2==R2"

        tagId = rfid_2_Reader.get_tag()
        lastTagId =  rfid_2_Reader.get_last_tag()

        if (rfid_2_SequentialReads > RFID_READS_TO_TRUST) :                                                 # and vid_L2_Msg == rfid_2_FuelScanMsg:
            rfidLanes = "R_IN_L2"
            if(rfid_1_FuelScanMsg[2:9] == rfid_2_FuelScanMsg[2:9]) :                                            # Flag if the RFID is seen in both lanes
                rfidLanes = "R_IN_BOTH"
                log2journal.info("R2_IN_BOTH : <%s>", repr(rfid_2_FuelScanMsg))

            log2journal.debug("RFID_L2 Log : <%s>", repr(rfid_2_FuelScanMsg))
            #plc_Out.write(rfid_2_FuelScanMsg.encode('utf-8'))
            log_result(now, 'RFID_L2', vid_L2_Msg, rfid_2_FuelScanMsg, tagId, lastTagId, rfid_2_SequentialReads, rfid_2_NullPolls, batteryStatus(tagId), vid_2_MatchesRfid2, rfidLanes)

        # record regardless of RFID, but only if VID is in scope
        elif (vid_L2_Msg != "EMPTY" and is_vid_in_scope(msg2BusNum(vid_L2_Msg), csvFleetList)) :
            rfidLanes = "R_NONE"
            log2journal.debug("VID_2 : <%s>", repr(vid_L2_Msg))
            #plc_Out.write(vid_L2_Msg.encode('utf-8')) # send to serial port 4
            log_result(now, 'VID_2', vid_L2_Msg, rfid_2_FuelScanMsg, tagId, lastTagId, vid_L2_MsgCnt,               vidsListSize,   batteryStatus(tagId), vid_2_MatchesRfid2, rfidLanes)
        else :
        ## WAB_TODO use a runtime command arg to switch on or off
            if vid_L2_Msg != "EMPTY":
                log2journal.debug("VID_2 FWD : <%s>", repr(vid_L2_Msg))
                #plc_Out.write(vid_L2_Msg.encode('utf-8')) # send to serial port 4

        # RFID Reader and VID are on 1 sec period
        # slightly over sample to ensure keeping up
        # allow for empty buffers occasionally
        time.sleep(0.9)  # sleep

        #_#end  Main While
#_#end if main
#_#end