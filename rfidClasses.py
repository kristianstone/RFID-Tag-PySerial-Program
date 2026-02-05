"""
A module that declares classes for the RFID Fuelbay Project.
"""

import csv

class Reader:
    """
    A class to represent an RFID Reader or VID 800.

    Attributes:
          get_status: 
          get_tag: A string of the RFID tag/ VID Tag currently being detected
          change_status: 
          update_tag: Function to update the tag being detected
          get_fleetNumber: Function to convert RFID tag into a VID 800 format string

    """

    # false if no tag, tagNumber = "Empty"
    def __init__(self, status, tagNumber):
        """
        Initializes an instance based on status and tag number

        Args:
            status: No longer required
            tagNumber: String of the RFID tag/ VID Tag currently being detected by the reader
            lastTagNumber
        """
        self.status = status # instance attribute 
        self.tagNumber = tagNumber # instance attribute
        self.lastTagNumber = tagNumber

    # get status - not required but will leave for video testing
    def get_status(self):
        """
        The status of the RFID reader/ VID 800
        """
        return self.status

    def find_first_unprintable(self, s):
        for i, char in enumerate(s):
            if not char.isprintable():
                return i  # Return the index immediately upon finding the first unprintable char
        return None # Return None if no unprintable characters are found

    # get tag
    def get_tag(self):
        """
        Returns the string of the RFID tag/ VID Tag currently being detected
        """
        ## WAB strip off trailing unprintable
        s = self.tagNumber
        index = self.find_first_unprintable(s)
        ## index = next((i for i, x in enumerate(s) if not x.isprintable()), None)
        return self.tagNumber[:index]

    # get tag
    def get_last_tag(self):
        """
        Returns the string of theLast  RFID tag/ VID Tag detected
        """
        ## WAB strip off trailing unprintable
        s = self.lastTagNumber
        index = self.find_first_unprintable(s)
        ## index = next((i for i, x in enumerate(s) if not x.isprintable()), None)
        return self.lastTagNumber[:index]

    # change status
    def change_status(self, newStatus):
        """
        May no longer be required

        Args:
            newStatus: 
        """
        self.status = newStatus

    # change tag
    def update_tag(self, newTag):
        """
        Function to update the tag being read by the RFID Reader/ VID 800

        Args:
            newTag: New tag string
        """

        if(newTag[0] == 'n' or newTag[0] == 'N') :
            self.lastTagNumber = self.tagNumber
        self.tagNumber = newTag


    '''
    This needs polishing.

    Concerns:
    - misreads from RFID readers i.e. does not consider chars and will break
    - rfid tags must be either a number or "EMPTY"
    '''
    def get_fleetNumber(self, csvFile):
        """
        Function to convert the RFID tag string to the fleet number of the bus the tag 
        is fitted to. 

        Args:
            csvFile: A formatted CSV file which contains a lookup table of each bus and RFID tag number
        """
        self.fleetNumber = "Tag Unknown" # default not registered

        if ((self.tagNumber[0] == 'N') or (self.tagNumber[0] == 'n')) :
            with open(csvFile, mode = 'r') as file: # read each row of csv file
                tagNum = self.tagNumber[1:] # remove the prefix 'N' or 'n'
                for x in csv.reader(file): 
                    if str(int(tagNum)) == str(x[1]): # checks if it exists in the list
                        self.fleetNumber = x[0] # update the fleet number

        return self.fleetNumber 
