import serial
import datetime as dt
import threading
import queue
import csv
import time
import os
import sys
import sqlite3
import argparse
import logging

import revpimodio2

from cysystemd.journal import JournaldLogHandler

from rfidConstants  import *
from rfidClasses    import *
from getGit         import *



#############################################################
#############################################################
#############################################################
### NOTE:
### Looking back down the fuel lane from the front of the Bus
### LEFT Lane is Lane 1
### Right Lane is lane 2
#############################################################
#############################################################
#############################################################

##################################
# update lane data in the database
##################################
def update_lane_data(conn, cursor, lane, vid, rfid):
    """
    """
    try:
        cursor.execute('UPDATE vid_data SET vid=?, rfid=? WHERE lane=?', (vid, rfid, lane))
    except sqlite3.OperationalError as e:
        print(f"Operational error: {e}")
        sys.exit(1) # bail out and let systemd restart things
    conn.commit()  # commit the changes to the database



#################################
# Check if VID string is in scope
#################################
# linear search may be slow as file gets bigger
# use a binary tree ?
# use a database ?
# less tahn 2000 buses
################################
def is_vid_in_scope(fleet_number, fleetList):
    with open(fleetList, mode='r', encoding="utf-8") as file:
        for row in csv.reader(file):
            if fleet_number == row[0]:
                return True
    return False



#######################
# UPS Shutdown Function
#######################
def shutdown_countdown_func():
    """
    Docstring for shutdown_countdown_func
    """
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



#########################################
# read a line from the serial port buffer
#########################################
def serialReadLine(s, readerName):
    """
    Read strings received from an RFID reader or VID 800 and organizes them into the correct queue.
    Strings are UTF-8 decoded.

    Args:
        readerName: String which indicates which reader the string is from: R1, R2 else VID 800.

    Raises:
        Exception: An error occured when communicating with the reader. The LED while turn on.
    """
    global rpiRelay
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



############################
# Diagnostic Logging  to CSV
############################
# considering another column which has flags that describe the mismatch issue
def log2CSV( when, msgOrigin, vidMsg, tagMsg, tagNum, prevTagNum, seqNum, nullPolls, vidMatchesTag, tagCntInLane):
    """
    Stores the results of the program into a CSV file for data analysis.
    Data is placed into columns:
                when,   lane,       vidMsg, tagMsg,    tagNum,   prevTagNum,    seqNum,  nullPolls,  vidMatchesTag, tagCntInLane

    Args:
        when            : The current date and time
        msgOrigin       : Which lane the RFID / VID reading occured
        vidMsg          : Msg received via the VID
        tagMsg          : Msg created via indexing the Tag
        tagNum          : Tag detected by the RFID reader
        prevTagNum      : Tag previously detected by the RFID reader
        seqNum          : Number of sequential Tag detections
        nullPolls       : Number of polls when queue was empty
        vidMatchesTag   : Flag showing if VID and Tag correlate
        tagCntInLane        : Indicate which lane(s) the Tag in

    Raises:
        Exception: An error occured writing to the CSV file.
    """



    #############################
    # Decode Tag's Battery Status
    #############################
    def batteryStatus(tagId) -> str:
        """
        Docstring for batteryStatus

        :param tagId: Description
        :return: Description
        :rtype: str
        """
        status = "ABSENT"

        if tagId[0] == 'N':
            status = "CHARGED"
        elif tagId[0] == 'n':
            status = "REPLACE"

        return status


    timeStamp = when.strftime('%Y-%m-%d, %H:%M:%S.%f')[:-3]

    CSV_LOG_FILE = "logs/log.csv"   # logrotate is used to rotate the log file
    global rpiRelay

    if (False is LOG_TO_CSV):
        #log2journal.error("LOG_TO_CSV=%s",LOG_TO_CSV)
        return

    msgV    = repr(vidMsg)
    msgVlen = len(vidMsg)

    msgT    = repr(tagMsg)
    msgTlen = len(msgT)
    battStat = batteryStatus(tagNum)

    if(msgVlen == STD_MSG_LEN):
        log2journal.info(   "CSV [%s,VID,%s,<%d>,TAG,%s,<%d>,%s,<%s>,<%s>,%s,%s,%s,%s]", msgOrigin,msgV,msgVlen,msgT,msgTlen,tagNum,seqNum,nullPolls,prevTagNum,battStat,vidMatchesTag,tagCntInLane)
    else :
        log2journal.warning("CSV [%s,VID,%s,<%d>,TAG,%s,<%d>,%s,<%d>,<%d>,%s,%s,%s,%s]", msgOrigin,msgV,msgVlen,msgT,msgTlen,tagNum,seqNum,nullPolls,prevTagNum,battStat,vidMatchesTag,tagCntInLane)

    # create headers for csv file
    write_header = (not (os.path.exists(CSV_LOG_FILE)) or (os.stat(CSV_LOG_FILE).st_size == 0))

    try:
        with open(CSV_LOG_FILE, mode='a', encoding="utf-8", newline='') as csvfile:
            fieldnames = ['Timestamp','TagOrigin','VIDMsg','VIDMsgLen','TagMsg','TagMsgLen','TagNum','TagSeqNum','NullPolls','PrevTagNum','BatteryStatus','VIDmatchsTag','TagsInLane']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if write_header:                                                                            # write header only if the file is new or has changed date
                writer.writeheader()
            writer.writerow({
                'Timestamp'         : timeStamp,
                'TagOrigin'         : msgOrigin,
                'VIDMsg'            : msgV,
                'VIDMsgLen'         : msgVlen,
                'TagMsg'            : msgT,
                'TagMsgLen'         : msgTlen,
                'TagNum'            : tagNum,
                'TagSeqNum'         : seqNum,
                'NullPolls'         : nullPolls,
                'PrevTagNum'        : prevTagNum,
                'BatteryStatus'     : battStat,
                'VIDmatchsTag'      : vidMatchesTag,
                'TagsInLane'        : tagCntInLane
            })
    except Exception as e:
        log2journal.error("Error writing CSV line to file {CSV_LOG_FILE}: {%s}",e)
        rpiRelay = LED_ON                                # turn on LED



#################################
# send a string out serial port 4
#################################
def sendToSerial4(lane, msg):
    """
    Docstring for sendToSerial4

    :param msg: Description
    """
    # ToDo could do another last minute check to only allow WellFormatted msgs out
    #if((MSG_POLLING not in rfid_1_FuelScanMsg) and (MSG_EMPTY not in rfid_1_FuelScanMsg)):

    if ( STD_MSG_LEN == len(msg) ):
        if(True is SEND_TO_SERIAL_4):
            log2journal.debug("Serial OUT:<%s>:<%s>", lane, repr(msg))
            plc_Out.write(msg.encode('utf-8'))
    else:
        log2journal.error("<%s>:<%s> is <%d> requires <%d>", lane, repr(msg), len(msg), STD_MSG_LEN)



########################################################
########################################################
if __name__ == '__main__':
########################################################
########################################################



    ##############################
    # Setup logging to the journal
    ##############################
    ### https://docs.python.org/3/library/logging.html
    # get an instance of the logger object this module will use
    log2journal = logging.getLogger(__name__)
    # instantiate the JournaldLogHandler to hook into systemd
    journald_handler = JournaldLogHandler()
    # set a formatter to include the level name
    #journald_handler.setFormatter(logging.Formatter('[%(levelname)s]-[%(filename)s:%(lineno)d:%(funcName)s]-> %(message)s'))
    journald_handler.setFormatter(logging.Formatter('[%(levelname)s]-[%(filename)s:%(lineno)d]->  %(message)s'))
    # add the journald handler to the current logger
    log2journal.addHandler(journald_handler)



    ##########
    # Git Info
    ##########
    print(f"Git Short Commit ID: {get_git_short_hash()}")
    print(f"Git Latest Tag: {get_latest_git_tag()}")
    print(f"Git Committer: {get_git_committer_info()}")

    last_commit_date = get_commit_date()
    if last_commit_date:
        print(f"Git Last Commit Date is: {last_commit_date}")



    #########################
    # CSV file for fleet list
    #########################
    csvFleetList = 'fleet_list.csv'



    ###############
    # UPS Variables
    ###############
    rpi = revpimodio2.RevPiModIO(autorefresh=True)      # initialize RevPiModIO



    ####################
    # Relay Output Value
    ####################
    rpiRelay = rpi.io.RevPiOutput.value
    rpiRelay = LED_OFF                                  # default relay open/ LED Off



    #############
    # RFID values
    #############
    LANE_EMPTY_MIN: int = 3                             # number of empty reads to declare Lane Empty

    ### WAB ToDo There are a lot of variables differing by the digit in the name "1" or "2"
    ###     This would sugest that the can be moved inside a class and made instance variables not global



    ############
    # VID values
    ############
    vid_L1_Msg:                 str = MSG_EMPTY
    vid_L1_MsgsReadFromQ:       int = 0

    vid_L2_Msg:                 str = MSG_EMPTY
    vid_L2_MsgsReadFromQ:       int = 0

    vidsListSize:               int = 0
    vidQueue:       queue.Queue[str]  = queue.Queue()       # queue for VID detector
    vid_Reader:     Reader = Reader(MSG_EMPTY)              # VID detector lane 1



    ######
    # RFID
    # ####
    LANE_1_MIN:         int     = 5                         # required read count for RFID reader
    LANE_2_MIN:         int     = 5                         # required read count for RFID reader
    LOG_TO_CSV:         bool    = True
    SEND_TO_SERIAL_4:   bool    = False
    MONITOR_UPS:        bool    = False

    rfid_1_FuelScanMsg:         str = MSG_EMPTY
    rfid_1_PrevFuelScanMsg:     str = MSG_INIT                      # initial RFID for lane 1
    rfid_1_SequentialReads:     int = 1                             # counter for RFID reader 1
    rfid_1_NullPolls:           int = 0                             # counter for empty reads on RFID reader 1
    rfid_1_Queue:               queue.Queue[str]  = queue.Queue()   # queue for reader 1
    rfid_1_Reader:              Reader = Reader(MSG_EMPTY)          # initalize first reader

    rfid_2_FuelScanMsg:         str = MSG_EMPTY
    rfid_2_PrevFuelScanMsg:     str = MSG_INIT                      # initial previous RFID for lane 2
    rfid_2_SequentialReads:     int = 1                             # counter for RFID reader 2
    rfid_2_NullPolls:           int = 0                             # counter for empty reads on RFID reader 2
    rfid_2_Queue:               queue.Queue[str]  = queue.Queue()   # queue for reader 2
    rfid_2_Reader:              Reader = Reader(MSG_EMPTY)          # second reader



    ###########################
    # Collect commandline args
    ###########################
    cmdLineParser = argparse.ArgumentParser(description=" Looking back down the fuel lane from the front of the Bus\r\n LEFT Lane is Lane 1\r\n Right Lane is lane 2")

    cmdLineParser.add_argument("--csvLogging",  "-c", type=int, default=1, help="[0] Disables logging to csv. [1] Enables logging to CSV file")
    cmdLineParser.add_argument("--debugLevel",  "-d", type=int, default=1, help="[0] NOTSET, [1] DEBUG, [2] INFO, [3] WARNING, [4] ERROR, [5] CRITICAL")

    cmdLineParser.add_argument("--emptyLaneMin","-e", type=int, default=3, help="Min number of consecutive Tag null reads to deem a Lane is vacant.")

    cmdLineParser.add_argument("--leftLaneMin", "-l", type=int, default=5, help="Min number [5] of consecutive Tag reads before is declared present in Lane 1.")
    cmdLineParser.add_argument("--rightLaneMin","-r", type=int, default=5, help="Min number [5] of consecutive Tag reads before is declared present in Lane 2.")

    cmdLineParser.add_argument("--fwdViaSerial","-s", type=int, default=0, help="[0] Disables forwarding. [1] Enables forwarding")

    cmdLineParser.add_argument("--monitorUPS","-u",   type=int, default=0, help="[0] Disables UPS monitor. [1] Enables UPS Monitor")

    cmdLineArgs = cmdLineParser.parse_args()

    LANE_1_MIN      = cmdLineArgs.leftLaneMin
    LANE_2_MIN      = cmdLineArgs.rightLaneMin
    LANE_EMPTY_MIN  = cmdLineArgs.emptyLaneMin

    if (0 == cmdLineArgs.csvLogging):
        LOG_TO_CSV = False

    if (1 == cmdLineArgs.fwdViaSerial):
        SEND_TO_SERIAL_4 = True

    if (1 == cmdLineArgs.monitorUPS):
        MONITOR_UPS = True

    if (0 == cmdLineArgs.debugLevel):
        log2journal.setLevel(logging.NOTSET)
    elif (1 == cmdLineArgs.debugLevel):
        log2journal.setLevel(logging.DEBUG)
    elif (2 == cmdLineArgs.debugLevel):
        log2journal.setLevel(logging.INFO)
    elif (3 == cmdLineArgs.debugLevel):
        log2journal.setLevel(logging.WARNING)
    elif (4 == cmdLineArgs.debugLevel):
        log2journal.setLevel(logging.ERROR)
    elif (5 == cmdLineArgs.debugLevel):
        log2journal.setLevel(logging.CRITICAL)
    else :
        log2journal.setLevel(logging.DEBUG)

    log2journal.info("Parameters:<-l[x]>LeftLaneMin=%d       <-l[x]>RightLaneMin=%d       <-e[x]>EmptyMin=%d"     , LANE_1_MIN, LANE_2_MIN,       LANE_EMPTY_MIN)
    log2journal.info("Parameters:<-c[0,1]>RecordToCSV=%s  <-s[0,1]>SendToSerial=%s <-l[1,2,3,4,5]>LogLevel=(%d)0"    , LOG_TO_CSV, SEND_TO_SERIAL_4, cmdLineArgs.debugLevel)
    log2journal.info("Parameters:<-u[0,1]>MonitorUPS=%s ", MONITOR_UPS)



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



    #####################
    # UPS Shutdown Thread
    #####################
    if (True == MONITOR_UPS):
        threading.Thread(target=shutdown_countdown_func).start()



    ###################################################
    # creating each thread to receive data from readers
    ###################################################
    threading.Thread(target=serialReadLine, args=(rfid_1_In, "RFRD1:",)).start()                                # reader 1 thread
    threading.Thread(target=serialReadLine, args=(rfid_2_In, "RFRD2:",)).start()                                # reader 2 thread
    threading.Thread(target=serialReadLine, args=(vid_In,    "VIDRD:",)).start()                                # VID detector thread



    ##############################################
    # database initialization
    # database is used to share data with the gui
    # SQL is used to exchange data with the GUI
    #############################################
    sql3Conn = sqlite3.connect('vid_data.db', check_same_thread = False)                                        # create or connect to the database
    # MAKE SURE ONLY THIS SCRIPT WRITES, TO AVOID CONFLICTS
    sql3Cursor = sql3Conn.cursor()                                                                                  # create a cursor object to execute SQL commands

    sql3Cursor.execute('''
        CREATE TABLE IF NOT EXISTS vid_data (
                lane INTEGER PRIMARY KEY,
                vid TEXT,
                rfid TEXT
        )
    ''')                                                                                                    # creates table with limited columns
    sql3Conn.commit()
    # initialize a column for each lane
    for lane in [1, 2]:
        sql3Cursor.execute('INSERT OR IGNORE INTO vid_data (lane, vid, rfid) VALUES (?, ?, ?)', (lane, '', ''))
    sql3Conn.commit()                                                                                           # commit the changes to the database



    ######################################
    # extract fleet number from VID String
    ######################################
    def msg2BusNum(msg):
        # assuming the VID string is formatted as "L-BBT<fleet_number>,00000000"
        try:
            return msg.split(',')[0][5:]
        except Exception as e: #Might make index error
            # might include more logic here to handle different formats
            print(f"Error extracting fleet number: '{msg}': {e}")
            return None



##############################################################################
##############################################################################
## Main Loop - this will run continuously to read from queues and process data
##############################################################################
##############################################################################
    log2journal.info("Enter RFID Reader Main Loop")
    while True:
        # time of event
        now = dt.datetime.now()



        ##########################
        # Process the RFID 1 Queue
        ##########################
        if rfid_1_Queue.empty():
            if (rfid_1_NullPolls > LANE_EMPTY_MIN) :                                                            # seqNumFuelScanMsgsFromRFID resets if too many empty reads
                if (rfid_1_SequentialReads != 0) :
                    log2journal.debug("L1_Empty:<%s><%d>", repr(rfid_1_FuelScanMsg), rfid_1_SequentialReads)
                    rfid_1_SequentialReads = 0
                    rfid_1_Reader.update_tag(MSG_EMPTY, Q_EMPTY)
                    rfid_1_FuelScanMsg = MSG_EMPTY
            else :
                rfid_1_NullPolls += 1
                rfid_1_Reader.update_tag(MSG_POLLING, Q_POLLING)
                rfid_1_FuelScanMsg = "1-" + MSG_POLLING + '-' + str(rfid_1_NullPolls)
                log2journal.debug("L1_Poll:<%s>", repr(rfid_1_FuelScanMsg))                                              # increment the empty counter for RFID reader 1
        else :
            rfid_1_NullPolls = 0                                                                                # reset empty counter if queue is not empty
            rfid_1_Reader.update_tag(rfid_1_Queue.get(True), Q_READY)
            # conversion to the proper string, look up table handled inside of reader class
            rfid_1_FuelScanMsg = "1-BBT" + rfid_1_Reader.get_BusNumFromTag(csvFleetList) + ",00000000" + '\r\n' # VID 800 outputs \r\n in the msg
            rfid_1_SequentialReads += 1

            if rfid_1_FuelScanMsg != rfid_1_PrevFuelScanMsg:
                rfid_1_SequentialReads = 1                                                                      # reset the counter to 1 if different tag is read

            rfid_1_PrevFuelScanMsg = rfid_1_FuelScanMsg                                                         # update previous RFID for lane 1
            log2journal.debug("L1_RFID_DQ:<%s><%d><%s>",rfid_1_Reader.get_tag(), rfid_1_SequentialReads, repr(rfid_1_FuelScanMsg))     # log the current RFID



        ##########################
        # Process the RFID 1 Queue
        ##########################
        if rfid_2_Queue.empty() :
            if (rfid_2_NullPolls > LANE_EMPTY_MIN) :                                                            # seqNumFuelScanMsgsFromRFID resets if too many empty reads
                if (rfid_2_SequentialReads != 0) :
                    log2journal.debug("L2_Empty:<%s><%d>", repr(rfid_2_FuelScanMsg), rfid_2_SequentialReads)
                    rfid_2_SequentialReads = 0
                    rfid_2_Reader.update_tag(MSG_EMPTY, Q_EMPTY)
                    rfid_2_FuelScanMsg = MSG_EMPTY
            else :
                rfid_2_NullPolls += 1
                rfid_2_Reader.update_tag(MSG_POLLING, Q_POLLING)
                rfid_2_FuelScanMsg = "2-" + MSG_POLLING + '-' + str(rfid_2_NullPolls)
                log2journal.debug("L2_Poll:<%s>", repr(rfid_2_FuelScanMsg))
        else :
            rfid_2_NullPolls = 0
            rfid_2_Reader.update_tag(rfid_2_Queue.get(True), Q_READY)
            rfid_2_FuelScanMsg = "2-BBT" + rfid_2_Reader.get_BusNumFromTag(csvFleetList) + ",00000000" + '\r\n' # VID 800 outputs \r\n in the msg
            rfid_2_SequentialReads += 1
                                                                                # increment the counter for RFID reader 2
            if rfid_2_FuelScanMsg != rfid_2_PrevFuelScanMsg:
                rfid_2_SequentialReads = 1

            rfid_2_PrevFuelScanMsg = rfid_2_FuelScanMsg                                                                                 # update previous RFID for lane 2
            log2journal.debug("L2_RFID_DQ:<%s><%d><%s>", rfid_2_Reader.get_tag(), rfid_2_SequentialReads, repr(rfid_2_FuelScanMsg))# repr to show escape characters like \n

        if(rfid_2_Reader.get_tag() == rfid_1_Reader.get_tag()):
            log2journal.error("TAG 1:<%s>2:<%s> in BOTH LANES", rfid_1_Reader.get_tag(), rfid_2_Reader.get_tag())



        ##########################
        # Flush VID detector queue
        ##########################
        vidsList = []
        while True:
            try:
                vid_input = vidQueue.get_nowait()
                vidsList.append(vid_input)
            except queue.Empty:
                break

        vid_L1_Msg = MSG_EMPTY                                                  # default value for VID lane 1
        vid_L1_MsgsReadFromQ = 0                                                # more than 1 will indicate falling behind

        vid_L2_Msg = MSG_EMPTY                                                  # default value for VID lane 2
        vid_L2_MsgsReadFromQ = 0                                                # more than 1 will indicate falling behind

        vidQEmpty:bool = True

        vidsListSize = len(vidsList)

        for vidIn in vidsList:
            if vidIn.startswith("1") :                                        # VID msgs for lane 1
                vid_L1_Msg = vidIn
                vid_L1_MsgsReadFromQ += 1
                vidQEmpty = False
            elif vidIn.startswith("2") :                                        # VID msgs for lane 2
                vid_L2_Msg = vidIn
                vid_L2_MsgsReadFromQ += 1
                vidQEmpty = False



        ####################################
        # share data with diagnostic console
        ####################################
        update_lane_data(sql3Conn, sql3Cursor, 1, vid_L1_Msg, rfid_1_FuelScanMsg)                                     # update lane 1 data in the database
        update_lane_data(sql3Conn, sql3Cursor, 2, vid_L2_Msg, rfid_2_FuelScanMsg)                                     # update lane 2 data in the database



        ########################
        # RFID data only logger:
        ########################

        # lane 1 rfid_1
        ###############
        vid_1_MatchesRfid1 = "V1!=R1"
        tagsIn = "L1_0TAG"

        if (msg2BusNum(vid_L1_Msg) == msg2BusNum(rfid_1_FuelScanMsg)):
            vid_1_MatchesRfid1 = "V1==R1"  #

        tagId       =   rfid_1_Reader.get_tag()
        lastTagId   =   rfid_1_Reader.get_last_tag()

        if (rfid_1_SequentialReads > LANE_1_MIN) :                                                                                                              # get LANE_1_MIN_ consecutive reads to trust the data
            tagsIn = "L1_1TAG"

            if((rfid_1_FuelScanMsg[2:9] == rfid_2_FuelScanMsg[2:9]) and (MSG_EMPTY not in rfid_1_FuelScanMsg ) and (MSG_POLLING not in rfid_1_FuelScanMsg )):   # Flag if the RFID is seen in both lanes
                tagsIn = "L1_2TAG"

            log2journal.debug("%s:<%d><%s>", tagsIn, len(rfid_1_FuelScanMsg), repr(rfid_1_FuelScanMsg))
            log2CSV(now, 'L1_RFID', vid_L1_Msg, rfid_1_FuelScanMsg, tagId, lastTagId, rfid_1_SequentialReads, rfid_1_NullPolls, vid_1_MatchesRfid1, tagsIn)
            sendToSerial4("L1T", rfid_1_FuelScanMsg)

        # record RFID if VID is in scope
        ################################
        elif (vid_L1_Msg != MSG_EMPTY):
            if( is_vid_in_scope(msg2BusNum(vid_L1_Msg), csvFleetList)) :
                log2CSV(now, 'L1_VID', vid_L1_Msg, rfid_1_FuelScanMsg, tagId, lastTagId, vid_L1_MsgsReadFromQ, vidsListSize, vid_1_MatchesRfid1, tagsIn)

            if (len(vid_L1_Msg) == STD_MSG_LEN):
                log2journal.debug("L1_VID FWD:<%d><%s>", len(vid_L1_Msg), repr(vid_L1_Msg))
                sendToSerial4("L1V",vid_L1_Msg)         # send to serial port 4
            else :
                log2journal.info("L1_VID Short:<%d><%s>", len(vid_L1_Msg), repr(vid_L1_Msg))
                if (len(vid_L1_Msg) == VID_MSG_MISSING_ODO_LEN):
                    sendToSerial4("L1X", (vid_L1_Msg[:-2] + ",00000000" + '\r\n'))         # send to serial port 4

    # lane 2 rfid_2
    ###############
        vid_2_MatchesRfid2 = "V2!=R2"
        tagsIn = "L2_0TAG"

        if (msg2BusNum(vid_L2_Msg) == msg2BusNum(rfid_2_FuelScanMsg)):
            vid_2_MatchesRfid2 = "V2==R2"

        tagId       =   rfid_2_Reader.get_tag()
        lastTagId   =   rfid_2_Reader.get_last_tag()

        if (rfid_2_SequentialReads > LANE_2_MIN) :
            tagsIn = "L2_1TAG"

            if((rfid_2_FuelScanMsg[2:9] == rfid_1_FuelScanMsg[2:9]) and (MSG_EMPTY not in rfid_2_FuelScanMsg ) and (MSG_POLLING not in rfid_2_FuelScanMsg )): # Flag if the RFID is seen in both lanes
                tagsIn = "L2_2TAG"

            log2journal.debug("%s:<%d><%s>", tagsIn, len(rfid_2_FuelScanMsg), repr(rfid_2_FuelScanMsg))
            log2CSV(now, 'L2_RFID', vid_L2_Msg, rfid_2_FuelScanMsg, tagId, lastTagId, rfid_2_SequentialReads, rfid_2_NullPolls, vid_2_MatchesRfid2, tagsIn)
            sendToSerial4("L2T", rfid_2_FuelScanMsg)

        # record rRFID if VID is in scope
        #################################
        elif (vid_L2_Msg != MSG_EMPTY) :

            if (is_vid_in_scope(msg2BusNum(vid_L2_Msg), csvFleetList)) :
                log2CSV(now, 'L2_VID', vid_L2_Msg, rfid_2_FuelScanMsg, tagId, lastTagId, vid_L2_MsgsReadFromQ, vidsListSize, vid_2_MatchesRfid2, tagsIn)

            if (len(vid_L2_Msg) == STD_MSG_LEN):
                log2journal.debug("L2_VID FWD:<%d><%s>",len(vid_L2_Msg), repr(vid_L2_Msg))
                sendToSerial4("L2V", vid_L2_Msg)
            else :
                log2journal.info("L2_VID Short:<%d><%s>",len(vid_L2_Msg), repr(vid_L2_Msg))
                if (len(vid_L2_Msg) == VID_MSG_MISSING_ODO_LEN):
                    sendToSerial4("L2X", (vid_L2_Msg[:-2] + ",00000000" + '\r\n'))         # send to serial port 4

        # RFID Reader and VID are on 1 sec period.
        # Slightly over sample to ensure keeping up
        # Allow for empty buffers occasionally

        time.sleep(0.9)  # sleep

        #_#end  Main While
#_#end if main
#_#end