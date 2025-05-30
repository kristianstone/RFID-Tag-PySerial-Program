import tkinter as tk

class RFIDGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("RFID Reader GUI")
        self.canvas = tk.Canvas(root, width=800, height=600, bg='white')
        self.canvas.pack()
        # rectangles for the each reader
        self.rect1 = self.canvas.create_rectangle(50, 50, 170, 170, fill="red")
        self.rect2 = self.canvas.create_rectangle(230, 50, 350, 170, fill="red")

    def update_lane(self, lane_number, status):
        if lane_number == 1:
            color = "green" if status else "red"
            self.canvas.itemconfig(self.rect1, fill=color)
        elif lane_number == 2:
            color = "green" if status else "red"
            self.canvas.itemconfig(self.rect2, fill=color)