import tkinter as tk

class RfidGui:
    def __init__(self, master):
        self.master = master
        # Initialize the main window
        self.master.title("RFID GUI")
        self.master.geometry("1200x700")

        # Creating Widgets
        self.label = tk.Label(master, text="Welcome to the RFID GUI")
        
        self.lane1 = tk.Label(master, text="Lane 1", bg="red", width=30, height=30)
        self.lane2 = tk.Label(master, text="Lane 2", bg="red", width=30, height=30)

        # packing items into frame
        self.label.grid(row=0, column=0, pady=20)
        self.lane1.grid(row=1, column=0, padx=200, pady=10)
        self.lane2.grid(row=1, column=1, padx=20, pady=10)

    def update_lane(self, laneNumber, status):
        """
        Update the status of a lane.
        :param lane_number: 1 or 2
        :param status: 'red' or 'green'
        """
        if laneNumber == 1:
            self.lane1.config(bg=status)
        elif laneNumber == 2:
            self.lane2.config(bg=status)
        else:
            print("Invalid lane number. Use 1 or 2.")