# pylint: disable= C0301, C0112, C0114, C0115, C0116

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
import serial
import sdnotify

import revpimodio2

from cysystemd.journal import JournaldLogHandler

from rfidConstants  import SHUTDOWN_COUNT_DOWN
from rfidConstants  import LED_ON
from rfidConstants  import LED_OFF
from rfidConstants  import STD_MSG_LEN
from rfidConstants  import MSG_EMPTY
from rfidConstants  import Q_EMPTY
from rfidConstants  import MSG_POLLING
from rfidConstants  import Q_POLLING
from rfidConstants  import Q_READY
from rfidConstants  import VID_MSG_MISSING_ODO_LEN

from rfidClasses    import Reader

from getGit         import get_git_short_hash
from getGit         import get_latest_git_tag
from getGit         import get_git_committer_info
from getGit         import get_commit_date



#############################################################
#############################################################
#############################################################
### NOTE:
### Looking back down the fuel lane from the front of the Bus
### LEFT  Lane is Lane 1
### RIGHT Lane is lane 2
#############################################################
#############################################################
#############################################################

##################################
# update lane data in the database
##################################
def update_lane_data(conn, cursor, laneNum, vid, rfid):
    try:
        cursor.execute('UPDATE vid_data SET vid=?, rfid=? WHERE lane=?', (vid, rfid, laneNum))
    except sqlite3.OperationalError as e:
        print(f"Operational error: {e}")
        sys.exit(1)     # bail out and let systemd restart things
    conn.commit()       # commit the changes to the database

# #_#end update_lane_data(


#################################
# Check if VID string is in scope
#################################
# linear search may be slow as file gets bigger
# use a binary tree ?
# use a database ?
# less than 2000 buses
################################
def is_vid_in_scope(fleet_number, fleetList):
    with open(fleetList, mode='r', encoding="utf-8") as file:
        for row in csv.reader(file):
            if fleet_number == row[0]:
                return True
    return False

# #_#end is_vid_in_scope(


#######################
# UPS Shutdown Function
#######################
def shutdown_countdown_func():
    while 1:                                                                                            # loop this thread to constantly monitor UPS status
        if rpi.io.RevPiStatus.value & (1 << 6):
            for i in range(SHUTDOWN_COUNT_DOWN, 0, -1):
                time.sleep(1)
                if (rpi.io.RevPiStatus.value & (1 << 6)):
                    log2journal.warning("Shutdown aborted!")
                    time.sleep(1)
                    break
                log2journal.critical("Shutting down in {%d} seconds...", i)
            else:
                log2journal.critical("Shutting down now...")
                os.system("sudo shutdown now")
        else:
            time.sleep(0.5)                                                                             # sleep for a short time to avoid busy waiting

# #_#end shutdown_countdown_func(


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
            if readerName == "Lane1:":                                                                  # add to reader 1 queue
                lane1Q.put(sline.decode('utf-8'))
            elif readerName == "Lane2:":                                                                # add to reader 2 queue
                lane2Q.put(sline.decode('utf-8'))                                                       # may consider bringing readerName back
            else:                                                                                       # add to VID queue
                vidQueue.put(sline.decode('utf-8'))
        except Exception as e:
            log2journal.error("%s %s Serial Read Error : %s ", [{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}], readerName, e)
            rpiRelay = LED_ON                                                                           # turn on LED
    # #_#end while 1
# #_#end serialReadLine(



############################
# Diagnostic Logging  to CSV
############################
# considering another column which has flags that describe the mismatch issue
def log2CSV(when, tagOrigin, vidMsg, tagMsg, tagIdNum, battStat, prevTagNum, seqNum, nullPolls, vidMatchesTag, tagCntInLane):
    """
    Stores the results of the program into a CSV file for data analysis.
    Data is placed into columns:
                when,   lane,       vidMsg, tagMsg,    tagIdNum,   prevTagNum,    seqNum,  nullPolls,  vidMatchesTag, tagCntInLane

    Args:
        when            : The current date and time
        tagOrigin       : Which lane the RFID / VID reading occured
        vidMsg          : Msg received via the VID
        tagMsg          : The Msg created via indexing the Tag
        tagIdNum          : The Tag detected by the RFID reader
        battStat        : The state of the Tag's battery
        prevTagNum      : Tag previously detected by the RFID reader
        seqNum          : Number of sequential Tag detections
        nullPolls       : Number of polls when queue was empty
        vidMatchesTag   : Flag showing if VID and Tag correlate
        tagCntInLane    : Indicate which lane(s) the Tag in

    Raises:
        Exception: An error occured writing to the CSV file.
    """

    timeStamp = when.strftime('%Y-%m-%d, %H:%M:%S.%f')[:-3]

    CSV_LOG_FILE = "logs/log.csv"   # logrotate is used to rotate the log file
    global rpiRelay

    if (False is LOG_TO_CSV):
        # log2journal.error("LOG_TO_CSV=%s",LOG_TO_CSV)
        return

    msgV    = repr(vidMsg)
    msgVlen = len(vidMsg)

    msgT    = repr(tagMsg)
    msgTlen = len(tagMsg)

    log2journal.info("CSV [%s,VID->,%s,<%d>,TAG->,%s,<%d>,%s,<%s>,<%s>,%s,%s,%s,%s]", tagOrigin, msgV, msgVlen, msgT, msgTlen, tagIdNum, seqNum, nullPolls, prevTagNum, battStat, vidMatchesTag, tagCntInLane)

    # create headers for csv file
    write_header = (not (os.path.exists(CSV_LOG_FILE)) or (os.stat(CSV_LOG_FILE).st_size == 0))

    try:
        with open(CSV_LOG_FILE, mode='a', encoding="utf-8", newline='') as csvfile:
            fieldnames = ['Timestamp', 'TagOrigin', 'VIDMsg', 'VIDMsgLen', 'TagMsg', 'TagMsgLen', 'TagNum', 'TagSeqNum', 'NullPolls', 'PrevTagNum', 'BatteryStatus', 'VIDmatchsTag', 'TagsInLane']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if write_header:                                                                            # write header only if the file is new or has changed date
                writer.writeheader()
            writer.writerow({
                'Timestamp'         : timeStamp,
                'TagOrigin'         : tagOrigin,
                'VIDMsg'            : msgV,
                'VIDMsgLen'         : msgVlen,
                'TagMsg'            : msgT,
                'TagMsgLen'         : msgTlen,
                'TagNum'            : tagIdNum,
                'TagSeqNum'         : seqNum,
                'NullPolls'         : nullPolls,
                'PrevTagNum'        : prevTagNum,
                'BatteryStatus'     : battStat,
                'VIDmatchsTag'      : vidMatchesTag,
                'TagsInLane'        : tagCntInLane
            })
    except Exception as e:
        log2journal.error("Error writing CSV line to file {CSV_LOG_FILE}: {%s}", e)
        rpiRelay = LED_ON                                # turn on LED

# #_#end log2CSV(

#################################
# send a string out serial port 4
#################################
def sendToSerial4(laneId, msg):
    # ToDo could do another last minute check to only allow WellFormatted msgs out
    # if ((MSG_POLLING not in rfid_1_FuelScanMsg) and (MSG_EMPTY not in rfid_1_FuelScanMsg)):

    if (STD_MSG_LEN == len(msg)):
        if (True is SEND_TO_SERIAL_4):
            log2journal.info("Serial OUT:<%s>:<%s>", laneId, repr(msg))
            plc_Out.write(msg.encode('utf-8'))
    else:
        log2journal.warning("<%s>:<%s> is <%d> requires <%d>", laneId, repr(msg), len(msg), STD_MSG_LEN)

# #_#end sendToSerial4(

# #######################################################
# #######################################################
if __name__ == '__main__':


    ##############################
    # Setup logging to the journal
    ##############################
    ### https://docs.python.org/3/library/logging.html
    # get an instance of the logger object this module will use
    log2journal = logging.getLogger(__name__)
    # instantiate the JournaldLogHandler to hook into systemd
    journald_handler = JournaldLogHandler()
    # set a formatter to include the level name
    # journald_handler.setFormatter(logging.Formatter('[%(levelname)s]-[%(filename)s:%(lineno)d:%(funcName)s]-> %(message)s'))
    journald_handler.setFormatter(logging.Formatter('[%(levelname)s]-[%(filename)s:%(lineno)d]->  %(message)s'))
    # add the journald handler to the current logger
    log2journal.addHandler(journald_handler)



    # notifer = sdnotify.SystemdNotifier()
    notifer = sdnotify.SystemdNotifier(debug=True)

    if "NOTIFY_SOCKET" in os.environ:
        notifer.notify("READY=1")
        print(f"NOTIFY_SOCKET set to READY")
    else :
        print(f"Cannot set NOTIFY_SOCKET")




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
    vid_L1_cntReadFromQ:        int = 0

    vid_L2_Msg:                 str = MSG_EMPTY
    vid_L2_cntReadFromQ:        int = 0

    vidsListSize:               int = 0
    vidQueue:       queue.Queue[str]  = queue.Queue()       # queue for VID detector
    vid_Reader:     Reader = Reader(MSG_EMPTY, "0", vidQueue)              # VID detector lane 1



    ######
    # RFID
    # ####
    LANE_1_MIN:         int     = 5                         # required read count for RFID reader
    LANE_2_MIN:         int     = 5                         # required read count for RFID reader
    LOG_TO_CSV:         bool    = True
    SEND_TO_SERIAL_4:   bool    = False
    MONITOR_UPS:        bool    = False

    lane1Q:             queue.Queue[str]  = queue.Queue()  # queue for reader 1
    lane1:              Reader = Reader(MSG_EMPTY, "1", lane1Q)    # initalize first reader

    lane2Q:             queue.Queue[str]  = queue.Queue()  # queue for reader 2
    lane2:              Reader = Reader(MSG_EMPTY, "2", lane2Q)    # second reader




    ##########################
    # Collect commandline args
    ##########################
    cmdLineParser = argparse.ArgumentParser(description=" Looking back down the fuel lane from the front of the Bus\r\n LEFT Lane is Lane 1\r\n Right Lane is lane 2")

    cmdLineParser.add_argument("--csvLogging",  "-c", type=int, default=1, help="[0] Disables logging to csv. [1] Enables logging to CSV file")
    cmdLineParser.add_argument("--debugLevel",  "-d", type=int, default=1, help="[0] NOTSET, [1] DEBUG, [2] INFO, [3] WARNING, [4] ERROR, [5] CRITICAL")

    cmdLineParser.add_argument("--emptyLaneMin", "-e", type=int, default=3, help="Min number of consecutive Tag null reads to deem a Lane is vacant.")

    cmdLineParser.add_argument("--leftLaneMin", "-l", type=int, default=5, help="Min number [5] of consecutive Tag reads before is declared present in Lane 1.")
    cmdLineParser.add_argument("--rightLaneMin", "-r", type=int, default=5, help="Min number [5] of consecutive Tag reads before is declared present in Lane 2.")

    cmdLineParser.add_argument("--fwdViaSerial", "-s", type=int, default=0, help="[0] Disables forwarding. [1] Enables forwarding")

    cmdLineParser.add_argument("--monitorUPS", "-u",   type=int, default=0, help="[0] Disables UPS monitor. [1] Enables UPS Monitor")

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

    log2journal.info("Parameters:<-l[x]>LeftLaneMin=%d       <-l[x]>RightLaneMin=%d       <-e[x]>EmptyMin=%d"       , LANE_1_MIN, LANE_2_MIN        , LANE_EMPTY_MIN)
    log2journal.info("Parameters:<-c[0,1]>RecordToCSV=%s  <-s[0,1]>SendToSerial=%s <-l[1,2,3,4,5]>LogLevel=(%d)0"   , LOG_TO_CSV, SEND_TO_SERIAL_4  , cmdLineArgs.debugLevel)
    log2journal.info("Parameters:<-u[0,1]>MonitorUPS=%s ", MONITOR_UPS)



    ###########################
    ### Serial Port Allocations
    ###########################
    # connect reader 1 - port 1 - COM11 on Windows - /dev/ttyUSB0 on Linux assumed
    try:
        lane1Serial_In = serial.Serial('/dev/ttyUSB0', baudrate=9600, bytesize=8, parity="N", stopbits=1)     # open serial port default 8N1
        # lane1Serial_In = serial.Serial('/dev/ttyUSB0', baudrate=9600, bytesize=7, parity="E", stopbits=1)    # open serial port default 7E1 - default

    except serial.SerialException as e:
        log2journal.error("Error opening serial port for: reader 1: {%s}", e)
        rpiRelay = LED_ON                                                                                       # turn on LED
        sys.exit()

    # connect reader 2 - port 2 - COM7 on Windows - /dev/ttyUSB1 on Linux
    try:
        lane2Serial_In = serial.Serial('/dev/ttyUSB1', baudrate=9600, bytesize=8, parity="N", stopbits=1)     # open serial port default 8N1
        # lane2Serial_In = serial.Serial('/dev/ttyUSB1', baudrate=9600, bytesize=7, parity="E", stopbits=1)    # open serial port default 7E1 - default
    except serial.SerialException as e:
        log2journal.error("Error opening serial port for: reader 2: {%s}", e)
        rpiRelay = LED_ON                                                                                       # turn on LED
        sys.exit()

    # connect VID detector input - port 3 - /dev/ttyUSB2 on Linux
    try:
        vid_In = serial.Serial('/dev/ttyUSB2', baudrate=9600, bytesize=8, parity="N", stopbits=1)
    except serial.SerialException as e:
        log2journal.error("Error opening serial port for: VID detector: {%s}", e)
        rpiRelay = LED_ON                                                                                       # turn on LED
        sys.exit()

    # connect output serial port - port 4 - /dev/ttyUSB3 on linux
    try:
        plc_Out = serial.Serial('/dev/ttyUSB3', baudrate=9600, bytesize=8, parity="N", stopbits=1)
    except serial.SerialException as e:
        log2journal.error("Error opening serial port for: output: {%s}", e)
        rpiRelay = LED_ON                                                                                       # turn on LED
        sys.exit()



    #####################
    # UPS Shutdown Thread
    #####################
    if (True is MONITOR_UPS):
        threading.Thread(target=shutdown_countdown_func).start()



    ###################################################
    # creating each thread to receive data from readers
    ###################################################
    threading.Thread(target=serialReadLine, args=(lane1Serial_In,   "Lane1:",)).start()                           # reader 1 thread
    threading.Thread(target=serialReadLine, args=(lane2Serial_In,   "Lane2:",)).start()                           # reader 2 thread
    threading.Thread(target=serialReadLine, args=(vid_In,           "VIDRD:",)).start()                                # VID detector thread



    ##############################################
    # database initialization
    # database is used to share data with the gui
    # SQL is used to exchange data with the GUI
    #############################################
    sql3Conn = sqlite3.connect('vid_data.db', check_same_thread = False)                                        # create or connect to the database
    # MAKE SURE ONLY THIS SCRIPT WRITES, TO AVOID CONFLICTS
    sql3Cursor = sql3Conn.cursor()                                                                              # create a cursor object to execute SQL commands

    sql3Cursor.execute('''
        CREATE TABLE IF NOT EXISTS vid_data (
                lane INTEGER PRIMARY KEY,
                vid TEXT,
                rfid TEXT
        )
    ''')                                                                                                        # creates table with limited columns
    sql3Conn.commit()
    # initialize a column for each lane
    for fuelLane in [1, 2]:
        sql3Cursor.execute('INSERT OR IGNORE INTO vid_data (lane, vid, rfid) VALUES (?, ?, ?)', (fuelLane, '', ''))
    sql3Conn.commit()                                                                                           # commit the changes to the database



    ######################################
    # extract fleet number from VID String
    # assumes the VID string is formatted
    # as "x-BBTxxxx,00000000\r\n"
    #     012345678901234567 8 9
    ######################################
    def busNumFromMsg(msg):
        if ((STD_MSG_LEN == len(msg)) and ('BBT' == msg[2:5:1]) and (',' == msg[9])):
            try:
                return msg.split(',')[0][5:]
            except Exception as e:  # Might make index error
                # might include more logic here to handle different formats
                print(f"Error extracting fleet number: '{msg}': {e}")

        return None
    # #_#end busNumFromMsg(



    ########################
    # Process the RFID Queue
    ########################
    def dequeRFID_Q_Lane(lane: Reader):
        num: str        = lane.num
        # log2journal.debug("dequeRFID_Q_Lane %s", num)
        if lane.queue.empty():
            if (lane.getNullPolls() > LANE_EMPTY_MIN) :                                                                            # seqNumFuelScanMsgsFromRFID resets if too many empty reads
                if (lane.getSequentialReads() != 0) :
                    log2journal.debug("L%s_Q_Empty:<%s><%d>", num, repr(lane.getFuelScanMsg()), lane.getSequentialReads())
                    lane.clearSequentialReads()
                    lane.updateTag(MSG_EMPTY, Q_EMPTY)
                    lane.setFuelScanMsg(MSG_EMPTY)
            else :
                lane.incNullPolls()
                lane.updateTag(MSG_POLLING, Q_POLLING)
                lane.setFuelScanMsg(num + "-" + MSG_POLLING + '-' + str(lane.getNullPolls()))
                log2journal.warning("L%s_Poll:<%s>", num, repr(lane.getFuelScanMsg()))                                                   # increment the empty counter for RFID reader 1
        else :
            lane.clearNullPolls()                                                                                                  # reset empty counter if queue is not empty
            lane.updateTag(lane.queue.get(True), Q_READY)
            lane.setFuelScanMsg(num + "-BBT" + lane.getBusNumFromTag(csvFleetList) + ",00000000" + "\r\n")                             # VID 800 outputs \r\n in the msg
            lane.incSequentialReads()

            if (lane.getFuelScanMsg() != lane.getPrevFuelScanMsg()):
                lane.setSequentialReads(1)                                                                                         # reset the counter to 1 if different tag is read

            lane.setPrevFuelScanMsg(lane.getFuelScanMsg())                                                                        # update previous RFID for lane 1
            log2journal.debug("L%s_TAG_DQ:<%s><%d><%s>", num, lane.getTag(), lane.getSequentialReads(), repr(lane.getFuelScanMsg()))    # log the current RFID

    # #_#end dequeRFIDLane(


    ####################
    # logLane
    ####################
    def logLane(vidMsg: str, thisLane: Reader, thatLane: Reader):
        num: str        = thisLane.num
        # log2journal.debug("logLane %s", num)
        now             = dt.datetime.now()
        tagId           = thisLane.getTag()
        lastTagId       = thisLane.getLastTag()
        tagBatt         = thisLane.getBatteryStatus()

        tagIn           = "L" + num + "_1TAG"
        vidMatchesRfid  = "_T" + num + "V" + num + "_"

        vidNum          =   "V0000" + num
        tagNum          =   "T0000" + num

        if (thisLane.getSequentialReads() > LANE_1_MIN) :                                                                  # get LANE_1_MIN_ consecutive reads to trust the data
            tagIn   = "L" + num + "_1TAG"

            vidNum = busNumFromMsg(vidMsg)
            tagNum = busNumFromMsg(thisLane.getFuelScanMsg())  # someting for several counts

            if (vidNum is None) and (tagNum is None) :
                vidMatchesRfid = "T" + num + "__V" + num
            else :
                if (vidNum == tagNum) :
                    if (vidNum is not None) and (tagNum is not None) :
                        vidMatchesRfid = "T" + num + "==V" + num
                    elif (vidNum is None) and (tagNum is not None) :
                        vidMatchesRfid = "T" + num + "ONLY"
                else :
                    vidMatchesRfid = "T" + num + "!=V" + num
                    log2journal.warning("VID%s:<%s> and TAG%s:<%s> do not match.", num, vidNum, tagNum, num)

            # Flag if the RFID is seen in both lanes
            if (((thisLane.getFuelScanMsg()[2:9] == thatLane.getFuelScanMsg()[2:9])) and (MSG_EMPTY not in thisLane.getFuelScanMsg()) and (MSG_POLLING not in thisLane.getFuelScanMsg())):
                log2journal.error("%s T1:<%s> T2<%s>", tagIn, repr(thisLane.getFuelScanMsg()), repr(thatLane.getFuelScanMsg()))
                tagIn = "L" + num + "_2TAG"

            log2journal.debug("%s:<%d><%s>", tagIn, len(thisLane.getFuelScanMsg()), repr(thisLane.getFuelScanMsg()))
            log2CSV(now, 'L' + num + '_TAG', vidMsg, thisLane.getFuelScanMsg(), tagId, tagBatt, lastTagId, thisLane.getSequentialReads(), thisLane.getNullPolls(), vidMatchesRfid, tagIn)
            sendToSerial4("L" + num + "_T", thisLane.getFuelScanMsg())

        # record if VID is in scope
        ################################
        elif (vidMsg != MSG_EMPTY):
            vidMatchesRfid  = "V" + num + "ONLY"
            vidNum = busNumFromMsg(vidMsg)
            if (is_vid_in_scope(vidNum, csvFleetList)) :
                log2CSV(now, 'L'  + num + '_VID', vidMsg, thisLane.getFuelScanMsg(), tagId, tagBatt, lastTagId, vid_L1_cntReadFromQ, vidsListSize, vidMatchesRfid, tagIn)

            if (len(vidMsg) == STD_MSG_LEN):
                log2journal.debug("L%s_VID FWD:<%d><%s>", num, len(vidMsg), repr(vidMsg))
                sendToSerial4("L" + num + "_V", vidMsg)                                                                           # send to serial port 4
            else :
                log2journal.info("L%s_VID Short:<%d><%s>", num, len(vidMsg), repr(vidMsg))
                if (len(vidMsg) == VID_MSG_MISSING_ODO_LEN):                                                            # if repairable pad then
                    sendToSerial4("L" + num + "_X", (vidMsg[:-2] + ",00000000" + "\r\n"))                                         # send to serial port 4

    # #_#end logLane(



    ##############################################################################
    ##############################################################################
    ## Main Loop - this will run continuously to read from queues and process data
    ##############################################################################
    ##############################################################################

    log2journal.info("Enter RFID Reader Main Loop")
    wdtCount = 1

    while True:
        # time of event

        dequeRFID_Q_Lane(lane1)
        dequeRFID_Q_Lane(lane2)

        # log the Tag being detected in both lanes.
        if ((lane1.isTagValid()) and (lane2.isTagValid())):
            if (lane2.getTag() == lane1.getTag()):
                log2journal.warning("BOTH_Q_DQ: TAG 1:<%s><%d> 2:<%s><%d>", lane1.getTag(), lane1.getSequentialReads(), lane2.getTag(), lane2.getSequentialReads())


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
        vid_L1_cntReadFromQ = 0                                                 # more than 1 will indicate falling behind

        vid_L2_Msg = MSG_EMPTY                                                  # default value for VID lane 2
        vid_L2_cntReadFromQ = 0                                                 # more than 1 will indicate falling behind

        vidQEmpty : bool = True

        vidsListSize = len(vidsList)

        for vidIn in vidsList :
            if (vidIn.startswith("1")) :                                          # VID msgs for lane 1
                vid_L1_Msg = vidIn
                vid_L1_cntReadFromQ += 1
                vidQEmpty = False
            elif (vidIn.startswith("2")) :                                        # VID msgs for lane 2
                vid_L2_Msg = vidIn
                vid_L2_cntReadFromQ += 1
                vidQEmpty = False

        if (False is vidQEmpty):
            log2journal.debug("VID_DQ V1:<%s><%d> V2:<%s><%d>", repr(vid_L1_Msg), vid_L1_cntReadFromQ, repr(vid_L2_Msg), vid_L2_cntReadFromQ)



        ####################################
        # share data with diagnostic console
        ####################################
        update_lane_data(sql3Conn, sql3Cursor, 1, vid_L1_Msg, lane1.getFuelScanMsg())                                     # update lane 1 data in the database
        update_lane_data(sql3Conn, sql3Cursor, 2, vid_L2_Msg, lane2.getFuelScanMsg())                                     # update lane 2 data in the database



        ####################
        # RFID data logging:
        ####################
        logLane(vid_L1_Msg, lane1, lane2)
        logLane(vid_L2_Msg, lane2, lane1)


        # log2journal.debug("WDT %d", wdtCount)
        notifer.notify("WATCHDOG=1")
        wdtCount += 1

        #######################################################
        # RFID Readers have P81 SW reset to Default Calibration
        # SC40A has been sent to ensure 1 second repeat
        # #####################################################
        # VID are on 1 sec period.
        # Slightly over sample to ensure keeping up
        # But be aware empty buffers occasionally
        #######################################################

        time.sleep(0.9)  # sleep

        # time.sleep(20)  # sleep 20 to test 15 sec watch dog
    # #_#end  Main While
# #_#end __name__ == '__main__'

# #_#end file



'''

count = 1
while True:
    print("Running... {}".format(count))
    n.notify("STATUS=Count is {}".format(count))
    count += 1
    time.sleep(2)

    ##########################
    # Process the RFID 2 Queue
    ##########################
    def dequeRFID_Q_Lane2(lane: Reader, num: int):
        if lane2Q.empty() :
            if (lane.getNullPolls() > LANE_EMPTY_MIN) :                                                                            # seqNumFuelScanMsgsFromRFID resets if too many empty reads
                if (lane.getSequentialReads() != 0) :
                    log2journal.debug("L%d_Q_Empty:<%s><%d>", num, repr(lane.getFuelScanMsg()), lane.getSequentialReads())
                    lane.clearSequentialReads()
                    lane.updateTag(MSG_EMPTY, Q_EMPTY)
                    lane.setFuelScanMsg(MSG_EMPTY)
            else :
                lane.incNullPolls()
                lane.updateTag(MSG_POLLING, Q_POLLING)
                lane.setFuelScanMsg(str(num) + "-" + MSG_POLLING + '-' + str(lane.getNullPolls()))
                log2journal.warning("L%d_Poll:<%s>", num, repr(lane.getFuelScanMsg()))
        else :
            lane.clearNullPolls()
            lane.updateTag(lane2Q.get(True), Q_READY)
            lane.setFuelScanMsg(str(num) + "-BBT" + lane.getBusNumFromTag(csvFleetList) + ",00000000" + "\r\n")                             # VID 800 outputs \r\n in the msg
            lane.incSequentialReads()                                                                                              # increment the counter for RFID reader 2

            if (lane.getFuelScanMsg() != lane.getPrevFuelScanMsg()):
                lane.setSequentialReads(1)

            lane.setPrevFuelScanMsg(lane.getFuelScanMsg())                                                                        # update previous RFID for lane 2
            log2journal.debug("L%d_TAG_DQ:<%s><%d><%s>", num, lane.getTag(), lane.getSequentialReads(), repr(lane.getFuelScanMsg()))   # repr to show escape characters like \n

    # #_#end dequeRFIDLane2(


    ####################
    #
    #
    ####################
    def logLane2(vidMsg: str, thisLane: Reader, thatLane: Reader):
        now             = dt.datetime.now()

        tagId           = thisLane.getTag()
        lastTagId       = thisLane.getLastTag()
        tagBatt         = thisLane.getBatteryStatus()

        tagIn           = "L2_1TAG"
        vidMatchesRfid  = "_T2V2_"

        vidNum          =   "V00002"
        tagNum          =   "T00002"

        if (thisLane.getSequentialReads() > LANE_2_MIN) :
            tagIn           = "L2_1TAG"

            vidNum = busNumFromMsg(vidMsg)
            tagNum = busNumFromMsg(thisLane.getFuelScanMsg())  # someting for several counts

            if (vidNum is None) and (tagNum is None) :
                vidMatchesRfid = "T2__V2"
            else :
                if (vidNum == tagNum) :
                    if (vidNum is not None) and (tagNum is not None) :
                        vidMatchesRfid = "T2==V2"
                    elif (vidNum is None) and (tagNum is not None) :
                        vidMatchesRfid = "T2ONLY"
                else :
                    vidMatchesRfid = "T2!=V2"
                    log2journal.warning("VID2:<%s> and TAG2:<%s> do not match.", vidNum, tagNum)

            if ((thisLane.getFuelScanMsg()[2:9] == thatLane.getFuelScanMsg()[2:9]) and (MSG_EMPTY not in thisLane.getFuelScanMsg()) and (MSG_POLLING not in thisLane.getFuelScanMsg())) :  # Flag if the RFID is seen in both lanes
                log2journal.error("%s T2:<%s> T1<%s>", tagIn, repr(thisLane.getFuelScanMsg()), repr(thatLane.getFuelScanMsg()))
                tagIn = "L2_2TAG"

            log2journal.debug("%s:<%d><%s>", tagIn, len(thisLane.getFuelScanMsg()), repr(thisLane.getFuelScanMsg()))
            log2CSV(now, 'L2_TAG', vidMsg, thisLane.getFuelScanMsg(), tagId, tagBatt, lastTagId, thisLane.getSequentialReads(), thisLane.getNullPolls(), vidMatchesRfid, tagIn)
            sendToSerial4("L2_T", thisLane.getFuelScanMsg())

        # record if VID is in scope
        #################################
        elif (vidMsg != MSG_EMPTY) :
            vidMatchesRfid  = "V2ONLY"
            vidNum = busNumFromMsg(vidMsg)
            if (is_vid_in_scope(vidNum, csvFleetList)) :
                log2CSV(now, 'L2_VID', vidMsg, thisLane.getFuelScanMsg(), tagId, tagBatt, lastTagId, vid_L2_cntReadFromQ, vidsListSize, vidMatchesRfid, tagIn)

            if (len(vidMsg) == STD_MSG_LEN):
                log2journal.debug("L2_VID FWD:<%d><%s>", len(vidMsg), repr(vidMsg))
                sendToSerial4("L2_V", vidMsg)                                                                           # send to serial port 4
            else :
                log2journal.info("L2_VID Short:<%d><%s>", len(vidMsg), repr(vidMsg))
                if (len(vidMsg) == VID_MSG_MISSING_ODO_LEN):                                                            # if repairable pad then
                    sendToSerial4("L2_X", (vidMsg[:-2] + ",00000000" + "\r\n"))                                         # send to serial port 4

    # #_#end logLane2(


'''