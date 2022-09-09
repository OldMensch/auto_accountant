from AAlib import *
from AAmessageBox import MessageBox

import tkinter as tk
from functools import partial as p
from datetime import *



class TransEditor(tk.Toplevel):
    def __init__(self, upper, a, t=1):  #upper is a reference to the original PortfolioApp
        """Opens a new trade editor with transaction \'t\' on asset \'a\' for editing\n
            upper - a reference to the tkinter window which called this editor\n
            If no \'t\' is entered, the new transaction editor will open"""
        super().__init__()
        self.configure(bg=palette("dark"))
        self.protocol("WM_DELETE_WINDOW", self.comm_cancel) #makes closing the window identical to hitting cancel
        self.grab_set()       #You can only interact with this window now
        self.focus_set()       #You can only interact with this window now
        self.resizable(False,False)  #So you cant resize this window

        if t==1:
            self.title("Create Transaction")
        else:
            self.title("Edit Transaction")
            TEMP["widgets"][a]["trans"][t].configure(bg="#ffffff")   #colors the transaction white in the main portfolio during editing

        self.upper, self.a, self.oldID = upper, a, t

        self.create_GUI()
        self.create_MENU()
        self.create_ENTRIES()
        
        self.render_ENTRIES()

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

        self.GUI["transEditorFrame"] = tk.Frame(self)

        self.GUI["title"] = tk.Label(self.GUI["transEditorFrame"], fg=palette("entrycursor"), font=settings("font"))
        if self.oldID==1:
            self.GUI["title"].configure(text="Create "+str(self.a.split("z")[0])+" Transaction")
        else:
            self.GUI["title"].configure(text="Edit "+str(self.a.split("z")[0])+" Transaction")

        self.GUI["buttonFrame"] = tk.Frame(self.GUI["transEditorFrame"], bg=palette("error"))
        self.GUI["entryFrame"] = tk.Frame(self.GUI["transEditorFrame"], bg=palette("light"))
        self.GUI["menuFrame"] = tk.Frame(self.GUI["transEditorFrame"])


        #GUI RENDERING
        #==============================
        self.GUI["transEditorFrame"].grid(padx=(20,20), pady=(20,20))

        self.GUI["title"].grid(column=0,row=0, pady=(20,20))
        self.GUI["buttonFrame"].grid(column=0,row=1)    
        self.GUI["entryFrame"].grid(column=0,row=2)
        self.GUI["menuFrame"].grid(column=0,row=3, pady=(20,20))


    def create_MENU(self):
        #MENU CREATION
        #==============================
        self.MENU = {}
        self.TYPES = {}

        #Buttons to set what the transaction type is
        for transType in assetclasslib[self.a.split("z")[1]]["validTrans"]:
            self.TYPES[transType] =   tk.Button(self.GUI["buttonFrame"], font=settings("font",0.5), bg=palette(transType), text=transType.capitalize(), command=p(self.comm_type, transType))

        #SAVE/CANCEL buttons
        self.MENU["save"] = tk.Button(self.GUI["menuFrame"], text="Save", bg=palette("entry"), fg="#00ff00", font=settings("font"), command=self.comm_save)
        self.MENU["cancel"] = tk.Button(self.GUI["menuFrame"], text="Cancel", bg=palette("entry"), fg="#ff0000", font=settings("font"), command=self.comm_cancel)
        self.MENU["delete"] = tk.Button(self.GUI["menuFrame"], text="Delete", bg="#ff0000", fg="#000000", font=settings("font"), command=self.comm_deleteTrans)


        #MENU RENDERING
        #==============================

        #Buttons to set what the transaction type is
        order = 0
        for transButton in self.TYPES:
            self.TYPES[transButton].grid(row=0,column=order)
            order += 1

        #SAVE/CANCEL buttons
        self.MENU["save"].pack(side="left")
        self.MENU["cancel"].pack(side="left")
        if self.oldID != 1:
            self.MENU["delete"].pack(side="left")


    def create_ENTRIES(self):  
        #STRING VARIABLES
        #==============================
        self.TEMP = {       #These are the default values for all inputs            
            "type":         tk.StringVar(self, value="purchase"),
            "desc":         tk.StringVar(self, value=""),
        #this is the time, right now
            "date":         tk.StringVar(self, value=str(datetime.now())[0:4]+"/"+str(datetime.now())[5:7]+"/"+str(datetime.now())[8:10]+" "+str(datetime.now())[11:13]+":"+str(datetime.now())[14:16]+":"+str(datetime.now())[17:19]),
            "wallet":       tk.StringVar(self, value="-NO WALLET SELECTED-"), #CHANGE THIS - there always has to be at least one wallet
            "wallet2":      tk.StringVar(self, value="-NO WALLET SELECTED-"), 
            "tokens":       tk.StringVar(self, value=""), 
            "usd":          tk.StringVar(self, value=""), 
            "price":        tk.StringVar(self, value=""), 
            "stakeType":    tk.StringVar(self, value="1: Tokens is the EXTRA"),
        }
        if self.oldID != 1:  #If not NEW, replace default value with what you're actually editing
            for key in PERM["assets"][self.a]["trans"][self.oldID]:
                self.TEMP[key].set(PERM["assets"][self.a]["trans"][self.oldID][key])
            if self.TEMP["type"].get() != "stake":
                self.TEMP["date"].set(self.oldID)

        self.autoprice = tk.StringVar(self, value="")   #This is the helpful display price for purchases and sales, which automatically adjusts to the user's entries


        #WIDGETS
        #==============================
        self.ENTRIES = {}
        self.LABELS = {}

        #ENTRIES
        #==============
        widthsetting = 24

        self.autopriceEntry = tk.Entry(self.GUI["entryFrame"], textvariable = self.autoprice, state="disabled", width = widthsetting, bg=palette("entry"), fg=palette("entrytext"), insertbackground=palette("entrycursor"), disabledbackground=palette("dark"), disabledforeground=palette("entrycursor"), font=settings("font"))


        self.ENTRIES["date"] = tk.Entry(self.GUI["entryFrame"], textvariable=self.TEMP["date"], width=widthsetting, justify="center", bg=palette("entry"), fg=palette("entrytext"), insertbackground=palette("entrycursor"), disabledbackground=palette("dark"), disabledforeground=palette("entrycursor"), font=settings("font"))
        for entry in ["tokens","usd","price"]:
            self.ENTRIES[entry] = tk.Entry(self.GUI["entryFrame"], textvariable=self.TEMP[entry], width=widthsetting, bg=palette("entry"), fg=palette("entrytext"), insertbackground=palette("entrycursor"), disabledbackground=palette("dark"), disabledforeground=palette("entrycursor"), font=settings("font"))
        self.ENTRIES["desc"] = tk.Text(self.GUI["entryFrame"], wrap="word", bg=palette("entry"), fg=palette("entrytext"), insertbackground=palette("entrycursor"), font=settings("font"), height=8,width=widthsetting)
        self.ENTRIES["desc"].insert(0.0, self.TEMP["desc"].get())
        
        stakeTypes = [
            "1: Tokens is the EXTRA",
            "2: Tokens is the new TOTAL"
        ]
        self.ENTRIES["stakeType"] = tk.OptionMenu(self.GUI["entryFrame"], self.TEMP["stakeType"], *stakeTypes)
        self.ENTRIES["stakeType"].configure(bg=palette("entry"), fg=palette("entrycursor"), font=settings("font"), highlightthickness=0)

        def alphaKey(e):        #creates a sorted list of all the current wallets
                return e.lower()
        walletList = []
        for w in PERM["wallets"]:
            walletList.append(w)
        walletList.sort(key=alphaKey)
        walletList.insert(0, "-NO WALLET SELECTED-")

        self.ENTRIES["wallet"] = tk.OptionMenu(self.GUI["entryFrame"], self.TEMP["wallet"], *walletList)
        self.ENTRIES["wallet"].configure(bg=palette("entry"), fg=palette("entrycursor"), font=settings("font"), highlightthickness=0)

        self.ENTRIES["wallet2"] = tk.OptionMenu(self.GUI["entryFrame"], self.TEMP["wallet2"], *walletList)
        self.ENTRIES["wallet2"].configure(bg=palette("entry"), fg=palette("entrycursor"), font=settings("font"), highlightthickness=0)


        #Entry restrictions
        def validDate(d):       #dear fuck why is this so complicated to perform!!!!!!!
            self.ENTRIES["date"].selection_clear()
            i = self.ENTRIES["date"].index('insert')
            if len(d.get()) < 19:
                d.insert(i, "0")
                d.insert(i, "0")
                self.ENTRIES["date"].icursor(i)
                for ignore in ["/"," ",":"]:
                    if d.get()[i-1] == ignore:
                        self.ENTRIES["date"].icursor(i-1)
            elif not d.get()[i-1].isdigit():
                d.delete(i-1)
                return
            elif i > 19:
                d.delete(19)
                return
            for ignore in ["/"," ",":"]:
                if d.get()[i] == ignore:
                    e = d.get()[i-1]
                    d.delete(i-1)
                    d.delete(i)
                    d.insert(i, e)
                    self.ENTRIES["date"].icursor(i+1)
                    return
            d.delete(i)
        def validDate2(char):
            if len(char) > 1 or not char.isdigit():
                return False    
            return True
        
        valDate = self.register(validDate2)
        self.ENTRIES["date"].configure(validate="key", vcmd=(valDate, '%S'))
        self.TEMP["date"].trace("w", lambda name, index, mode, sv=self.ENTRIES["date"]: validDate(sv))
             
            
        def validFloat(new, char):
            if char == " ":                         # no spaces
                return False
            if new == "" or new == ".":             #these just become 0 when saving
                    return True
            try: 
                float(new)  #must be convertible to float
                if float(new) < 0:                      #cant be negative
                    return False
                return True
            except:
                return False
        valFloat = self.register(validFloat)
        self.ENTRIES["price"].configure(validate="key", vcmd=(valFloat, '%P', '%S'))
        for entry in ["tokens","usd",]:
            self.ENTRIES[entry].configure(validate="key", vcmd=(valFloat, '%P', '%S'))
            self.TEMP[entry].trace("w", lambda name, index, mode: self.updateAutoPrice())
        


        #LABELS
        #==============
        labelText = ["Description","Date","Wallet","Destination Wallet",self.a.split("z")[0],"USD","Price","Stake Type"]
        labelKeys = ["desc","date","wallet","wallet2","tokens","usd","price","stakeType"]
        for key in range(len(labelKeys)):
            self.LABELS[labelKeys[key]] = tk.Label(self.GUI["entryFrame"], text=labelText[key], bg=palette("light"), fg=palette("entrycursor"), font=settings("font",0.5))


    def render_ENTRIES(self):
        #Appropriately colors the background
        self.GUI["transEditorFrame"].configure(bg=palette(self.TEMP["type"].get()))
        self.GUI["title"].configure(bg=palette(self.TEMP["type"].get()))
        
        for slave in self.GUI["entryFrame"].grid_slaves():
            slave.grid_forget()
        self.autopriceEntry.grid_forget()

        #ENTRIES
        #==============
        #Time and Date
        self.LABELS["date"].grid(column=0,row=0, sticky="NSEW")
        self.ENTRIES["date"].grid(column=1,row=0)
        if self.TEMP["type"].get() == "stake":
            self.ENTRIES["date"].configure(state="disabled", textvariable=tk.StringVar(self, "CONTINUOUS"))
        else:
            self.ENTRIES["date"].configure(state="normal", textvariable=self.TEMP["date"])
        
        #Wallet
        self.LABELS["wallet"].grid(column=0,row=1, sticky="NS")
        self.ENTRIES["wallet"].grid(column=1,row=1, sticky="NSEW")

        #Wallet2
        if self.TEMP["type"].get() == "transfer":
            self.LABELS["wallet2"].grid(column=0,row=2, sticky="NS")
            self.ENTRIES["wallet2"].grid(column=1,row=2, sticky="NSEW")
        
        #Tokens
        self.LABELS["tokens"].grid(column=0,row=3, sticky="NS")
        self.ENTRIES["tokens"].grid(column=1,row=3, sticky="NS")

        #USD
        if self.TEMP["type"].get() == "purchase" or self.TEMP["type"].get() == "sale":
            self.LABELS["usd"].grid(column=0,row=4, sticky="NS")
            self.ENTRIES["usd"].grid(column=1,row=4, sticky="NS")

        #Price
        if self.TEMP["type"].get() == "purchase" or self.TEMP["type"].get() == "sale":
            self.LABELS["price"].grid(column=0,row=5, sticky="NS")
            self.autopriceEntry.grid(column=1,row=5, sticky="NS")
            self.updateAutoPrice()
        elif self.TEMP["type"].get() == "gift" or self.TEMP["type"].get() == "expense":
            self.LABELS["price"].grid(column=0,row=5, sticky="NS")
            self.ENTRIES["price"].grid(column=1,row=5, sticky="NS")

        #Staking Type
        if self.TEMP["type"].get() == "stake":
            self.LABELS["stakeType"].grid(column=0,row=5, sticky="NS")
            self.ENTRIES["stakeType"].grid(column=1,row=5, sticky="NSEW")

        #Description
        self.LABELS["desc"].grid(column=0,row=6, sticky="NS")
        self.ENTRIES["desc"].grid(column=1,row=6, sticky="NS")


    def P(self, a, t=None):
        """Returns DATA DICTIONARY for transaction \'t\' from asset \'a\' \n
            OR, returns the list of all transaction DATA DICTIONARIES from asset \'a\'"""
        if t == None:
            return PERM["assets"][a]["trans"]
        return PERM["assets"][a]["trans"][t]
    def updateAutoPrice(self):
        tokens = self.ENTRIES["tokens"].get()
        usd = self.ENTRIES["usd"].get()
        if tokens == "" or tokens == "." or float(tokens) == 0:
            return
        if usd == "" or usd == ".":
            usd = 0
        self.autoprice.set(float(usd)/float(tokens))


    def comm_type(self, type):
        self.TEMP["type"] = tk.StringVar(self, value=type)
        self.render_ENTRIES()

    def comm_deleteTrans(self):
        #open an "are you sure????" prompt here
        PERM["assets"][self.a]["trans"].pop(self.oldID)             #removal from logical asset
        TEMP["widgets"][self.a]["trans"].pop(self.oldID).destroy()   #removal from visual asset. .destroy is NECESSARY to prevent memory leaks!
        self.upper.undo_save()
        self.upper.metrics_ASSET(self.a)
        self.upper.refreshScrollbars()
        self.upper.focus_set()
        self.destroy()  #no extra commands, so that closing the window is functionally identical to cancellation



    def comm_save(self):
        #DATA CULLING AND CONVERSION PART I
        #==============================
        #converts all tk.StringVar's to their proper final format
        TEMP2 = {}
        for string in self.TEMP:
            TEMP2[string] = self.TEMP[string].get()
        TEMP2["desc"] = self.ENTRIES["desc"].get(1.0,"end").rstrip()

        #converts number entries to 0 if equivalent to "" or "."
        for string in ["tokens","usd","price"]:
            if TEMP2[string] == "" or TEMP2[string] == ".":
                TEMP2[string] = "0"

        #This is what the transaction ID will be
        if TEMP2["type"]  == "stake":
            ID = TEMP2["wallet"]
        elif TEMP2["type"]  == "SWAP":
            ID = TEMP2["date"] + "swap"
        else:
            ID = TEMP2["date"]

        #Removes data irrelevant to this specific transaction type
        TEMP2.pop("date")
        if TEMP2["type"]  != "transfer":
            TEMP2.pop("wallet2")
        if TEMP2["type"]  != "purchase" and TEMP2["type"] != "sale":
            TEMP2.pop("usd")
        if TEMP2["type"]  != "gift" and TEMP2["type"] != "expense":
            TEMP2.pop("price")
        if TEMP2["type"]  != "stake":
            TEMP2.pop("stakeType")

        # CHECKS
        #==============================
        error = None
        #new ID will be unique?
        for t in PERM["assets"][self.a]["trans"]:
            if t == ID and t != self.oldID:
                if TEMP2["type"] == "stake":
                    error = p(MessageBox, self, "ERROR!", "A stake already exists for "+self.a.split("z")[0]+" on the "+TEMP2["wallet"]+" wallet!")
                else:
                    error = p(MessageBox, self, "ERROR!", "A transaction already exists with this time and date for "+self.a.split("z")[0]+"!")

        #valid date format?
        if TEMP2["type"] != "stake":
            try:
                datetime( int(ID[:4]), int(ID[5:7]), int(ID[8:10]), int(ID[11:13]), int(ID[14:16]), int(ID[17:19]) )
            except:
                error = p(MessageBox, self, "ERROR!", "Invalid date!")

        #selected a wallet? (start out with nothing selected)
        if TEMP2["wallet"] == "-NO WALLET SELECTED-":
            error = p(MessageBox, self, "ERROR!", "No wallet was selected")
        #selected a wallet2? (start out with nothing selected)
        if TEMP2["type"] == "transfer":
            if TEMP2["wallet2"] == "-NO WALLET SELECTED-":
                error = p(MessageBox, self, "ERROR!", "No destination wallet was selected")
            if TEMP2["wallet2"] == TEMP2["wallet"]:
                error = p(MessageBox, self, "ERROR!", "You cannot transfer from a wallet to itself! A transfer from a wallet to itself isn't really a transfer at all, yeah? ")

        #Tokens is non-zero?
        if float(TEMP2["tokens"]) == 0:
            error = p(MessageBox, self, "ERROR!", "Tokens must be non-zero!")

        #USD is non-zero for purchases and sales?
        if TEMP2["type"] == "purchase" or TEMP2["type"] == "sale":
            if float(TEMP2["usd"]) == 0:
                error = p(MessageBox, self, "ERROR!", "USD must be non-zero!")
        
        #Price is non-zero for gifts and expenses?
        if TEMP2["type"] == "gift" or TEMP2["type"] == "expense":
            if float(TEMP2["price"]) == 0:
                error = p(MessageBox, self, "ERROR!", "Price must be non-zero!")

        if error != None:
            error()
            return
        


        #TRANSACTION SAVING AND OVERWRITING
        #==============================
        #check: has the ID been changed, or is the transaction new?? if ID change: insert new one with this data, delete old transaction. if new, just update the information
        if self.oldID == 1 or self.oldID != ID:     #NEW: The transaction is a new transaction
            PERM["assets"][self.a]["trans"][ID] = TEMP2
            self.upper.create_TRANS_WIDGET(self.a, ID)
            if self.oldID != 1: #ID CHANGE: The transaction ID was changed (could be date, or wallet if staked)
                PERM["assets"][self.a]["trans"].pop(self.oldID)             #removal from logical asset
                TEMP["widgets"][self.a]["trans"].pop(self.oldID).destroy()   #removal from visual asset. .destroy is NECESSARY to prevent memory leaks!
            self.upper.render_ASSET(self.a)
        else:
            #we only edited an old transaction, so:
            PERM["assets"][self.a]["trans"][self.oldID].update(TEMP2)
            self.upper.reconfig_TRANS(self.a, self.oldID)


        self.upper.undo_save()
        self.upper.metrics_ASSET(self.a)
        self.upper.refreshScrollbars()
        self.upper.focus_set()
        self.destroy()

    def _esc(self,event):    #Exit this window
        self.comm_cancel()
    def comm_cancel(self):  
        if self.oldID != 1:
            self.upper.reconfig_TRANS(self.a, self.oldID)
        self.upper.focus_set()
        self.destroy()  #no extra commands, so that closing the window is functionally identical to cancellation






