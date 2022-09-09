import tkinter as tk
from typing import overload
from AAlib import *
from threading import Thread
from functools import partial as p
import time

#CREDIT: Credit to the guy on StackOverflow that I found this from! thank you!

class ToolTip(object):
    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0
        self.STOP = 0
        self.fadetime = settings("tooltipFade")
        self.popuptime = settings("tooltipPopup")

    def showtip(self, text):
        stoporig = self.STOP
        time.sleep(self.popuptime)
        if self.STOP != stoporig:
            return
        self.text = text
        if self.tipwindow or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + self.widget.winfo_width()
        y = y + cy + self.widget.winfo_rooty() + self.widget.winfo_height()/2
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_attributes('-alpha', 0)
        tw.wm_overrideredirect(1)
        tw.wm_attributes('-alpha', 1)
        label = tk.Label(tw, text=self.text, justify="left", bd=0, bg=palette("tooltipbg"), fg=palette("tooltipfg"), font=settings("font", 0.5))
        tw.wm_geometry("+%d+%d" % (x, y))
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            for i in range(0,self.fadetime):
                tw.wm_attributes('-alpha',(self.fadetime-i)/self.fadetime)
                time.sleep(0.01)
            tw.destroy()

def CreateToolTip(widget, text):
    toolTip = ToolTip(widget)
    def enter(event):
        Thread(target=p(toolTip.showtip, text), daemon=True).start()
    def leave(event):
        toolTip.STOP += 1
        Thread(target=toolTip.hidetip, daemon=True).start()
    widget.bind('<Enter>', enter)
    widget.bind('<Leave>', leave)