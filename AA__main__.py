#In-house
from AAlib import *
from AAmarketData import startMarketDataLoops, marketdatalib
from AAimport import *

from AAassetEditor import AssetEditor
from AAtransEditor import TransEditor
from AAprofileManager import ProfileManager
from AAwalletManager import WalletManager

from AAmessageBox import MessageBox
from AAtooltip import CreateToolTip

#Default Python
import tkinter as tk
from functools import partial as p
from tkinter.filedialog import *
import os
import copy

from threading import Thread



class Portfolio(tk.Tk):
    def __init__(self):
        super().__init__()
        loadSettings()
        initializeIcons()
        self.configure(bg=palette("error")) #you should NOT see this color (except when totally re-rendering all the assets)
        self.protocol("WM_DELETE_WINDOW", self.comm_quit) #makes closing the window identical to hitting cancel
        self.focus_set()              #You can only interact with this window now
        self.title("Portfolio Manager")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self.create_taskbar()
        self.create_GUI()
        self.create_MENU()
        
        self.reject_reorient = False
        self.undoRedo = [0, 0, 0]

        if settings("offlineMode"):
            global marketdatalib
            try:
                print("||INFO|| OFFLINE MODE - NOT USING REAL MARKET DATA")
                marketdatalib = json.load(open("#OfflineMarketData.json", "r"))
                print("||INFO|| Data is from " + marketdatalib["_timestamp"])
            except:
                print("||ERROR|| Failed to load offline market data, data file not found!")
                settingslib["offlineMode"] = False

        if settings("startWithLastSaveDir") and os.path.isfile(settings("lastSaveDir")):
            self.comm_loadPortfolio(True, settings("lastSaveDir"))
        else:
            self.comm_newPortfolio(True, first=True)

        if not settings("offlineMode"):
            startMarketDataLoops(self, settings("offlineMode"))

        #GLOBAL BINDINGS
        #==============================
        self.bind("<MouseWheel>", self._mousewheel)
        self.bind("<Control-MouseWheel>", self._ctrl_mousewheel)
        self.bind("<Control-z>", self._ctrl_z)
        self.bind("<Control-y>", self._ctrl_y)
        self.bind("<Escape>", self._esc)

        self.geometry("%dx%d+%d+%d" % (settings("portWidth")/2, settings("portHeight")/2, self.winfo_x()-self.winfo_rootx(),0))#slaps this window in the upper-left-hand corner of the screen
        self.state('zoomed') #starts the window maximized (not same as fullscreen!)


#TASKBAR, LOADING SAVING MERGING and QUITTING
#=============================================================
    def create_taskbar(self):
        taskbar = tk.Menu(self, tearoff=0)     #The big white bar across the top of the window
        self.configure(menu=taskbar)

        #"File" Tab
        filemenu = tk.Menu(self, tearoff=0)
        taskbar.add_cascade(menu=filemenu, label="File")
        filemenu.add_command(label="New",     command=self.comm_newPortfolio)
        filemenu.add_command(label="Load...",    command=self.comm_loadPortfolio)
        filemenu.add_command(label="Save",    command=self.comm_savePortfolio)
        filemenu.add_command(label="Save As...", command=p(self.comm_savePortfolio, True))
        filemenu.add_command(label="Merge Portfolio", command=self.comm_mergePortfolio)
        importmenu = tk.Menu(self, tearoff=0)
        filemenu.add_cascade(menu=importmenu, label="Import")
        importmenu.add_command(label="Import Coinbase/Coinbase Pro History", command=self.comm_importCoinbase)
        importmenu.add_command(label="Import Gemini/Gemini Earn History", command=self.comm_importGemini)
        importmenu.add_command(label="Import Etherscan History", )#command=self.comm_importEtherscan)
        filemenu.add_separator()
        filemenu.add_command(label="QUIT", command=self.comm_quit)

        #"Settings" Tab
        settingsmenu = tk.Menu(self, tearoff=0)
        taskbar.add_cascade(menu=settingsmenu, label="Settings")
        settingsmenu.add_command(label="Change Orientation", command=self.comm_reorient)

        #"About" Tab
        aboutmenu = tk.Menu(self, tearoff=0)
        taskbar.add_cascade(menu=aboutmenu, label="About")
        aboutmenu.add_command(label="MIT License", command=self.comm_copyright)

        #"DEBUG" Tab
        debugmenu = tk.Menu(self, tearoff=0)
        taskbar.add_cascade(menu=debugmenu, label="DEBUG")
        debugmenu.add_command(label="Export PERM to DEBUG.json",     command=self.DEBUG_print_PERM)
        debugmenu.add_command(label="Export TEMP to DEBUG.json",     command=self.DEBUG_print_TEMP)
        debugmenu.add_command(label="Export Market Data for Offline Mode.json",     command=self.DEBUG_save_marketdatalib)

    def DEBUG_print_PERM(self):
        json.dump(PERM, open("DEBUG.json", "w"), sort_keys=True, indent=4)
    def DEBUG_print_TEMP(self):
        toWrite = str(TEMP).replace('<',"\'").replace('>',"\'").replace('\'',"\"")
        open("DEBUG.json", "w").write(toWrite)
        toDump = json.load(open("DEBUG.json", 'r'))
        json.dump(toDump, open("DEBUG.json", "w"), sort_keys=True, indent=4)
    def DEBUG_save_marketdatalib(self):
        json.dump(marketdatalib, open("#OfflineMarketData.json", "w"), indent=4, sort_keys=True)

    def comm_importCoinbase(self):
        dir = askopenfilename( filetypes={("CSV",".csv")}, title="Import Coinbase/Coinbase Pro History")
        if dir == "":
            return
        #This determines whether or not the file is a coinbase or coinbase pro file
        if open(dir, "r").readlines()[0][0:9] == "portfolio":
            import_coinbase_pro(self, dir) 
        else:   
            import_coinbase(self, dir)
    def comm_importGemini(self):
        dir = askopenfilename( filetypes={("XLSX",".xlsx")}, title="Import Gemini/Gemini Earn History")
        if dir == "":
            return
        import_gemini(self, dir)

    def comm_savePortfolio(self, saveAs=False, secondary=None):
        if saveAs or self.savedir == "":
            dir = asksaveasfilename( defaultextension=".JSON", filetypes={("JSON",".json")}, title="Save Portfolio")
            self.title("Portfolio Manager - " + dir)
        else:
            dir = self.savedir
        if dir == "":
            return
        
        json.dump(PERM, open(dir, 'w'), sort_keys=True, indent=4)
        if secondary != None:
            secondary()
        if saveAs:
            self.savedir = dir
    def comm_newPortfolio(self, finalize=False, first=False):
        self.savedir = ""
        self.init_PERM()
        self.title("Portfolio Manager")
        self.profile = ""   #name of the currently selected profile. Always starts with no filter applied.
        self.create_PORTFOLIO_WIDGETS()
        self.create_metrics()
        self.create_PROFILE_MENU()
        if not first:
            self.undo_save()
    def comm_loadPortfolio(self, finalize=False, holdDir=""):
        if holdDir == "":  
            dir = askopenfilename( filetypes={("JSON",".json")}, title="Load Portfolio")
        else:
            dir = holdDir #holdDir only used for loading the last file opened with this program on startup
        if dir == "":
            return
        try:
            decompile = json.load(open(dir, 'r'))    #Attempts to load the file
            try:
                decompile["assets"] #pulls these data libraries to ensure that this contains the required data
                decompile["wallets"]
                decompile["profiles"]
                self.init_PERM(decompile)
            except:
                MessageBox(self, "Error!", "\""+dir.split("/").pop()+"\" is missing data." )
                return
        except:
            MessageBox(self, "Error!", "\"file\" is an unparseable JSON file. Probably missing commas or brackets." )
            return
        self.title("Portfolio Manager - " + dir)
        self.savedir = dir
        self.profile = ""   #name of the currently selected profile. Always starts with no filter applied.
        self.create_PORTFOLIO_WIDGETS()
        self.create_metrics()
        self.create_PROFILE_MENU()         
        self.undo_save()  
    def comm_mergePortfolio(self, finalize=False):
        dir = askopenfilename( filetypes={("JSON",".json")}, title="Load Portfolio for Merging")
        if dir == "":
            return
        try:
            decompile = json.load(open(dir, 'r'))    #Attempts to load the file
            try:
                decompile["assets"] #pulls these data libraries to ensure that this contains the required data
                decompile["wallets"]
                decompile["profiles"]
                self.init_PERM(decompile, True)
            except:
                MessageBox(self, "Error!", "\"file\" is missing data." )
                return
        except:
            MessageBox(self, "Error!", "\"file\" is an unparseable JSON file. Probably missing commas or brackets." )
            return
        self.savedir = "" #resets the savedir. who's to say where a merged portfolio should save to? why should it be the originally loaded file, versus any recently merged ones?
        self.title("Portfolio Manager")
        self.profile = ""   #name of the currently selected profile. Always starts with no filter applied.
        self.create_PORTFOLIO_WIDGETS()
        self.create_metrics()
        self.create_PROFILE_MENU()
        self.undo_save()

    def comm_quit(self, finalize=False):
        """Quits the program. Set finalize to TRUE to skip the \'are you sure?' prompt."""
        if not finalize:   
            if self.isUnsaved():
                MessageBox(self, "Unsaved Changes", "Are you sure you want to quit? This cannot be undone!", defQuitName="Cancel", options=["Quit", "Save and Quit"], 
                commands=[p(self.comm_quit, True), p(self.comm_savePortfolio, secondary=p(self.comm_quit, True))], colors=["#ff0000", "#0088ff"])
            else:
                self.comm_quit(True)
        else:
            #also, closing the program always saves the settings!
            settings("lastSaveDir", set=self.savedir)
            saveSettings()
            exit(1)

    def comm_reorient(self):
        if not self.reject_reorient:
            if settings("orientation") == "rows":
                settings("orientation", set="columns")
            else:
                settings("orientation", set="rows")
            self.reject_reorient = True
            self.render_PORTFOLIO()
            self.reject_reorient = False

    def init_PERM(self, toLoad=None, merge=False):
        if not merge:
            PERM.clear()
            PERM.update({
            "assets" : {},
            "wallets" : {},
            "profiles" : {}
            })
        if toLoad != None:
            if not merge:     #loading profile
                PERM.update(toLoad)
            else:               #merging profiles
                #Merges assets and transactions. If transactions are of the same ID, the old portfolio is overwritten
                for asset in list(toLoad["assets"]):
                    if asset not in PERM["assets"]:
                        PERM["assets"][asset] = toLoad["assets"][asset]
                    else:
                        PERM["assets"][asset]["trans"].update( toLoad["assets"][asset]["trans"] )
                PERM["wallets"].update(toLoad["wallets"])
                PERM["profiles"].update(toLoad["profiles"])

    def isUnsaved(self):
        if {} == PERM["wallets"] == PERM["profiles"] == PERM["assets"]: #there is nothing to save, so nothing is unsaved     
            return False
        elif self.savedir == "": 
            return True     #If you haven't loaded or saved anything yet, then yes, its 100% unsaved
        elif not os.path.isfile(self.savedir):
            return True     #Only happens if you deleted the file that the program was referencing, while using the program
        lastSaveHash = hash(json.dumps(json.load(open(self.savedir, 'r')))) #hash for last loaded file
        currentDataHash = hash(json.dumps(PERM, sort_keys=True))
        if currentDataHash == lastSaveHash:
            return False    #The hashes are different, so you have 
        return True


#OVERARCHING GUI
#=============================================================
    def create_GUI(self):
        #GUI CREATION
        #==============================
        self.GUI = {}

        #contains the menu
        self.GUI["menuFrame"] = tk.Frame(self, bg=palette("dark"))
        
        #The little bar on the bottom
        self.GUI["bottomFrame"] = tk.Frame(self, bg=palette("accent"))
        self.GUI["bottomLabel"] = tk.Button(self.GUI["bottomFrame"], bd=0, bg=palette("accent"), text="Copyright © 2021 Shane Evanson", fg=palette("entrycursor"), font=settings("font",0.4), command=self.comm_copyright)

        #Necessary hierarchy for making the Asset a scrollable region
        self.GUI["assetCanvas"] = tk.Canvas(self, bg=palette("light"), highlightthickness=0)
        self.GUI["assetFrame"] = tk.Frame(self.GUI["assetCanvas"], bg=palette("light"))
        
        self.GUI["scroll_v"] = tk.Scrollbar(self, orient="vertical", troughcolor=palette("error"), command=self.GUI["assetCanvas"].yview)
        self.GUI["scroll_h"] = tk.Scrollbar(self, orient="horizontal", command=self.GUI["assetCanvas"].xview)
        self.GUI["scroll_notch"] = tk.Frame(self, bg=palette("scrollnotch"), bd=0)

        self.GUI["assetCanvas"].configure(xscrollcommand=self.GUI["scroll_h"].set, yscrollcommand=self.GUI["scroll_v"].set)
        self.GUI["assetCanvas"].create_window(0, 0, window=self.GUI["assetFrame"], anchor=tk.NW)

        #BINDINGS
        #==============================
        self.GUI["scroll_h"].bind("<MouseWheel>", self._ctrl_mousewheel)


        #GUI RENDERING
        #==============================
        self.GUI["menuFrame"]       .grid(column=0,row=0, columnspan=2, sticky="EW")
        self.GUI["bottomFrame"]     .grid(column=0,row=3, columnspan=2, sticky="EW")
        self.GUI["bottomLabel"]     .pack(side="left")
        self.GUI["scroll_v"]        .grid(column=1,row=1, sticky="NS")
        self.GUI["scroll_h"]        .grid(column=0,row=2, sticky="EW")
        self.GUI["scroll_notch"]    .grid(column=1,row=2, sticky="NSEW")

    def create_MENU(self):
        #MENU CREATION
        #==============================
        self.MENU = {}

        self.MENU["newPortfolio"] = tk.Button(self.GUI["menuFrame"],  image=icons("new"), bg=palette("entry"), command=self.comm_newPortfolio)
        self.MENU["loadPortfolio"] = tk.Button(self.GUI["menuFrame"], image=icons("load"), bg=palette("entry"), command=self.comm_loadPortfolio)
        self.MENU["savePortfolio"] = tk.Button(self.GUI["menuFrame"], image=icons("save"), bg=palette("entry"), command=self.comm_savePortfolio)
        self.MENU["settings"] = tk.Button(self.GUI["menuFrame"], image=icons("settings2"), bg=palette("entry"), command=p(MessageBox, self, "whoop",  "no settings menu implemented yet!"))

        self.MENU["undo"] = tk.Button(self.GUI["menuFrame"], image=icons("undo"), bg=palette("entry"), command=p(self._ctrl_z, None))
        self.MENU["redo"] = tk.Button(self.GUI["menuFrame"], image=icons("redo"), bg=palette("entry"), command=p(self._ctrl_y, None))

        self.MENU["info"] = tk.Button(self.GUI["menuFrame"], image=icons("info2"), bg=palette("entry"), command=self.comm_portfolio_info)
        self.MENU["newAsset"] = tk.Button(self.GUI["menuFrame"], text="+ Asset",  bg=palette("entry"), fg=palette("entrycursor"), font=settings("font"), command=p(AssetEditor, self, 1))
        self.MENU["wallets"] = tk.Button(self.GUI["menuFrame"], text="Wallets",  bg=palette("entry"), fg=palette("entrycursor"), font=settings("font"), command=p(WalletManager, self))
    
        self.MENU["profiles"] = tk.Button(self.GUI["menuFrame"], image=icons("profiles"),  bg=palette("entry"), fg=palette("entrycursor"), font=settings("font"),command=p(ProfileManager, self))
        
        #MENU TOOLTIPS
        #==============================
        tooltips = {
            "newPortfolio":"Create a new portfolio",
            "loadPortfolio":"Load an existing portfolio",
            "savePortfolio":"Save this portfolio",
            "settings":"Settings",

            "undo":"Undo last action",
            "redo":"Redo last action",

            "info":"Show metrics info and stats about the whole portfolio",
            "newAsset":"Create a new asset",
            "wallets":"Manage wallets",
            "profiles":"Manage filter profiles",
        }
        for button in self.MENU:
            CreateToolTip(self.MENU[button] ,tooltips[button])

        #MENU RENDERING
        #==============================
        self.MENU["newPortfolio"]       .grid(column=0,row=0, sticky="NS")
        self.MENU["loadPortfolio"]      .grid(column=1,row=0, sticky="NS")
        self.MENU["savePortfolio"]      .grid(column=2,row=0, sticky="NS")
        self.MENU["settings"]           .grid(column=3,row=0, sticky="NS", padx=(0,settings("font")[1]))

        self.MENU["undo"]               .grid(column=4,row=0, sticky="NS")
        self.MENU["redo"]               .grid(column=5,row=0, sticky="NS", padx=(0,settings("font")[1]))

        self.MENU["info"]               .grid(column=6,row=0, sticky="NS")
        self.MENU["newAsset"]           .grid(column=7,row=0, sticky="NS")
        self.MENU["wallets"]            .grid(column=8,row=0, sticky="NS", padx=(0,settings("font")[1]))

        #NOTE: the profile selection menu is in column #9
        self.MENU["profiles"]           .grid(column=10,row=0, sticky="NS")

    def create_PROFILE_MENU(self):
        def alphaKey(e):        #creates a sorted list of all the current profiles
                return e.lower()
        profilesList = []
        for prof in PERM["profiles"]:
            profilesList.append(prof)
        profilesList.sort(key=alphaKey)
        profilesList.insert(0, "-NO FILTER-")

        if "profileSelect" in self.MENU:
            self.MENU["profileSelect"].destroy()

        if self.profile == "":
            self.MENU["profileSelectValue"] = tk.StringVar(self, profilesList[0])
        else:
            self.MENU["profileSelectValue"] = tk.StringVar(self, profilesList[profilesList.index(self.profile)])

        self.MENU["profileSelect"] = tk.OptionMenu(self.GUI["menuFrame"], self.MENU["profileSelectValue"], *profilesList, command=self.comm_applyFilter)
        self.MENU["profileSelect"].configure(bg=palette("entry"), fg=palette("entrycursor"), font=settings("font"), highlightthickness=0)

        
        self.MENU["profileSelect"]      .grid(column=9,row=0, sticky="NS")

    def comm_applyFilter(self, *kwargs):
        if kwargs[0] == "-NO FILTER-":
            self.profile = ""
            self.render_PORTFOLIO()
            self.create_metrics()
        else:
            self.profile = kwargs[0]
            self.render_PORTFOLIO()
            self.create_metrics()

    def comm_portfolio_info(self):
        
        #List of wallets that are both in-use and whitelisted
        walletString = "Wallets: "
        for wallet in TEMP["metrics"][" PORTFOLIO"]["filtered"]["wallets"]:
                walletString += str(wallet) + ", "
        displayInfo = walletString[:-2]

        #Total portfolio value
        displayInfo += "\nPortfolio Value: "
        try: displayInfo += format_number(TEMP["metrics"][" PORTFOLIO"]["filtered"]["value"]) + " USD"
        except: displayInfo += "MISSINGDATA"

        #24hr Change
        displayInfo += "\n24-Hour Change: "
        try: displayInfo += format_number(TEMP["metrics"][" PORTFOLIO"]["filtered"]["day_change"], ".2f")
        except: displayInfo += "MISSINGDATA"

        #24hr % Change
        displayInfo += "\n24-Hour % Change: "
        try: displayInfo += format_number(TEMP["metrics"][" PORTFOLIO"]["day%"], ".4f") + "%"
        except: displayInfo += "MISSINGDATA"

        #Week % Change
        displayInfo += "\nWeek % Change: "
        try: displayInfo += format_number(TEMP["metrics"][" PORTFOLIO"]["week%"], ".4f") + "%"
        except: displayInfo += "MISSINGDATA"
        
        #Month % Change
        displayInfo += "\nMonth % Change: "
        try: displayInfo += format_number(TEMP["metrics"][" PORTFOLIO"]["month%"], ".4f") + "%"
        except: displayInfo += "MISSINGDATA"
        
        MessageBox(self, "Overall Stats and Information", displayInfo, width=100, height=25)
    
    
#LABELS FRAMES BUTTONS AND OTHER TKINTER OBJECTS
#=============================================================
    def create_PORTFOLIO_WIDGETS(self):
        """Initializes tkinter widgets for all assets and transactions"""

        for slave in self.GUI["assetFrame"].grid_slaves(): #~150 milliseconds for 585 transactions. Not great, not terrible
            slave.destroy()

        #The assets, their add transactin buttons, and the frame which contains all the transactions
        for a in PERM["assets"]: 
            self.create_ASSET_WIDGETS(a)      #20 milliseconds

        for a in PERM["assets"]:  
            for t in PERM["assets"][a]["trans"]:
                self.create_TRANS_WIDGET(a,t)  #75-85 milliseconds for 585 transactions... linear extrapolation is still only 1.333 seconds for as much as 10,000 transactions. FAR beyond what should be here anyways.

        self.render_PORTFOLIO() #10-20ms

    def create_ASSET_WIDGETS(self, a):
        """Initializes tkinter widgets for asset a"""
        TEMP["widgets"][a] = {
            "assetFrame":    tk.Frame(self.GUI["assetFrame"], bg=palette("accentdark")),
            "transFrame":    tk.Frame(self.GUI["assetFrame"], bg=palette("light")),
            "trans":         {},
        }
        TEMP["widgets"][a] 
        TEMP["widgets"][a].update({
            "settings":      tk.Button(TEMP["widgets"][a]["assetFrame"], image=icons("settings"), bg=palette("accentdark"), command = p(AssetEditor, self, a)),
            "info":          tk.Button(TEMP["widgets"][a]["assetFrame"], image=icons("info"), bg=palette("accentdark"), command = p(self.comm_asset_info, a)),
            "name":          tk.Label(TEMP["widgets"][a]["assetFrame"], font=settings("font"), bg=palette("accentdark"), fg=palette("entrytext")),
            "newTrans":      tk.Button(TEMP["widgets"][a]["assetFrame"], text="+", font=settings("font"), bg=palette("accentdark"), fg=palette("entrytext"), command = p(TransEditor, self, a, 1)),

            "longName":      tk.Label(TEMP["widgets"][a]["assetFrame"], text=PERM["assets"][a]["name"], font=settings("font", 0.75), bg=palette("accent"), fg=palette("entrytext")),
            "tokens":        tk.Label(TEMP["widgets"][a]["assetFrame"], font=settings("font", 0.75), bg=palette("accent"), fg=palette("entrycursor")),
        })
        #ASSET TOOLTIPS
        #==============================
        tooltips = {
            "settings":"Modify " + a.split("z")[0], 
            "info":"Show metrics info and stats about " + a.split("z")[0],
            "newTrans":"Add a transaction to " + a.split("z")[0],
        }
        for tip in tooltips:
            CreateToolTip(TEMP["widgets"][a][tip] ,tooltips[tip])

    def create_TRANS_WIDGET(self, a, t):
        TEMP["widgets"][a]["trans"][t] = tk.Button(TEMP["widgets"][a]["transFrame"], bd=3, justify="left", text=self.transName(t, PERM["assets"][a]["trans"][t]), bg=palette(PERM["assets"][a]["trans"][t]["type"]), font=settings("font", 0.75), command=p(TransEditor, self, a, t))


#RENDERING SAID TKINTER OBJECTS
#=============================================================
    def render_PORTFOLIO(self):     #10-20ms to render 600 transactions. Very nice! Performance exceeds necessity (unless you become a frivolent day trader, perhaps)
        """Calling this will re-render all assets, and all transactions"""
        sortedAssets = self.assets_sorted_filtered()   #2-3 milliseconds
        
        self.GUI["assetCanvas"].grid_forget()
        for slave in self.GUI["assetFrame"].grid_slaves():   #5-6 milliseconds
            slave.grid_forget()

        for a in sortedAssets:             #5-6 milliseconds
            self.render_ASSET(a)
        
        order = 0
        if settings("orientation") == "rows":               #2-3 milliseconds
            for a in sortedAssets:
                TEMP["widgets"][a]["assetFrame"].grid(column=0,row=order, sticky="NSEW")
                TEMP["widgets"][a]["assetFrame"].configure(padx=0)
                TEMP["widgets"][a]["transFrame"].grid(column=1,row=order, sticky="NSW")
                TEMP["widgets"][a]["transFrame"].grid_rowconfigure(0, weight=1)
                order += 1
        else:
            for a in sortedAssets:
                TEMP["widgets"][a]["assetFrame"].grid(column=order,row=0, sticky="NSEW")
                TEMP["widgets"][a]["assetFrame"].configure(padx=5)
                TEMP["widgets"][a]["transFrame"].grid(column=order,row=1, sticky="NSEW")
                TEMP["widgets"][a]["transFrame"].grid_rowconfigure(0, weight=0)
                TEMP["widgets"][a]["transFrame"].grid_columnconfigure(0, weight=1)
                order += 1
                
        self.GUI["assetCanvas"]    .grid(column=0,row=1, sticky="NSEW")    #0 ms

        self.create_metrics()
        #Thread(target=).start()

        self.refreshScrollbars()    #500+ milliseconds... ugh... so damn slow...
        
    def render_ASSET(self,a):
        """Calling this will re-render all transactions for a asset \'a\'"""
        sortedTrans = self.trans_sorted_filtered(a)  #0-2 milliseconds

        for slave in TEMP["widgets"][a]["transFrame"].grid_slaves():
            slave.grid_forget()

        order = 0
        if settings("orientation") == "rows":       #3-4 milliseconds
            for t in sortedTrans:
                TEMP["widgets"][a]["trans"][t].grid(column=order,row=0, sticky="NSEW")
                order += 1
        else:
            for t in sortedTrans:
                TEMP["widgets"][a]["trans"][t].grid(column=0,row=order, sticky="NSEW")     
                order += 1

        TEMP["widgets"][a]["assetFrame"].grid_rowconfigure(1, weight=1)        #0 ms!!!
        TEMP["widgets"][a]["assetFrame"].grid_columnconfigure(2, weight=1)

        TEMP["widgets"][a]["settings"].grid(   column=0, row=0, sticky="NS")           #2 milliseconds
        TEMP["widgets"][a]["info"].grid(       column=1, row=0, sticky="NSW")
        TEMP["widgets"][a]["name"].grid(       column=2, row=0, sticky="W")
        TEMP["widgets"][a]["newTrans"].grid(   column=3, row=0, sticky="NS")

        TEMP["widgets"][a]["longName"].grid(   column=0, row=1, sticky="NSEW", columnspan=4)
        TEMP["widgets"][a]["tokens"].grid(     column=0, row=2, sticky="NSEW", columnspan=4)


    def reconfig_ASSET(self,a):
        """Calling this will reload the configuration for asset \'a\'"""
        TEMP["widgets"][a]["longName"].configure(text=PERM["assets"][a]["name"])
        #HOLDINGS
        metricsString = format_number(TEMP["metrics"][a]["holdings"]) + " " + a.split("z")[0]

        #PRICE
        try: metricsString += "\nPrice: " + format_number(marketdatalib[a]["price"]) + " USD/" +  a.split("z")[0]  
        except: metricsString += "\nPrice: NODATA" 

        #VALUE
        try: metricsString += "\nValue: " + format_number(TEMP["metrics"][a]["filtered"]["value"]) + " USD"   
        except: metricsString += "\nValue: NODATA" 

        TEMP["widgets"][a]["tokens"].configure(text=metricsString)
    def reconfig_TRANS(self,a,t):
        """Calling this will reload the configuration for transaction \'t\' on asset \'a\'"""
        TEMP["widgets"][a]["trans"][t].configure(text=self.transName(t, PERM["assets"][a]["trans"][t]), bg=palette(PERM["assets"][a]["trans"][t]["type"])) #set the button's command and name
    def transName(self, t, data):
        string = ""
        #date & time (but we cut off the time)
        if data["type"] == "stake":
            string += "Continuous"
        else:
            string += t[0:10]

        #wallets
        if data["type"] == "transfer":
            string += "\nFrom: " + data["wallet"] +"\nTo: " + data["wallet2"]
        else:
            string += "\n" + data["wallet"]

        #tokens
        string += "\n" + format_number(data["tokens"])
        
        #USD
        if data["type"] == "purchase" or data["type"] == "sale":
            string += "\n" + format_number(data["usd"])

        #Price
        if data["type"] == "purchase" or data["type"] == "sale":
            string += "\n" + format_number( float(data["usd"]) / float(data["tokens"]) )
        elif data["type"] == "gift" or data["type"] == "expense":
            string += "\n" + format_number(data["price"])

        return string

    def comm_asset_info(self, a):
        #ASSET CLASS
        displayInfo = "Asset Class: " + assetclasslib[a.split("z")[1]]["name"]

        #WALLETS and their HOLDINGS
        walletsTokensString = ""
        for w in self.whitelisted_wallets():
            if w in TEMP["metrics"][a]["wallets"]:
                walletsTokensString +=  ", " + w + ":" + format_number(TEMP["metrics"][a]["wallets"][w])
        displayInfo += "\nWallets: " + walletsTokensString[2:]

        #TOTAL HOLDINGS
        displayInfo += "\nTotal Tokens: " + format_number(TEMP["metrics"][a]["filtered"]["holdings"])

        #CURRENT PRICE
        displayInfo += "\nPrice: "
        try: displayInfo += format_number(marketdatalib[a]["price"])
        except: displayInfo += "MISSINGDATA"

        #CURRENT TOTAL VALUE
        displayInfo += "\nValue: "
        try: displayInfo += format_number(TEMP["metrics"][a]["filtered"]["value"], ".2f")
        except: displayInfo += "MISSINGDATA"

        #MARKET CAP
        displayInfo += "\nMarket Cap: "
        try: displayInfo += format_number(marketdatalib[a]["marketCap"], ".2f")
        except: displayInfo += "MISSINGDATA"

        #24hr Volume
        displayInfo += "\n24-Hour Volume: "
        try: displayInfo += format_number(marketdatalib[a]["volume24h"], ".2f")
        except: displayInfo += "MISSINGDATA"

        #24hr Change
        displayInfo += "\n24-Hour Change: "
        try: displayInfo += format_number(TEMP["metrics"][a]["filtered"]["day_change"], ".2f")
        except: displayInfo += "MISSINGDATA"

        #24hr % Change
        displayInfo += "\n24-Hour % Change: "
        try: displayInfo += format_number(marketdatalib[a]["day%"], ".4f") + "%"
        except: displayInfo += "MISSINGDATA"

        #Week % Change
        displayInfo += "\nWeek % Change: "
        try: displayInfo += format_number(marketdatalib[a]["week%"], ".4f") + "%"
        except: displayInfo += "MISSINGDATA"

        #Month % Change
        displayInfo += "\nMonth % Change: "
        try: displayInfo += format_number(marketdatalib[a]["month%"], ".4f") + "%"
        except: displayInfo += "MISSINGDATA"

        #Portfolio Makeup
        displayInfo += "\nPortfolio Weight: "
        try: displayInfo += format_number(float(TEMP["metrics"][a]["filtered"]["portfolio%"])*100, ".4f") + "%"
        except: displayInfo += "MISSINGDATA"

        MessageBox(self, a.split("z")[0] + " Stats and Information", displayInfo, width=100, height=25)


#METRICS
#=============================================================
    def create_metrics(self):
        """Calculates and renders all metrics for all assets, and the overall portfolio"""
        TEMP["metrics"].clear()
        for a in PERM["assets"]:
            self.metrics_ASSET(a, False)
        self.metrics_PORTFOLIO()

    def metrics_PORTFOLIO(self):
        """Calculates all metrics for the overall portfolio"""
        #ABSOLUTE AND FILTERED TOTALS
        #================================
        TEMP["metrics"][" PORTFOLIO"] = {
            "wallets" : set(),
            "value" : 0,
            "day_change":0,
            "week_change":0,
            "month_change":0,
            "day%":"MISSINGDATA",
            "week%":"MISSINGDATA",
            "month%":"MISSINGDATA",
            #filtered values
            "filtered":{
                "wallets" : set(),
                "value" : 0,
                "day_change":0,
                "week_change":0,
                "month_change":0,
            }
        }
     
        for a in PERM["assets"]:
            #Compiles complete list of all wallets used in the portfolio
            TEMP["metrics"][" PORTFOLIO"]["wallets"].update(set(TEMP["metrics"][a]["wallets"]))
            #Adds the total value of this asset to the total portfolio value (if price data cannot be found, asset is assumed to be worthless)
            try: TEMP["metrics"][" PORTFOLIO"]["value"] += TEMP["metrics"][a]["holdings"] * marketdatalib[a]["price"]
            except: pass

            #Compiles complete list of all wallets used in the filtered portfolio
            TEMP["metrics"][" PORTFOLIO"]["filtered"]["wallets"].update(   set.intersection( set(TEMP["metrics"][a]["wallets"]) , set(self.whitelisted_wallets()) )   )
            #Adds the value of this asset to the filtered total portfolio value (if price data can be found, if not, asset is assumed to be worthless)
            try: TEMP["metrics"][" PORTFOLIO"]["filtered"]["value"] += TEMP["metrics"][a]["holdings"] * marketdatalib[a]["price"]
            except: pass

        #Has to be a separate loop so that the total portfolio value is actually the total
        for a in PERM["assets"]:
            try:
                self.calculate_portfolio_percentage(a)
                TEMP["metrics"][" PORTFOLIO"]["day_change"] += TEMP["metrics"][a]["day_change"]
                TEMP["metrics"][" PORTFOLIO"]["filtered"]["day_change"] += TEMP["metrics"][a]["filtered"]["day_change"]
                TEMP["metrics"][" PORTFOLIO"]["week_change"] += TEMP["metrics"][a]["week_change"]
                TEMP["metrics"][" PORTFOLIO"]["filtered"]["week_change"] += TEMP["metrics"][a]["filtered"]["week_change"]
                TEMP["metrics"][" PORTFOLIO"]["month_change"] += TEMP["metrics"][a]["month_change"]
                TEMP["metrics"][" PORTFOLIO"]["filtered"]["month_change"] += TEMP["metrics"][a]["filtered"]["month_change"]
            except: pass

        #Calculates the 24-hour % performance of the portfolio
        try:
            TEMP["metrics"][" PORTFOLIO"]["day%"] = (TEMP["metrics"][" PORTFOLIO"]["day_change"] / (TEMP["metrics"][" PORTFOLIO"]["value"] - TEMP["metrics"][" PORTFOLIO"]["day_change"])) * 100
            TEMP["metrics"][" PORTFOLIO"]["week%"] = (TEMP["metrics"][" PORTFOLIO"]["week_change"] / (TEMP["metrics"][" PORTFOLIO"]["value"] - TEMP["metrics"][" PORTFOLIO"]["week_change"])) * 100
            TEMP["metrics"][" PORTFOLIO"]["month%"] = (TEMP["metrics"][" PORTFOLIO"]["month_change"] / (TEMP["metrics"][" PORTFOLIO"]["value"] - TEMP["metrics"][" PORTFOLIO"]["month_change"])) * 100
        except: pass

    def metrics_ASSET(self,a, updatePortfolio=True):
        """Calculates all metrics for asset \'a\'
        \n By default, this will also update the overall portfolio metrics"""
        TEMP["metrics"][a] = {
                "wallets": {},
                "holdings" : 0,
                "value" : 0,
                "portfolio%":"MISSINGDATA",
                "day_change":"MISSINGDATA",
                "week_change":"MISSINGDATA",
                "month_change":"MISSINGDATA",
                #Filtered values
                "filtered":{
                    "wallets": {},
                    "holdings" : 0,
                    "value" : 0,
                    "portfolio%":"MISSINGDATA",
                    "day_change":"MISSINGDATA",
                    "week_change":"MISSINGDATA",
                    "month_change":"MISSINGDATA",
                }
            }
        self.calculate_holdings(a)
        self.calculate_value(a)
        self.calculate_changes(a)
        #self.calculate_realized_profit(a)
        #self.calculate_unrealized_profit(a)
        #self.calculate_unrealized_cash_flow(a)

        #Resets the displayed metrics for asset 'a'
        self.reconfig_ASSET(a)

        if updatePortfolio:
            self.metrics_PORTFOLIO()
            

    def calculate_holdings(self, a):    #Makes list of all wallets related to this asset, and their holdings, and calculates the overall holdings
        """Creates dictionary of all wallets and their respective holdings for asset \'a\', as well as the total holdings for asset a"""
        holdings = TEMP["metrics"][a]["wallets"]

        for t in PERM["assets"][a]["trans"]:
            currentTrans = PERM["assets"][a]["trans"][t]
            transWallet = currentTrans["wallet"]
            tokens = float(currentTrans["tokens"])   #tokens are stored as strings, remember? And that's necessary!
            delta = 0
            #PURCHASES, GIFTS, and STAKING
            if currentTrans["type"] == "purchase" or currentTrans["type"] == "gift" or currentTrans["type"] == "stake":
                delta = tokens
            #SALES AND EXPENSES
            elif currentTrans["type"] == "sale" or currentTrans["type"] == "expense":
                delta = -tokens
            #TRANSFERS
            elif currentTrans["type"] == "transfer":
                transWallet2 = currentTrans["wallet2"]
                delta = -tokens
                if transWallet2 in holdings: holdings[transWallet2] += tokens
                else: holdings[transWallet2] = tokens

            #Finalizes the transactions effects
            if transWallet in holdings: holdings[transWallet] += delta
            else: holdings[transWallet] = delta

        #Total holdings and filtered holdings for this asset
        for w in holdings:
            TEMP["metrics"][a]["holdings"] += holdings[w]
        for w in set.intersection(set(self.whitelisted_wallets()),set(holdings)):
            TEMP["metrics"][a]["filtered"]["holdings"] += holdings[w]     
    def calculate_value(self, a):   #Calculates the overall value of this asset, filtered and unfiltered
        """Using total holdings metrics and the price from marketdatalib, this calculates asset a\'s total value in the portfolio"""
        try:
            TEMP["metrics"][a]["value"] = TEMP["metrics"][a]["holdings"] * marketdatalib[a]["price"]
            TEMP["metrics"][a]["filtered"]["value"] = TEMP["metrics"][a]["filtered"]["holdings"] * marketdatalib[a]["price"]
        except:
            TEMP["metrics"][a]["value"] = "MISSINGDATA"
            TEMP["metrics"][a]["filtered"]["value"] = "MISSINGDATA"
    def calculate_changes(self, a): #Calculates the value lost or gained in the last 24 hours, week, and month for this asset, filtered and unfiltered
        value = TEMP["metrics"][a]["value"]
        filtered_value = TEMP["metrics"][a]["filtered"]["value"]
        try:
            TEMP["metrics"][a]["day_change"] = value-(value / (1 + (marketdatalib[a]["day%"]/100)))
            TEMP["metrics"][a]["filtered"]["day_change"] = filtered_value-(filtered_value / (1 + (marketdatalib[a]["day%"]/100)))

            TEMP["metrics"][a]["week_change"] = value-(value / (1 + (marketdatalib[a]["week%"]/100)))
            TEMP["metrics"][a]["filtered"]["week_change"] = filtered_value-(filtered_value / (1 + (marketdatalib[a]["week%"]/100)))

            TEMP["metrics"][a]["month_change"] = value-(value / (1 + (marketdatalib[a]["month%"]/100)))
            TEMP["metrics"][a]["filtered"]["month_change"] = filtered_value-(filtered_value / (1 + (marketdatalib[a]["month%"]/100)))
        except: pass

    def calculate_portfolio_percentage(self, a): #Calculates how much of the value of your portfolio is this asset, filtered and unfiltered
        try:
            TEMP["metrics"][a]["portfolio%"] = TEMP["metrics"][a]["value"] / TEMP["metrics"][" PORTFOLIO"]["value"]
            TEMP["metrics"][a]["filtered"]["portfolio%"] = TEMP["metrics"][a]["filtered"]["value"] / TEMP["metrics"][" PORTFOLIO"]["filtered"]["value"]
        except: pass

#BINDINGS
#=============================================================
    def _mousewheel(self, event):   #Scroll up and down the assets pane
        if self.grab_current() == None: #If any other window is open, then you can't do this
            scrollDir = event.delta/120
            delta = settings("font")[1]*4    #bigger font size means faster scrolling!
            if self.GUI["assetFrame"].winfo_y() > -delta and scrollDir > 0:
                self.GUI["assetCanvas"].yview_moveto(0)
            else:
                self.GUI["assetCanvas"].yview_moveto( (-self.GUI["assetFrame"].winfo_y()-delta*scrollDir) / self.GUI["assetFrame"].winfo_height() )
    def _ctrl_mousewheel(self, event):  #Scroll left and right across the assets pane
        if self.grab_current() == None: #If any other window is open, then you can't do this
            scrollDir = event.delta/120
            delta = settings("font")[1]*8    #bigger font size means faster scrolling!
            if self.GUI["assetFrame"].winfo_x() > -delta and scrollDir > 0:
                self.GUI["assetCanvas"].xview_moveto(0)
            else:
                self.GUI["assetCanvas"].xview_moveto( (-self.GUI["assetFrame"].winfo_x()-delta*scrollDir) / self.GUI["assetFrame"].winfo_width() )
    def _ctrl_z(self,event):    #Undo your last action
        if self.grab_current() == None: #If any other window is open, then you can't do this
            lastAction = (self.undoRedo[2]-1)%100
            #If there actually IS a previous action, load that
            if lastAction >= self.undoRedo[0] and lastAction <= self.undoRedo[1]:
                self.undoRedo[2] = (self.undoRedo[2]-1)%100
                PERM.clear()
                PERM.update(copy.deepcopy(TEMP["undo"][lastAction]))
                self.profile = ""   #name of the currently selected profile. Always starts with no filter applied.
                self.create_PORTFOLIO_WIDGETS()
                self.create_metrics()
                self.create_PROFILE_MENU()   
    def _ctrl_y(self,event):    #Redo your last action
        if self.grab_current() == None: #If any other window is open, then you can't do this
            nextAction = (self.undoRedo[2]+1)%100
            #If there actually IS a next action, load that
            if nextAction >= self.undoRedo[0] and nextAction <= self.undoRedo[1]:
                self.undoRedo[2] = (self.undoRedo[2]+1)%100
                PERM.clear()
                PERM.update(copy.deepcopy(TEMP["undo"][nextAction]))
                self.profile = ""   #name of the currently selected profile. Always starts with no filter applied.
                self.create_PORTFOLIO_WIDGETS()
                self.create_metrics()
                self.create_PROFILE_MENU() 
    def _esc(self,event):    #Exit this window
        if self.grab_current() == None: #If any other window is open, then you can't do this
            self.comm_quit()

#USEFUL COMMANDS
#=============================================================
    def undo_save(self):
        """Saves current portfolio in the memory should the user wish to undo their last modification"""
        #############
        #NOTE: Undo savepoints are triggered when:
        ###############3
        # Loading a portfolio, creating a new portfolio, or merging portfolios causes an undosave
        # UNIMPLEMENTED: importing coinbase or gemini transaction histories cause an undosave
        # Modifying/Creating a(n): Asset, Transaction, Wallet, Profile
        #overwrites the cur + 1th slot with data
        TEMP["undo"][(self.undoRedo[2]+1)%100] = copy.deepcopy(PERM)

        if self.undoRedo[1] - self.undoRedo[0] <= 0 and self.undoRedo[1] != self.undoRedo[0]:
            self.undoRedo[0] = (self.undoRedo[0]+1)%100
        self.undoRedo[2] = (self.undoRedo[2]+1)%100
        self.undoRedo[1] = self.undoRedo[2]

    def whitelisted_wallets(self):
        """Returns list of whitelisted wallets under current profile"""
        #If the profile whitelists no wallets, then all wallets are whitelisted
        if self.profile == "" or len(PERM["profiles"][self.profile]["wallets"]) == 0:
            return list(PERM["wallets"])
        else:
            return PERM["profiles"][self.profile]["wallets"]

    def trans_sorted_filtered(self, a):
        """Returns a sorted list of all the whitelisted transactions for asset \'a\'"""
        filteredTrans = self.trans_filtered(a)
        if len(filteredTrans) == 0:
            return []

        if settings("sort_trans") == "alpha":
            alpha = []
            numeric = []
            for t in filteredTrans:
                try:
                    int(t.replace("/","").replace(" ","").replace(":",""))
                    numeric.append(t)
                except:
                    if t[16:].upper() == "SWAP":
                        numeric.append(t)
                    else:
                        alpha.append(t)
            def alphaKey(e):
                return e.lower()
            def numericKey(e):
                for c in "/ :SWAP":     #removes these character before sorting
                    e = e.replace(c,"")
                return int(e)
            alpha.sort(key=alphaKey)
            numeric.sort(reverse=True, key=numericKey)
            return alpha+numeric
    def assets_sorted_filtered(self, reverse=False):
        """Returns a sorted list of all the whitelisted assets"""
        if settings("sort_asset") == "alpha":
            sorted = []
            for a in self.assets_filtered():
                sorted.append(a)
            sorted.sort(reverse=reverse)
            i=1
            for a in sorted:
                TEMP["widgets"][a]["name"].configure(text=str(i)+" : "+a.split("z")[0])
                i+=1
            return sorted
    def trans_filtered(self, a):
        if self.profile == "" or len(PERM["profiles"][self.profile]["wallets"]) == 0:
            return PERM["assets"][a]["trans"]
        else:
            filteredTrans = []
            for t in PERM["assets"][a]["trans"]:
                if PERM["assets"][a]["trans"][t]["wallet"] in self.whitelisted_wallets(): #If this transaction's wallet is on the whitelist, then add it to the filtered list
                    filteredTrans.append(t) 
                elif PERM["assets"][a]["trans"][t]["type"] == "transfer" and PERM["assets"][a]["trans"][t]["wallet2"] in self.whitelisted_wallets(): #if its a transfer and wallet2 is on the whitelist:
                    filteredTrans.append(t)
            return filteredTrans
    def assets_filtered(self):
        """Returns a list of whitelisted assets under the current filter profile (Filters by Wallet, Asset, and Class)"""
        if self.profile == "":
            return set(PERM["assets"])
        #Raw profile filter data
        walletList =  set(PERM["profiles"][self.profile]["wallets"])
        classList = set(PERM["profiles"][self.profile]["classes"])

        #Whitelists, in the form of assets
        whitelistedWallets = set()
        whitelistedAssets = set(PERM["profiles"][self.profile]["assets"])
        whitelistedClasses = set()

        #Adds whitelisted wallets
        if walletList != set():    #If we're actually using this filter...
            for a in PERM["assets"]:     #Then for every asset in the portfolio....
                for applicableWallet in TEMP["metrics"][a]["wallets"]:  #and for every wallet relevant to that asset...
                    if applicableWallet in walletList:  #If that wallet is whitelisted:
                        whitelistedWallets.add(a)          #add this asset to the whitelist
                        break   #skips to the next asset
        else:
            whitelistedWallets = set(PERM["assets"])
        #Whitelisted assets already added, this was very easy to do. Still need to fix it if one is empty
        if whitelistedAssets == set():
            whitelistedAssets = set(PERM["assets"])
        #Adds whitelisted classes
        if classList != set():    #If we're actually using this filter...
            for a in PERM["assets"]:     #Then for every asset in the portfolio....
                if a.split("z")[1] in classList:     #If the class of this asset is whitelisted...
                    whitelistedClasses.add(a)   #Add it to the class whitelist
        else:
            whitelistedClasses = set(PERM["assets"])

        #The true whitelist is the interection of all three whitelists
        return whitelistedWallets.intersection(whitelistedAssets).intersection(whitelistedClasses)
               

    def refreshScrollbars(self):
        self.GUI["assetFrame"].update()    #takes 500 milliseconds for 585 transactions... gross
        self.GUI["assetCanvas"].configure(scrollregion=self.GUI["assetFrame"].bbox("ALL"))  #0ms!!!!




    def comm_copyright(self):
        MessageBox(self,
        "MIT License", 

        """Copyright (c) 2021 Shane Evanson

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the \"Software\"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.""", width=78, height=20)

        





if __name__ == "__main__":
    Portfolio().mainloop()





