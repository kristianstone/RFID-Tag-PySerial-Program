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
          change_tag: Function to update the tag being detected
          get_fleetNumber: Function to convert RFID tag into a VID 800 format string

    """

    # false if no tag, tagNumber = "Empty"
    def __init__(self, status, tagNumber):
        """
        Initializes an instance based on status and tag number

        Args:
            status: No longer required
            tagNumber: String of the RFID tag/ VID Tag currently being detected by the reader
        """
        self.status = status # instance attribute 
        self.tagNumber = tagNumber # instance attribute

    # get status - not required but will leave for video testing
    def get_status(self):
        """
        The status of the RFID reader/ VID 800
        """
        return self.status

    # get tag
    def get_tag(self):
        """
        Returns the string of the RFID tag/ VID Tag currently being detected
        """
        return self.tagNumber
    
    # change status
    def change_status(self, newStatus):
        """
        May no longer be required

        Args:
            newStatus: 
        """
        self.status = newStatus

    # change tag
    def change_tag(self, newTag):
        """
        Function to update the tag being read by the RFID Reader/ VID 800

        Args:
            newTag: New tag string
        """
        self.tagNumber = newTag


    '''
    This needs polishing.

    Concerns:
    - misreads from RFID readers i.e. does not consider chars and will break
    - rfid tags must be either a number or "empty"
    '''
    def get_fleetNumber(self, csvFile):
        """
        Function to convert the RFID tag string to the fleet number of the bus the tag 
        is fitted to. 

        Args:
            csvFile: A formatted CSV file which contains a lookup table of each bus and RFID tag number
        """
        self.fleetNumber = "Tag Not Registered" # default not registered
        if self.tagNumber == "empty":
            return self.fleetNumber

        with open(csvFile, mode = 'r') as file: # read each row of csv file
            tagNum = self.tagNumber[1:] # remove the prefix 'N' or 'n'
            for x in csv.reader(file): 
                if str(int(tagNum)) == str(x[1]): # checks if it exists in the list
                    self.fleetNumber = x[0] # update the fleet number

        return self.fleetNumber 


    # check battery if prefix is 'N' or 'n'