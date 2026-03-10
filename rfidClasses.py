# pylint: disable=C0114, C0115, C0116
"""
A module that declares classes for the RFID Fuelbay Project.
"""

import csv
from rfidConstants import  *

class Reader:
    """
    A class to represent an RFID Reader or VID 800.

    Attributes:
          get_status:
          get_tag: A string of the RFID tag/ VID Tag currently being detected
          change_status:
          update_tag: Function to update the tag being detected
          get_BusNumFromTag: Function to convert RFID tag into a VID 800 format string

    """

    # false if no tag, tagNumber = "Empty"
    def __init__(self, tagNumber):
        """
        Initializes an instance based on status and tag number

        Args:
            status: No longer required
            tagNumber: String of the RFID tag/ VID Tag currently being detected by the reader
            lastTagNumber
        """
        self.tagNumber      :str  = tagNumber     # instance attribute
        self.lastTagNumber  :str  = tagNumber
        self.qStatus        :int  = Q_EMPTY
        self.sequentialReads:int  = 1
        self.nullPolls      :int  = 0
        self.tagValid       :bool = False
        self.fleetNumber    :str  = "TagUnknown"
        self.fuelScanMsg    :str  = MSG_EMPTY
        self.prevFuelScanMsg:str  = MSG_INIT                      # initial RFID for lane 1


    # get status - not required but will leave for video testing
    def get_status(self):
        # The status of the RFID reader/ VID 800
        return self.status


    def find_first_unprintable(self, s) -> int:
        for i, char in enumerate(s):
            if not char.isprintable():
                return i                    # Return the index immediately upon finding the first unprintable char
        return len(s)                       # Return length of string if no unprintable characters are found


    # get tag
    def get_tag(self) -> str :
        # Returns the string of the RFID tag/ VID Tag currently being detected
        s = self.tagNumber
        ## WAB strip off trailing unprintable
        ## index = next((i for i, x in enumerate(s) if not x.isprintable()), None)
        index = self.find_first_unprintable(s)
        return self.tagNumber[:index]


    def clearSequentialReads(self) :
        self.sequentialReads = 0

    def incSequentialReads(self) :
        self.sequentialReads += 1

    def setSequentialReads(self, value:int) :
        self.sequentialReads = value

    def getSequentialReads(self) -> int :
        return self.sequentialReads


    def clearNullPolls(self) :
        self.nullPolls = 0

    def incNullPolls(self) :
        self.nullPolls += 1

    def setNullPolls(self, value:int) :
        self.nullPolls = value

    def getNullPolls(self) -> int:
        return self.nullPolls


    def setFuelScanMsg(self, value:str) :
        self.fuelScanMsg = value

    def getFuelScanMsg(self) -> str:
        return self.fuelScanMsg


    def setPrevFuelScanMsg(self, value:str) :
        self.prevFuelScanMsg = value

    def getPrevFuelScanMsg(self) -> str:
        return self.prevFuelScanMsg


    # get tag
    def is_tag_valid(self) -> bool :
        return self.tagValid

    # get tag
    def get_last_tag(self) -> str:
        # Returns the string of the Last  RFID tag/ VID Tag detected
        # WAB strip off trailing unprintable
        s = self.lastTagNumber
        index = self.find_first_unprintable(s)
        return self.lastTagNumber[:index]



    # change tag
    def update_tag(self, newTag, qStatus) -> bool :
        # Function to update the tag being read

        if(newTag[0] == 'n' or newTag[0] == 'N') :                          # record last valid tag
            self.lastTagNumber = self.tagNumber
            self.tagValid = True
        else:
            self.tagValid = False

        self.tagNumber = newTag
        self.status = qStatus

        return self.tagValid



    ## WAB ToDo This needs polishing.
    ## - rfid tags are:  "EMPTY" "2_POLLING_" or "1_POLLING_"
    ## Concerns:
    ## - misreads from RFID readers i.e. does not consider chars and will break


    def get_BusNumFromTag(self, csvFile):
        """
        Function to convert the RFID tag string to the fleet number of the bus the tag
        is fitted to.

        Args:
            csvFile: A formatted CSV file which contains a lookup table of each bus and RFID tag number
        """

        self.fleetNumber = "Tag Unknown" # default not registered

        if ((self.tagNumber[0] == 'N') or (self.tagNumber[0] == 'n')) :
            with open(csvFile, mode='r', encoding="utf-8") as file: # read each row of csv file
                tagNum = self.tagNumber[1:] # remove the prefix 'N' or 'n'
                for x in csv.reader(file):
                    if str(int(tagNum)) == str(x[1]): # checks if it exists in the list
                        self.fleetNumber = x[0] # update the fleet number
        else :
            print ("Tag does not start with N|n")

        return self.fleetNumber
