import tkinter as tk
from AAlib import *
import threading
from functools import partial as p
import time


class ToolTipWindow(object):
    def __init__(self):
        #Important variables
        self.text = ''
        self.widget = None
        self.tipwindow = None

        #Tooltip Window
        self.tipwindow = tk.Toplevel(self.widget)
        self.tipwindow.wm_attributes('-alpha', 0)   #Invisible
        self.tipwindow.wm_overrideredirect(1)
        self.label = tk.Label(self.tipwindow, justify='left', bd=0, bg=palette('tooltipbg'), fg=palette('tooltipfg'), font=settings('font', 0.5))
        self.label.pack(ipadx=1)

        #Threading
        self.leave_event = threading.Event()
        self.leave_event.set()
        self.enter_event = threading.Event()
        threading.Thread(target=self.tooltip, daemon=True, args=(self.enter_event, self.leave_event)).start()


    def tooltip(self, enter_event, leave_event):
        leave_flag = True
        enter_flag = False
        while True:
            if enter_flag: #You are hovering over a button. If you dont leave first, this "times out", and displays the tooltip
                leave_flag = leave_event.wait(0.5) #Waits for 1 second before popup
                #If user leaves before we should do the popup
                if not leave_flag: #User stays long enough, change text, move window to right location, display the tooltip
                    self.label.config(text=self.text)
                    x, y, cx, cy = self.widget.bbox('insert')
                    x = x +      self.widget.winfo_rootx() + self.widget.winfo_width()
                    y = y + cy + self.widget.winfo_rooty() + self.widget.winfo_height()/2
                    self.tipwindow.wm_attributes('-alpha', 1)
                    self.tipwindow.wm_geometry('+%d+%d' % (x, y))
                    self.tipwindow.lift()
                    leave_flag = leave_event.wait() #Waits however long until user leaves the button
                    self.tipwindow.wm_attributes('-alpha', 0)   
            
            enter_flag = enter_event.wait() #Waits however long until user hovers over a button again

    def enter(self, widget, text, event):
        self.widget = widget
        self.text = text
        self.enter_event.set()
        self.leave_event.clear()

    def leave(self, event):
        self.leave_event.set()
        self.enter_event.clear()

    def CreateToolTip(self, widget, displayText):
        widget.bind('<Enter>', p(self.enter, widget, displayText))
        widget.bind('<Leave>', self.leave)

