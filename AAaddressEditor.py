from AAlib import *
from AAmessageBox import MessageBox

import tkinter as tk
from functools import partial as p



class AddressEditor(tk.Toplevel):
    def __init__(self, upper, wallet, address=1):  #upper is a reference to the original PortfolioApp, master is a reference to the TopLevel GUI 
        '''Opens a new wallet editor to modify the name or description of a wallet'''
        super().__init__()
        self.configure(bg=palette('dark'))
        self.protocol('WM_DELETE_WINDOW', self.comm_close) #makes closing the window identical to hitting cancel
        self.grab_set()       #You can only interact with this window now
        self.focus_set()
        self.resizable(False,False)  #So you cant resize this window

        self.upper, self.wallet, self.address = upper, wallet, address
        if address == 1:
            self.title('Create Address')
        else:
            self.title('Edit Address')

        self.create_GUI()

        #BINDINGS
        #==============================
        self.bind('<Escape>', self._esc)
        
        self.update()    #Necessary, so that geometry() has the correct window dimensions
        self.geometry('+%d+%d' % ( (self.winfo_screenwidth()-self.winfo_width())/2 + self.winfo_x()-self.winfo_rootx(),
                                                    (self.winfo_screenheight()-self.winfo_height())/2 ))#centers the window in the middle of the screen
        

    def create_GUI(self):
        #OVERARCHING GUI
        #==============================
        self.GUI = {}
        self.GUI['walletEditorFrame'] = tk.Frame(self, bg=palette('accent'))
        self.GUI['title'] = tk.Label(self.GUI['walletEditorFrame'], fg=palette('entrycursor'), bg=palette('accent'), font=settings('font'))
        if self.address == 1:   self.GUI['title'].configure(text='Create Address')
        else:                   self.GUI['title'].configure(text='Edit Address')
        self.GUI['entryFrame'] = tk.Frame(self.GUI['walletEditorFrame'], bg=palette('light'))
        self.GUI['menuFrame'] = tk.Frame(self.GUI['walletEditorFrame'])


        self.GUI['walletEditorFrame'].grid(padx=(20,20), pady=(20,20))

        self.GUI['title'].grid(column=0,row=0, pady=(20,20))
        self.GUI['entryFrame'].grid(column=0,row=2)
        self.GUI['menuFrame'].grid(column=0,row=3, pady=(20,20))

        #MENU
        #==============================
        self.MENU = {}

        self.MENU['save'] = tk.Button(self.GUI['menuFrame'], text='Save', bg=palette('entry'), fg='#00ff00', font=settings('font'), command=self.comm_save)
        self.MENU['cancel'] = tk.Button(self.GUI['menuFrame'], text='Cancel', bg=palette('entry'), fg='#ff0000', font=settings('font'), command=self.comm_close)
        self.MENU['delete'] = tk.Button(self.GUI['menuFrame'], text='Delete', bg='#ff0000', fg='#000000', font=settings('font'), command=self.comm_deleteAddress)

        self.MENU['save'].pack(side='left')
        self.MENU['cancel'].pack(side='left')
        if self.address != 1:   self.MENU['delete'].pack(side='left')

      
        #LABELS AND ENTRY BOXES
        #==============================
        self.TEMP =  tk.StringVar(self, value='')

        #Fill in values if not new
        if self.address != 1:     self.TEMP.set(self.address)

        self.ENTRIES = {}
        widthsetting = 52

        self.ENTRIES['name'] = tk.Entry(self.GUI['entryFrame'], textvariable=self.TEMP, width=widthsetting, bg=palette('entry'), fg=palette('entrytext'), insertbackground=palette('entrycursor'), font=settings('font'))
        self.ENTRIES['name']    .grid(column=1,row=0, sticky='NS')

    def comm_deleteAddress(self):
        PERM['wallets'][self.wallet]['addresses'].remove(self.address)  #destroy the old address
        self.upper.refresh_addresses()
        self.comm_close()


    def comm_save(self):
        ID = self.TEMP.get().rstrip().lstrip()

        # CHECKS
        #==============================
        #new ticker will be unique?
        for w in PERM['wallets']:  
            if ID in PERM['wallets'][w]['addresses']:
                MessageBox(self, 'ERROR!', 'This address already falls under the ' + w + ' wallet!')
                return
        #Name isn't an empty string?
        if ID == '':
            MessageBox(self, 'ERROR!', 'Must enter something')
            return

        #ADDRESS SAVING
        #==============================
        PERM['wallets'][self.wallet]['addresses'].append(ID)
        #If we've renamed an address, delete the old one.
        if self.address != 1 and self.address != ID:
            PERM['wallets'][self.wallet]['addresses'].remove(self.address)

        self.upper.refresh_addresses()
        self.comm_close()

    def _esc(self,event):    #Exit this window
        self.comm_close()
    def comm_close(self):  
        self.upper.grab_set()
        self.upper.focus_set()
        self.destroy()  #no extra commands, so that closing the window is functionally identical to cancellation






