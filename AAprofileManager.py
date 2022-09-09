from AAlib import *
from AAprofileEditor import ProfileEditor

import tkinter as tk
from functools import partial as p



class ProfileManager(tk.Toplevel):
    def __init__(self, upper):  #upper is a reference to the original PortfolioApp, master is a reference to the TopLevel GUI 
        """Opens the Profile Manager for editing filter profiles"""
        super().__init__()
        self.configure(bg=palette("dark"))
        self.protocol("WM_DELETE_WINDOW", self.comm_close) #makes closing the window identical to hitting cancel
        self.grab_set()       #You can only interact with this window now
        self.focus_set()
        self.resizable(False,False)  #So you cant resize this window

        self.title("Manage Filter Profiles")

        self.upper = upper
        self.profile = ""
        self.hashold = hash(json.dumps(PERM["profiles"], sort_keys=True))

        self.create_GUI()
        self.create_MENU()
        self.create_profiles()
        self.create_others()
        self.disable_all()

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

        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(0,weight=1)
        self.GUI["profileManagerFrame"] = tk.Frame(self, bg=palette("accent"))
        self.GUI["profileManagerFrame"].grid_columnconfigure(0,weight=1)

        self.GUI["title"] = tk.Label(self.GUI["profileManagerFrame"], text="Manage Filter Profiles", fg=palette("entrycursor"), bg=palette("accent"), font=settings("font"))
        self.GUI["newProfile"] = tk.Button(self.GUI["profileManagerFrame"], text="+ Profile", bg=palette("purchase"), fg="#000000", font=settings("font", 0.75), command=p(ProfileEditor, self, 1))
        self.GUI["editProfile"] = tk.Button(self.GUI["profileManagerFrame"], text="Edit", bg=palette("transfer"), fg="#000000", font=settings("font", 0.75), command=p(ProfileEditor, self))
        self.GUI["titleWallets"] = tk.Label(self.GUI["profileManagerFrame"], text="Filter by Wallet", fg=palette("entrycursor"), bg=palette("accentdark"), font=settings("font", 0.75))
        self.GUI["titleAssets"] = tk.Label(self.GUI["profileManagerFrame"], text="Filter by Asset", fg=palette("entrycursor"), bg=palette("accentdark"), font=settings("font", 0.75))
        self.GUI["titleClasses"] = tk.Label(self.GUI["profileManagerFrame"], text="Filter by Class", fg=palette("entrycursor"), bg=palette("accentdark"), font=settings("font", 0.75))

        #PROFILE SELECTION
        #=================
        self.GUI["profileCanvas"] = tk.Canvas(self.GUI["profileManagerFrame"], bg=palette("light"), highlightthickness=0)
        self.GUI["profileFrame"] = tk.Frame(self.GUI["profileCanvas"], bg=palette("light"))
        
        self.GUI["scroll_profiles"] = tk.Scrollbar(self.GUI["profileManagerFrame"], orient="vertical", command=self.GUI["profileCanvas"].yview)

        self.GUI["profileCanvas"].configure(yscrollcommand=self.GUI["scroll_profiles"].set)
        self.GUI["profileCanvas"].create_window(0, 0, window=self.GUI["profileFrame"], anchor=tk.NW)

        #WALLET SELECTION
        #=================
        self.GUI["walletCanvas"] = tk.Canvas(self.GUI["profileManagerFrame"], bg=palette("light"), highlightthickness=0)
        self.GUI["walletFrame"] = tk.Frame(self.GUI["walletCanvas"], bg=palette("light"))
        
        self.GUI["scroll_wallets"] = tk.Scrollbar(self.GUI["profileManagerFrame"], orient="vertical", command=self.GUI["walletCanvas"].yview)

        self.GUI["walletCanvas"].configure(yscrollcommand=self.GUI["scroll_wallets"].set)
        self.GUI["walletCanvas"].create_window(0, 0, window=self.GUI["walletFrame"], anchor=tk.NW)

        #ASSET SELECTION
        #=================
        self.GUI["assetCanvas"] = tk.Canvas(self.GUI["profileManagerFrame"], bg=palette("light"), highlightthickness=0)
        self.GUI["assetFrame"] = tk.Frame(self.GUI["assetCanvas"], bg=palette("light"))
        
        self.GUI["scroll_assets"] = tk.Scrollbar(self.GUI["profileManagerFrame"], orient="vertical", command=self.GUI["assetCanvas"].yview)

        self.GUI["assetCanvas"].configure(yscrollcommand=self.GUI["scroll_assets"].set)
        self.GUI["assetCanvas"].create_window(0, 0, window=self.GUI["assetFrame"], anchor=tk.NW)

        #ASSET CLASS SELECTION
        #=================
        self.GUI["classCanvas"] = tk.Canvas(self.GUI["profileManagerFrame"], bg=palette("light"), highlightthickness=0)
        self.GUI["classFrame"] = tk.Frame(self.GUI["classCanvas"], bg=palette("light"))
        
        self.GUI["scroll_classes"] = tk.Scrollbar(self.GUI["profileManagerFrame"], orient="vertical", command=self.GUI["classCanvas"].yview)

        self.GUI["classCanvas"].configure(yscrollcommand=self.GUI["scroll_classes"].set)
        self.GUI["classCanvas"].create_window(0, 0, window=self.GUI["classFrame"], anchor=tk.NW)

        #GUI RENDERING
        #==============================
        self.GUI["profileManagerFrame"].grid(padx=(20,20), pady=(20,20))

        self.GUI["title"].grid(             column=0,row=0, columnspan=9, pady=(20,20))
        self.GUI["newProfile"].grid(        column=0,row=1, columnspan=1, sticky="NSEW")
        self.GUI["editProfile"].grid(       column=1,row=1, columnspan=2, sticky="NSEW")
        self.GUI["titleWallets"].grid(      column=3,row=1, columnspan=2, sticky="NSEW")
        self.GUI["titleAssets"].grid(       column=5,row=1, columnspan=2, sticky="NSEW")
        self.GUI["titleClasses"].grid(      column=7,row=1, columnspan=2, sticky="NSEW")

        self.GUI["profileCanvas"].grid(     column=0,row=2, columnspan=2,sticky="NSEW")
        self.GUI["scroll_profiles"].grid(   column=2,row=2, sticky="NSE")
        self.GUI["walletCanvas"].grid(      column=3,row=2, sticky="NSEW")
        self.GUI["scroll_wallets"].grid(    column=4,row=2, sticky="NS")
        self.GUI["assetCanvas"].grid(       column=5,row=2, sticky="NSEW")
        self.GUI["scroll_assets"].grid(     column=6,row=2, sticky="NS")
        self.GUI["classCanvas"].grid(       column=7,row=2, sticky="NSEW")
        self.GUI["scroll_classes"].grid(    column=8,row=2, sticky="NS")

    def create_MENU(self):
        #MENU CREATION
        #==============================
        self.MENU = {
            "close" : tk.Button(self.GUI["profileManagerFrame"], text="Close", bg=palette("entry"), fg="#ffffff", font=settings("font"), command=self.comm_close),
            "clearWallets" : tk.Button(self.GUI["profileManagerFrame"], text="Clear All", bg=palette("entry"), fg="#ffffff", font=settings("font"), command=self.comm_clearWallets),
            "clearAssets" : tk.Button(self.GUI["profileManagerFrame"], text="Clear All", bg=palette("entry"), fg="#ffffff", font=settings("font"), command=self.comm_clearAssets),
            "clearClasses" : tk.Button(self.GUI["profileManagerFrame"], text="Clear All", bg=palette("entry"), fg="#ffffff", font=settings("font"), command=self.comm_clearClasses),
        }
        #MENU RENDERING
        #==============================
        self.MENU["close"].grid(column=0,row=3, columnspan=3, pady=(20,20))
        self.MENU["clearWallets"].grid(column=3,row=3, columnspan=2, pady=(20,20))
        self.MENU["clearAssets"].grid(column=5,row=3, columnspan=2, pady=(20,20))
        self.MENU["clearClasses"].grid(column=7,row=3, columnspan=2, pady=(20,20))


    def disable_all(self):
        for w in self.WALLETS:
            self.WALLETS[w].configure(state="disabled")
        for a in self.ASSETS:
            self.ASSETS[a].configure(state="disabled")
        for c in self.CLASSES:
            self.CLASSES[c].configure(state="disabled")
        self.MENU["clearWallets"].configure(state="disabled")
        self.MENU["clearAssets"].configure(state="disabled")
        self.MENU["clearClasses"].configure(state="disabled")
        self.GUI["editProfile"].configure(state="disabled")
    def enable_all(self):
        for w in self.WALLETS:
            self.WALLETS[w].configure(state="normal")
        for a in self.ASSETS:
            self.ASSETS[a].configure(state="normal")
        for c in self.CLASSES:
            self.CLASSES[c].configure(state="normal")
        self.MENU["clearWallets"].configure(state="normal")
        self.MENU["clearAssets"].configure(state="normal")
        self.MENU["clearClasses"].configure(state="normal")
        self.GUI["editProfile"].configure(state="normal")

    def comm_clearWallets(self):
        for w in self.WALLETS:
            self.WALLETS[w].configure(bg="#000000", fg="#ffffff")
        PERM["profiles"][self.profile]["wallets"].clear()
    def comm_clearAssets(self):
        for a in self.ASSETS:
            self.ASSETS[a].configure(bg="#000000", fg="#ffffff")
        PERM["profiles"][self.profile]["assets"].clear()
    def comm_clearClasses(self):
        for c in self.CLASSES:
            self.CLASSES[c].configure(bg="#000000", fg="#ffffff")
        PERM["profiles"][self.profile]["classes"].clear()

    def reset_visuals(self):    #sets color of all buttons everywhere to black
        for prof in self.PROFILES:
            self.PROFILES[prof].configure(bg="#000000", fg="#ffffff")
        for w in self.WALLETS:
            self.WALLETS[w].configure(bg="#000000", fg="#ffffff")
        for a in self.ASSETS:
            self.ASSETS[a].configure(bg="#000000", fg="#ffffff")
        for c in self.CLASSES:
            self.CLASSES[c].configure(bg="#000000", fg="#ffffff")

    def comm_selectProfile(self, prof):
        if prof == self.profile:    #deselecting a profile
            self.profile = ""
            self.reset_visuals()
            self.PROFILES[prof].configure(bg="#000000", fg="#ffffff")   #set color to black and text to white
            self.disable_all()
        elif prof != self.profile and self.profile != "":            #selecting another profile while one is already active
            self.profile = prof
            self.reset_visuals()
            self.PROFILES[prof].configure(bg="#ffffff", fg="#000000")   #set color to white and text to black
            self.setup()
        else:                       #selecting a profile when none are selected
            self.profile = prof
            self.PROFILES[prof].configure(bg="#ffffff", fg="#000000")   #set color to white and text to black
            self.setup()
            self.enable_all()

    def comm_selectWallet(self, w):
        if PERM["profiles"][self.profile]["wallets"].count(w) == 1:   #if selected wallet is in the current profile...
            PERM["profiles"][self.profile]["wallets"].pop(PERM["profiles"][self.profile]["wallets"].index(w))        #remove it
            self.WALLETS[w].configure(bg="#000000", fg="#ffffff")
        else:                                               #if not...
            PERM["profiles"][self.profile]["wallets"].append(w)     #add it
            self.WALLETS[w].configure(bg="#ffffff", fg="#000000")
    def comm_selectAsset(self, a):
        if PERM["profiles"][self.profile]["assets"].count(a) == 1:   #if selected asset is in the current profile...
            PERM["profiles"][self.profile]["assets"].pop(PERM["profiles"][self.profile]["assets"].index(a))        #remove it
            self.ASSETS[a].configure(bg="#000000", fg="#ffffff")
        else:                                               #if not...
            PERM["profiles"][self.profile]["assets"].append(a)     #add it
            self.ASSETS[a].configure(bg="#ffffff", fg="#000000")
    def comm_selectClass(self, c):
        if PERM["profiles"][self.profile]["classes"].count(c) == 1:   #if selected asset is in the current profile...
            PERM["profiles"][self.profile]["classes"].pop(PERM["profiles"][self.profile]["classes"].index(c))        #remove it
            self.CLASSES[c].configure(bg="#000000", fg="#ffffff")
        else:                                               #if not...
            PERM["profiles"][self.profile]["classes"].append(c)     #add it
            self.CLASSES[c].configure(bg="#ffffff", fg="#000000")

    def setup(self):
        for w in PERM["profiles"][self.profile]["wallets"]:
            self.WALLETS[w].configure(bg="#ffffff", fg="#000000")
        for a in PERM["profiles"][self.profile]["assets"]:
            self.ASSETS[a].configure(bg="#ffffff", fg="#000000")
        for c in PERM["profiles"][self.profile]["classes"]:
            self.CLASSES[c].configure(bg="#ffffff", fg="#000000")


    def create_profiles(self):        
        #ENTRY CREATION
        #==============================
        def alphaKey(e):        #creates a sorted list of all the current profiles
                return e.lower()
        sortedProfiles = []
        for prof in PERM["profiles"]:
            sortedProfiles.append(prof)
        sortedProfiles.sort(key=alphaKey)

        self.PROFILES = {}
        for slave in self.GUI["profileFrame"].grid_slaves():
            slave.destroy()

        for prof in sortedProfiles:
            if len(str(prof)) > 24:
                self.PROFILES[prof] = tk.Button(self.GUI["profileFrame"], text=prof, bg=palette("entry"), fg="#ffffff", font=settings("font", 0.75), command=p(self.comm_selectProfile, prof))
            else:
                self.PROFILES[prof] = tk.Button(self.GUI["profileFrame"], text=prof, bg=palette("entry"), fg="#ffffff", font=settings("font", 0.75), width=24, command=p(self.comm_selectProfile, prof))
            self.PROFILES[prof].bind("<MouseWheel>", self._mousewheel_profiles)

        #RENDERING
        #==============================
        order = 0
        for entry in self.PROFILES:
            self.PROFILES[entry].grid(column=0, row=order, sticky="EW")
            order += 1
        
        self.refreshProfileScrollbar()

    def create_others(self):
        #ENTRY CREATION
        #==============================
        def alphaKey(e):        #creates a sorted list of all the current profiles
                return e.lower()
        sortedWallets = []
        sortedAssets = []
        sortedClasses = []
        for w in PERM["wallets"]:
            sortedWallets.append(w)
        for a in PERM["assets"]:
            sortedAssets.append(a)
        for c in assetclasslib:
            sortedClasses.append(c)
        sortedWallets.sort(key=alphaKey)
        sortedAssets.sort(key=alphaKey)
        sortedClasses.sort(key=alphaKey)

        self.WALLETS = {}
        self.ASSETS = {}
        self.CLASSES = {}

        for w in sortedWallets:
            if len(str(w)) > 20:
                self.WALLETS[w] = tk.Button(self.GUI["walletFrame"], text=w, bg=palette("entry"), fg="#ffffff", font=settings("font", 0.75), command=p(self.comm_selectWallet, w))
            else:
                self.WALLETS[w] = tk.Button(self.GUI["walletFrame"], text=w, bg=palette("entry"), fg="#ffffff", font=settings("font", 0.75), width=20, command=p(self.comm_selectWallet, w))
            self.WALLETS[w].bind("<MouseWheel>", self._mousewheel_wallets)
        for a in sortedAssets:
            if len(str(a)) > 20:
                self.ASSETS[a] = tk.Button(self.GUI["assetFrame"], text=a.split("z")[0] + " (" + a.split("z")[1] + ")", bg=palette("entry"), fg="#ffffff", font=settings("font", 0.75), command=p(self.comm_selectAsset, a))
            else:
                self.ASSETS[a] = tk.Button(self.GUI["assetFrame"], text=a.split("z")[0] + " (" + a.split("z")[1] + ")", bg=palette("entry"), fg="#ffffff", font=settings("font", 0.75), width=20, command=p(self.comm_selectAsset, a))
            self.ASSETS[a].bind("<MouseWheel>", self._mousewheel_assets)
        for c in sortedClasses:
            if len(str(c)) > 20:
                self.CLASSES[c] = tk.Button(self.GUI["classFrame"], text=assetclasslib[c]["name"], bg=palette("entry"), fg="#ffffff", font=settings("font", 0.75), command=p(self.comm_selectClass, c))
            else:
                self.CLASSES[c] = tk.Button(self.GUI["classFrame"], text=assetclasslib[c]["name"], bg=palette("entry"), fg="#ffffff", font=settings("font", 0.75), width=20, command=p(self.comm_selectClass, c))
            self.CLASSES[c].bind("<MouseWheel>", self._mousewheel_classes)
        #RENDERING
        #==============================
        order = 0
        for w in self.WALLETS:
            self.WALLETS[w].grid(column=0, row=order, sticky="EW")
            order += 1
        order = 0
        for a in self.ASSETS:
            self.ASSETS[a].grid(column=0, row=order, sticky="EW")
            order += 1
        order = 0
        for c in self.CLASSES:
            self.CLASSES[c].grid(column=0, row=order, sticky="EW")
            order += 1

        #The scrollbars thing... but it only has to be done once, so why have a command?
        self.GUI["walletFrame"].update()  
        beeBox = self.GUI["walletFrame"].bbox("ALL")
        self.GUI["walletCanvas"].configure(scrollregion=beeBox, width=beeBox[2])  #0ms!!!!

        self.GUI["assetFrame"].update()  
        beeBox = self.GUI["assetFrame"].bbox("ALL")
        self.GUI["assetCanvas"].configure(scrollregion=beeBox, width=beeBox[2])  #0ms!!!!

        self.GUI["classFrame"].update()  
        beeBox = self.GUI["classFrame"].bbox("ALL")
        self.GUI["classCanvas"].configure(scrollregion=beeBox, width=beeBox[2])  #0ms!!!!




#BINDINGS
#=============================================================
    def _mousewheel_profiles(self, event):
        scrollDir = event.delta/120
        delta = settings("font")[1]*2    #bigger font size means faster scrolling!
        if self.GUI["profileFrame"].winfo_y() > -delta and scrollDir > 0:
            self.GUI["profileCanvas"].yview_moveto(0)
        else:
            self.GUI["profileCanvas"].yview_moveto( (-self.GUI["profileFrame"].winfo_y()-delta*scrollDir) / self.GUI["profileFrame"].winfo_height() )
    def _mousewheel_wallets(self, event):
        scrollDir = event.delta/120
        delta = settings("font")[1]*2    #bigger font size means faster scrolling!
        if self.GUI["walletFrame"].winfo_y() > -delta and scrollDir > 0:
            self.GUI["walletCanvas"].yview_moveto(0)
        else:
            self.GUI["walletCanvas"].yview_moveto( (-self.GUI["walletFrame"].winfo_y()-delta*scrollDir) / self.GUI["walletFrame"].winfo_height() )
    def _mousewheel_assets(self, event):
        scrollDir = event.delta/120
        delta = settings("font")[1]*2    #bigger font size means faster scrolling!
        if self.GUI["assetFrame"].winfo_y() > -delta and scrollDir > 0:
            self.GUI["assetCanvas"].yview_moveto(0)
        else:
            self.GUI["assetCanvas"].yview_moveto( (-self.GUI["assetFrame"].winfo_y()-delta*scrollDir) / self.GUI["assetFrame"].winfo_height() )
    def _mousewheel_classes(self, event):
        scrollDir = event.delta/120
        delta = settings("font")[1]*2    #bigger font size means faster scrolling!
        if self.GUI["classFrame"].winfo_y() > -delta and scrollDir > 0:
            self.GUI["classCanvas"].yview_moveto(0)
        else:
            self.GUI["classCanvas"].yview_moveto( (-self.GUI["classFrame"].winfo_y()-delta*scrollDir) / self.GUI["classFrame"].winfo_height() )
    def _esc(self,event):    #Exit this window
        if self.grab_current() == self: #If any other window is open, then you can't do this
            self.comm_close()

    def refreshProfileScrollbar(self):
        self.GUI["profileFrame"].update()  
        beeBox = self.GUI["profileFrame"].bbox("ALL")
        self.GUI["profileCanvas"].configure(scrollregion=beeBox, width=beeBox[2])  #0ms!!!!


    def comm_close(self):  
        if self.upper.profile not in PERM["profiles"]:    #If we renamed or deleted a profile that's in use, we have to reset this
            self.upper.profile = ""
        hashnew = hash(json.dumps(PERM["profiles"], sort_keys=True))
        if self.hashold != hashnew:
            self.upper.create_PROFILE_MENU()    #Redoes the dropdown filtered list
            self.upper.render_PORTFOLIO()
            self.upper.undo_save()
        self.upper.focus_set()
        self.destroy()  #no extra commands, so that closing the window is functionally identical to cancellation






