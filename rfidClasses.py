# pylint: disable=C0114, C0115, C0116
"""
A module that declares classes for the RFID Fuelbay Project.
"""

import csv

from rfidConstants  import Q_EMPTY
from rfidConstants  import MSG_INIT
from rfidConstants  import MSG_EMPTY

class Reader:
    """
    A class to represent an RFID Reader or VID 800.

    Attributes:
          get_status:
          tag: A string of the RFID tag/ VID Tag currently being detected
          change_status:
          updateTag: Function to update the tag being detected
          getBusNumFromTag: Function to convert RFID tag into a VID 800 format string

    """

    # false if no tag, tagNumber = "Empty"
    def __init__(self, tagNumber: str, num: str):
        """
        Initializes an instance based on status and tag number

        Args:
            status: No longer required
            tagNumber: String of the RFID tag/ VID Tag currently being detected by the reader
            lastTagNumber
        """
        self.num            : str = num
        self.tagNumber      : str  = tagNumber     # instance attribute
        self.tagValid       : bool = False
        self.batteryState   : str  = "ABSENT"
        self.sequentialReads: int  = 1
        self.lastTagNumber  : str  = tagNumber
        self.qStatus        : int  = Q_EMPTY

        self.nullPolls      : int  = 0

        self.fleetNumber    : str  = "TagUnknown"
        self.fuelScanMsg    : str  = MSG_EMPTY

        self.prevFuelScanMsg: str  = MSG_INIT                      # initial RFID for lane 1


    def findFirstUnprintable(self, s) -> int:
        for i, char in enumerate(s):
            if not char.isprintable():
                return i                    # Return the index immediately upon finding the first unprintable char
        return len(s)                       # Return length of string if no unprintable characters are found


    # get tag
    def getTag(self) -> str :
        # Returns the string of the RFID tag/ VID Tag currently being detected
        s = self.tagNumber
        ## WAB strip off trailing unprintable
        ## index = next((i for i, x in enumerate(s) if not x.isprintable()), None)
        index = self.findFirstUnprintable(s)
        return self.tagNumber[:index]


    def clearSequentialReads(self) :
        self.sequentialReads = 0

    def incSequentialReads(self) :
        self.sequentialReads += 1

    def setSequentialReads(self, value: int) :
        self.sequentialReads = value

    def getSequentialReads(self) -> int :
        return self.sequentialReads


    def clearNullPolls(self) :
        self.nullPolls = 0

    def incNullPolls(self) :
        self.nullPolls += 1

    def setNullPolls(self, value: int) :
        self.nullPolls = value

    def getNullPolls(self) -> int:
        return self.nullPolls


    def setFuelScanMsg(self, value: str) :
        self.fuelScanMsg = value

    def getFuelScanMsg(self) -> str:
        return self.fuelScanMsg


    def setPrevFuelScanMsg(self, value: str) :
        self.prevFuelScanMsg = value

    def getPrevFuelScanMsg(self) -> str:
        return self.prevFuelScanMsg


    # get tag
    def isTagValid(self) -> bool :
        return self.tagValid

    # get tag Battry Condition
    def getBatteryStatus(self) -> str :
        return self.batteryState

    # get tag
    def getLastTag(self) -> str:
        # Returns the string of the Last  RFID tag/ VID Tag detected
        # WAB strip off trailing unprintable
        s = self.lastTagNumber
        index = self.findFirstUnprintable(s)
        return self.lastTagNumber[:index]



    # change tag
    def updateTag(self, newTag, status) -> bool :
        # Function to update the tag being read

        if (newTag[0] == 'N') :                          # record last valid tag
            self.tagValid = True
            self.batteryState = "CHARGED"

        elif (newTag[0] == 'n') :                          # record last valid tag
            self.tagValid = True
            self.batteryState = "REPLACE"

        else :
            self.tagValid = False
            self.batteryState = "ABSENT"

        self.lastTagNumber = self.tagNumber
        self.tagNumber = newTag

        self.qStatus = status

        return self.tagValid



    ## WAB ToDo This needs polishing.
    ## - rfid tags are:  "EMPTY" "2_POLLING_" or "1_POLLING_"
    ## Concerns:
    ## - misreads from RFID readers i.e. does not consider chars and will break


    def getBusNumFromTag(self, csvFile):
        """
        Function to convert the RFID tag string to the fleet number of the bus the tag
        is fitted to.

        Args:
            csvFile: A formatted CSV file which contains a lookup table of each bus and RFID tag number
        """

        self.fleetNumber = "XXXX"                                           # default not registered

        if ((self.tagNumber[0] == 'N') or (self.tagNumber[0] == 'n')) :
            with open(csvFile, mode='r', encoding="utf-8") as file:         # read each row of csv file
                tagNum = self.tagNumber[1:]                                 # remove the prefix 'N' or 'n'
                for x in csv.reader(file):
                    if str(int(tagNum)) == str(x[1]):                       # checks if it exists in the list
                        self.fleetNumber = x[0]                             # update the fleet number
        else :
            print("Tag does not start with N|n")

        return self.fleetNumber
