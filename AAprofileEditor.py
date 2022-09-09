from AAlib import *
from AAmessageBox import MessageBox

import tkinter as tk
from functools import partial as p



class ProfileEditor(tk.Toplevel):
    def __init__(self, upper, prof=None):  #upper is a reference to the original PortfolioApp, master is a reference to the TopLevel GUI 
        """Opens a new wallet editor to modify the name or description of a wallet"""
        super().__init__()
        self.configure(bg=palette("dark"))
        self.protocol("WM_DELETE_WINDOW", self.comm_cancel) #makes closing the window identical to hitting cancel
        self.grab_set()       #You can only interact with this window now
        self.focus_set()
        self.resizable(False,False)  #So you cant resize this window

        self.upper= upper
        if prof == 1:
            self.title("Create Profile")
            self.prof = 1
        else:
            self.title("Edit Profile")
            self.prof = upper.profile

        self.create_GUI()
        self.create_MENU()
        self.create_ENTRIES()

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

        self.GUI["profileEditorFrame"] = tk.Frame(self, bg=palette("accent"))

        self.GUI["title"] = tk.Label(self.GUI["profileEditorFrame"], fg=palette("entrycursor"), bg=palette("accent"), font=settings("font"))
        if self.prof == 1:
            self.GUI["title"].configure(text="Create Profile")
        else:
            self.GUI["title"].configure(text="Edit Profile")

        self.GUI["entryFrame"] = tk.Frame(self.GUI["profileEditorFrame"], bg=palette("light"))
        self.GUI["menuFrame"] = tk.Frame(self.GUI["profileEditorFrame"])


        #GUI RENDERING
        #==============================
        self.GUI["profileEditorFrame"].grid(padx=(20,20), pady=(20,20))

        self.GUI["title"].grid(column=0,row=0, pady=(20,20))
        self.GUI["entryFrame"].grid(column=0,row=2)
        self.GUI["menuFrame"].grid(column=0,row=3, pady=(20,20))

    def create_MENU(self):
        #MENU CREATION
        #==============================
        self.MENU = {}

        #SAVE/CANCEL buttons
        self.MENU["save"] = tk.Button(self.GUI["menuFrame"], text="Save", bg=palette("entry"), fg="#00ff00", font=settings("font"), command=self.comm_save)
        self.MENU["cancel"] = tk.Button(self.GUI["menuFrame"], text="Cancel", bg=palette("entry"), fg="#ff0000", font=settings("font"), command=self.comm_cancel)
        self.MENU["delete"] = tk.Button(self.GUI["menuFrame"], text="Delete", bg="#ff0000", fg="#000000", font=settings("font"), command=self.comm_deleteProfile)

        #MENU RENDERING
        #==============================

        #SAVE/CANCEL buttons
        self.MENU["save"].pack(side="left")
        self.MENU["cancel"].pack(side="left")
        if self.prof != 1:
            self.MENU["delete"].pack(side="left")

    def create_ENTRIES(self):        
        #STRING VARIABLES
        #==============================
        self.TEMP = {       #These are the default values for all inputs    
            "name":         tk.StringVar(self, value="")
        }
        if self.prof != 1:  #If not NEW, replace default value with what you're actually editing
            self.TEMP["name"].set(self.prof)

        #WIDGETS
        #==============================
        self.ENTRIES = {}
        self.LABELS = {}

        #ENTRIES
        #==============
        widthsetting = 24

        self.ENTRIES["name"] = tk.Entry(self.GUI["entryFrame"], textvariable=self.TEMP["name"], width=widthsetting, bg=palette("entry"), fg=palette("entrytext"), insertbackground=palette("entrycursor"), font=settings("font"))
        
        #Entry restrictions

        def validName(new):
            if len(new) > 24:
                return False
            return True
        valName = self.register(validName)
        self.ENTRIES["name"].configure(validate="key", vcmd=(valName, '%P'))
        
        #LABELS
        #==============
        self.LABELS["name"] = tk.Label(self.GUI["entryFrame"], text="Name", bg=palette("light"), fg=palette("entrycursor"), font=settings("font",0.5))

        #RENDERING
        #==============================

        self.LABELS["name"]     .grid(column=0,row=0, sticky="NS")
        self.ENTRIES["name"]    .grid(column=1,row=0, sticky="NS")

    def comm_deleteProfile(self):
        PERM["profiles"].pop(self.prof)  #destroy the old profile
        self.upper.profile = ""
        self.upper.create_profiles()
        self.upper.disable_all()
        self.upper.reset_visuals()
        self.comm_cancel()


    def comm_save(self):
        #DATA CULLING AND CONVERSION PART I
        #==============================
        #converts all tk.StringVar's to their proper final format

        ID = self.TEMP["name"].get().rstrip().lstrip()

        # CHECKS
        #==============================
        #new ticker will be unique?
        for prof in PERM["profiles"]:
            if prof.lower() == ID.lower() and prof != self.prof:
                MessageBox(self, "ERROR!", "A profile already exists with this name!")
                return

        #Name isn't an empty string?
        if ID == "":
            MessageBox(self, "ERROR!", "Must enter a name for this profile")
            return



        #TRANSACTION SAVING AND OVERWRITING
        #==============================
        if self.prof == 1 or self.prof != ID:
            PERM["profiles"][ID] = {"wallets":[],"assets":[], "classes":[]}   #creates new profile
            if self.prof != 1:   #PROFILE RE-NAMED
                self.upper.profile = ID
                PERM["profiles"][ID] = PERM["profiles"][self.prof]  #copies old data to new profile
                PERM["profiles"].pop(self.prof)  #destroy the old profile
        
        self.upper.create_profiles()

        if self.prof != 1 and self.prof != ID:   #re-whitens original selection after recreating the profile menu
            self.upper.PROFILES[ID].configure(bg="#ffffff", fg="#000000")
        elif self.upper.profile != "":
            self.upper.PROFILES[self.upper.profile].configure(bg="#ffffff", fg="#000000")

        self.comm_cancel()

    def _esc(self,event):    #Exit this window
        self.comm_cancel()
    def comm_cancel(self):  
        self.upper.grab_set()
        self.upper.focus_set()
        self.destroy()  #no extra commands, so that closing the window is functionally identical to cancellation






