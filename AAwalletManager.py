from AAlib import *
from AAmessageBox import MessageBox
from AAtooltip import CreateToolTip
from AAwalletEditor import WalletEditor

import tkinter as tk
from functools import partial as p



class WalletManager(tk.Toplevel):
    def __init__(self, upper):  #upper is a reference to the original PortfolioApp, master is a reference to the TopLevel GUI 
        """Opens the Wallet Manager for selecting wallets to modify or delete"""
        super().__init__()
        self.configure(bg=palette("dark"))
        self.protocol("WM_DELETE_WINDOW", self.comm_close) #makes closing the window identical to hitting cancel
        self.grab_set()       #You can only interact with this window now
        self.focus_set()
        self.resizable(False,False)  #So you cant resize this window

        self.title("Manage Wallets")

        self.upper = upper

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

        self.grid_columnconfigure(0,weight=1)
        self.grid_rowconfigure(0,weight=1)
        self.GUI["walletManagerFrame"] = tk.Frame(self, bg=palette("accent"))
        self.GUI["walletManagerFrame"].grid_columnconfigure(0,weight=1)

        self.GUI["title"] = tk.Label(self.GUI["walletManagerFrame"], text="Manage Wallets", fg=palette("entrycursor"), bg=palette("accent"), font=settings("font"))
        self.GUI["newWallet"] = tk.Button(self.GUI["walletManagerFrame"], text="+ Wallet", bg=palette("purchase"), fg="#000000", font=settings("font"), command=p(WalletEditor, self, 1))
        self.GUI["menuFrame"] = tk.Frame(self.GUI["walletManagerFrame"])


        self.GUI["entryCanvas"] = tk.Canvas(self.GUI["walletManagerFrame"], bg=palette("light"), highlightthickness=0)
        self.GUI["entryFrame"] = tk.Frame(self.GUI["entryCanvas"], bg=palette("error"))
        
        self.GUI["scroll_v"] = tk.Scrollbar(self.GUI["walletManagerFrame"], orient="vertical", command=self.GUI["entryCanvas"].yview)

        self.GUI["entryCanvas"].configure(yscrollcommand=self.GUI["scroll_v"].set)
        self.GUI["entryCanvas"].create_window(0, 0, window=self.GUI["entryFrame"], anchor=tk.NW)

        #GUI RENDERING
        #==============================
        self.GUI["walletManagerFrame"].grid(padx=(20,20), pady=(20,20))

        self.GUI["title"].grid(column=0,row=0, columnspan=2, pady=(20,20))
        self.GUI["newWallet"].grid(column=0,row=1, columnspan=2, sticky="NSEW")
        self.GUI["entryCanvas"].grid(column=0,row=2, sticky="NSEW")
        self.GUI["scroll_v"].grid(column=1,row=2, sticky="NS")
        self.GUI["menuFrame"].grid(column=0,row=3, columnspan=2, pady=(20,20))

    def create_MENU(self):
        #MENU CREATION
        #==============================
        self.MENU = {
            "close" : tk.Button(self.GUI["menuFrame"], text="Close", bg=palette("entry"), fg="#ffffff", font=settings("font"), command=self.comm_close)
        }
        #MENU RENDERING
        #==============================
        self.MENU["close"].pack(side="left")

    def create_ENTRIES(self):        
        #ENTRY CREATION
        #==============================
        def alphaKey(e):
                return e.lower()
        sortedWallets = list(PERM["wallets"])
        sortedWallets.sort(key=alphaKey)

        self.ENTRIES = {}
        for slave in self.GUI["entryFrame"].grid_slaves():
            slave.destroy()

        for w in sortedWallets:
            if len(str(w)) > 20:
                self.ENTRIES[w] = tk.Button(self.GUI["entryFrame"], text=w, bg=palette("entry"), fg="#ffffff", font=settings("font", 0.75), command=p(WalletEditor, self, w))
            else:
                self.ENTRIES[w] = tk.Button(self.GUI["entryFrame"], text=w, bg=palette("entry"), fg="#ffffff", font=settings("font", 0.75), command=p(WalletEditor, self, w), width=20)
            self.ENTRIES[w].bind("<MouseWheel>", self._mousewheel)

        #RENDERING
        #==============================
        order = 0
        for entry in self.ENTRIES:
            self.ENTRIES[entry].grid(column=0, row=order, sticky="EW")
            order += 1
        
        self.refreshScrollbars()

#BINDINGS
#=============================================================
    def _mousewheel(self, event):
        scrollDir = event.delta/120
        delta = settings("font")[1]*2    #bigger font size means faster scrolling!
        if self.GUI["entryFrame"].winfo_y() > -delta and scrollDir > 0:
            self.GUI["entryCanvas"].yview_moveto(0)
        else:
            self.GUI["entryCanvas"].yview_moveto( (-self.GUI["entryFrame"].winfo_y()-delta*scrollDir) / self.GUI["entryFrame"].winfo_height() )
    def refreshScrollbars(self):
        self.GUI["entryFrame"].update()  
        beeBox = self.GUI["entryFrame"].bbox("ALL")
        self.GUI["entryCanvas"].configure(scrollregion=beeBox, width=beeBox[2])  #0ms!!!!

    def _esc(self,event):    #Exit this window
        if self.grab_current() == self: #If any other window is open, then you can't do this
            self.comm_close()
    def comm_close(self):  
        self.upper.focus_set()
        self.destroy()  #no extra commands, so that closing the window is functionally identical to cancellation






