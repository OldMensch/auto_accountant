
from AAlib import *
import threading
from functools import partial as p


class ToolTipWindow(object):
    def __init__(self, mouse_pos_command):
        #Important variables
        self.text = ''
        self.widget = None
        self.tipwindow = None
        self.mouse_pos_command = mouse_pos_command

        #Tooltip Window
        self.tipwindow = tk.Toplevel(self.widget)
        self.tipwindow.wm_attributes('-alpha', 0)   #Invisible
        self.tipwindow.wm_overrideredirect(1)
        self.label = tk.Label(self.tipwindow, justify='left', bd=0, bg=palette('tooltipbg'), fg=palette('tooltipfg'), font=setting('font', 0.5))
        self.label.pack(ipadx=1)

        #Threading
        self.leave_event = threading.Event()
        self.leave_event.set()
        self.enter_event = threading.Event()
        threading.Thread(target=self.tooltip, daemon=True, args=(self.enter_event, self.leave_event)).start()


    def tooltip(self, enter_event, leave_event):
        leave_flag = True
        while True:
            enter_event.wait() #Waits however long until user hovers over a button again
            
            leave_flag = leave_event.wait(1) #Waits for 1 second before popup
            #If user leaves before we should do the popup
            if not leave_flag: #User stays long enough, change text, move window to right location, display the tooltip
                mouse_pos = self.mouse_pos_command() #Retrieves mous position info from the main portfolio
                self.tipwindow.wm_geometry('+%d+%d' % (mouse_pos[0]+5, mouse_pos[1]+5))
                self.label.config(text=self.text)
                self.tipwindow.wm_attributes('-alpha', 1)
                self.tipwindow.lift()
                leave_flag = leave_event.wait() #Waits however long until user leaves the button
                self.tipwindow.wm_attributes('-alpha', 0)   
            

    def enter(self, widget, text, event):
        self.widget = widget
        self.text = text
        self.enter_event.set()
        self.leave_event.clear()

    def leave(self, event):
        self.leave_event.set()
        self.enter_event.clear()

    def SetToolTip(self, widget, displayText):
        widget.bind('<Enter>', p(self.enter, widget, displayText))
        widget.bind('<Leave>', self.leave)

