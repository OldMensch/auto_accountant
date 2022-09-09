from AAlib import *
from AAmessageBox import MessageBox

import tkinter as tk
from functools import partial as p
from datetime import *
from mpmath import mpf as precise
from mpmath import mp



class TransEditor(tk.Toplevel):
    def __init__(self, upper, a, t=1):  #upper is a reference to the original PortfolioApp
        '''Opens a new trade editor with transaction \'t\' on asset \'a\' for editing\n
            upper - a reference to the tkinter window which called this editor\n
            If no \'t\' is entered, the new transaction editor will open'''
        super().__init__()
        self.configure(bg=palette('dark'))
        self.protocol('WM_DELETE_WINDOW', self.comm_cancel) #makes closing the window identical to hitting cancel
        self.grab_set()       #You can only interact with this window now
        self.focus_set()       #You can only interact with this window now
        self.resizable(False,False)  #So you cant resize this window

        if t==1:
            self.title('Create Transaction')
        else:
            self.title('Edit Transaction')

        self.upper, self.a, self.oldID = upper, a, t

        self.create_GUI()
        self.create_MENU()
        self.create_ENTRIES()
        
        self.render_ENTRIES()

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

        self.GUI['transEditorFrame'] = tk.Frame(self)

        self.GUI['title'] = tk.Label(self.GUI['transEditorFrame'], fg=palette('entrycursor'), font=settings('font'))
        if self.oldID==1:
            self.GUI['title'].configure(text='Create '+str(self.a.split('z')[0])+' Transaction')
        else:
            self.GUI['title'].configure(text='Edit '+str(self.a.split('z')[0])+' Transaction')

        self.GUI['buttonFrame'] = tk.Frame(self.GUI['transEditorFrame'], bg=palette('error'))
        self.GUI['entryFrame'] = tk.Frame(self.GUI['transEditorFrame'], bg=palette('light'))
        self.GUI['menuFrame'] = tk.Frame(self.GUI['transEditorFrame'])


        #GUI RENDERING
        #==============================
        self.GUI['transEditorFrame'].grid(padx=(20,20), pady=(20,20))

        self.GUI['title'].grid(column=0,row=0, pady=(20,20))
        self.GUI['buttonFrame'].grid(column=0,row=1)    
        self.GUI['entryFrame'].grid(column=0,row=2)
        self.GUI['menuFrame'].grid(column=0,row=3, pady=(20,20))


    def create_MENU(self):
        #MENU CREATION
        #==============================
        self.MENU = {}
        self.TYPES = {}

        #Buttons to set what the transaction type is
        for transType in assetclasslib[self.a.split('z')[1]]['validTrans']:
            self.TYPES[transType] =   tk.Button(self.GUI['buttonFrame'], font=settings('font',0.5), bg=palette(transType), text=transType.capitalize(), command=p(self.comm_type, transType))

        #SAVE/CANCEL buttons
        self.MENU['save'] = tk.Button(self.GUI['menuFrame'], text='Save', bg=palette('entry'), fg='#00ff00', font=settings('font'), command=self.comm_save)
        self.MENU['cancel'] = tk.Button(self.GUI['menuFrame'], text='Cancel', bg=palette('entry'), fg='#ff0000', font=settings('font'), command=self.comm_cancel)
        self.MENU['delete'] = tk.Button(self.GUI['menuFrame'], text='Delete', bg='#ff0000', fg='#000000', font=settings('font'), command=self.comm_deleteTrans)


        #MENU RENDERING
        #==============================

        #Buttons to set what the transaction type is
        order = 0
        for transButton in self.TYPES:
            self.TYPES[transButton].grid(row=0,column=order)
            order += 1

        #SAVE/CANCEL buttons
        self.MENU['save'].pack(side='left')
        self.MENU['cancel'].pack(side='left')
        if self.oldID != 1:
            self.MENU['delete'].pack(side='left')


    def create_ENTRIES(self):  
        #STRING VARIABLES
        #==============================
        self.TEMP = {       #These are the default values for all inputs            
            'type':         tk.StringVar(self, value='purchase'),
            'desc':         tk.StringVar(self, value=''),
        #this is the time, right now
            'date':         tk.StringVar(self, value=str(datetime.now())[0:4]+'/'+str(datetime.now())[5:7]+'/'+str(datetime.now())[8:10]+' '+str(datetime.now())[11:13]+':'+str(datetime.now())[14:16]+':'+str(datetime.now())[17:19]),
            'wallet':       tk.StringVar(self, value='-NO WALLET SELECTED-'), #CHANGE THIS - there always has to be at least one wallet
            'wallet2':      tk.StringVar(self, value='-NO WALLET SELECTED-'), 
            'tokens':       tk.StringVar(self, value=''), 
            'usd':          tk.StringVar(self, value=''), 
            'price':        tk.StringVar(self, value=''), 
        }
        if self.oldID != 1:  #If not NEW, replace default value with what you're actually editing
            for key in PERM['assets'][self.a]['trans'][self.oldID]:
                self.TEMP[key].set(PERM['assets'][self.a]['trans'][self.oldID][key])
            self.TEMP['date'].set(self.oldID)

        self.autoprice = tk.StringVar(self, value='')   #This is the helpful display price for purchases and sales, which automatically adjusts to the user's entries
        self.autoUSD = tk.StringVar(self, value='')   #This is the helpful display USD for gifts and expenses, which automatically adjusts to the user's entries


        #WIDGETS
        #==============================
        self.ENTRIES = {}
        self.LABELS = {}

        #ENTRIES
        #==============
        widthsetting = 24

        self.autopriceEntry = tk.Entry(self.GUI['entryFrame'], textvariable = self.autoprice, state='disabled', width = widthsetting, bg=palette('entry'), fg=palette('entrytext'), insertbackground=palette('entrycursor'), disabledbackground=palette('dark'), disabledforeground=palette('entrycursor'), font=settings('font'))
        self.autoUSDEntry = tk.Entry(self.GUI['entryFrame'], textvariable = self.autoUSD, state='disabled', width = widthsetting, bg=palette('entry'), fg=palette('entrytext'), insertbackground=palette('entrycursor'), disabledbackground=palette('dark'), disabledforeground=palette('entrycursor'), font=settings('font'))


        self.ENTRIES['date'] = tk.Entry(self.GUI['entryFrame'], textvariable=self.TEMP['date'], width=widthsetting, justify='center', bg=palette('entry'), fg=palette('entrytext'), insertbackground=palette('entrycursor'), disabledbackground=palette('dark'), disabledforeground=palette('entrycursor'), font=settings('font'))
        for entry in ['tokens','usd','price']:
            self.ENTRIES[entry] = tk.Entry(self.GUI['entryFrame'], textvariable=self.TEMP[entry], width=widthsetting, bg=palette('entry'), fg=palette('entrytext'), insertbackground=palette('entrycursor'), disabledbackground=palette('dark'), disabledforeground=palette('entrycursor'), font=settings('font'))
        self.ENTRIES['desc'] = tk.Text(self.GUI['entryFrame'], wrap='word', bg=palette('entry'), fg=palette('entrytext'), insertbackground=palette('entrycursor'), font=settings('font'), height=8,width=widthsetting)
        self.ENTRIES['desc'].insert(0.0, self.TEMP['desc'].get())
        
        def alphaKey(e):        #creates a sorted list of all the current wallets
                return e.lower()
        walletList = []
        for w in PERM['wallets']:
            walletList.append(w)
        walletList.sort(key=alphaKey)
        walletList.insert(0, '-NO WALLET SELECTED-')

        self.ENTRIES['wallet'] = tk.OptionMenu(self.GUI['entryFrame'], self.TEMP['wallet'], *walletList)
        self.ENTRIES['wallet'].configure(bg=palette('entry'), fg=palette('entrycursor'), font=settings('font'), highlightthickness=0)

        self.ENTRIES['wallet2'] = tk.OptionMenu(self.GUI['entryFrame'], self.TEMP['wallet2'], *walletList)
        self.ENTRIES['wallet2'].configure(bg=palette('entry'), fg=palette('entrycursor'), font=settings('font'), highlightthickness=0)


        #Entry restrictions
        def validDate(d):       #dear fuck why is this so complicated to perform!!!!!!!
            self.ENTRIES['date'].selection_clear()
            i = self.ENTRIES['date'].index('insert')
            if len(d.get()) < 19:
                d.insert(i, '0')
                d.insert(i, '0')
                self.ENTRIES['date'].icursor(i)
                for ignore in ['/',' ',':']:
                    if d.get()[i-1] == ignore:
                        self.ENTRIES['date'].icursor(i-1)
            elif not d.get()[i-1].isdigit():
                d.delete(i-1)
                return
            elif i > 19:
                d.delete(19)
                return
            for ignore in ['/',' ',':']:
                if d.get()[i] == ignore:
                    e = d.get()[i-1]
                    d.delete(i-1)
                    d.delete(i)
                    d.insert(i, e)
                    self.ENTRIES['date'].icursor(i+1)
                    return
            d.delete(i)
        def validDate2(char):
            if len(char) > 1 or not char.isdigit():
                return False    
            return True
        
        valDate = self.register(validDate2)
        self.ENTRIES['date'].configure(validate='key', vcmd=(valDate, '%S'))
        self.TEMP['date'].trace('w', lambda name, index, mode, sv=self.ENTRIES['date']: validDate(sv))
             
            
        def validFloat(new, char):
            if char == ' ':                         # no spaces
                return False
            if new == '' or new == '.':             #these just become 0 when saving
                    return True
            try: 
                float(new)  #must be convertible to a number
                if float(new) < 0:                      #cant be negative
                    return False
                return True
            except:
                return False
        valFloat = self.register(validFloat)
        #Applies typing restrictions to tokens/usd/price entries
        for entry in ['tokens','usd', 'price']:
            self.ENTRIES[entry].configure(validate='key', vcmd=(valFloat, '%P', '%S'))

        #Applies autoprice and autousd to tokens/usd and tokens/price respectively, both a convenient display for the user
        for entry in ['tokens','usd',]:
            self.TEMP[entry].trace('w', lambda name, index, mode: self.updateAutoPrice())
        for entry in ['tokens','price',]:
            self.TEMP[entry].trace('w', lambda name, index, mode: self.updateAutoUSD())
        


        #LABELS
        #==============
        labelText = ['Description','Date','Wallet','Destination Wallet',self.a.split('z')[0],'USD','Price']
        labelKeys = ['desc','date','wallet','wallet2','tokens','usd','price']
        for key in range(len(labelKeys)):
            self.LABELS[labelKeys[key]] = tk.Label(self.GUI['entryFrame'], text=labelText[key], bg=palette('light'), fg=palette('entrycursor'), font=settings('font',0.5))


    def render_ENTRIES(self):
        transaction_type = self.TEMP['type'].get()

        #Appropriately colors the background
        self.GUI['transEditorFrame'].configure(bg=palette(transaction_type))
        self.GUI['title'].configure(bg=palette(transaction_type))
        
        for slave in self.GUI['entryFrame'].grid_slaves():
            slave.grid_forget()
        self.autopriceEntry.grid_forget()
        self.autoUSDEntry.grid_forget()

        #ENTRIES
        #==============
        #Time and Date
        self.LABELS['date'].grid(column=0,row=0, sticky='NSEW')
        self.ENTRIES['date'].grid(column=1,row=0)
        self.ENTRIES['date'].configure(state='normal', textvariable=self.TEMP['date'])
        
        #Wallet
        self.LABELS['wallet'].grid(column=0,row=1, sticky='NS')
        self.ENTRIES['wallet'].grid(column=1,row=1, sticky='NSEW')

        #Wallet2
        if transaction_type == 'transfer':
            self.LABELS['wallet2'].grid(column=0,row=2, sticky='NS')
            self.ENTRIES['wallet2'].grid(column=1,row=2, sticky='NSEW')
        
        #Tokens
        self.LABELS['tokens'].grid(column=0,row=3, sticky='NS')
        self.ENTRIES['tokens'].grid(column=1,row=3, sticky='NS')

        #USD
        if transaction_type in ['purchase', 'sale']:
            self.LABELS['usd'].grid(column=0,row=4, sticky='NS')
            self.ENTRIES['usd'].grid(column=1,row=4, sticky='NS')
        elif transaction_type in ['gift', 'expense']:
            self.LABELS['usd'].grid(column=0,row=4, sticky='NS')
            self.autoUSDEntry.grid(column=1,row=4, sticky='NS')
            self.updateAutoUSD()

        #Price
        if transaction_type in ['purchase', 'sale']:
            self.LABELS['price'].grid(column=0,row=5, sticky='NS')
            self.autopriceEntry.grid(column=1,row=5, sticky='NS')
            self.updateAutoPrice()
        elif transaction_type in ['gift', 'expense']:
            self.LABELS['price'].grid(column=0,row=5, sticky='NS')
            self.ENTRIES['price'].grid(column=1,row=5, sticky='NS')

        #Description
        self.LABELS['desc'].grid(column=0,row=6, sticky='NS')
        self.ENTRIES['desc'].grid(column=1,row=6, sticky='NS')


    def updateAutoPrice(self):
        tokens = self.ENTRIES['tokens'].get()
        usd = self.ENTRIES['usd'].get()
        if tokens in ['', '.'] or mp.almosteq(precise(tokens), precise(0)):     return  #We have to stop the calculation if tokens == 0, cause then we'd divide by 0
        if usd in ['', '.']:                                                    usd = 0
        self.autoprice.set(precise(usd)/precise(tokens))

    def updateAutoUSD(self):
        tokens = self.ENTRIES['tokens'].get()
        price = self.ENTRIES['price'].get()
        if tokens in ['', '.']:     tokens = 0
        if price in ['', '.']:      price = 0
        self.autoUSD.set(precise(tokens)*precise(price))

    def comm_type(self, type):
        self.TEMP['type'] = tk.StringVar(self, value=type)
        self.render_ENTRIES()

    def comm_deleteTrans(self):
        PERM['assets'][self.a]['trans'].pop(self.oldID)             #removal from logical asset
        self.upper.undo_save()
        self.upper.metrics_ASSET(self.a)
        self.upper.market_metrics_ASSET(self.a)
        self.upper.render(self.a, True)
        self.comm_cancel()



    def comm_save(self):
        #DATA CULLING AND CONVERSION PART I
        #==============================
        #converts all tk.StringVar's to their proper final format
        TEMP2 = {}
        for string in self.TEMP:
            TEMP2[string] = self.TEMP[string].get().lstrip().rstrip()
        TEMP2['desc'] = self.ENTRIES['desc'].get(1.0,'end').lstrip().rstrip()

        #converts number entries to 0 if equivalent to '' or '.'
        for string in ['tokens','usd','price']:
            if TEMP2[string] in ['', '.']:
                TEMP2[string] = '0'

        #This is what the transaction ID will be
        ID = TEMP2['date']

        #Removes data irrelevant to this specific transaction type
        for data in list(TEMP2):
            if data not in translib[TEMP2['type']]:
                TEMP2.pop(data)

        # CHECKS
        #==============================
        error = None
        #new ID will be unique?
        for t in PERM['assets'][self.a]['trans']:
            if t == ID and t != self.oldID:
                error = p(MessageBox, self, 'ERROR!', 'A transaction already exists with this time and date for '+self.a.split('z')[0]+'!')

        #valid date format?
        try:        datetime( int(ID[:4]), int(ID[5:7]), int(ID[8:10]), int(ID[11:13]), int(ID[14:16]), int(ID[17:19]) )
        except:     error = p(MessageBox, self, 'ERROR!', 'Invalid date!')

        #selected a wallet? (start out with nothing selected)
        if TEMP2['wallet'] == '-NO WALLET SELECTED-':
            error = p(MessageBox, self, 'ERROR!', 'No wallet was selected')
        #selected a wallet2? (start out with nothing selected)
        if TEMP2['type'] == 'transfer':
            if TEMP2['wallet2'] == '-NO WALLET SELECTED-':
                error = p(MessageBox, self, 'ERROR!', 'No destination wallet was selected')
            if TEMP2['wallet2'] == TEMP2['wallet']:
                error = p(MessageBox, self, 'ERROR!', 'You cannot transfer from a wallet to itself! A transfer from a wallet to itself isn\'t really a transfer at all, yeah? ')

        #Tokens is non-zero?
        if mp.almosteq(precise(TEMP2['tokens']),0):
            error = p(MessageBox, self, 'ERROR!', 'Tokens must be non-zero!')

        #USD is non-zero for purchases and sales?
        if TEMP2['type'] in ['purchase', 'sale']:
            if mp.almosteq(precise(TEMP2['usd']),0):
                error = p(MessageBox, self, 'ERROR!', 'USD must be non-zero!')
        
        #Price is non-zero for gifts and expenses?
        if TEMP2['type'] in ['gift','expense']:
            if mp.almosteq(precise(TEMP2['price']),0):
                error = p(MessageBox, self, 'ERROR!', 'Price must be non-zero!')

        if error != None:
            error()
            return
        


        #TRANSACTION SAVING AND OVERWRITING
        #==============================
        #check: has the ID been changed, or is the transaction new?? if ID change: insert new one with this data, delete old transaction. if new, just update the information
        
        #Creates a new transaction or overwrites the old one
        PERM['assets'][self.a]['trans'][ID] = TEMP2       
        #Removes the old transaction if we've changed the date AKA the ID
        if self.oldID not in [1, ID]:        PERM['assets'][self.a]['trans'].pop(self.oldID)


        self.upper.undo_save()
        self.upper.metrics_ASSET(self.a)
        self.upper.market_metrics_ASSET(self.a)
        self.upper.render(self.a, True)
        self.comm_cancel()

    def _esc(self,event):    #Exit this window
        self.comm_cancel()
    def comm_cancel(self):  
        self.upper.grab_set()
        self.upper.focus_set()
        self.destroy()  #no extra commands, so that closing the window is functionally identical to cancellation






