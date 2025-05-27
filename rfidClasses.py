# classes for reader
import csv

class Reader:
    # false if no tag, tagNumber = "Empty"
    def __init__(self, status, tagNumber):
        self.status = status # instance attribute 
        self.tagNumber = tagNumber # instance attribute

    # get status - not required but will leave for video testing
    def get_status(self):
        return self.status

    # get tag
    def get_tag(self):
        return self.tagNumber
    
    # change status
    def change_status(self, newStatus):
        self.status = newStatus

    # change tag
    def change_tag(self, newTag):
        self.tagNumber = newTag


    '''
    This needs polishing.

    Concerns:
    - misreads from RFID readers i.e. does not consider chars and will break
    - rfid tags must be either a number or "empty"
    '''
    def get_fleetNumber(self, csvFile):
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







        
