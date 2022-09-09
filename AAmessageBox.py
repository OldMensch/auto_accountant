from AAlib import *

import tkinter as tk
from functools import partial as p




class MessageBox(tk.Toplevel):
    def __init__(self, upper, t, m, defQuitName="Ok", defColor="#ffffff", options=[], commands=[], colors=[], width=32, height=8):  #upper is a reference to the original PortfolioApp, master is a reference to the TopLevel GUI 
        """Opens a message box with message \'m\' and title \'t\'.\n
            \'yn\' - False by default, but if true, its not just an OK box, but a yes-no and returns a boolean\n
            You can enter a p command for the yes-no conditons, \'y\' and \'n\'. NOTE: y also applies for "OK" functions\n
            \'upper\' - a reference to the tkinter window which called this editor"""
        super().__init__()
        if len(options) != len(commands) != len(colors):
            raise Exception("MissingInputError: Entered " + len(commands) + " commands for " + len(options) + " options and " + len(colors) + " colors. All must be equal!")
        for option in options:
            if not isinstance(option, (str)):
                raise Exception("InvalidInputError: One or multiple options are not STRING type")
        for command in commands:
            if not isinstance(command, (p)):
                raise Exception("InvalidInputError: One or multiple commands are not p type")
        for color in colors:
            if not isinstance(color, (str)):
                raise Exception("InvalidInputError: One or multiple colors are not STRING type")
            if color[0] != "#" and color != "": #Empty strings are acceptable and it just uses the default color
                raise Exception("InvalidInputError: \'" + color + "\' is not a color")

        self.configure(bg=palette("dark"))
        self.grab_set()       #You can only interact with this window now
        self.focus_set()
        self.resizable(False,False)  #So you cant resize this window
        self.title(t)

        self.upper, self.m, self.t, self.defQuitName, self.defColor, self.options, self.commands, self.colors, self.width, self.height = upper, m, t, defQuitName, defColor, options, commands, colors, width, height

        self.create_GUI()
        self.create_MENU()
        
        self.protocol("WM_DELETE_WINDOW", self.comm_quit) #makes closing the window identical to hitting 'YES' or 'OK

        #BINDINGS
        #==============================
        self.bind("<Escape>", self._esc)
        
        self.update()    #Necessary, so that geometry() has the correct window dimensions
        self.geometry("+%d+%d" % ( (self.winfo_screenwidth()-self.winfo_width())/2 + self.winfo_x()-self.winfo_rootx(),
                                                    (self.winfo_screenheight()-self.winfo_height())/2 ))#centers the window in the middle of the screen


    def create_GUI(self):
        #GUI CREATION
        #==============================
        self.GUI = {}

        self.GUI["messageBoxFrame"] = tk.Frame(self, bg=palette("accent"))

        self.GUI["title"] = tk.Label(self.GUI["messageBoxFrame"], text=self.t, fg=palette("entrytext"),bg=palette("accent"), font=settings("font"))
        self.GUI["messageFrame"] = tk.Text(self.GUI["messageBoxFrame"], fg=palette("entrycursor"), bg=palette("dark"), font=settings("font", 0.75), height=self.height,width=self.width,wrap="word")
        self.GUI["messageFrame"].insert(0.0, self.m)
        self.GUI["messageFrame"].configure(state="disabled")
        self.GUI["menuFrame"] = tk.Frame(self.GUI["messageBoxFrame"])


        #GUI RENDERING
        #==============================
        self.GUI["messageBoxFrame"].grid(padx=(20,20), pady=(20,20))

        self.GUI["title"].grid(column=0,row=0, pady=(20,20))
        self.GUI["messageFrame"].grid(column=0,row=1)    
        self.GUI["menuFrame"].grid(column=0,row=3, pady=(20,20))

    def create_MENU(self):
        #MENU CREATION
        #==============================
        self.MENU = {}

        #The default quitting button, and other extra buttons
        self.MENU[self.defQuitName] =  tk.Button(self.GUI["menuFrame"], text=self.defQuitName, bg=palette("entry"), fg=self.defColor, font=settings("font"), command=self.comm_quit)
        if len(self.options) > 0:
            for option in self.options:
                i = self.options.index(option)
                self.MENU[option] =  tk.Button(self.GUI["menuFrame"], text=option, bg=palette("entry"), font=settings("font"), command=p(self.comm_custom, self.commands[i] ))
                if self.colors[i] == "":
                    self.MENU[option].configure(fg="#ffffff")
                else:
                    self.MENU[option].configure(fg=self.colors[i])


        #MENU RENDERING
        #==============================

        #OK/YES/NO buttons
        for widget in self.MENU:
            self.MENU[widget].pack(side="left")


    def comm_custom(self, part):
        part()
        self.comm_quit()

    def _esc(self,event):    #Exit this window
        self.comm_quit()
    def comm_quit(self):
        self.upper.focus_set()
        self.destroy()





