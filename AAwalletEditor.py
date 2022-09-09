from AAlib import *
from AAmessageBox import MessageBox
from AAaddressEditor import AddressEditor

import tkinter as tk
from functools import partial as p



class WalletEditor(tk.Toplevel):
    def __init__(self, upper, w=1):  #upper is a reference to the original PortfolioApp, master is a reference to the TopLevel GUI 
        '''Opens a new wallet editor to modify the name or description of a wallet'''
        super().__init__()
        self.configure(bg=palette('dark'))
        self.protocol('WM_DELETE_WINDOW', self.comm_close) #makes closing the window identical to hitting cancel
        self.grab_set()       #You can only interact with this window now
        self.focus_set()
        self.resizable(False,False)  #So you cant resize this window

        self.upper, self.w= upper, w
        if w == 1:
            self.title('Create Wallet')
        else:
            self.title('Edit Wallet')

        self.create_GUI()
        self.create_MENU()
        self.create_ENTRIES()

        #BINDINGS
        #==============================
        self.bind('<Escape>', self._esc)
        
        self.update()    #Necessary, so that geometry() has the correct window dimensions
        self.geometry('+%d+%d' % ( (self.winfo_screenwidth()-self.winfo_width())/2 + self.winfo_x()-self.winfo_rootx(),
                                                    (self.winfo_screenheight()-self.winfo_height())/2 ))#centers the window in the middle of the screen
        

    def create_GUI(self):
        #GUI CREATION
        #==============================
        self.GUI = {}

        self.GUI['walletEditorFrame'] = tk.Frame(self, bg=palette('accent'))

        self.GUI['title'] = tk.Label(self.GUI['walletEditorFrame'], fg=palette('entrycursor'), bg=palette('accent'), font=settings('font'))
        if self.w == 1:     self.GUI['title'].configure(text='Create Wallet')
        else:               self.GUI['title'].configure(text='Edit '+self.w+' Wallet')

        self.GUI['entryFrame'] = tk.Frame(self.GUI['walletEditorFrame'], bg=palette('light'))
        self.GUI['menuFrame'] = tk.Frame(self.GUI['walletEditorFrame'])

        self.GUI['newAddress'] = tk.Button(self.GUI['walletEditorFrame'], text='+ Address', bg=palette('purchase'), fg='#000000', font=settings('font'), command=p(AddressEditor, self, self.w, 1))
        #The list of associated addresses
        self.GUI['addressCanvas'] = tk.Canvas(self.GUI['walletEditorFrame'], bg=palette('light'), highlightthickness=0)
        self.GUI['addressFrame'] = tk.Frame(self.GUI['addressCanvas'], bg=palette('light'))
        
        self.GUI['scroll_addresses'] = tk.Scrollbar(self.GUI['walletEditorFrame'], orient='vertical', command=self.GUI['addressCanvas'].yview)

        self.GUI['addressCanvas'].configure(yscrollcommand=self.GUI['scroll_addresses'].set)
        self.GUI['addressCanvas'].create_window(0, 0, window=self.GUI['addressFrame'], anchor=tk.NW)


        #GUI RENDERING
        #==============================
        self.GUI['walletEditorFrame'].grid(padx=(20,20), pady=(20,20))

        self.GUI['title'].grid(column=0,row=0, pady=(20,20))
        self.GUI['entryFrame'].grid(column=0,row=1, sticky='S')
        self.GUI['menuFrame'].grid(column=0,row=2, pady=(20,20))

        #If this is a new wallet we don't want this option just yet
        if self.w != 1:
            self.GUI['newAddress'].grid(column=1,row=0, columnspan=2, sticky='NSEW')
            self.GUI['newAddress'].grid(column=1,row=0, columnspan=2, sticky='NSEW')

            self.GUI['addressCanvas'].grid(column=1,row=1, sticky='NSEW')
            self.GUI['scroll_addresses'].grid(column=2,row=1, sticky='NS')

    def create_MENU(self):
        #MENU CREATION
        #==============================
        self.MENU = {}

        #SAVE/CANCEL buttons
        self.MENU['save'] = tk.Button(self.GUI['menuFrame'], text='Save', bg=palette('entry'), fg='#00ff00', font=settings('font'), command=self.comm_save)
        self.MENU['cancel'] = tk.Button(self.GUI['menuFrame'], text='Cancel', bg=palette('entry'), fg='#ff0000', font=settings('font'), command=self.comm_close)
        self.MENU['delete'] = tk.Button(self.GUI['menuFrame'], text='Delete', bg='#ff0000', fg='#000000', font=settings('font'), command=self.comm_deleteWallet)

        #MENU RENDERING
        #==============================

        #SAVE/CANCEL buttons
        self.MENU['save'].pack(side='left')
        self.MENU['cancel'].pack(side='left')
        if self.w != 1:
            self.MENU['delete'].pack(side='left')

    def refresh_addresses(self):    
        #Destroy all the old widgets
        for address in list(self.ADDRESSES):
            self.ADDRESSES.pop(address).destroy()
        
        def alphaKey(e):
            return e.lower()
        sortedAddresses = list(PERM['wallets'][self.w]['addresses'])
        sortedAddresses.sort(key=alphaKey)
        
        order = 0
        for address in sortedAddresses:
            self.ADDRESSES[address] = tk.Button(self.GUI['addressFrame'], text=address, bg=palette('entry'), fg='#ffffff', font=settings('font', 0.75), command=p(AddressEditor, self, self.w, address), width=16)
            #We abbreviate the address to the first 13 characters then a '...' if its length exceeds 16 characters, which it almost certainly will
            if len(address) > 16:   self.ADDRESSES[address].configure(text=address[:13]+'...')
            self.ADDRESSES[address].bind('<MouseWheel>', self._mousewheel_addresses)
            self.ADDRESSES[address].grid(column=0, row=order)
            order += 1


    def create_ENTRIES(self):   
        #STRING VARIABLES
        #==============================
        self.TEMP = {       #These are the default values for all inputs    
            'name':         tk.StringVar(self, value=''),
            'desc':         tk.StringVar(self, value='')
        }
        if self.w != 1:  #If not NEW, replace default value with what you're actually editing
            self.TEMP['name'].set(self.w)
            self.TEMP['desc'].set(PERM['wallets'][self.w]['desc'])

        #WIDGETS
        #==============================
        self.ENTRIES = {}
        self.LABELS = {}
        self.ADDRESSES = {}

        #ENTRIES
        #==============
        if self.w != 1:
            self.refresh_addresses()


        widthsetting = 24

        self.ENTRIES['name'] = tk.Entry(self.GUI['entryFrame'], textvariable=self.TEMP['name'], width=widthsetting, bg=palette('entry'), fg=palette('entrytext'), insertbackground=palette('entrycursor'), font=settings('font'))
        
        self.ENTRIES['desc'] = tk.Text(self.GUI['entryFrame'], wrap='word', bg=palette('entry'), fg=palette('entrytext'), insertbackground=palette('entrycursor'), font=settings('font'), height=8,width=widthsetting)
        self.ENTRIES['desc'].insert(0.0, self.TEMP['desc'].get())
        
        #Entry restrictions

        def validName(new):
            if len(new) > 24:
                return False
            return True
        valName = self.register(validName)
        self.ENTRIES['name'].configure(validate='key', vcmd=(valName, '%P'))
        
        #LABELS
        #==============
        self.LABELS['name'] = tk.Label(self.GUI['entryFrame'], text='Name', bg=palette('light'), fg=palette('entrycursor'), font=settings('font',0.5))
        self.LABELS['desc'] = tk.Label(self.GUI['entryFrame'], text='Description', bg=palette('light'), fg=palette('entrycursor'), font=settings('font',0.5))


        #RENDERING
        #==============================

        self.LABELS['name']     .grid(column=0,row=0, sticky='NS')
        self.ENTRIES['name']    .grid(column=1,row=0, sticky='NS')

        self.LABELS['desc']     .grid(column=0,row=1, sticky='NS')
        self.ENTRIES['desc']    .grid(column=1,row=1, sticky='NS')
        
    def updateProfileInstance(self, newID=None):
        '''If a wallet name is modified, or a wallet is deleted, that change has to be applied to profiles. This does that.'''
        profiles = PERM['profiles']
        for p in profiles:
            if profiles[p]['wallets'].count(self.w) == 1:    #if this asset is in there, pop it
                profiles[p]['wallets'].pop(profiles[p]['wallets'].index(self.w))
                if newID != None:
                    profiles[p]['wallets'].append(newID)

    def comm_deleteWallet(self):
        #You can only delete a wallet if its name is not used by any transaction in the portfolio
        if self.w in TEMP['metrics'][' PORTFOLIO']['wallets']:   #is the wallet you're deleting used anywhere in the portfolio?
            MessageBox(self, 'Error!', 'You cannot delete this wallet, as it is used by existing transactions.') # If so, you can't delete it. 
            return

        PERM['wallets'].pop(self.w)  #destroy the old wallet
        self.updateProfileInstance()
        self.upper.create_ENTRIES() #It is easiest just to totally re-render the wallet manager after deleting a wallet
        self.upper.refreshScrollbars()
        self.comm_close()


    def comm_save(self):
        #DATA CULLING AND CONVERSION
        #==============================
        #converts all tk.StringVar's to their proper final format
        TEMP2 = {
            'desc' : self.ENTRIES['desc'].get(1.0,'end').rstrip().lstrip()
        }
        
        ID = self.TEMP['name'].get().rstrip().lstrip()

        # CHECKS
        #==============================
        #new ticker will be unique?
        for w in PERM['wallets']:       #Can't do a one-liner here cause we compare the lower case of each name
            if w.lower() == ID.lower() and w != self.w:
                MessageBox(self, 'ERROR!', 'A wallet already exists with this name!')
                return

        #Name isn't an empty string?
        if ID == '':
            MessageBox(self, 'ERROR!', 'Must enter a name for this wallet')
            return


        #WALLET SAVING AND OVERWRITING
        #==============================
        if self.w != 1:     PERM['wallets'][ID] = {'addresses':PERM['wallets'][self.w]['addresses'], 'desc':TEMP2['desc']}
        else:               PERM['wallets'][ID] = {'addresses':[], 'desc':TEMP2['desc']} #Creates the new wallet

        if self.w != 1 and self.w != ID:   #WALLET RE-NAMED
            #destroy the old wallet
            PERM['wallets'].pop(self.w)     
            for a in PERM['assets']:
                if self.w in TEMP['metrics'][a]['wallets']:   #skips assets that make no use of this wallet
                    for t in PERM['assets'][a]['trans']:
                        currTrans = PERM['assets'][a]['trans'][t]
                        if currTrans['wallet'] == self.w:
                            currTrans['wallet'] =  ID            #sets logical wallet name to new name
                        if currTrans['type'] == 'TRANSFER' and currTrans['wallet2'] == self.w:
                            currTrans['wallet2'] =  ID            #sets logical wallet name to new name
            self.updateProfileInstance(ID)
        
        self.upper.create_ENTRIES()
        self.comm_close()

    def _mousewheel_addresses(self, event):
        scrollDir = event.delta/120
        delta = settings('font')[1]*2    #bigger font size means faster scrolling!
        if self.GUI['addressFrame'].winfo_y() > -delta and scrollDir > 0:
            self.GUI['addressCanvas'].yview_moveto(0)
        else:
            self.GUI['addressCanvas'].yview_moveto( (-self.GUI['addressFrame'].winfo_y()-delta*scrollDir) / self.GUI['addressFrame'].winfo_height() )

    def _esc(self,event):    #Exit this window
        if self.grab_current() == self: #If any other window is open, then you can't do this
            self.comm_close()
    def comm_close(self):  
        self.upper.grab_set()
        self.upper.focus_set()
        self.destroy()  #no extra commands, so that closing the window is functionally identical to cancellation






