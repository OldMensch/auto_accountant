#In-house
from AAlib import marketdatalib
from AAmarketData import getMissingPrice, startMarketDataLoops
from AAimport import *
from AAdialogues import *
from AAtooltip import ToolTipWindow


#Default Python
import tkinter as tk
from functools import partial as p
from tkinter.filedialog import *
import os
import math

import threading

class AutoAccountant(tk.Tk):
    def __init__(self):
        super().__init__()
        loadSettings()
        initializeIcons()
        self.configure(bg=palette('error')) #you should NOT see this color (except when totally re-rendering all the assets)
        self.protocol('WM_DELETE_WINDOW', self.comm_quit) #makes closing the window identical to hitting cancel
        self.grab_set()
        self.focus_set()              #This window is brought to to forefront
        self.title('Portfolio Manager')
        
        self.undoRedo = [0, 0, 0]  #index of first undosave, index of last undosave, index of currently loaded undosave
        self.rendered = ('portfolio', None) #'portfolio' renders all the assets. 'asset' combined with the asset tickerclass renders that asset
        self.page = 0 #This indicates which page of data we're on. If we have 600 assets and 30 per page, we will have 20 pages.
        self.sorted = []
        self.GRID_SELECTION = [-1, -1]
        self.ToolTips = ToolTipWindow()
        self.universal_GRID_height = None

        self.create_GUI()
        self.create_taskbar()
        self.create_MENU()

        self.online_event = threading.Event()

        #Try to load last-used JSON file, if the file works and we have it set to start with the last used portfolio
        if setting('startWithLastSaveDir') and os.path.isfile(setting('lastSaveDir')):    self.comm_loadPortfolio(setting('lastSaveDir'))
        else:                                                                               self.comm_newPortfolio(first=True)

        #Now that the hard data is loaded, we need market data
        if setting('offlineMode'):
            #If in Offline Mode, try to load any saved offline market data. If there isn't a file... loads nothing.
            try:
                marketdatalib.update(json.load(open('#OfflineMarketData.json', 'r')))
                self.GUI['offlineIndicator'].config(text='OFFLINE MODE - Data from ' + marketdatalib['_timestamp'][0:16])
                self.GUI['offlineIndicator'].pack(side='right') #Turns on a bright red indicator, which lets you know you're in offline mode
                self.market_metrics()
                self.render(sort=True)
            except:
                self.online_event.set()
                print('||ERROR|| Failed to load offline market data! Change the setting to go online.')
        else:
            self.online_event.set()

        #We always turn on the threads for gethering market data. Even without internet, they just wait for the internet to turn on.
        startMarketDataLoops(self, self.online_event)

        #GLOBAL BINDINGS
        #==============================
        self.bind('<MouseWheel>', self._mousewheel)
        self.bind('<Control-z>', self._ctrl_z)
        self.bind('<Control-y>', self._ctrl_y)
        self.bind('<Escape>', self._esc)
        self.bind('<Delete>', self._del)

        self.geometry('%dx%d+%d+%d' % (setting('portWidth')/2, setting('portHeight')/2, self.winfo_x()-self.winfo_rootx(),0))#slaps this window in the upper-left-hand corner of the screen
        self.state('zoomed') #starts the window maximized (not same as fullscreen!)


#NOTE: Tax forms have been temporarily disabled to speed up boot time until I implement a better method

#TASKBAR, LOADING SAVING MERGING and QUITTING
#=============================================================
    def create_taskbar(self):
        self.TASKBAR = {}
        self.TASKBAR['taskbar'] = tk.Menu(self, tearoff=0)     #The big white bar across the top of the window
        self.configure(menu=self.TASKBAR['taskbar'])

        #'File' Tab
        self.TASKBAR['file'] = tk.Menu(self, tearoff=0)
        self.TASKBAR['taskbar'].add_cascade(menu=self.TASKBAR['file'], label='File')
        self.TASKBAR['file'].add_command(label='New',     command=self.comm_newPortfolio)
        self.TASKBAR['file'].add_command(label='Load...',    command=self.comm_loadPortfolio)
        self.TASKBAR['file'].add_command(label='Save',    command=self.comm_savePortfolio)
        self.TASKBAR['file'].add_command(label='Save As...', command=p(self.comm_savePortfolio, True))
        self.TASKBAR['file'].add_command(label='Merge Portfolio', command=self.comm_mergePortfolio)
        importmenu = tk.Menu(self, tearoff=0)
        self.TASKBAR['file'].add_cascade(menu=importmenu, label='Import')
        importmenu.add_command(label='Import Binance History',      command=self.comm_import_binance)
        importmenu.add_command(label='Import Coinbase History',     command=self.comm_import_coinbase)
        importmenu.add_command(label='Import Coinbase Pro History', command=self.comm_import_coinbase_pro)
        importmenu.add_command(label='Import Etherscan History',    command=self.comm_import_etherscan)
        importmenu.add_command(label='Import Gemini History',       command=self.comm_import_gemini)
        importmenu.add_command(label='Import Gemini Earn History',  command=self.comm_import_gemini_earn)
        importmenu.add_command(label='Import Yoroi Wallet History', command=self.comm_import_yoroi)
        self.TASKBAR['file'].add_separator()
        self.TASKBAR['file'].add_command(label='QUIT', command=self.comm_quit)

        #'Settings' Tab
        self.TASKBAR['settings'] = tk.Menu(self, tearoff=0)
        self.TASKBAR['taskbar'].add_cascade(menu=self.TASKBAR['settings'], label='Settings')
        #self.TASKBAR['settings'].add_command(label='Restore Default Settings', command=self.restoreDefaultSettings)

        def toggle_offline_mode():
            set_setting('offlineMode',not setting('offlineMode'))
            if setting('offlineMode'): #Changed to Offline Mode
                json.dump(marketdatalib, open('#OfflineMarketData.json', 'w'), indent=4, sort_keys=True)
                self.online_event.clear()
                self.GUI['offlineIndicator'].config(text='OFFLINE MODE - Data from ' + marketdatalib['_timestamp'][0:16])
                self.GUI['offlineIndicator'].pack(side='right') #Turns on a bright red indicator, which lets you know you're in offline mode
            else:                           #Changed to Online Mode
                self.online_event.set()
                self.GUI['offlineIndicator'].forget() #Removes the offline indicator

        self.TASKBAR['settings'].values = {}

        self.TASKBAR['settings'].values['offlineMode'] = tk.BooleanVar(value=setting('offlineMode'))
        self.TASKBAR['settings'].add_checkbutton(label='Offline Mode', command=toggle_offline_mode, variable=self.TASKBAR['settings'].values['offlineMode'])


        #'About' Tab
        self.TASKBAR['about'] = tk.Menu(self, tearoff=0)
        self.TASKBAR['taskbar'].add_cascade(menu=self.TASKBAR['about'], label='About')
        self.TASKBAR['about'].add_command(label='MIT License', command=self.comm_copyright)

        #'Info' Tab
        self.TASKBAR['info'] = tk.Menu(self, tearoff=0)
        self.TASKBAR['taskbar'].add_cascade(menu=self.TASKBAR['info'], label='Info')

        def toggle_header(info):
            if info in setting('header_portfolio'):    self.hide_info(info)
            else:                                       self.show_info(info)

        self.TASKBAR['info'].values = {}
        for info in assetinfolib:
            self.TASKBAR['info'].values[info] = tk.BooleanVar(value=info in setting('header_portfolio')) #Default value true if in the header list
            self.TASKBAR['info'].add_checkbutton(label=assetinfolib[info]['name'], command=p(toggle_header, info), variable=self.TASKBAR['info'].values[info])

        #'Accounting' Tab
        self.TASKBAR['accounting'] = tk.Menu(self, tearoff=0)
        self.TASKBAR['taskbar'].add_cascade(menu=self.TASKBAR['accounting'], label='Accounting')
        def set_accounting_method(method):
            set_setting('accounting_method', method)
            self.metrics()
            self.render(sort=True)
        self.accounting_method = tk.StringVar()
        self.accounting_method.set(setting('accounting_method'))
        self.TASKBAR['accounting'].add_radiobutton(label='First in First Out (FIFO)',       variable=self.accounting_method, value='fifo',    command=p(set_accounting_method, 'fifo'))
        self.TASKBAR['accounting'].add_radiobutton(label='Last in First Out (LIFO)',        variable=self.accounting_method, value='lifo',    command=p(set_accounting_method, 'lifo'))
        self.TASKBAR['accounting'].add_radiobutton(label='Highest in First Out (HIFO)',     variable=self.accounting_method, value='hifo',    command=p(set_accounting_method, 'hifo'))

        #'Taxes' Tab
        self.TASKBAR['taxes'] = tk.Menu(self, tearoff=0)
        self.TASKBAR['taskbar'].add_cascade(menu=self.TASKBAR['taxes'], label='Taxes')
        self.TASKBAR['taxes'].add_command(label='Generate data for IRS Form 8949', command=self.tax_Form_8949)
        self.TASKBAR['taxes'].add_command(label='Generate data for IRS Form 1099-MISC', command=self.tax_Form_1099MISC)

        #'DEBUG' Tab
        self.TASKBAR['DEBUG'] = tk.Menu(self, tearoff=0)
        self.TASKBAR['taskbar'].add_cascade(menu=self.TASKBAR['DEBUG'], label='DEBUG')
        self.TASKBAR['DEBUG'].add_command(label='Export TEMP to DEBUG.json',     command=self.DEBUG_print_TEMP)
        self.TASKBAR['DEBUG'].add_command(label='DEBUG dialogue box',     command=self.DEBUG_dialogue)
        self.TASKBAR['DEBUG'].add_command(label='DEBUG find all missing price data',     command=self.DEBUG_find_all_missing_prices)
        self.TASKBAR['DEBUG'].add_command(label='DEBUG delete all transactions, by wallet',     command=self.DEBUG_delete_all_of_asset)
        #debugmenu.add_command(label='Restart Auto-Accountant',     command=self.DEBUG_restart_test)

        
    def tax_Form_8949(self):
        dir = asksaveasfilename( defaultextension='.CSV', filetypes={('CSV','.csv')}, title='Save data for IRS Form 8949')
        if dir == '':   return
        self.metrics(tax_report='8949')
        open(dir, 'w', newline='').write(TEMP['taxes']['8949'].to_csv())
    def tax_Form_1099MISC(self):
        dir = asksaveasfilename( defaultextension='.CSV', filetypes={('CSV','.csv')}, title='Save data for IRS Form 1099-MISC')
        if dir == '':   return
        self.metrics(tax_report='1099-MISC')
        open(dir, 'w', newline='').write(TEMP['taxes']['1099-MISC'].to_csv())


    def DEBUG_print_TEMP(self):
        toWrite = str(TEMP).replace('<','\'').replace('>','\'').replace('\'','\'')
        open('DEBUG.json', 'w').write(toWrite)
        toDump = json.load(open('DEBUG.json', 'r'))
        json.dump(toDump, open('DEBUG.json', 'w'), sort_keys=True, indent=4)
    def DEBUG_dialogue(self):
        testdialogue = Dialogue(self, 'Dialogue Title')
        testdialogue.add_menu_button('close', command=testdialogue.close)
        testdialogue.add_label(0, 0, 'dayte:')
        testdialogue.add_label(0, 1, 'positive float: ')
        testdialogue.add_label(0, 2, 'float: ')
        testdialogue.add_label(0, 3, 'one-liner:')
        testdialogue.add_label(0, 4, 'description:')
        date = testdialogue.add_entry(1, 0, '0000/00/00 00:00:00', format='date')
        posfloat = testdialogue.add_entry(1, 1, '', format='pos_float', charLimit=16)
        float = testdialogue.add_entry(1, 2, '', format='float', charLimit=16)
        text = testdialogue.add_entry(1, 3, '', charLimit=10)
        desc = testdialogue.add_entry(1, 4, 'a\nb\nc', format='description')
        def printdata():    print(desc.entry())
        testdialogue.add_menu_button('print data', command=printdata)
        testdialogue.center_dialogue()
    def DEBUG_restart_test(self):
        self.destroy()
    def DEBUG_find_all_missing_prices(self):
        for t in MAIN_PORTFOLIO.transactions():
            DATE = t.date()
            missing = t.get('missing')[1]
            if 'loss_price' in missing:   t._data['loss_price'] = getMissingPrice(DATE, t._data['loss_asset'])
            if 'fee_price' in missing:    t._data['fee_price'] =  getMissingPrice(DATE, t._data['fee_asset'])
            if 'gain_price' in missing:   t._data['gain_price'] = getMissingPrice(DATE, t._data['gain_asset'])
            t.recalculate()
        self.metrics()
        self.render(sort=True)
    def DEBUG_delete_all_of_asset(self):
        for transaction in list(MAIN_PORTFOLIO.transactions()):
            if transaction.wallet() == 'Binance':
                MAIN_PORTFOLIO.delete_transaction(transaction.get_hash())
        self.metrics()
        self.render(sort=True)

    def comm_import_binance(self, wallet=None):
        if wallet == None:    ImportationDialogue(self, self.comm_import_binance, 'Binance Wallet') 
        else:
            dir = askopenfilename( filetypes={('CSV','.csv')}, title='Import Binance Transaction History')
            if dir == '':   return
            import_binance(self, dir, wallet)
    def comm_import_coinbase(self, wallet=None):
        if wallet == None:    ImportationDialogue(self, self.comm_import_coinbase, 'Coinbase Wallet') 
        else:
            dir = askopenfilename( filetypes={('CSV','.csv')}, title='Import Coinbase Transaction History')
            if dir == '':   return
            import_coinbase(self, dir, wallet)
    def comm_import_coinbase_pro(self, wallet=None):
        if wallet == None:    ImportationDialogue(self, self.comm_import_coinbase_pro, 'Coinbase Pro Wallet') 
        else:
            dir = askopenfilename( filetypes={('CSV','.csv')}, title='Import Coinbase Pro Transaction History')
            if dir == '':   return
            import_coinbase_pro(self, dir, wallet)
    def comm_import_etherscan(self, wallet=None):
        if wallet == None:    ImportationDialogue(self, self.comm_import_etherscan, 'Ethereum Wallet') 
        else:
            ETHdir = askopenfilename( filetypes={('CSV','.csv')}, title='Import Etherscan ETH Transaction History')
            if ETHdir == '':   return
            ERC20dir = askopenfilename( filetypes={('CSV','.csv')}, title='Import Etherscan ERC-20 Transaction History')
            if ERC20dir == '':   return
            import_etherscan(self, ETHdir, ERC20dir, wallet)
    def comm_import_gemini(self, wallet=None):
        if wallet == None:    ImportationDialogue(self, self.comm_import_gemini, 'Gemini Wallet') 
        else:
            dir = askopenfilename( filetypes={('XLSX','.xlsx')}, title='Import Gemini Transaction History')
            if dir == '':   return
            import_gemini(self, dir, wallet)
    def comm_import_gemini_earn(self, wallet=None):
        if wallet == None:    ImportationDialogue(self, self.comm_import_gemini_earn, 'Gemini Earn Wallet') 
        else:
            dir = askopenfilename( filetypes={('XLSX','.xlsx')}, title='Import Gemini Earn Transaction History')
            if dir == '':   return
            import_gemini_earn(self, dir, wallet)
    def comm_import_yoroi(self, wallet=None):
        if wallet == None:    ImportationDialogue(self, self.comm_import_yoroi, 'Yoroi Wallet') 
        else:
            dir = askopenfilename( filetypes={('CSV','.csv')}, title='Import Yoroi Wallet Transaction History')
            if dir == '':   return
            import_yoroi(self, dir, wallet)


    def comm_savePortfolio(self, saveAs=False, secondary=None):
        if saveAs or setting('lastSaveDir') == '':
            dir = asksaveasfilename( defaultextension='.JSON', filetypes={('JSON','.json')}, title='Save Portfolio')
        else:
            dir = setting('lastSaveDir')
        if dir == '':
            return
        self.title('Portfolio Manager - ' + dir)
        json.dump(MAIN_PORTFOLIO.toJSON(), open(dir, 'w'), sort_keys=True)
        if secondary:   secondary()
        if saveAs:      set_setting('lastSaveDir', dir)
    def comm_newPortfolio(self, first=False):
        set_setting('lastSaveDir', '')
        MAIN_PORTFOLIO.clear()
        self.title('Portfolio Manager')
        self.profile = ''   #name of the currently selected profile. Always starts with no filter applied.
        self.metrics()
        self.render(('portfolio',None), True)
        if not first:   self.undo_save()
    def comm_loadPortfolio(self, dir=None):
        if dir == None: dir = askopenfilename( filetypes={('JSON','.json')}, title='Load Portfolio')
        if dir == '':   return
        try:    decompile = json.load(open(dir, 'r'))    #Attempts to load the file
        except:
            Message(self, 'Error!', 'File couldn\'t be loaded. Probably corrupt or something.' )
            self.comm_newPortfolio(first=True)
            return
        MAIN_PORTFOLIO.loadJSON(decompile)
        self.title('Portfolio Manager - ' + dir)
        set_setting('lastSaveDir', dir)
        self.profile = ''   #name of the currently selected profile. Always starts with no filter applied.
        self.metrics()
        self.render(('portfolio',None), True)
        self.undo_save()  
    def comm_mergePortfolio(self): #Doesn't overwrite current portfolio by default.
        dir = askopenfilename( filetypes={('JSON','.json')}, title='Load Portfolio for Merging')
        if dir == '':
            return
        try:
            decompile = json.load(open(dir, 'r'))    #Attempts to load the file
        except:
            Message(self, 'Error!', '\'file\' is an unparseable JSON file. Probably missing commas or brackets.' )
            return
        MAIN_PORTFOLIO.loadJSON(decompile, True, False)
        set_setting('lastSaveDir', '') #resets the savedir. who's to say where a merged portfolio should save to? why should it be the originally loaded file, versus any recently merged ones?
        self.title('Portfolio Manager')
        self.profile = ''   #name of the currently selected profile. Always starts with no filter applied.
        self.metrics()
        self.render(('portfolio',None), True)
        self.undo_save()

    def comm_quit(self, finalize=False):
        '''Quits the program. Set finalize to TRUE to skip the \'are you sure?' prompt.'''
        if not finalize:   
            if self.isUnsaved():
                unsavedPrompt = Prompt(self, 'Unsaved Changes', 'Are you sure you want to quit? This cannot be undone!')
                unsavedPrompt.add_menu_button('Quit', bg='#ff0000', command=p(self.comm_quit, True) )
                unsavedPrompt.add_menu_button('Save and Quit', bg='#0088ff', command=p(self.comm_savePortfolio, secondary=p(self.comm_quit, True)))
                unsavedPrompt.center_dialogue()
            else:
                self.comm_quit(True)
        else:
            #also, closing the program always saves the settings!
            saveSettings()
            exit(1)

    def isUnsaved(self):
        lastSaveDir = setting('lastSaveDir')
        if MAIN_PORTFOLIO.isEmpty(): #there is nothing to save, thus nothing is unsaved     
            return False
        elif lastSaveDir == '': 
            return True     #If you haven't saved anything yet, then yes, its 100% unsaved
        elif not os.path.isfile(lastSaveDir):
            return True     #Only happens if you deleted the file that the program was referencing, while using the program
        lastSaveHash = hash(json.dumps(json.load(open(lastSaveDir, 'r')))) #hash for last loaded file
        currentDataHash = hash(json.dumps(MAIN_PORTFOLIO.toJSON(), sort_keys=True))
        if currentDataHash == lastSaveHash:
            return False    #Hashes are the same, file is most recent copy
        else:
            return True     #Hashes are different, file is modified


#OVERARCHING GUI FRAMEWORK
#=============================================================
    def create_GUI(self):
        #GUI CREATION
        #==============================
        self.GUI = {}
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        #contains the menu
        self.GUI['menuFrame'] = tk.Frame(self, bg=palette('menudark'))
        #contains the big title and overall stats for the portfolio/asset 
        self.GUI['primaryFrame'] = tk.Frame(self, bg=palette('accentdark'))
        self.GUI['title'] = tk.Label(self.GUI['primaryFrame'], width=16, text='Auto-Accountant', font=setting('font', 1.5), fg=palette('entrytext'),  bg=palette('accent'))
        self.GUI['subtitle'] = tk.Label(self.GUI['primaryFrame'], text='Overall Portfolio', font=setting('font', 1), fg=palette('entrycursor'),  bg=palette('accent'))
        self.GUI['buttonFrame'] = tk.Frame(self.GUI['primaryFrame'], bg=palette('accentdark'))
        self.GUI['info'] = tk.Button(self.GUI['buttonFrame'], image=icons('info2'), bg=palette('entry'), command=self.comm_portfolio_info)
        self.GUI['edit'] = tk.Button(self.GUI['buttonFrame'], image=icons('settings2'), bg=palette('entry'))
        self.GUI['new_asset'] =       tk.Button(self.GUI['buttonFrame'], text='+ Asset',  bg=palette('entry'), fg=palette('entrycursor'), font=setting('font'), command=p(AssetEditor, self))
        self.GUI['new_transaction'] = tk.Button(self.GUI['buttonFrame'], text='+ Trans',  bg=palette('entry'), fg=palette('entrycursor'), font=setting('font'), command=p(TransEditor, self))
        self.GUI['info_pane'] = TextBox(self.GUI['primaryFrame'], state='readonly', font=setting('font', 1.5), fg=palette('entrycursor'),  bg=palette('accent'), width=1)
        self.GUI['back'] = tk.Button(self.GUI['primaryFrame'], text='Return to\nPortfolio', font=setting('font', 0.5),  fg=palette('entrycursor'), bg=palette('entry'), command=p(self.render, ('portfolio',None), True))
        self.GUI['page_number'] = tk.Label(self.GUI['primaryFrame'], text='Page XXX of XXX', font=setting('font', 0.5), fg=palette('entrycursor'),  bg=palette('accentdark'))
        self.GUI['page_next'] = tk.Button(self.GUI['primaryFrame'], image=icons('arrow_down'), bg=palette('entry'), command=self.comm_page_next)
        self.GUI['page_last'] = tk.Button(self.GUI['primaryFrame'], image=icons('arrow_up'), bg=palette('entry'), command=self.comm_page_last)
        #contains the list of assets/transactions
        self.GUI['GRIDframe'] = tk.Frame(self, bg=palette('dark'))
        #The little bar on the bottom
        self.GUI['bottomFrame'] = tk.Frame(self, bg=palette('accent'))
        self.GUI['copyright'] = tk.Button(self.GUI['bottomFrame'], bd=0, bg=palette('accent'), text='Copyright © 2022 Shane Evanson', fg=palette('entrycursor'), font=setting('font',0.4), command=self.comm_copyright)
        self.GUI['offlineIndicator'] = tk.Label(self.GUI['bottomFrame'], bd=0, bg='#ff0000', text=' OFFLINE MODE ', fg='#ffffff', font=setting('font',0.4))

        #GUI RENDERING
        #==============================
        self.GUI['menuFrame']       .grid(column=0,row=0, columnspan=2, sticky='EW')

        self.GUI['primaryFrame']    .grid(column=0,row=1, sticky='NS')
        self.GUI['title']           .grid(column=0,row=0, columnspan=2)
        self.GUI['subtitle']        .grid(column=0,row=1, columnspan=2, sticky='EW')
        self.GUI['buttonFrame']     .grid(column=0,row=2, columnspan=2, sticky='EW')
        self.GUI['info']            .pack(side='left')
        self.GUI['new_transaction'] .pack(side='right')
        self.GUI['new_asset']       .pack(side='right')
        self.GUI['info_pane']       .grid(column=0,row=3, columnspan=2, sticky='NSEW')
        self.GUI['primaryFrame'].rowconfigure(3, weight=1)
        self.GUI['page_number']     .grid(column=0,row=5, columnspan=2, sticky='SEW')
        self.GUI['page_last']       .grid(column=0,row=6, sticky='SE')
        self.GUI['page_next']       .grid(column=1,row=6, sticky='SW')
        
        self.GUI['GRIDframe']  .grid(column=1,row=1, sticky='NSEW')
        
        self.GUI['bottomFrame']     .grid(column=0,row=2, columnspan=2, sticky='EW')
        self.GUI['copyright']       .pack(side='left')

    def create_GRID(self):
        '''Initializes the grid of labels which displays all of the information about assets and transactions'''
        #Creates the GRID dictionary, and dictionary for the headers
        TEMP['GRID'] = { 0:{} }

        #for itemsPerPage rows of data...
        for r in range(1, setting('itemsPerPage')+1):
            self.GUI['GRIDframe'].rowconfigure(r, weight=1, uniform='uniform')    #Makes the whole thing stretch vertically to fit the righthand window
            if r not in TEMP['GRID']:   TEMP['GRID'][r] = {}
        #Generates labels for every column we need
        for c in range(len(setting('header_portfolio'))+1): #We always start out on the portfolio page, and thus, we start out with as many columns as there are headers
            self.GRID_add_col()
            
    def GRID_remove_col(self):  #Removing columns is slow, sadly. Not sure how to improve this really
        '''Removes a column of labels from the GRID'''
        lastcol = len(TEMP['GRID'][0])-1
        if lastcol == 0:        return
        for r in TEMP['GRID']:  TEMP['GRID'][r].pop(lastcol).destroy()
    def GRID_add_col(self):
        '''Adds a column of labels to the GRID'''
        lastcol = len(TEMP['GRID'][0])

        #The header
        if lastcol == 0:
            corner = TEMP['GRID'][0][0] = tk.Label(self.GUI['GRIDframe'], text='#', font=setting('font', 0.75), fg=palette('entrytext'), bg=palette('light'), relief='groove', bd=1)
            corner.grid(column=0,row=0, sticky='NSEW')
        else:
            header =  TEMP['GRID'][0][lastcol] = tk.Button(self.GUI['GRIDframe'], command=p(self.set_sort, lastcol-1), font=setting('font', 0.75), fg=palette('entrytext'), bg=palette('light'), relief='groove', bd=1)
            header.bind('<Button-3>', p(self._header_menu, lastcol-1))
            header.grid(row=0, column=lastcol, sticky='NSEW')

        #The rest of the column
        for GRID_ROW in range(1, len(TEMP['GRID'])):
            label = TEMP['GRID'][GRID_ROW][lastcol] = tk.Label(self.GUI['GRIDframe'], font=setting('font'), fg=palette('entrycursor'), bg=palette('dark'), relief='groove', bd=0,anchor='w')
            if lastcol == 0: label.configure(bg=palette('medium'))
            label.grid(row=GRID_ROW, column=lastcol, sticky='EW')
            label.bind('<Button-1>', p(self._left_click_row, GRID_ROW))
            label.bind('<Button-3>', p(self._right_click_row, GRID_ROW))
            label.bind('<Shift-Button-1>', p(self._shift_left_click_row, GRID_ROW))
            label.bind('<Enter>', p(self.color_row, GRID_ROW, None, palette('medium')))
            label.bind('<Leave>', p(self.color_row, GRID_ROW, None, None))
    def GRID_set_col(self, n):
        '''Adds or removes columns until there are \n\ columns. n must be greater than or equal to 0, and this ignores the \'#\' column.'''
        if n < 0: raise Exception('||ERROR|| Cannot set number of columns to less than 1')
        while len(TEMP['GRID'][0])-1 != n:
            curlength = len(TEMP['GRID'][0])-1
            if curlength > n: self.GRID_remove_col()
            if curlength < n: self.GRID_add_col()


    def _header_menu(self, i, event):
        if self.rendered[0] == 'asset':  return  #There is no menu for the transactions ledger view
        info = setting('header_portfolio')[i]
        m = tk.Menu(tearoff = 0)
        if i != 0:                                      m.add_command(label ='Move Left', command=p(self.move_info, info, 'left'))
        if i != len(setting('header_portfolio'))-1:     m.add_command(label ='Move Right', command=p(self.move_info, info, 'right'))
        if i != 0:                                      m.add_command(label ='Move to Beginning', command=p(self.move_info, info, 'beginning'))
        if i != len(setting('header_portfolio'))-1:     m.add_command(label ='Move to End', command=p(self.move_info, info, 'end'))
        m.add_separator()
        m.add_command(label ='Hide ' + assetinfolib[info]['name'], command=p(self.hide_info, info))
        try:        m.tk_popup(event.x_root, event.y_root)
        finally:    m.grab_release()
    def _drag_header(self, i, event):
        None

    def _left_click_row(self, GRID_ROW, event): # Opens up the asset subwindow, or transaction editor upon clicking a label within this row
        #if we double clicked on an asset/transaction, thats when we open it.
        if self.GRID_SELECTION == [GRID_ROW, GRID_ROW]:
            i = self.page*setting('itemsPerPage')+GRID_ROW-1
            try:
                if self.rendered[0] == 'portfolio': self.render(('asset',self.sorted[i]), True)
                else:                               TransEditor(self, self.sorted[i])
            except: return
            self.GRID_clear_selection()
        else:
            self.GRID_clear_selection()
            self.GRID_SELECTION = [GRID_ROW, GRID_ROW]
        self.color_row(GRID_ROW)
    def _right_click_row(self, GRID_ROW, event): # Opens up a little menu of stuff you can do to this asset/transaction
        #we've right clicked with a selection of multiple items
        if self.GRID_SELECTION != [-1, -1] and self.GRID_SELECTION[0] != self.GRID_SELECTION[1]:
            m = tk.Menu(tearoff = 0)
            m.add_command(label ='Delete selection', command=p(self.GRID_delete_selection, self.GRID_SELECTION))
            try:        m.tk_popup(event.x_root, event.y_root)
            finally:    m.grab_release()
        #We've right clicked a single item
        else:
            i = self.page*setting('itemsPerPage')+GRID_ROW-1
            try:
                if self.rendered[0] == 'portfolio':  asset = self.sorted[i]
                else:                   trans = self.sorted[i]
            except: return
            m = tk.Menu(tearoff = 0)
            if self.rendered[0] == 'portfolio':
                ticker = MAIN_PORTFOLIO.asset(asset).ticker()
                m.add_command(label ='Open ' + ticker + ' Ledger', command=p(self.render, ('asset',asset), True))
                m.add_command(label ='Edit ' + ticker, command=p(AssetEditor, self, asset))
                m.add_command(label ='Show detailed info', command=p(self.comm_asset_info, asset))
                m.add_command(label ='Delete ' + ticker, command=p(self.GRID_delete_selection, [GRID_ROW, GRID_ROW]))
            else:
                t = MAIN_PORTFOLIO.transaction(trans)
                m.add_command(label ='Edit ' + t.date(), command=p(TransEditor, self, trans))
                m.add_command(label ='Copy ' + t.date(), command=p(TransEditor, self, trans, True))
                m.add_command(label ='Delete ' + t.date(), command=p(self.GRID_delete_selection, [GRID_ROW, GRID_ROW]))
                if t.ERROR:
                    m.add_separator()
                    m.add_command(label ='ERROR information...', command=p(Message, self, 'Transaction Error!', t.ERR_MSG))
            try:        m.tk_popup(event.x_root, event.y_root)
            finally:    m.grab_release()

    def _shift_left_click_row(self, GRID_ROW, event):
        #We already have a multi-selection. Reset it.
        if self.GRID_SELECTION[0] != self.GRID_SELECTION[1]:                                            #We already have a selection, but clicked again. Reset the selection.
            oldsel = self.GRID_SELECTION
            self.GRID_SELECTION = [GRID_ROW, GRID_ROW]
            for row in range(oldsel[0], oldsel[1]+1):   self.color_row(row)
        #We have no selection. Start it.
        elif self.GRID_SELECTION[0] == -1:   self.GRID_SELECTION = [GRID_ROW, GRID_ROW]                   #This is the first selection we're making
        #We already have a single selection. Expand it.
        elif GRID_ROW > self.GRID_SELECTION[0]:    self.GRID_SELECTION[1] = GRID_ROW
        else:                               self.GRID_SELECTION[0] = GRID_ROW

        #We've changed the selection. Recolor everything.
        for row in range(self.GRID_SELECTION[0], self.GRID_SELECTION[1]+1):   self.color_row(row)
 

    def GRID_clear_selection(self):
        if self.GRID_SELECTION == [-1, -1]: return
        oldsel = self.GRID_SELECTION
        self.GRID_SELECTION = [-1, -1]
        for row in range(oldsel[0], oldsel[1]+1):   self.color_row(row)

    def GRID_delete_selection(self, toDelete, *kwargs):
        if self.rendered[0] == 'asset':
            for item_index in range( self.page*setting('itemsPerPage')+toDelete[0]-1, self.page*setting('itemsPerPage')+toDelete[1]):
                try:    MAIN_PORTFOLIO.delete_transaction(self.sorted[item_index])
                except: continue
        else:
            Message(self, 'Unimplemented', 'You can\'t delete assets from here, for now.')
            return
        self.GRID_SELECTION = [-1, -1]
        self.undo_save()
        self.metrics()
        self.render(sort=True)


    def create_MENU(self):
        #MENU CREATION
        #==============================
        self.MENU = {}

        self.MENU['newPortfolio'] = tk.Button(self.GUI['menuFrame'],  image=icons('new'), bg=palette('entry'), command=self.comm_newPortfolio)
        self.MENU['loadPortfolio'] = tk.Button(self.GUI['menuFrame'], image=icons('load'), bg=palette('entry'), command=self.comm_loadPortfolio)
        self.MENU['savePortfolio'] = tk.Button(self.GUI['menuFrame'], image=icons('save'), bg=palette('entry'), command=self.comm_savePortfolio)
        self.MENU['settings'] = tk.Button(self.GUI['menuFrame'], image=icons('settings2'), bg=palette('entry'), command=p(Message, self, 'whoop',  'no settings menu implemented yet!'))

        self.MENU['undo'] = tk.Button(self.GUI['menuFrame'], image=icons('undo'), bg=palette('entry'), command=p(self._ctrl_z, None))
        self.MENU['redo'] = tk.Button(self.GUI['menuFrame'], image=icons('redo'), bg=palette('entry'), command=p(self._ctrl_y, None))

        self.MENU['wallets'] = tk.Button(self.GUI['menuFrame'], text='Wallets',  bg=palette('entry'), fg=palette('entrycursor'), font=setting('font'), command=p(WalletManager, self))
        self.MENU['addresses'] = tk.Button(self.GUI['menuFrame'], text='Addresses',  bg=palette('entry'), fg=palette('entrycursor'), font=setting('font'), command=p(AddressManager, self))
        self.MENU['profiles'] = tk.Button(self.GUI['menuFrame'], image=icons('profiles'),  bg=palette('entry'), fg=palette('entrycursor'), font=setting('font'),command=p(ProfileManager, self))

        #MENU RENDERING
        #==============================
        self.MENU['newPortfolio']       .grid(column=0,row=0, sticky='NS')
        self.MENU['loadPortfolio']      .grid(column=1,row=0, sticky='NS')
        self.MENU['savePortfolio']      .grid(column=2,row=0, sticky='NS')
        self.MENU['settings']           .grid(column=3,row=0, sticky='NS', padx=(0,setting('font')[1]))

        self.MENU['undo']               .grid(column=4,row=0, sticky='NS')
        self.MENU['redo']               .grid(column=5,row=0, sticky='NS', padx=(0,setting('font')[1]))

        self.MENU['wallets']            .grid(column=8,row=0, sticky='NS')
        self.MENU['addresses']          .grid(column=9,row=0, sticky='NS', padx=(0,setting('font')[1]))

        self.MENU['profiles']           .grid(column=10,row=0, sticky='NS')

        #MENU TOOLTIPS
        #==============================
        menu_tooltips = {
            'newPortfolio':     'Create a new portfolio',
            'loadPortfolio':    'Load an existing portfolio',
            'savePortfolio':    'Save this portfolio',
            'settings':         'Settings',

            'undo':             'Undo last action',
            'redo':             'Redo last action',

            'wallets':          'Manage wallets',
            'addresses':        'Manage addresses',
            'profiles':         'Manage filter profiles',
        }
        for button in self.MENU:
            self.ToolTips.SetToolTip(self.MENU[button] ,menu_tooltips[button])


    def comm_page_next(self):
        if self.rendered[0] == 'portfolio':  maxpage = math.ceil(len(MAIN_PORTFOLIO.assets())/setting('itemsPerPage')-1)
        else:                   maxpage = math.ceil(len(MAIN_PORTFOLIO.asset(self.rendered[1])._ledger)/setting('itemsPerPage')-1)
        if self.page < maxpage: 
            self.page += 1
            self.GRID_clear_selection()
            self.render()
    def comm_page_last(self):
        if self.page > 0: 
            self.page -= 1
            self.GRID_clear_selection()
            self.render()

# PORTFOLIO RENDERING
#=============================================================
    def render(self, toRender=None, sort=False): #TODO: Kinda slow (~250ms for an asset with a ledger with ~500 transactions), inefficiency of GRID and tkinter
        '''Call to render the portfolio, or a ledger
        \ntoRender - tuple of portfolio/asset, and asset name if relevant'''
        #Creates the GRID if it hasn't been yet
        if 'GRID' not in TEMP:      self.create_GRID()

        #If we're trying to render an asset that no longer exists, go back to the main portfolio instead
        if toRender == None:
            if self.rendered[0] == 'asset' and not MAIN_PORTFOLIO.hasAsset(self.rendered[1]):   toRender = ('portfolio',None)
        elif   toRender[0] == 'asset' and not MAIN_PORTFOLIO.hasAsset(toRender[1]):             toRender = ('portfolio',None)

        #These are things that don't need to change unless we're changing the level from PORTFOLIO to ASSET or vice versa
        if toRender != None:
            self.page = 0 #We return to the first page if changing from portfolio to asset or vice versa
            self.GRID_clear_selection()  #Clear the selection too. 
            if toRender[0] == 'portfolio':
                self.GRID_set_col(len(setting('header_portfolio'))) #TODO: Lag here (~30ms), addition of GRID columns is slow
                self.GUI['info'].configure(command=self.comm_portfolio_info)
                self.GUI['edit'].pack_forget()
                self.GUI['new_asset'].pack(side='right')
                self.GUI['back'].grid_forget()
            else:
                self.GRID_set_col(len(setting('header_asset'))) #TODO: Lag here (~150ms), destruction of GRID columns is slow
                self.GUI['info'].configure(command=p(self.comm_asset_info, toRender[1]))
                self.GUI['edit'].configure(command=p(AssetEditor, self, toRender[1]))
                self.GUI['edit'].pack(side='left')
                self.GUI['new_asset'].forget()
                self.GUI['back'].grid(row=4, column=0, columnspan=2)

            #Setting up stuff in the Primary Pane
            if toRender[0] == 'portfolio':
                self.GUI['title'].configure(text='Auto-Accountant')
                self.GUI['subtitle'].configure(text='Overall Portfolio')
            else:      
                self.GUI['title'].configure(text=MAIN_PORTFOLIO.asset(toRender[1]).name())
                self.GUI['subtitle'].configure(text=MAIN_PORTFOLIO.asset(toRender[1]).ticker())
            
            #Sets the asset - 0ms
            self.rendered = toRender

        #Updates the information panel on the lefthand side
        self.update_info_pane()

        #Sorts the assets/transactions
        if sort:    self.sort() #TODO: This is fast (~5ms for ~500 transactions) but could probably be faster

        #Appropriately enabled/diables the page-setting buttons - 0ms
        maxpage = math.ceil(len(self.sorted)/setting('itemsPerPage'))-1
        if maxpage == -1: maxpage = 0
        if self.page < maxpage:     self.GUI['page_next'].configure(state='normal')
        else:                       self.GUI['page_next'].configure(state='disabled')
        if self.page > 0:           self.GUI['page_last'].configure(state='normal')
        else:                       self.GUI['page_last'].configure(state='disabled')
        self.GUI['page_number'].configure(text='Page ' + str(self.page+1) + ' of ' + str(maxpage+1))

        #Appropriately renames the headers
        if self.rendered[0] == 'portfolio':  header = setting('header_portfolio')
        else:                   header = setting('header_asset')
        for i in range(len(header)):
            TEMP['GRID'][0][i+1].configure(text=self.infoLib(self.rendered[1], header[i], 'headername'))

        #Fills in the page with info
        self.populate() # TODO: This is a little slow (~30-80ms for 30 items in the GRID), not sure how to make it fater though

    def update_info_pane(self):
        textbox = self.GUI['info_pane']
        textbox.clear()

        if self.rendered[0] == 'portfolio':
            for info in ['value','day%','unrealized_profit_and_loss','unrealized_profit_and_loss%']:
                textbox.insert_text(portfolioinfolib[info]['headername'], justify='center')
                textbox.newline()
                info_format = portfolioinfolib[info]['format']
                fg_color = MAIN_PORTFOLIO.color(info)[0]
                if fg_color == None: fg_color = palette('neutral')
                if info_format == 'percent':    ending = ' %'
                else: ending = ' USD'
                textbox.insert_triplet('',MAIN_PORTFOLIO.prettyPrint(info).replace('%',''), ending, fg=fg_color, justify='center', font=setting('font2',1.5))
                textbox.newline()
        else:
            for info in ['value','day%','unrealized_profit_and_loss','unrealized_profit_and_loss%']:
                textbox.insert_text(assetinfolib[info]['headername'].replace('\n',' '), justify='center')
                textbox.newline()
                info_format = assetinfolib[info]['format']
                fg_color = MAIN_PORTFOLIO.asset(self.rendered[1]).color(info)[0]
                if fg_color == None: fg_color = palette('neutral')
                if info_format == 'percent':    ending = ' %'
                else: ending = ' USD'
                textbox.insert_triplet('',MAIN_PORTFOLIO.asset(self.rendered[1]).prettyPrint(info).replace('%',''), ending, fg=fg_color, justify='center', font=setting('font2',1.5))
                textbox.newline()

    def populate(self):
        '''Populates the GRID with info'''
        #All the info for every asset 

        for row in range(self.page*setting('itemsPerPage'), (self.page+1)*setting('itemsPerPage')):
            GRID_ROW = (row % setting('itemsPerPage')) + 1
            #Row Number ### 2-10 ms
            TEMP['GRID'][GRID_ROW][0].configure(text=row+1)
            
            #Filling the GRID for each row...
            try:    entry = self.sorted[row] #Entry will be the TICKERCLASS or HASH
            except: entry = None
            if self.rendered[0] == 'portfolio':  headers = setting('header_portfolio')
            else:                   headers = setting('header_asset')
            for info in headers:
                #The GRID text for each column in this row...
                label = TEMP['GRID'][GRID_ROW][headers.index(info)+1]
                if entry == None:           label.configure(text='')
                elif self.rendered[0] == 'portfolio':   label.configure(text=MAIN_PORTFOLIO.asset(entry).prettyPrint(info))
                else:                                   label.configure(text=MAIN_PORTFOLIO.transaction(entry).prettyPrint(info, self.rendered[1]))

            #Colors the GRID for this row
            self.color_row(GRID_ROW)

    def color_row(self, GRID_ROW, fg=None, bg=None, *kwargs):    #Function that colors the nth row, visual_row, 
        #entry will either be nothing (nothing to display at this row in the GRID), or an asset TICKERCLASS, or a transaction HASH
        try:    entry = self.sorted[GRID_ROW-1+self.page*setting('itemsPerPage')]
        except: entry = None

        if self.rendered[0] == 'portfolio': headers = setting('header_portfolio')
        else:                               headers = setting('header_asset')

        #All the info bits
        for info in headers:
            label = TEMP['GRID'][GRID_ROW][headers.index(info)+1]

            #Gathering data that coloring is contingent upon
            if entry:
                # ERROR Background color override - something is wrong with this asset or transaction! probably missing data.
                if (self.rendered[0] == 'portfolio' and MAIN_PORTFOLIO.asset(entry).ERROR) or (self.rendered[0] == 'asset' and MAIN_PORTFOLIO.transaction(entry).ERROR):        
                    label.configure(fg=palette('errortext'), bg=palette('error'))
                    continue
                elif self.rendered[0] == 'portfolio':  
                    color = MAIN_PORTFOLIO.asset(entry).color(info)
                    labeltext = MAIN_PORTFOLIO.asset(entry).prettyPrint(info)
                else:     
                    color = MAIN_PORTFOLIO.transaction(entry).color(info, self.rendered[1])
                    labeltext = MAIN_PORTFOLIO.transaction(entry).prettyPrint(info, self.rendered[1])
            else:
                color = labeltext = (None, None)

            #Foreground Coloring
            if labeltext == MISSINGDATA:        label.configure(fg=palette('missingdata'))
            elif fg:                            label.configure(fg=fg)
            elif color[0] != None:              label.configure(fg=color[0])
            else:                               label.configure(fg=palette('default_info_color'))

            #Background Coloring
            if color[1] != None:                label.configure(bg=color[1])
            elif bg:                            label.configure(bg=bg)
            elif GRID_ROW in range(self.GRID_SELECTION[0], self.GRID_SELECTION[1]+1): label.configure(bg=palette('medium'))
            else:                               label.configure(bg=palette('dark'))


#All the commands for reordering, showing, and hiding the info columns
    def move_info(self, info, shift='beginning'):
        if   shift == 'beginning':  i = 0
        elif shift == 'right':      i = setting('header_portfolio').index(info) + 1
        elif shift == 'left':       i = setting('header_portfolio').index(info) - 1
        elif shift == 'end':        i = len(setting('header_portfolio'))
        new = setting('header_portfolio')
        new.remove(info)
        new.insert(i, info)
        set_setting('header_portfolio', new)
        self.render()
    def hide_info(self, info):
        new = setting('header_portfolio')
        new.remove(info)
        set_setting('header_portfolio', new)
        self.TASKBAR['info'].values[info].set(False)
        self.GRID_remove_col()
        self.render()
    def show_info(self, info):
        new = setting('header_portfolio')
        new.insert(0, info)
        set_setting('header_portfolio', new)
        self.TASKBAR['info'].values[info].set(True)
        self.GRID_add_col()
        self.render()
#All the commands for sorting the assets
    def set_sort(self, row): #Sets the sorting mode, sorts the assets by it, then rerenders everything
        if self.rendered[0] == 'portfolio':
            info = setting('header_portfolio')[row]
            if setting('sort_asset')[0] == info:    set_setting('sort_asset',[info, not setting('sort_asset')[1]])
            else:                                   set_setting('sort_asset',[info, False])
        else:
            info = setting('header_asset')[row]
            if setting('sort_trans')[0] == info:    set_setting('sort_trans',[info, not setting('sort_trans')[1]])
            else:                                   set_setting('sort_trans',[info, False])
        self.render(sort=True)
    def sort(self): #Sorts the assets or transactions by the metric defined in settings
        '''Sorts the assets or transactions by the metric defined in settings'''
        if self.rendered[0] == 'portfolio':  #Assets
            info = setting('sort_asset')[0]    #The info we're sorting by
            reverse = setting('sort_asset')[1] #Whether or not it is in reverse order

            sorted = list(MAIN_PORTFOLIO.assetkeys())
            sorted.sort() #Sorts the assets alphabetically by their tickerclass first. This is the default.
            def alphaKey(e):    return MAIN_PORTFOLIO.asset(e).get(info).lower()
            def numericKey(e):
                n = MAIN_PORTFOLIO.asset(e).get(info)
                try: return float(n)
                except: return (reverse-0.5)*float('inf') #Sends missing data values to the bottom of the sorted list
        else:   #Transactions
            info = setting('sort_trans')[0]    #The info we're sorting by
            reverse = setting('sort_trans')[1] #Whether or not it is in reverse order

            sorted = list(MAIN_PORTFOLIO.asset(self.rendered[1])._ledger) #a dict of relevant transactions, this is a list of their keys.

            def logicKey(e): return MAIN_PORTFOLIO.transaction(e)   #By default, we sort by the special sorting algorithm (date, then type, then wallet, etc. etc.)
            sorted.sort(reverse=not reverse, key=logicKey)
            
            def alphaKey(e):    
                data = MAIN_PORTFOLIO.transaction(e).get(info).lower()
                if data:    return data
                else:               return ''
            def numericKey(e):
                n = MAIN_PORTFOLIO.transaction(e).get(info)
                try: return float(n)
                except: return (reverse-0.5)*float('inf') #Sends missing data values to the bottom of the sorted list
            def value_quantity_price(e):
                t = MAIN_PORTFOLIO.transaction(e)
                if   info == 'value':     return t.value(self.rendered[1])
                elif info == 'quantity':  return t.quantity(self.rendered[1])
                elif info == 'price':     return t.price(self.rendered[1])
        
        if   self.rendered[0] == 'asset' and info == 'date':                         pass  #This is here to ensure that the default date order is newest to oldest. This means reverse alphaetical
        elif self.infoLib(self.rendered[1], info, 'format') == 'alpha':   sorted.sort(reverse=reverse, key=alphaKey)
        elif self.rendered[0] == 'asset' and info in ['value','quantity','price']:   sorted.sort(reverse=not reverse, key=value_quantity_price)
        else:                                                       sorted.sort(reverse=not reverse, key=numericKey)

        self.sorted = sorted  



#INFO FUNCTIONS
#=============================================================

    def infoLib(self, asset, info, characteristic):   #A single command for getting formatting and header names for info bits
        if asset == None:   return assetinfolib[info][characteristic]
        else:               return transinfolib[info][characteristic]

    def comm_portfolio_info(self): #A wholistic display of all relevant information to the overall portfolio 
        message = Message(self, 'Overall Stats and Information', '', font=setting('font'), width=80, height=20)
        DEFCOLOR, DEFFONT = palette('neutral'), setting('font2')

        # NUMBER OF TRANSACTIONS, NUMBER OF ASSETS
        message.insert_triplet('• ', MAIN_PORTFOLIO.prettyPrint('number_of_transactions'), '', fg=DEFCOLOR, font=DEFFONT, newline=False)
        message.insert_triplet(' transactions loaded under ', MAIN_PORTFOLIO.prettyPrint('number_of_assets'), ' assets', fg=DEFCOLOR, font=DEFFONT)

        # USD PER WALLET
        message.insert('• Total USD by wallet:')
        message.insert_triplet('\t*TOTAL*:\t\t\t', format_general(MAIN_PORTFOLIO.get('value'), 'alpha', 20), ' USD', fg=DEFCOLOR, font=DEFFONT)
        wallets = list(MAIN_PORTFOLIO.get('wallets'))
        def sortByUSD(w):   return MAIN_PORTFOLIO.get('wallets')[w]  #Wallets are sorted by their total USD value
        wallets.sort(reverse=True, key=sortByUSD)
        for w in wallets:    #Wallets, a list of wallets by name, and their respective net valuations
            quantity = MAIN_PORTFOLIO.get('wallets')[w]
            if not zeroish(quantity):
                message.insert_triplet('\t'+w+':\t\t\t', format_general(quantity, 'alpha', 20), ' USD', fg=DEFCOLOR, font=DEFFONT)

        # MASS INFORMATION
        for data in ['day_change','day%', 'week%', 'month%', 'unrealized_profit_and_loss', 'unrealized_profit_and_loss%']:
            info_format = portfolioinfolib[data]['format']
            fg_color = MAIN_PORTFOLIO.color(data)[0] #Returns the foreground color we want for this info bit, if it has one
            if fg_color == None: fg_color = palette('neutral')
            text1 = '• '+portfolioinfolib[data]['name']+':\t\t\t\t'
            if info_format == 'percent':
                message.insert_triplet(text1, format_general(MAIN_PORTFOLIO.get(data)*100, 'alpha', 20), ' %', fg=fg_color, font=DEFFONT)
            else:
                message.insert_triplet(text1, format_general(MAIN_PORTFOLIO.get(data), 'alpha', 20), ' USD', fg=fg_color, font=DEFFONT)
    
    def comm_asset_info(self, a): #A wholistic display of all relevant information to an asset 
        asset = MAIN_PORTFOLIO.asset(a)
        message = Message(self, asset.name() + ' Stats and Information', '', font=setting('font'), width=80, height=20)
        DEFCOLOR, DEFFONT = palette('neutral'), setting('font2')

        # NUMBER OF TRANSACTIONS
        message.insert_triplet('• ', str(len(MAIN_PORTFOLIO.asset(a)._ledger)), ' transactions loaded under ' + asset.ticker(), fg=DEFCOLOR, font=DEFFONT)
        # ASSET CLASS
        message.insert_triplet('• Asset Class:\t\t\t\t', asset.prettyPrint('class'), '', fg=DEFCOLOR, font=DEFFONT)

        # UNITS PER WALLET
        message.insert('• Total '+asset.ticker()+' by wallet:')
        message.insert_triplet('\t*TOTAL*:\t\t\t', format_general(asset.get('holdings'), 'alpha', 20), ' '+asset.ticker(), fg=DEFCOLOR, font=DEFFONT)
        wallets = list(MAIN_PORTFOLIO.asset(a).get('wallets'))  
        def sortByUnits(w):   return MAIN_PORTFOLIO.asset(a).get('wallets')[w]    #Wallets are sorted by their total # of units
        wallets.sort(reverse=True, key=sortByUnits)
        for w in wallets:
            quantity = MAIN_PORTFOLIO.asset(a).get('wallets')[w]
            if not zeroish(quantity):
                message.insert_triplet('\t' + w + ':\t\t\t', format_general(quantity, 'alpha', 20), ' '+asset.ticker(), fg=DEFCOLOR, font=DEFFONT)

        # MASS INFORMATION
        for data in ['price','value', 'marketcap', 'volume24h', 'day_change', 'day%', 'week%', 'month%', 'portfolio%','unrealized_profit_and_loss','unrealized_profit_and_loss%']:
            info_format = assetinfolib[data]['format']
            fg_color = asset.color(data)[0] #Returns the foreground color we want for this info bit, if it has one
            if fg_color == None: fg_color = DEFCOLOR
            text1 = '• '+ assetinfolib[data]['name']+':\t\t\t\t'
            if data == 'price':
                message.insert_triplet(text1, format_general(asset.get(data), 'alpha', 20), ' USD/'+asset.ticker(), fg=fg_color, font=DEFFONT)
            elif info_format == 'percent':
                message.insert_triplet(text1, format_general(asset.get(data)*100, 'alpha', 20), ' %', fg=fg_color, font=DEFFONT)
            else:
                message.insert_triplet(text1, format_general(asset.get(data), 'alpha', 20), ' USD', fg=fg_color, font=DEFFONT)




#METRICS
#=============================================================
    def metrics(self, tax_report=''): # Recalculates all static and dynamic metrics for all assets and the overall protfolio
        '''Calculates and renders all static metrics for all assets, and the overall portfolio'''
        TEMP['taxes'] = { 
            '8949':     pd.DataFrame(columns=['Description of property','Date acquired','Date sold or disposed of','Proceeds','Cost or other basis','Gain or (loss)']) ,
            '1099-MISC':pd.DataFrame(columns=['Date acquired', 'Value of assets']),
            }
            
        self.perform_automatic_accounting(tax_report) # TODO: LAGGY! (~650ms for ~12000 transactions)
        for asset in MAIN_PORTFOLIO.assets():
            self.calculate_average_buy_price(asset)
        self.metrics_PORTFOLIO() #~0ms, since its just a few O(1) operations
        self.market_metrics() #Only like 2 ms

    def metrics_PORTFOLIO(self): #Recalculates all static metrics for the overall portfolio
        '''Calculates all metrics for the overall portfolio'''
        MAIN_PORTFOLIO._metrics['number_of_transactions'] = len(MAIN_PORTFOLIO.transactions())
        MAIN_PORTFOLIO._metrics['number_of_assets'] = len(MAIN_PORTFOLIO.assets())

    def market_metrics(self):   # Recalculates all dynamic metrics based on data recovered from the internet
        for asset in MAIN_PORTFOLIO.assets():    
            self.calculate_value(asset)
            self.calculate_unrealized_profit_and_loss(asset)
            self.calculate_changes(asset)
            self.calculate_net_cash_flow(asset)
        self.market_metrics_PORTFOLIO()
    def market_metrics_PORTFOLIO(self): #Recalculates all dynamic market metrics for the overall portfolio
        #Calculates the overall portfolio value
        value = 0
        for a in MAIN_PORTFOLIO.assetkeys():    #Compiles complete list of all wallets used in the portfolio
            try: value += MAIN_PORTFOLIO.asset(a).get('value') #Adds the total value of this asset to the overall portfolio value. If no price data can be found we assume this asset it worthless.
            except: None
        MAIN_PORTFOLIO._metrics['value'] = value

        #Has to be a separate loop so that the total portfolio value is actually the total
        MAIN_PORTFOLIO._metrics.update({'day_change':0,'week_change':0,'month_change':0})
        for a in MAIN_PORTFOLIO.assetkeys():
            self.calculate_percentage_of_portfolio(a)
            try:
                MAIN_PORTFOLIO._metrics['day_change'] += MAIN_PORTFOLIO.asset(a).get('day_change')
                MAIN_PORTFOLIO._metrics['week_change'] += MAIN_PORTFOLIO.asset(a).get('week_change')
                MAIN_PORTFOLIO._metrics['month_change'] += MAIN_PORTFOLIO.asset(a).get('month_change')
            except: pass

        #Calculates the 24-hour % performance of the portfolio
        try:
            MAIN_PORTFOLIO._metrics['day%'] =   MAIN_PORTFOLIO.get('day_change') /   (MAIN_PORTFOLIO.get('value') - MAIN_PORTFOLIO.get('day_change'))
            MAIN_PORTFOLIO._metrics['week%'] =  MAIN_PORTFOLIO.get('week_change') /  (MAIN_PORTFOLIO.get('value') - MAIN_PORTFOLIO.get('week_change'))
            MAIN_PORTFOLIO._metrics['month%'] = MAIN_PORTFOLIO.get('month_change') / (MAIN_PORTFOLIO.get('value') - MAIN_PORTFOLIO.get('month_change'))
        except: pass

        self.calculate_portfolio_value_by_wallet()
        self.calculate_portfolio_unrealized_profit_and_loss()

            
    def perform_automatic_accounting(self, tax_report=''):   #Dependent on the Accounting Method, calculates the Holdings per Wallet, Total Holdings, Average Buy Price, Real P&L (Capital Gains)
        
        #Creates a list of all transactions, sorted chronologically #NOTE: Lag is ~17ms for ~12000 transactions
        transactions = list(MAIN_PORTFOLIO.transactions()) #0ms
        #def sortByDate(e):  return e.date()
        transactions.sort()


        ###################################
        # TRANSFER LINKING - #NOTE: Lag is ~20ms for 159 transfer pairs under ~12000 transactions
        ###################################
        #Before we can iterate through all of our transactions, we need to pair up transfer_IN and transfer_OUTs, otherwise we lose track of cost basis which is BAD
        transfer_IN = []    #A list of all transfer_INs, chronologically ordered
        transfer_OUT = []   #A list of all transfer_OUTs, chronologically ordered
        for t in transactions:
            #For both case we assume there is an ERROR until we can resolve it.
            if t.type() == 'transfer_in':     
                t.ERROR,t.ERR_MSG = True,'Failed to automatically find a '+t.get('gain_asset')[:-2]+' \'Transfer Out\' transaction that pairs with this \'Transfer In\'.'
                transfer_IN.append(t)
            elif t.type() == 'transfer_out':    
                t.ERROR,t.ERR_MSG = True,'Failed to automatically find a '+t.get('loss_asset')[:-2]+' \'Transfer In\' transaction that pairs with this \'Transfer Out\'.'
                transfer_OUT.append(t)
            else:
                t.ERROR = False
        #Then, iterating through all the transactions, we pair them up. 
        for t_out in transfer_OUT:
            for t_in in transfer_IN: #We have to look at all the t_in's
                # We pair them up if they have the same asset, occur within 5 minutes of eachother, and if their quantities are within 0.1% of eachother
                if t_in.get('gain_asset') == t_out.get('loss_asset') and acceptableTimeDiff(t_in.date(),t_out.date(),300) and acceptableDifference(t_in.get('gain_quantity'), t_out.get('loss_quantity'), 0.1):
                        #SUCCESS - We've paired this t_out with a t_in!
                        transfer_IN.remove(t_in) # Remove it from the transfer_IN list.
                        t_out._dest_wallet = t_in.wallet() #We found a partner for this t_out, so set its _dest_wallet variable to the t_in's wallet
                        #Between transfer_in and transfer_out, use the more precise quantity, overwriting the less precise with it.
                        if len(t_in.get('gain_quantity')) > len(t_out.get('loss_quantity')): #if t_in's string is longer...
                            t_out._data['gain_quantity'] = t_in.get('loss_quantity')     #t_in has more precise value, overwrite t_out with that quantity
                        else:   t_in._data['gain_quantity'] = t_out.get('loss_quantity') #t_out has less precise value, overwrite t_in with that quantity
                        #Resolve the ERROR state for the newly wedded couple
                        t_out.ERROR = False
                        t_in.ERROR = False

        ###################################
        # AUTO-ACCOUNTING
        ###################################
        #Transfers linked. It's showtime. Time to perform the Auto-Accounting!
        
        # INFO VARIABLES - data we collect as we account for every transaction #NOTE: Lag is 0ms for ~12000 transactions
        metrics = {}
        for asset in MAIN_PORTFOLIO.assetkeys():
            metrics[asset] = {
                'cash_flow':                0,
                'realized_profit_and_loss': 0,
                'tax_capital_gains':        0,
                'tax_income':               0,
            }
        
        # HOLDINGS - The data structure which tracks asset's original price across sales #NOTE: Lag is 0ms for ~12000 transactions
        holdings = {}
        for asset in MAIN_PORTFOLIO.assetkeys():
            MAIN_PORTFOLIO.asset(asset).ERROR = False # Assume assets are free of error at first. We check all transactions later.
            holdings[asset] = {}
            for wallet in MAIN_PORTFOLIO.walletkeys():
                #Removing these transactions is literally just a priority queue, for which heaps are basically the best implementation
                holdings[asset][wallet] = gain_heap() 

        # STORE and DISBURSE QUANTITY - functions which add, or remove a 'gain', to the HOLDINGS data structure.
        
        def store_quantity(hash, price, quantity, date, a, w):   #NOTE: Lag is ~136 ms for ~12000 transactions
            '''Adds specified gaining transaction to specified wallet.'''
            holdings[a][w].store(hash, precise(price), precise(quantity), date)

        def disburse_quantity(t, quantity, a, w, w2=None):  #NOTE: Lag is ~75ms for ~12000 transactions
            '''Removes specified quantity of asset from specified wallet.\n
                Returns the cost basis of the removed quantity.\n
                If wallet2 \'w2\' specified, instead moves quantity into w2.'''
            #NOTE - Lag is ~55ms for ~12000 transactions
            result = holdings[a][w].disburse(precise(quantity))
            if not zeroish(result[0]):
                t.ERROR,t.ERR_MSG = True,'User disbursed more ' + a.split('z')[0] + ' than they owned from the '+w+' wallet, with ' + str(result[0]) + ' remaining to disburse.'
                
            #NOTE - Lag is ~20ms for ~12000 transactions
            cost_basis = 0
            for gain in result[1]: #Result[1] is a list of gain objects that were just disbursed
                cost_basis += gain._price*gain._quantity
                if tax_report == '8949': tax_8949(t, gain, quantity)
                if w2: store_quantity(gain._hash, gain._price, gain._quantity, gain._date, a, w2)   #Moves transfers into the other wallet
            return cost_basis

        def tax_8949(t, gain, total_disburse):
            ################################################################################################
            # This might still be broken. ALSO: Have to separate the transactions into short- and long-term
            ################################################################################################
            if zeroish(gain._quantity):     return
            if t.type() == 'transfer_out':  return 
            store_date = MAIN_PORTFOLIO.transaction(gain._hash).date()  # Date of aquisition
            disburse_date = t.date()                                    # Date of disposition
            cost_basis = gain._price*gain._quantity
            #The 'post-fee-value' is the sales profit, after fees, weighted to the actual quantity sold 
            post_fee_value = (precise(t.get('gain_value'))-precise(t.get('fee_value')))*(gain._quantity/precise(total_disburse))
            if post_fee_value < 0:  post_fee_value = 0     #If we gained nothing and there was a fee, it will be negative. We can't have negative proceeds.
            form8949 = {
                'Description of property':      str(gain._quantity) + ' ' + MAIN_PORTFOLIO.transaction(gain._hash).get('gain_asset').split('z')[0],  # 0.0328453 ETH
                'Date acquired':                store_date[5:7]+'/'+store_date[8:10]+'/'+store_date[:4],            # 11/12/2021    month, day, year
                'Date sold or disposed of':     disburse_date[5:7]+'/'+disburse_date[8:10]+'/'+disburse_date[:4],   # 6/23/2022     month, day, year
                'Proceeds':                     str(post_fee_value),    # to value gained from this sale/trade/expense/gift_out. could be negative if its a gift_out with a fee.
                'Cost or other basis':          str(cost_basis),        # the cost basis of these tokens
                'Gain or (loss)':               str(precise(post_fee_value) - precise(cost_basis))  # the Capital Gains from this. The P&L. 
                }
            TEMP['taxes']['8949'] = TEMP['taxes']['8949'].append(form8949, ignore_index=True)

        for t in transactions:
            if t.get('missing')[0]:  t.ERROR,t.ERR_MSG = True,t.prettyPrint('missing')   #NOTE: Lag ~10ms for ~12000 transactions
            if t.ERROR: continue    #If there is an ERROR with this transaction, ignore it to prevent crashing. User expected to fix this immediately.

            #NOTE: Lag ~30ms for ~12000 transactions
            DATE,TYPE,WALLET = t.date(),t.type(),t.wallet()
            LA,FA,GA = t.get('loss_asset'),t.get('fee_asset'),t.get('gain_asset')
            LQ,FQ,GQ = t.get('loss_quantity'), t.get('fee_quantity'), t.get('gain_quantity')
            LV,FV,GV = t.get('loss_value'),t.get('fee_value'),t.get('gain_value')
            LOSS_COST_BASIS,FEE_COST_BASIS = 0,0
            
            # COST BASIS CALCULATION - The real 'auto-accounting' happens here      #NOTE: Laag ~450ms for ~12000 transactions. 
            # NOTE: We have to do the gain, then the fee, then the loss, because some Binance trades incur a fee in the crypto you just bought
            # GAINS - We gain assets one way or another
            if TYPE in ['purchase','purchase_crypto_fee']:      store_quantity(t.get_hash(), (LV+FV)/precise(GQ),          GQ, DATE, GA, WALLET) # Purchase price includes fee
            elif TYPE in ['gift_in','card_reward','income']:    store_quantity(t.get_hash(), precise(t.get('gain_price')), GQ, DATE, GA, WALLET) # Fee is defined already
            elif TYPE == 'trade':                               store_quantity(t.get_hash(), LV/precise(GQ),               GQ, DATE, GA, WALLET) # Trade price doesn't include fee
            # FEE LOSS - We lose assets because of a fee
            if FA:                                              FEE_COST_BASIS =  disburse_quantity(t, FQ, FA, WALLET)
            # LOSS - We lose assets one way or another.
            if TYPE in ['sale','trade','expense','gift_out']:   LOSS_COST_BASIS = disburse_quantity(t, LQ, LA, WALLET)
            elif TYPE == 'transfer_out':                        LOSS_COST_BASIS = disburse_quantity(t, LQ, LA, WALLET, t._dest_wallet)


            # METRIC CALCULATION

            # CASH FLOW - Only sales/purchases/trades affect cash_flow. trades, because it makes more sense to have them than not, even though they are independent of USD.
            if TYPE in ['purchase','purchase_crypto_fee']:  metrics[GA]['cash_flow'] -= GV + FV
            elif TYPE  == 'sale':                           metrics[LA]['cash_flow'] += LV - FV
            elif TYPE == 'trade':   # Trades are a sort of 'indirect purchase/sale' of an asset. For them, the fee is lumped with the sale, not the purchase
                metrics[LA]['cash_flow'] += LV - FV
                metrics[GA]['cash_flow'] -= GV
            
            # REALIZED PROFIT AND LOSS - Sales and trades sometimes profit, whereas gift_outs, expenses, as well as any fees always incur a loss
            # Fees are always a realized loss, if there is one
            if FA:                      metrics[FA]['realized_profit_and_loss'] -= FEE_COST_BASIS   # Base fee cost is realized
            elif TYPE == 'purchase':            metrics[GA]['realized_profit_and_loss'] -= FV        # Base fee cost is realized to asset bought
            elif TYPE == 'sale':                metrics[LA]['realized_profit_and_loss'] -= FV        # Base fee cost is realized to asset sold
            #Expenses and gift_outs are a complete realized loss. Sales and trades we already lost the fee, but hopefully gain more from sale yield
            if TYPE in ['expense','gift_out']:  metrics[LA]['realized_profit_and_loss'] -= LOSS_COST_BASIS  # Base loss cost is realized
            elif TYPE in ['sale','trade']:      metrics[LA]['realized_profit_and_loss'] += LV - LOSS_COST_BASIS # Base loss cost is realized, but sale yields the loss value

            # CAPITAL GAINS TAX
            #Independent transfer fees are taxed as a 'sale'
            if TYPE in ['gift_out','transfer_out','transfer_in'] and FA: metrics[FA]['tax_capital_gains'] += FV - FEE_COST_BASIS
            #Expenses taxed as a 'sale', trade treated as an immediate sale and purchase
            elif TYPE in ['sale','trade']:                               metrics[LA]['tax_capital_gains'] += (LV - FV) - LOSS_COST_BASIS 
            elif TYPE == 'expense':                                      metrics[LA]['tax_capital_gains'] += (LV + FV) - LOSS_COST_BASIS 

            # INCOME TAX
            if TYPE in ['card_reward','income']:    #This accounts for all transactions taxable as INCOME: card rewards, and staking rewards
                metrics[GA]['tax_income'] += GV
                if tax_report=='1099-MISC':  
                    TEMP['taxes']['1099-MISC'] = TEMP['taxes']['1099-MISC'].append( {'Date acquired':DATE, 'Value of assets':str(GV)}, ignore_index=True)
                    
            #*** *** *** DONE FOR THIS TRANSACTION *** *** ***#
            
        #And that's it! We calculate the average buy price AFTER figuring out what tokens we have left.

        #ERRORS - applies error state to any asset with an erroneous transaction on its ledger.
        for t in transactions:
            if t.ERROR:     
                if t.get('loss_asset'): MAIN_PORTFOLIO.asset(t.get('loss_asset')).ERROR = True
                if t.get('fee_asset'):  MAIN_PORTFOLIO.asset(t.get('fee_asset')).ERROR =  True
                if t.get('gain_asset'): MAIN_PORTFOLIO.asset(t.get('gain_asset')).ERROR = True

        for a in MAIN_PORTFOLIO.assetkeys(): #TODO: Lag is like 30ms for ~4000 transactions
            #Update this asset's metrics dictionary with our newly calculated information
            asset = MAIN_PORTFOLIO.asset(a)
            asset._metrics.update(metrics[a])

            total_cost_basis = 0    #The overall cost basis of what you currently own
            total_holdings = 0      #The total # units you hold of this asset
            wallet_holdings = {}    #A dictionary indicating your total units held, by wallet
            for w in holdings[a]:
                wallet_holdings[w] = 0
                for gain in holdings[a][w]._dict.values():
                    total_cost_basis        += gain._price*gain._quantity   #cost basis of this gain
                    total_holdings          += gain._quantity               #Single number for the total number of tokens
                    wallet_holdings[w]      += gain._quantity               #Number of tokens within each wallet

            asset._metrics['cost_basis'] =  total_cost_basis
            asset._metrics['holdings'] =    total_holdings
            asset._metrics['wallets'] =     wallet_holdings
            
    def calculate_average_buy_price(self, asset):
        try:    asset._metrics['average_buy_price'] = asset.get('cost_basis') / asset.get('holdings')
        except: asset._metrics['average_buy_price'] = 0
    def calculate_value(self, asset):   #Calculates the overall value of this asset
        #Must be a try statement because it relies on market data
        try:    asset._metrics['value'] = asset.get('holdings') * asset.get('price')
        except: asset._metrics['value'] = MISSINGDATA
    def calculate_unrealized_profit_and_loss(self, asset):
        #You need current market data for these bad boys
        average_buy_price = asset.get('average_buy_price')
        try:        
            asset._metrics['unrealized_profit_and_loss'] =      asset.get('value') - ( average_buy_price * asset.get('holdings') )
            asset._metrics['unrealized_profit_and_loss%'] =   ( asset.get('price') /  average_buy_price )-1
        except:     asset._metrics['unrealized_profit_and_loss%'] = asset._metrics['unrealized_profit_and_loss'] = 0
    def calculate_changes(self, asset): #Calculates the unrealized USD lost or gained in the last 24 hours, week, and month for this asset
        #Must be a try statement because it relies on market data
        value = asset.get('value')
        try:
            asset._metrics['day_change'] =   value-(value / (1 + asset.get('day%')))
            asset._metrics['week_change'] =  value-(value / (1 + asset.get('week%')))
            asset._metrics['month_change'] = value-(value / (1 + asset.get('month%')))
        except: pass
    def calculate_net_cash_flow(self, asset): #Calculates what the cash flow would become if you sold everything right now
        #Must be a try statement because it relies on market data
        try:    asset._metrics['net_cash_flow'] = asset.get('cash_flow') + asset.get('value') 
        except: asset._metrics['net_cash_flow'] = 0
    def calculate_percentage_of_portfolio(self, a): #Calculates how much of the value of your portfolio is this asset - NOTE: must be done after total portfolio value calculated
        asset = MAIN_PORTFOLIO.asset(a)
        portfolio_value = MAIN_PORTFOLIO.get('value')
        try:    asset._metrics['portfolio%'] = MAIN_PORTFOLIO.asset(a).get('value')  / MAIN_PORTFOLIO.get('value')
        except: asset._metrics['portfolio%'] = 0

    def calculate_portfolio_value_by_wallet(self):    #For the overall portfolio, calculates the total value held within each wallet
        wallets = {}
        for wallet in MAIN_PORTFOLIO.walletkeys():     #Creates a list of wallets, defaulting to 0$ within each
            wallets[wallet] = 0
        for asset in MAIN_PORTFOLIO.assets():       #Then, for every asset, we look at its 'wallets' dictionary, and sum up the value of each wallet's tokens by wallet
            for wallet in asset.get('wallets'):
                # Asset wallet list is total units by wallet, multiply by asset price to get value
                try:    wallets[wallet] += asset.get('wallets')[wallet] * asset.get('price')
                except: pass
        MAIN_PORTFOLIO._metrics['wallets'] = wallets
    def calculate_portfolio_unrealized_profit_and_loss(self):
        total_unrealized_profit = 0
        for asset in MAIN_PORTFOLIO.assets():
            try:    total_unrealized_profit += asset.get('unrealized_profit_and_loss')
            except: continue    #Just ignore assets missing price data
        try:        
            MAIN_PORTFOLIO._metrics['unrealized_profit_and_loss'] = total_unrealized_profit
            MAIN_PORTFOLIO._metrics['unrealized_profit_and_loss%'] = total_unrealized_profit / (MAIN_PORTFOLIO.get('value') - total_unrealized_profit)
        except:
            MAIN_PORTFOLIO._metrics['unrealized_profit_and_loss'] = MAIN_PORTFOLIO._metrics['unrealized_profit_and_loss%'] = 0


#BINDINGS
#=============================================================
    def _mousewheel(self, event):   #Scroll up and down the assets pane
        if self.grab_current() == self: #If any other window is open, then you can't do this
            if event.delta > 0:     self.comm_page_last()
            elif event.delta < 0:   self.comm_page_next()
    def _ctrl_z(self,event):    #Undo your last action
        if self.grab_current() == self: #If any other window is open, then you can't do this
            lastAction = (self.undoRedo[2]-1)%len(TEMP['undo'])
            #If there actually IS a previous action, load that
            if (self.undoRedo[1] > self.undoRedo[0] and lastAction >= self.undoRedo[0] and lastAction <= self.undoRedo[1]) or (self.undoRedo[1] < self.undoRedo[0] and (lastAction >= self.undoRedo[0] or lastAction <= self.undoRedo[1])):
                if lastAction == self.undoRedo[0]:  self.MENU['undo'].configure(state='disabled')
                else:                               self.MENU['undo'].configure(state='normal')
                self.MENU['redo'].configure(state='normal')
                self.undoRedo[2] = (self.undoRedo[2]-1)%len(TEMP['undo'])
                MAIN_PORTFOLIO.loadJSON(TEMP['undo'][lastAction])
                self.profile = ''   #name of the currently selected profile. Always starts with no filter applied.
                self.metrics()
                self.render(sort=True)
    def _ctrl_y(self,event):    #Redo your last action
        if self.grab_current() == self: #If any other window is open, then you can't do this
            nextAction = (self.undoRedo[2]+1)%len(TEMP['undo'])
            #If there actually IS a next action, load that
            if (self.undoRedo[1] > self.undoRedo[0] and nextAction >= self.undoRedo[0] and nextAction <= self.undoRedo[1]) or (self.undoRedo[1] < self.undoRedo[0] and (nextAction >= self.undoRedo[0] or nextAction <= self.undoRedo[1])):
                if nextAction == self.undoRedo[1]:  self.MENU['redo'].configure(state='disabled')
                else:                               self.MENU['redo'].configure(state='normal')
                self.MENU['undo'].configure(state='normal')
                self.undoRedo[2] = (self.undoRedo[2]+1)%len(TEMP['undo'])
                MAIN_PORTFOLIO.loadJSON(TEMP['undo'][nextAction])    #9ms to merely reload the data into memory
                self.profile = ''   #name of the currently selected profile. Always starts with no filter applied.
                self.metrics()  #2309 ms holy fuck
                self.render(sort=True)
    def _esc(self,event):    #Exit this window
        if self.grab_current() == self: #If any other window is open, then you can't do this
            if self.GRID_SELECTION != [-1, -1]:  self.GRID_clear_selection()
            elif self.rendered[0] == 'portfolio':  self.comm_quit()        #If we're on the main page, exit the program
            else:                   self.render(('portfolio',None), True)  #If we're looking at an asset, go back to the main page
    def _del(self,event):    #Delete any selected items
        if self.grab_current() == self: #If any other window is open, then you can't do this
            if self.GRID_SELECTION != [-1, -1]:  self.GRID_delete_selection(self.GRID_SELECTION)
#USEFUL COMMANDS
#=============================================================
    def undo_save(self):
        '''Saves current portfolio in the memory should the user wish to undo their last modification'''
        #############
        #NOTE: Undo savepoints are triggered when:
        ###############3
        # Loading a portfolio, creating a new portfolio, or merging portfolios causes an undosave
        # Importing transaction histories causes an undosave
        # Modifying/Creating a(n): Address, Asset, Transaction, Wallet
        #overwrites the cur + 1th slot with data
        self.MENU['redo'].configure(state='disabled')
        self.MENU['undo'].configure(state='normal')

        TEMP['undo'][(self.undoRedo[2]+1)%len(TEMP['undo'])] = MAIN_PORTFOLIO.toJSON()

        if self.undoRedo[1] - self.undoRedo[0] <= 0 and self.undoRedo[1] != self.undoRedo[0]:
            self.undoRedo[0] = (self.undoRedo[0]+1)%len(TEMP['undo'])
        self.undoRedo[2] = (self.undoRedo[2]+1)%len(TEMP['undo'])
        self.undoRedo[1] = self.undoRedo[2]




    def comm_copyright(self):
        Message(self,
        'MIT License', 

        '''Copyright (c) 2022 Shane Evanson

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the \'Software\'), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED \'AS IS\', WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.''', width=78, height=20)

        





if __name__ == '__main__':
    print('||    AUTO-ACCOUNTANT    ||')
    AutoAccountant().mainloop()





