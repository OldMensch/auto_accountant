#In-house

from AAlib import marketdatalib
from AAmarketData import startMarketDataLoops
from AAimport import *

from AAdialogues import *

from AAtooltip import ToolTipWindow

#3rd party libraries
from mpmath import mpf as precise
from mpmath import mp
mp.dps = 100

#Default Python
import tkinter as tk
from functools import partial as p
from tkinter.filedialog import *
import os
import copy
import math

import threading
from random import random as r

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
        self.asset = None #If we're on the main menu, this is None. If we're looking at a specific asset, this is the asset name.
        self.page = 0 #This indicates which page of data we're on. If we have 600 assets and 30 per page, we will have 20 pages.
        self.sorted = []
        self.GRID_SELECTION = [-1, -1]
        self.ToolTips = ToolTipWindow()

        self.create_GUI()
        self.create_taskbar()
        self.create_MENU()
        self.create_tooltips()

        self.online_event = threading.Event()

        #Try to load last-used JSON file, if the file works and we have it set to start with the last used portfolio
        if settings('startWithLastSaveDir') and os.path.isfile(settings('lastSaveDir')):    self.comm_loadPortfolio(settings('lastSaveDir'))
        else:                                                                               self.comm_newPortfolio(first=True)

        #Now that the hard data is loaded, we need market data
        if settings('offlineMode'):
            #If in Offline Mode, try to load any saved offline market data. If there isn't a file... loads nothing.
            try:
                marketdatalib.update(json.load(open('#OfflineMarketData.json', 'r')))
                self.GUI['offlineIndicator'].config(text='OFFLINE MODE - Data from ' + marketdatalib['_timestamp'][0:16])
                self.GUI['offlineIndicator'].pack(side='right') #Turns on a bright red indicator, which lets you know you're in offline mode
                self.market_metrics()
                self.render(None, True)
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
        self.bind('<Shift-MouseWheel>', self._shift_mousewheel)
        self.bind('<Control-z>', self._ctrl_z)
        self.bind('<Control-y>', self._ctrl_y)
        self.bind('<Escape>', self._esc)
        self.bind('<Delete>', self._del)

        self.geometry('%dx%d+%d+%d' % (settings('portWidth')/2, settings('portHeight')/2, self.winfo_x()-self.winfo_rootx(),0))#slaps this window in the upper-left-hand corner of the screen
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
        importmenu.add_command(label='Import Coinbase History', command=self.comm_importCoinbase)
        importmenu.add_command(label='Import Coinbase Pro History', command=self.comm_importCoinbasePro)
        importmenu.add_command(label='Import Gemini History', command=self.comm_importGemini)
        importmenu.add_command(label='Import Gemini Earn History', command=self.comm_importGeminiEarn)
        importmenu.add_command(label='Import Etherscan History', command=self.comm_importEtherscan)
        self.TASKBAR['file'].add_separator()
        self.TASKBAR['file'].add_command(label='QUIT', command=self.comm_quit)

        #'Settings' Tab
        self.TASKBAR['settings'] = tk.Menu(self, tearoff=0)
        self.TASKBAR['taskbar'].add_cascade(menu=self.TASKBAR['settings'], label='Settings')
        #self.TASKBAR['settings'].add_command(label='Restore Default Settings', command=self.restoreDefaultSettings)

        def toggle_offline_mode():
            settingslib['offlineMode'] = not settingslib['offlineMode']
            if settingslib['offlineMode']: #Changed to Offline Mode
                json.dump(marketdatalib, open('#OfflineMarketData.json', 'w'), indent=4, sort_keys=True)
                self.online_event.clear()
                self.GUI['offlineIndicator'].config(text='OFFLINE MODE - Data from ' + marketdatalib['_timestamp'][0:16])
                self.GUI['offlineIndicator'].pack(side='right') #Turns on a bright red indicator, which lets you know you're in offline mode
            else:                           #Changed to Online Mode
                self.online_event.set()
                self.GUI['offlineIndicator'].forget() #Removes the offline indicator

        self.TASKBAR['settings'].values = {}

        self.TASKBAR['settings'].values['offlineMode'] = tk.BooleanVar(value=settings('offlineMode'))
        self.TASKBAR['settings'].add_checkbutton(label='Offline Mode', command=toggle_offline_mode, variable=self.TASKBAR['settings'].values['offlineMode'])


        #'About' Tab
        self.TASKBAR['about'] = tk.Menu(self, tearoff=0)
        self.TASKBAR['taskbar'].add_cascade(menu=self.TASKBAR['about'], label='About')
        self.TASKBAR['about'].add_command(label='MIT License', command=self.comm_copyright)

        #'Info' Tab
        self.TASKBAR['info'] = tk.Menu(self, tearoff=0)
        self.TASKBAR['taskbar'].add_cascade(menu=self.TASKBAR['info'], label='Info')

        def toggle_header(info):
            if info in settings('header_portfolio'):    self.hide_info(info)
            else:                                       self.show_info(info)

        self.TASKBAR['info'].values = {}
        for info in assetinfolib:
            self.TASKBAR['info'].values[info] = tk.BooleanVar(value=info in settings('header_portfolio')) #Default value true if in the header list
            self.TASKBAR['info'].add_checkbutton(label=assetinfolib[info]['name'], command=p(toggle_header, info), variable=self.TASKBAR['info'].values[info])

        #'Accounting' Tab
        self.TASKBAR['accounting'] = tk.Menu(self, tearoff=0)
        self.TASKBAR['taskbar'].add_cascade(menu=self.TASKBAR['accounting'], label='Accounting')
        def set_accounting_method(method):
            settingslib['accounting_method'] = method
            self.metrics()
            self.render(self.asset, True)
        self.accounting_method = tk.StringVar()
        self.accounting_method.set(settings('accounting_method'))
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
        self.TASKBAR['DEBUG'].add_command(label='DEBUG add 200 AMP transactions',     command=self.DEBUG_test_AMP_trans)
        #debugmenu.add_command(label='Restart Auto-Accountant',     command=self.DEBUG_restart_test)

    def restoreDefaultSettings(self):
        Message(self, 'Error!', 'This would restart the program... but this seems to cause crashing. Will fix eventually.')
        return
        settingslib.clear()
        settingslib.update(defsettingslib)
        saveSettings()
        self.destroy()
        
    def tax_Form_8949(self):
        self.perform_automatic_accounting(tax_report='8949')
        dir = asksaveasfilename( defaultextension='.CSV', filetypes={('CSV','.csv')}, title='Save data for IRS Form 8949')
        if dir == '':
            return
        open(dir, 'w', newline='').write(TEMP['taxes']['8949'].to_csv())
    def tax_Form_1099MISC(self):
        dir = asksaveasfilename( defaultextension='.CSV', filetypes={('CSV','.csv')}, title='Save data for IRS Form 1099-MISC')
        if dir == '':
            return
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
    def DEBUG_test_AMP_trans(self):
        MAIN_PORTFOLIO.add_wallet(Wallet('TEST_WALLET','delete me! do it, do it now!'))
        MAIN_PORTFOLIO.add_asset(Asset('AMPzc', 'AMP Token', 'this is extremely cool or something'))
        for i in range(10,95):
            MAIN_PORTFOLIO.add_transaction(Transaction('00'+str(i)+'/11/11 11:11:11','purchase','TEST_WALLET',loss=[None,str(i),None],fee=[None,str(1),None],gain=['AMPzc',str(i*20),None]))
            MAIN_PORTFOLIO.add_transaction(Transaction('01'+str(i)+'/11/11 11:11:11','sale',    'TEST_WALLET',loss=['AMPzc',str(i*20),None],fee=[None,str(1),None],gain=[None,str(i),None]))
        self.metrics()
        self.render(self.asset, True)


    def comm_importCoinbase(self, wallet=None):
        if wallet == None:    ImportationDialogue(self, self.comm_importCoinbase, 'Coinbase Wallet') 
        else:
            dir = askopenfilename( filetypes={('CSV','.csv')}, title='Import Coinbase Transaction History')
            if dir == '':   return
            import_coinbase(self, dir, wallet)
    def comm_importCoinbasePro(self, wallet=None):
        if wallet == None:    ImportationDialogue(self, self.comm_importCoinbasePro, 'Coinbase Pro Wallet') 
        else:
            dir = askopenfilename( filetypes={('CSV','.csv')}, title='Import Coinbase Pro Transaction History')
            if dir == '':   return
            import_coinbase_pro(self, dir, wallet)
    def comm_importGemini(self, wallet=None):
        if wallet == None:    ImportationDialogue(self, self.comm_importGemini, 'Gemini Wallet') 
        else:
            dir = askopenfilename( filetypes={('XLSX','.xlsx')}, title='Import Gemini Transaction History')
            if dir == '':   return
            import_gemini(self, dir, wallet)
    def comm_importGeminiEarn(self, wallet=None):
        if wallet == None:    ImportationDialogue(self, self.comm_importGeminiEarn, 'Gemini Earn Wallet') 
        else:
            dir = askopenfilename( filetypes={('XLSX','.xlsx')}, title='Import Gemini Earn Transaction History')
            if dir == '':   return
            import_gemini_earn(self, dir, wallet)
    def comm_importEtherscan(self, wallet=None):
        if wallet == None:    ImportationDialogue(self, self.comm_importEtherscan, 'Ethereum Wallet') 
        else:
            ETHdir = askopenfilename( filetypes={('CSV','.csv')}, title='Import Etherscan ETH Transaction History')
            if ETHdir == '':   return
            ERC20dir = askopenfilename( filetypes={('CSV','.csv')}, title='Import Etherscan ERC-20 Transaction History')
            if ERC20dir == '':   return
            import_etherscan(self, ETHdir, ERC20dir, wallet)

    def comm_savePortfolio(self, saveAs=False, secondary=None):
        if saveAs or settings('lastSaveDir') == '':
            dir = asksaveasfilename( defaultextension='.JSON', filetypes={('JSON','.json')}, title='Save Portfolio')
        else:
            dir = settings('lastSaveDir')
        if dir == '':
            return
        self.title('Portfolio Manager - ' + dir)
        json.dump(MAIN_PORTFOLIO.toJSON(), open(dir, 'w'), sort_keys=True)
        if secondary != None:   secondary()
        if saveAs:              settingslib['lastSaveDir'] = dir
    def comm_newPortfolio(self, first=False):
        settingslib['lastSaveDir'] = ''
        MAIN_PORTFOLIO.clear()
        self.title('Portfolio Manager')
        self.profile = ''   #name of the currently selected profile. Always starts with no filter applied.
        self.metrics()
        self.render(None, True)
        if not first:
            self.undo_save()
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
        settingslib['lastSaveDir'] = dir
        self.profile = ''   #name of the currently selected profile. Always starts with no filter applied.
        self.metrics()
        self.render(None, True)   
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
        settingslib['lastSaveDir'] = '' #resets the savedir. who's to say where a merged portfolio should save to? why should it be the originally loaded file, versus any recently merged ones?
        self.title('Portfolio Manager')
        self.profile = ''   #name of the currently selected profile. Always starts with no filter applied.
        self.metrics()
        self.render(None, True)
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
        lastSaveDir = settings('lastSaveDir')
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
        self.GUI['title'] = tk.Label(self.GUI['primaryFrame'], width=16, text='Auto-Accountant', font=settings('font', 1.5), fg=palette('entrytext'),  bg=palette('accent'))
        self.GUI['subtitle'] = tk.Label(self.GUI['primaryFrame'], text='Overall Portfolio', font=settings('font', 1), fg=palette('entrycursor'),  bg=palette('accent'))
        self.GUI['buttonFrame'] = tk.Frame(self.GUI['primaryFrame'], bg=palette('accentdark'))
        self.GUI['info'] = tk.Button(self.GUI['buttonFrame'], image=icons('info2'), bg=palette('entry'), command=self.comm_portfolio_info)
        self.GUI['edit'] = tk.Button(self.GUI['buttonFrame'], image=icons('settings2'), bg=palette('entry'))
        self.GUI['new_asset'] =       tk.Button(self.GUI['buttonFrame'], text='+ Asset',  bg=palette('entry'), fg=palette('entrycursor'), font=settings('font'), command=p(AssetEditor, self))
        self.GUI['new_transaction'] = tk.Button(self.GUI['buttonFrame'], text='+ Trans',  bg=palette('entry'), fg=palette('entrycursor'), font=settings('font'), command=p(TransEditor, self))
        self.GUI['summary'] = tk.Label(self.GUI['primaryFrame'], font=settings('font', 0.5), fg=palette('entrycursor'),  bg=palette('accent'))
        self.GUI['back'] = tk.Button(self.GUI['primaryFrame'], text='Return to\nPortfolio', font=settings('font', 0.5),  fg=palette('entrycursor'), bg=palette('entry'), command=p(self.render, None, True))
        self.GUI['page_number'] = tk.Label(self.GUI['primaryFrame'], text='Page XXX of XXX', font=settings('font', 0.5), fg=palette('entrycursor'),  bg=palette('accentdark'))
        self.GUI['page_next'] = tk.Button(self.GUI['primaryFrame'], image=icons('arrow_down'), bg=palette('entry'), command=self.comm_page_next)
        self.GUI['page_last'] = tk.Button(self.GUI['primaryFrame'], image=icons('arrow_up'), bg=palette('entry'), command=self.comm_page_last)
        #contains the list of assets/transactions
        self.GUI['secondaryFrame'] = tk.Frame(self, bg=palette('dark'))
        #The little bar on the bottom
        self.GUI['bottomFrame'] = tk.Frame(self, bg=palette('accent'))
        self.GUI['copyright'] = tk.Button(self.GUI['bottomFrame'], bd=0, bg=palette('accent'), text='Copyright © 2022 Shane Evanson', fg=palette('entrycursor'), font=settings('font',0.4), command=self.comm_copyright)
        self.GUI['offlineIndicator'] = tk.Label(self.GUI['bottomFrame'], bd=0, bg='#ff0000', text=' OFFLINE MODE ', fg='#ffffff', font=settings('font',0.4))

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
        self.GUI['summary']         .grid(column=0,row=3, columnspan=2, sticky='NSEW')
        self.GUI['primaryFrame'].rowconfigure(3, weight=1)
        self.GUI['page_number']     .grid(column=0,row=5, columnspan=2, sticky='SEW')
        self.GUI['page_last']       .grid(column=0,row=6, sticky='SE')
        self.GUI['page_next']       .grid(column=1,row=6, sticky='SW')
        
        self.GUI['secondaryFrame']  .grid(column=1,row=1, sticky='NSEW')
        
        self.GUI['bottomFrame']     .grid(column=0,row=2, columnspan=2, sticky='EW')
        self.GUI['copyright']       .pack(side='left')

    def create_GRID(self):
        '''Initializes the grid of labels which displays all of the information about assets and transactions'''
        #Creates the GRID dictionary, and dictionary for the headers
        TEMP['GRID'] = { 0:{} }

        #for itemsPerPage rows of data...
        for r in range(1, settings('itemsPerPage')+1):
            self.GUI['secondaryFrame'].rowconfigure(r, weight=1)    #Makes the whole thing stretch vertically to fit the righthand window
            if r not in TEMP['GRID']:
                TEMP['GRID'][r] = {}
        #Generates labels for every column we need
        for c in range(len(settings('header_portfolio'))+1): #We always start out on the portfolio page, and thus, we start out with as many columns as there are headers
            self.GRID_add_col()
            
    def GRID_remove_col(self):
        '''Removes a column of labels from the GRID'''
        lastcol = len(TEMP['GRID'][0])-1
        if lastcol == 0:
            raise Exception('||ERROR|| Cannot delete \'#\' column from the GRID')
        for r in TEMP['GRID']:
            TEMP['GRID'][r].pop(lastcol).destroy()
    def GRID_add_col(self):
        '''Adds a column of labels to the GRID'''
        lastcol = len(TEMP['GRID'][0])

        #The header
        if lastcol == 0:
            TEMP['GRID'][0][0] = tk.Label(self.GUI['secondaryFrame'], text='#', font=settings('font', 0.75), fg=palette('entrytext'), bg=palette('light'), relief='groove', bd=1).grid(column=0,row=0, sticky='NSEW')
        else:
            header =  TEMP['GRID'][0][lastcol] = tk.Button(self.GUI['secondaryFrame'], command=p(self.set_sort, lastcol-1), font=settings('font', 0.75), fg=palette('entrytext'), bg=palette('light'), relief='groove', bd=1)
            header.bind('<Button-3>', p(self._header_menu, lastcol-1))
            header.grid(row=0, column=lastcol, sticky='NSEW')

        #The rest of the column
        for GRID_ROW in range(1, len(TEMP['GRID'])):
            label = TEMP['GRID'][GRID_ROW][lastcol] = tk.Label(self.GUI['secondaryFrame'], font=settings('font'), fg=palette('entrycursor'), bg=palette('dark'), relief='groove', bd=0)
            label.grid(row=GRID_ROW, column=lastcol, sticky='EW')
            label.bind('<Button-1>', p(self._left_click_row, GRID_ROW))
            label.bind('<Button-3>', p(self._right_click_row, GRID_ROW))
            label.bind('<Shift-Button-1>', p(self._shift_left_click_row, GRID_ROW))
            label.bind('<Enter>', p(self.color_row, GRID_ROW, None, palette('medium')))
            label.bind('<Leave>', p(self.color_row, GRID_ROW, None, None))
    def _header_menu(self, i, event):
        if self.asset != None:  return  #There is no menu for LEDGER view
        info = settings('header_portfolio')[i]
        m = tk.Menu(tearoff = 0)
        if i != 0:                                      m.add_command(label ='Move Left', command=p(self.move_info_left, info))
        if i != len(settings('header_portfolio'))-1:    m.add_command(label ='Move Right', command=p(self.move_info_right, info))
        if i != 0:                                      m.add_command(label ='Move to Beginning', command=p(self.move_info_beginning, info))
        if i != len(settings('header_portfolio'))-1:    m.add_command(label ='Move to End', command=p(self.move_info_end, info))
        m.add_separator()
        m.add_command(label ='Hide ' + assetinfolib[info]['name'], command=p(self.hide_info, info))
        try:        m.tk_popup(event.x_root, event.y_root)
        finally:    m.grab_release()
    def _left_click_row(self, GRID_ROW, event): # Opens up the asset subwindow, or transaction editor upon clicking a label within this row
        #if we double clicked on an asset/transaction, thats when we open it.
        if self.GRID_SELECTION == [GRID_ROW, GRID_ROW]:
            i = self.page*settings('itemsPerPage')+GRID_ROW-1
            try:
                if self.asset == None:  self.render(self.sorted[i], True)
                else:                   TransEditor(self, self.sorted[i])
            except: return
            self.GRID_clear_selection()
        else:
            self.GRID_clear_selection()
            self.GRID_SELECTION = [GRID_ROW, GRID_ROW]
    def _right_click_row(self, GRID_ROW, event): # Opens up a little menu of stuff you can do to this asset/transaction
        #we've right clicked with a selection of multiple items
        if self.GRID_SELECTION != [-1, -1] and self.GRID_SELECTION[0] != self.GRID_SELECTION[1]:
            m = tk.Menu(tearoff = 0)
            m.add_command(label ='Delete selection', command=p(self.GRID_delete_selection, self.GRID_SELECTION))
            try:        m.tk_popup(event.x_root, event.y_root)
            finally:    m.grab_release()
        #We've right clicked a single item
        else:
            i = self.page*settings('itemsPerPage')+GRID_ROW-1
            try:
                if self.asset == None:  asset = self.sorted[i]
                else:                   trans = self.sorted[i]
            except: return
            m = tk.Menu(tearoff = 0)
            if self.asset == None:
                ticker = MAIN_PORTFOLIO.asset(asset).ticker()
                m.add_command(label ='Open ' + ticker + ' Ledger', command=p(self.render, asset, True))
                m.add_command(label ='Edit ' + ticker, command=p(AssetEditor, self, asset))
                m.add_command(label ='Show detailed info', command=p(self.comm_asset_info, asset))
                m.add_command(label ='Delete ' + ticker, command=p(self.GRID_delete_selection, [GRID_ROW, GRID_ROW]))
            else:
                t = MAIN_PORTFOLIO.transaction(trans)
                m.add_command(label ='Edit ' + t.date(), command=p(TransEditor, self, trans))
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
        if self.asset != None:
            for item_index in range( self.page*settings('itemsPerPage')+toDelete[0]-1, self.page*settings('itemsPerPage')+toDelete[1]):
                try:    MAIN_PORTFOLIO.delete_transaction(self.sorted[item_index])
                except: continue
        else:
            Message(self, 'Unimplemented', 'You can\'t delete assets from here, for now.')
            return
        self.GRID_SELECTION = [-1, -1]
        self.undo_save()
        self.metrics()
        self.render(self.asset, True)


    def GRID_set_col(self, n):
        '''Adds or removes columns until there are \n\ columns. n must be greater than or equal to 0, and this ignores the \'#\' column.'''
        if n < 0:
            raise Exception('||ERROR|| Cannot set number of columns to less than 1')
        while len(TEMP['GRID'][0])-1 != n:
            curlength = len(TEMP['GRID'][0])-1
            if curlength > n:
                self.GRID_remove_col()
            if curlength < n:
                self.GRID_add_col()

    def create_tooltips(self):
        #MENU TOOLTIPS
        #==============================
        menu_tooltips = {
            'newPortfolio':'Create a new portfolio',
            'loadPortfolio':'Load an existing portfolio',
            'savePortfolio':'Save this portfolio',
            'settings':'Settings',

            'undo':'Undo last action',
            'redo':'Redo last action',

            'wallets':'Manage wallets',
            'addresses':'Manage addresses',
            'profiles':'Manage filter profiles',
        }
        for button in self.MENU:
            self.ToolTips.CreateToolTip(self.MENU[button] ,menu_tooltips[button])

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

        self.MENU['wallets'] = tk.Button(self.GUI['menuFrame'], text='Wallets',  bg=palette('entry'), fg=palette('entrycursor'), font=settings('font'), command=p(WalletManager, self))
        self.MENU['addresses'] = tk.Button(self.GUI['menuFrame'], text='Addresses',  bg=palette('entry'), fg=palette('entrycursor'), font=settings('font'), command=p(AddressManager, self))
        self.MENU['profiles'] = tk.Button(self.GUI['menuFrame'], image=icons('profiles'),  bg=palette('entry'), fg=palette('entrycursor'), font=settings('font'),command=p(ProfileManager, self))

        #MENU RENDERING
        #==============================
        self.MENU['newPortfolio']       .grid(column=0,row=0, sticky='NS')
        self.MENU['loadPortfolio']      .grid(column=1,row=0, sticky='NS')
        self.MENU['savePortfolio']      .grid(column=2,row=0, sticky='NS')
        self.MENU['settings']           .grid(column=3,row=0, sticky='NS', padx=(0,settings('font')[1]))

        self.MENU['undo']               .grid(column=4,row=0, sticky='NS')
        self.MENU['redo']               .grid(column=5,row=0, sticky='NS', padx=(0,settings('font')[1]))

        self.MENU['wallets']            .grid(column=8,row=0, sticky='NS')
        self.MENU['addresses']          .grid(column=9,row=0, sticky='NS', padx=(0,settings('font')[1]))

        #NOTE: the profile selection menu is in column #10
        self.MENU['profiles']           .grid(column=11,row=0, sticky='NS')


    def comm_page_next(self):
        if self.asset == None:  maxpage = math.ceil(len(MAIN_PORTFOLIO.assets())/settings('itemsPerPage')-1)
        else:                   maxpage = math.ceil(len(MAIN_PORTFOLIO.asset(self.asset)._ledger)/settings('itemsPerPage')-1)
        if self.page < maxpage: self.page += 1
        self.render(self.asset)
    def comm_page_last(self):
        if self.page > 0: self.page -= 1
        self.render(self.asset)

# PORTFOLIO RENDERING
#=============================================================
    def render(self, asset=None, sort=False):
        '''Call to render the portfolio, or a ledger
        \nasset - if rendering an ledger page, the ledger to be rendered. \'asset=None\' renders the portfolio'''
        #Creates the GRID if it hasn't been yet
        if 'GRID' not in TEMP:      self.create_GRID()
        #These are things that don't need to change unless we're changing from the PORTFOLIO to the LEDGER view
        if self.asset != asset:
            self.page = 0 #We return to the first page if changing from portfolio to asset or vice versa
            self.GRID_clear_selection()  #Clear the selection too. 
            if asset == None:
                self.GRID_set_col(len(settings('header_portfolio')))
                self.GUI['info'].configure(command=self.comm_portfolio_info)
                self.GUI['edit'].pack_forget()
                self.GUI['new_asset'].pack(side='right')
                self.GUI['back'].grid_forget()
            else:
                self.GRID_set_col(len(settings('header_asset')))
                self.GUI['info'].configure(command=p(self.comm_asset_info, asset))
                self.GUI['edit'].configure(command=p(AssetEditor, self, asset))
                self.GUI['edit'].pack(side='left')
                self.GUI['new_asset'].forget()
                self.GUI['back'].grid(row=4, column=0, columnspan=2)

        #Setting up stuff in the Primary Pane
        if asset == None:
            self.GUI['title'].configure(text='Auto-Accountant')
            self.GUI['subtitle'].configure(text='Overall Portfolio')
        else:      
            self.GUI['title'].configure(text=MAIN_PORTFOLIO.asset(asset).name())
            self.GUI['subtitle'].configure(text=MAIN_PORTFOLIO.asset(asset).ticker())

        #Sets the asset - 0ms
        if asset == None:   self.asset = None
        else:               self.asset = asset
        
        #Sorts the assets/transactions - 0ms for <30 Transactions *** CHECK THIS ON MORE TRANSACTIONS
        if sort:    self.sort()
            
        #Appropriately enabled/diables the page-setting buttons - 0ms
        maxpage = math.ceil(len(self.sorted)/settings('itemsPerPage'))-1
        if maxpage == -1: maxpage = 0
        if self.page < maxpage:     self.GUI['page_next'].configure(state='normal')
        else:                       self.GUI['page_next'].configure(state='disabled')
        if self.page > 0:           self.GUI['page_last'].configure(state='normal')
        else:                       self.GUI['page_last'].configure(state='disabled')
        self.GUI['page_number'].configure(text='Page ' + str(self.page+1) + ' of ' + str(maxpage+1))

        #Appropriately renames the headers
        if self.asset == None:  header = settings('header_portfolio')
        else:                   header = settings('header_asset')
        for i in range(len(header)):
            TEMP['GRID'][0][i+1].configure(text=self.infoLib(self.asset, header[i], 'headername'))

        #Fills in the page with info
        self.populate()

    def populate(self):
        '''Populates the GRID with info'''
        #All the info for every asset 

        for row in range(self.page*settings('itemsPerPage'), (self.page+1)*settings('itemsPerPage')):
            GRID_ROW = (row % settings('itemsPerPage')) + 1
            #Row Number ### 2-10 ms
            TEMP['GRID'][GRID_ROW][0].configure(text=row+1)
            
            #Filling the GRID for each row...
            try:    entry = self.sorted[row] #Entry will be the TICKERCLASS or HASH
            except: entry = None
            if self.asset == None:  headers = settings('header_portfolio')
            else:                   headers = settings('header_asset')
            for info in headers:
                #The GRID text for each column in this row...
                label = TEMP['GRID'][GRID_ROW][headers.index(info)+1]
                if entry == None:           label.configure(text='')
                elif self.asset == None:    label.configure(text=MAIN_PORTFOLIO.asset(entry).prettyPrint(info))
                else:                       label.configure(text=MAIN_PORTFOLIO.transaction(entry).prettyPrint(info, self.asset))

            #Colors the GRID for this row
            self.color_row(GRID_ROW)

    def color_row(self, GRID_ROW, fg=None, bg=None, *kwargs):    #Function that colors the nth row, visual_row, 
        #entry will either be nothing (nothing to display at this row in the GRID), or an asset TICKERCLASS, or a transaction HASH
        try:    entry = self.sorted[GRID_ROW-1+self.page*settings('itemsPerPage')]
        except: entry = None

        if self.asset == None:  headers = settings('header_portfolio')
        else:                   headers = settings('header_asset')

        #The row number
        if fg != None:  TEMP['GRID'][GRID_ROW][0].configure(fg=fg) 
        else:           TEMP['GRID'][GRID_ROW][0].configure(fg=palette('entrycursor')) 
        if bg!= None:   TEMP['GRID'][GRID_ROW][0].configure(bg=bg)
        else:           TEMP['GRID'][GRID_ROW][0].configure(bg=palette('medium'))
        
        #All the info bits
        for info in headers:
            label = TEMP['GRID'][GRID_ROW][headers.index(info)+1]

            #Gathering data that coloring is contingent upon
            if entry != None:
                # ERROR Background color override - something is wrong with this asset or transaction! probably missing data.
                if (self.asset == None and MAIN_PORTFOLIO.asset(entry).ERROR) or (self.asset != None and MAIN_PORTFOLIO.transaction(entry).ERROR):        
                    label.configure(fg=palette('errortext'), bg=palette('error'))
                    continue
                if self.asset == None:  
                    labeldata = MAIN_PORTFOLIO.asset(entry).get(info)
                    labeltext = MAIN_PORTFOLIO.asset(entry).prettyPrint(info)
                else:                   
                    labeldata = MAIN_PORTFOLIO.transaction(entry).get(info, self.asset)
                    labeltext = MAIN_PORTFOLIO.transaction(entry).prettyPrint(info, self.asset)
                color = self.infoLib(self.asset, info, 'color')
            else:
                color = labeltext = None

            #Foreground Coloring
            if labeltext == MISSINGDATA:        label.configure(fg=palette('missingdata'))
            elif color == 'profitloss':
                if labeldata < 0:               label.configure(fg=palette('loss'))
                elif labeldata > 0:             label.configure(fg=palette('profit'))
                else:                           label.configure(fg=palette('entrycursor'))
            elif color == 'accounting':
                if labeldata < 0:               label.configure(fg=palette('loss'))
                else:                           label.configure(fg=palette('entrycursor'))
            elif fg != None:                    label.configure(fg=fg)
            else:                               label.configure(fg=palette('entrycursor'))

            
            #Background Coloring
            if color == 'type':                                             label.configure(bg=palette(labeldata))
            elif GRID_ROW in range(self.GRID_SELECTION[0], self.GRID_SELECTION[1]+1): label.configure(bg=palette('medium'))
            elif bg!= None:                                                 label.configure(bg=bg)
            else:                                                           label.configure(bg=palette('dark'))


#All the commands for reordering, showing, and hiding the info columns
    def move_info_beginning(self, info):
        settingslib['header_portfolio'].remove(info)
        settingslib['header_portfolio'].insert(0, info)
        self.render()
    def move_info_left(self, info):
        i = settingslib['header_portfolio'].index(info) - 1
        settingslib['header_portfolio'].remove(info)
        settingslib['header_portfolio'].insert(i, info)
        self.render()
    def move_info_right(self, info):
        i = settingslib['header_portfolio'].index(info) + 1
        settingslib['header_portfolio'].remove(info)
        settingslib['header_portfolio'].insert(i, info)
        self.render()
    def move_info_end(self, info):
        settingslib['header_portfolio'].remove(info)
        settingslib['header_portfolio'].append(info)
        self.render()
    def hide_info(self, info):
        settingslib['header_portfolio'].remove(info)
        self.TASKBAR['info'].values[info].set(False)
        self.GRID_remove_col()
        self.render()
    def show_info(self, info):
        settingslib['header_portfolio'].insert(0,info)
        self.TASKBAR['info'].values[info].set(True)
        self.GRID_add_col()
        self.render()
#All the commands for sorting the assets
    def set_sort(self, row): #Sets the sorting mode, sorts the assets by it, then rerenders everything
        if self.asset == None:
            info = settings('header_portfolio')[row]
            if settings('sort_asset')[0] == info:   settingslib['sort_asset'][1] = not settingslib['sort_asset'][1]
            else:                                   settingslib['sort_asset'] = [info, False]
        else:
            info = settings('header_asset')[row]
            if settings('sort_trans')[0] == info:   settingslib['sort_trans'][1] = not settingslib['sort_trans'][1]
            else:                                   settingslib['sort_trans'] = [info, False]
        self.render(self.asset, True)
    def sort(self): #Sorts the assets or transactions by the metric defined in settings
        '''Sorts the assets or transactions by the metric defined in settings'''
        if self.asset == None:  #Assets
            info = settings('sort_asset')[0]    #The info we're sorting by
            reverse = settings('sort_asset')[1] #Whether or not it is in reverse order

            sorted = list(MAIN_PORTFOLIO.assetkeys())
            sorted.sort() #Sorts the assets alphabetically by their tickerclass first. This is the default.
            def alphaKey(e):    return MAIN_PORTFOLIO.asset(e).get(info).lower()
            def numericKey(e):
                n = MAIN_PORTFOLIO.asset(e).get(info)
                try: return float(n)
                except: return (reverse-0.5)*float('inf') #Sends missing data values to the bottom of the sorted list
        else:   #Transactions
            info = settings('sort_trans')[0]    #The info we're sorting by
            reverse = settings('sort_trans')[1] #Whether or not it is in reverse order

            sorted = list(MAIN_PORTFOLIO.asset(self.asset)._ledger) #a dict of relevant transactions, this is a list of their keys.

            def dateKey(e): return MAIN_PORTFOLIO.transaction(e).date()
            sorted.sort(reverse=not reverse, key=dateKey) #Sorts the transactions by their date first. This is the default.

            def alphaKey(e):    
                data = MAIN_PORTFOLIO.transaction(e).get(info).lower()
                if data != None:    return data
                else:               return ''
            def numericKey(e):
                n = MAIN_PORTFOLIO.transaction(e).get(info)
                try: return float(n)
                except: return (reverse-0.5)*float('inf') #Sends missing data values to the bottom of the sorted list
            def value_quantity_price(e):
                t = MAIN_PORTFOLIO.transaction(e)
                if info == 'value':     return t.value(self.asset)
                if info == 'quantity':  return t.quantity(self.asset)
                if info == 'price':     return t.price(self.asset)
        
        if self.asset != None and info == 'date':                   sorted.sort(reverse=not reverse, key=alphaKey)  #This is here to ensure that the default date order is newest to oldest. This means reverse alphaetical
        elif self.infoLib(self.asset, info, 'format') == 'alpha':   sorted.sort(reverse=reverse, key=alphaKey)
        elif info in ['value','quantity','price']:                  sorted.sort(reverse=not reverse, key=value_quantity_price)
        else:                                                       sorted.sort(reverse=not reverse, key=numericKey)

        self.sorted = sorted        



#INFO FUNCTIONS
#=============================================================

    def infoLib(self, asset, info, characteristic):   #A single command for getting formatting and header names for info bits
        if asset == None:   return assetinfolib[info][characteristic]
        else:               return transinfolib[info][characteristic]

    def comm_portfolio_info(self): #A wholistic display of all relevant information to the overall portfolio 
        displayInfo = ''

        #Total number of assets and transactions, mainly for measuring performance
        displayInfo += str(TEMP['metrics'][' PORTFOLIO']['number_of_transactions']) + ' transactions loaded under ' + str(TEMP['metrics'][' PORTFOLIO']['number_of_assets']) + ' assets'

        #List of wallets that are both in-use and whitelisted
        walletString = '\nWallets: '
        for wallet in TEMP['metrics'][' PORTFOLIO']['wallets']:
                walletString += str(wallet) + ', '
        displayInfo += walletString[:-2]

        #Total portfolio value
        displayInfo += '\nPortfolio Value: '
        try: displayInfo += format_number(TEMP['metrics'][' PORTFOLIO']['value']) + ' USD'
        except: displayInfo += MISSINGDATA

        #24hr Change
        displayInfo += '\n24-Hour Change: '
        try: displayInfo += format_number(TEMP['metrics'][' PORTFOLIO']['day_change'], '.2f')
        except: displayInfo += MISSINGDATA

        #24hr % Change
        displayInfo += '\n24-Hour % Change: '
        try: displayInfo += format_number(TEMP['metrics'][' PORTFOLIO']['day%'], '.4f') + '%'
        except: displayInfo += MISSINGDATA

        #Week % Change
        displayInfo += '\nWeek % Change: '
        try: displayInfo += format_number(TEMP['metrics'][' PORTFOLIO']['week%'], '.4f') + '%'
        except: displayInfo += MISSINGDATA
        
        #Month % Change
        displayInfo += '\nMonth % Change: '
        try: displayInfo += format_number(TEMP['metrics'][' PORTFOLIO']['month%'], '.4f') + '%'
        except: displayInfo += MISSINGDATA
        
        Message(self, 'Overall Stats and Information', displayInfo, width=100, height=25)
    
    def comm_asset_info(self, a): #A wholistic display of all relevant information to an asset 
        asset = MAIN_PORTFOLIO.asset(a)
        #ASSET CLASS
        displayInfo = 'Asset Class: ' + assetclasslib[asset.assetClass()]['name']

        #WALLETS and their HOLDINGS
        walletsTokensString = ''
        for w in TEMP['metrics'][a]['wallets']:
            if not mp.almosteq(TEMP['metrics'][a]['wallets'][w],0):
                walletsTokensString +=  ', ' + w + ':' + str(TEMP['metrics'][a]['wallets'][w])
        displayInfo += '\nWallets: ' + walletsTokensString[2:]

        for info in ['holdings', 'price', 'value', 'marketcap', 'volume24h', 'day_change', 'day%', 'week%', 'month%', 'portfolio%']:
            displayInfo += '\n' + assetinfolib[info]['name'] + ': ' + str(asset.get(info))


        Message(self, asset.ticker() + ' Stats and Information', displayInfo, width=100, height=25)



#METRICS
#=============================================================
    def metrics(self): # Recalculates all static metrics for all assets and the overall protfolio
        '''Calculates and renders all static metrics for all assets, and the overall portfolio'''
        if 'metrics' not in TEMP: TEMP['metrics'] = {} #To remove metrics for assets that may no longer exist
        TEMP['taxes'] = { 
            '8949':     pd.DataFrame(columns=['Description of property','Date acquired','Date sold or disposed of','Proceeds','Cost or other basis','Gain or (loss)']) ,
            '1099-MISC':pd.DataFrame(columns=['Date acquired', 'Value of assets']),
            }

        self.perform_automatic_accounting()
        for a in MAIN_PORTFOLIO.assetkeys():    self.metrics_ASSET(a, False)
        self.metrics_PORTFOLIO()
        self.market_metrics()

    def market_metrics(self):   # Recalculates all dynamic metrics based on data recovered from the internet
        for a in MAIN_PORTFOLIO.assetkeys():    self.market_metrics_ASSET(a, False)
        self.market_metrics_PORTFOLIO()

    def market_metrics_PORTFOLIO(self): #Recalculates all dynamic market metrics for the overall portfolio
        #Calculates the overall portfolio value
        value = precise(0)
        for a in MAIN_PORTFOLIO.assetkeys():    #Compiles complete list of all wallets used in the portfolio
            try: value += MAIN_PORTFOLIO.asset(a).get('value') #Adds the total value of this asset to the overall portfolio value. If no price data can be found we assume this asset it worthless.
            except: None
        TEMP['metrics'][' PORTFOLIO']['value'] = value

        #Has to be a separate loop so that the total portfolio value is actually the total
        TEMP['metrics'][' PORTFOLIO']['day_change'] = precise(0)
        TEMP['metrics'][' PORTFOLIO']['week_change'] = precise(0)
        TEMP['metrics'][' PORTFOLIO']['month_change'] = precise(0)
        for a in MAIN_PORTFOLIO.assetkeys():
            try:
                self.calculate_portfolio_percentage(a)
                TEMP['metrics'][' PORTFOLIO']['day_change'] += TEMP['metrics'][a]['day_change']
                TEMP['metrics'][' PORTFOLIO']['week_change'] += TEMP['metrics'][a]['week_change']
                TEMP['metrics'][' PORTFOLIO']['month_change'] += TEMP['metrics'][a]['month_change']
            except: pass

        #Calculates the 24-hour % performance of the portfolio
        try:
            TEMP['metrics'][' PORTFOLIO']['day%'] = TEMP['metrics'][' PORTFOLIO']['day_change'] / (TEMP['metrics'][' PORTFOLIO']['value'] - TEMP['metrics'][' PORTFOLIO']['day_change'])
            TEMP['metrics'][' PORTFOLIO']['week%'] = TEMP['metrics'][' PORTFOLIO']['week_change'] / (TEMP['metrics'][' PORTFOLIO']['value'] - TEMP['metrics'][' PORTFOLIO']['week_change'])
            TEMP['metrics'][' PORTFOLIO']['month%'] = TEMP['metrics'][' PORTFOLIO']['month_change'] / (TEMP['metrics'][' PORTFOLIO']['value'] - TEMP['metrics'][' PORTFOLIO']['month_change'])
        except: pass
    def market_metrics_ASSET(self,a, updatePortfolio=True): #Recalculates all dyanmic market metrics for asset 'a'
        self.calculate_value(a)
        self.calculate_unrealized_profit_and_loss(a)
        self.calculate_changes(a)
        self.calculate_net_cash_flow(a)

        if updatePortfolio:
            self.market_metrics_PORTFOLIO()
    def metrics_PORTFOLIO(self): #Recalculates all static metrics for the overall portfolio
        '''Calculates all metrics for the overall portfolio'''
        #ABSOLUTE AND FILTERED TOTALS
        #================================
        TEMP['metrics'][' PORTFOLIO'] = {}
        wallets = TEMP['metrics'][' PORTFOLIO']['wallets'] = set()
        for a in MAIN_PORTFOLIO.assetkeys():    #Compiles complete list of all wallets actually used in the portfolio
            try:    wallets.update(set(TEMP['metrics'][a]['wallets']))
            except: continue
        TEMP['metrics'][' PORTFOLIO']['number_of_transactions'] = len(MAIN_PORTFOLIO.transactions())
        TEMP['metrics'][' PORTFOLIO']['number_of_assets'] = len(MAIN_PORTFOLIO.assets())
    def metrics_ASSET(self,a, updatePortfolio=True): #Recalculates all static metrics for asset 'a'
        '''Calculates all metrics for asset \'a\'
        \n By default, this will also update the overall portfolio metrics'''
        if a not in TEMP['metrics']: TEMP['metrics'][a] = {}

        if updatePortfolio:
            self.metrics_PORTFOLIO()
            
    def perform_automatic_accounting(self, tax_report=''):   #Dependent on the Accounting Method, calculates the Holdings per Wallet, Total Holdings, Average Buy Price, Real P&L (Capital Gains)
        
        #Creates a list of all transactions, sorted chronologically
        transactions = list(MAIN_PORTFOLIO.transactions()) #0ms
        def sortByDate(e):  return e.date()
        transactions.sort(key=sortByDate)


        ###################################
        # TRANSFER LINKING
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
                # We pair them up if they have the same asset, occur within 10 seconds of eachother, and if their quantities are within 0.1% of eachother
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

        # INFO VARIABLES - data we collect as we account for every transaction
        metrics = {}
        for asset in MAIN_PORTFOLIO.assetkeys():
            metrics[asset] = {
                'cash_flow':                precise(0),
                'realized_profit_and_loss': precise(0),
                'tax_capital_gains':        precise(0),
                'tax_income':               precise(0),
            }
        
        # HOLDINGS - The data structure which tracks asset's original price across sales
        holdings = {}
        for asset in MAIN_PORTFOLIO.assetkeys():
            MAIN_PORTFOLIO.asset(asset).ERROR = False # Assume assets are free of error at first. We check all transactions later.
            holdings[asset] = {}
            for wallet in MAIN_PORTFOLIO.walletkeys():
                #A list of tuples, sorted by accounting method, formatted as so: (date, price, quantity remaining) for each transaction where we gained crypto
                holdings[asset][wallet] = [] 

        # STORE and DISBURSE QUANTITY - functions which add, or remove a 'gain', to the HOLDINGS data structure.
        accounting_method = settings('accounting_method')

        def store_quantity(hash, price, quantity, a, w, is_transfer=False):   #Takes ~150 ms for around 2222 transactions
            '''Adds specified gaining transaction to specified wallet.'''
            #Where a 'gains' transaction is any that earns the user crypto, and isn't transfer_in, since transfer_in just moves other gains around
            #So, that is, purchase, gift_in, card_reward, income, and trade.

            new_gain = [hash, precise(price), precise(quantity), MAIN_PORTFOLIO.transaction(hash).date()] #Unique hash, price, quantity, date
            
            if is_transfer:      #If we transferred a gain out and back again, merge it with itself
                for gain in holdings[a][w]:
                    if new_gain[0] == gain[0]:  #If hash identical, then its the same transaction
                        gain[2] += new_gain[2]
                        return
                        
            if len(holdings[a][w])==0:       
                holdings[a][w].append(new_gain)
            else:   #Binary insertion sort. Always insert left of identical
                L,R = (0,holdings[a][w][0]), (len(holdings[a][w])-1,holdings[a][w][len(holdings[a][w])-1])
                c=L[1]
                while L[0] != R[0] and L[1] != R[1]:
                    if L[0]>R[0]: break
                    ci = (L[0]+R[0])//2
                    if   accounting_method == 'hifo':   #HIFO - Most expensive sold first, cheapest at the end
                        if   new_gain[1] < c[1]:    L = (ci+1,holdings[a][w][ci+1])
                        elif new_gain[1] > c[1]:    R = (ci-1,holdings[a][w][ci-1])
                        else:                       L = R = (ci,holdings[a][w][ci])
                    elif accounting_method == 'fifo':   #FIFO - Oldest sold first, newest at the end
                        if   new_gain[3] < c[3]:    L = (ci+1,holdings[a][w][ci+1])
                        elif new_gain[3] > c[3]:    R = (ci-1,holdings[a][w][ci-1])
                        else:                       L = R = (ci,holdings[a][w][ci])
                    elif accounting_method == 'lifo':   #LIFO - Newest sold first, oldest at the end
                        if   new_gain[3] > c[3]:    L = (ci+1,holdings[a][w][ci+1])
                        elif new_gain[3] < c[3]:    R = (ci-1,holdings[a][w][ci-1])
                        else:                       L = R = (ci,holdings[a][w][ci])
                if   accounting_method == 'hifo':   holdings[a][w].insert(L[0]+(new_gain[3] > c[3]), new_gain)
                elif accounting_method == 'fifo':   holdings[a][w].insert(L[0]+(new_gain[3] > c[3]), new_gain)
                elif accounting_method == 'lifo':   holdings[a][w].insert(L[0]+(new_gain[3] < c[3]), new_gain)
                    

        def disburse_quantity(t, quantity, a, w, w2=None):
            '''Removes specified quantity of asset from specified wallet.\n
                Returns the cost basis of the removed quantity.\n
                If wallet2 \'w2\' specified, instead moves quantity into w2.'''
            cost_basis = precise(0)
            remaining_to_remove = precise(quantity)
            if len(holdings) == 0:  return  # ERROR - We're trying to remove tokens.... when there are none. We only report the error on the first one
            for gain in list(holdings[a][w]):
                #CASE 1: the remaining quantity equals or falls above that of this gain.
                if mp.almosteq(gain[2], remaining_to_remove) or remaining_to_remove > gain[2]:
                    cost_basis += gain[1]*gain[2]       #Add the value of this gain to the cost_basis
                    remaining_to_remove -= gain[2]      #Reduce the remaining quantity to remove
                    if w2 != None: store_quantity(gain[0],gain[1],gain[2],a,w2,True)        
                                                                              #The 'post-fee-value' is the sales profit, after fees, weighted to the gain quantity sold 
                    if tax_report == '8949': tax_8949(t, gain, gain[2], quantity)
                    del holdings[a][w][0]    #We have exhausted this gain. Remove it from holdings.
                #CASE 2: the remaining quantity equals or falls below that of this gain. 
                else:
                    cost_basis += gain[1]*remaining_to_remove           #Add the value of what's removed to the cost_basis
                    holdings[a][w][0][2] -= remaining_to_remove         #Remove the final bit from this gain
                    if w2 != None: store_quantity(gain[0],gain[1],remaining_to_remove,a,w2,True)
                    if tax_report == '8949': tax_8949(t, gain, remaining_to_remove, quantity)
                    remaining_to_remove = 0      #Reduce the remaining quantity to remove
                    break                                               #Stop iterating, we've completely disbursed this quantity
            if not zeroish(remaining_to_remove) and remaining_to_remove > 0:   # ERROR - We've removed more than we have. This is a big problem!
                t = MAIN_PORTFOLIO.transaction(t.get_hash())
                t.ERROR,t.ERR_MSG = True,'User disbursed more ' + a.split('z')[0] + ' than they owned from the '+w+' wallet, with ' + str(remaining_to_remove) + ' remaining to disburse.'
            return cost_basis

        def tax_8949(t, gain, subtrans_disburse, total_disburse):
            #########################################################################
            # This is like, way broken right now. This is a tomorrow problem though.
            #########################################################################
            if mp.almosteq(subtrans_disburse, 0):   return
            disburse_date = t.date()
            store_date = MAIN_PORTFOLIO.transaction(gain[0]).date()
            cost_basis = gain[1]*subtrans_disburse
            #The 'post-fee-value' is the sales profit, after fees, weighted to the actual quantity sold 
            post_fee_value = precise(t.get('gain_value'))-precise(t.get('fee_value'))*(subtrans_disburse/precise(total_disburse))
            if post_fee_value < 0:  post_fee_value = precise(0)     #If we gained nothing and there was a fee, it will be negative. We can't have negative proceeds.
            form8949 = {
                'Description of property':      str(subtrans_disburse) + ' ' + MAIN_PORTFOLIO.transaction(gain[0]).get('gain_asset').split('z')[0],  # 0.0328453 ETH
                'Date acquired':                store_date[5:7]+'/'+store_date[8:10]+'/'+store_date[:4],            # 11/12/2021    month, day, year
                'Date sold or disposed of':     disburse_date[5:7]+'/'+disburse_date[8:10]+'/'+disburse_date[:4],   # 6/23/2022     month, day, year
                'Proceeds':                     str(post_fee_value),    # to value gained from this sale/trade/expense/gift_out. could be negative if its a gift_out with a fee.
                'Cost or other basis':          str(cost_basis),        # the cost basis of these tokens
                'Gain or (loss)':               str(precise(post_fee_value) - precise(cost_basis))  # the Capital Gains from this. The P&L. 
                }
            TEMP['taxes']['8949'] = TEMP['taxes']['8949'].append(form8949, ignore_index=True)

        for t in transactions:
            if not t.hasMinInfo()[0]:  t.ERROR,t.ERR_MSG = True,t.hasMinInfo()[1]
            if t.ERROR: continue    #If there is an ERROR with this transaction, ignore it to prevent crashing. User expected to fix this immediately.
            if t.type() == 'transfer_in': continue  #Ignore transfer_in's: due to transfer linking, we can get the t_in wallet name through t_out

            DATE,TYPE,WALLET = t.date(),t.type(),t.wallet()
            LA,FA,GA = t.get('loss_asset'),t.get('fee_asset'),t.get('gain_asset')
            try: LQ = precise(t.get('loss_quantity'))
            except: pass
            try: FQ  = precise(t.get('fee_quantity'))
            except: pass
            try: GQ = precise(t.get('gain_quantity'))
            except: pass
            LOSS_VALUE,FEE_VALUE,GAIN_VALUE = precise(t.get('loss_value')),precise(t.get('fee_value')),precise(t.get('gain_value'))
            LOSS_COST_BASIS,FEE_COST_BASIS = precise(0),precise(0)


            # COST BASIS CALCULATION - The real 'auto-accounting' happens here

            # LOSS - We lose assets one way or another.
            if TYPE in ['sale','trade','expense','gift_out']:   LOSS_COST_BASIS = disburse_quantity(t, LQ, LA, WALLET)
            elif TYPE == 'transfer_out':                        LOSS_COST_BASIS = disburse_quantity(t, LQ, LA, WALLET, t._dest_wallet)
            # FEE LOSS - We lose assets because of a fee
            if FA != None:                                      FEE_COST_BASIS =  disburse_quantity(t, FQ, FA, WALLET)
            # GAINS - We gain assets one way or another
            if TYPE == 'purchase':                              store_quantity(t.get_hash(), (LQ+FQ)/GQ, GQ, GA, WALLET)                    # Purchase price includes fee
            elif TYPE in ['gift_in','card_reward','income']:    store_quantity(t.get_hash(), precise(t.get('gain_price')), GQ, GA, WALLET)  # These have an exact price defined
            elif TYPE == 'trade':                               store_quantity(t.get_hash(), LOSS_VALUE/GQ, GQ, GA, WALLET)                 # Loss/Gain value same, gain price is this


            # METRIC CALCULATION

            # CASH FLOW - Only sales/purchases affect cash flow - thats the only way money goes in/out of your bank account
            if TYPE  == 'purchase': metrics[GA]['cash_flow'] -= GAIN_VALUE + FEE_VALUE
            elif TYPE  == 'sale':   metrics[LA]['cash_flow'] += LOSS_VALUE - FEE_VALUE
            elif TYPE == 'trade':   # Trades are a sort of 'indirect purchase/sale' of an asset.
                metrics[LA]['cash_flow'] += LOSS_VALUE - FEE_VALUE
                metrics[GA]['cash_flow'] -= GAIN_VALUE
            
            # REALIZED PROFIT AND LOSS - Sales and trades sometimes profit, whereas gift_outs, expenses, as well as any fees always incur a loss
            # Fees are always a realized loss, if there is one
            if FA != None:                      metrics[FA]['realized_profit_and_loss'] -= FEE_COST_BASIS   # Base fee cost is realized
            elif TYPE == 'purchase':            metrics[GA]['realized_profit_and_loss'] -= FEE_VALUE        # Base fee cost is realized to asset bought
            elif TYPE == 'sale':                metrics[LA]['realized_profit_and_loss'] -= FEE_VALUE        # Base fee cost is realized to asset sold
            #Expenses and gift_outs are a complete realized loss. Sales and trades we already lost the fee, but hopefully gain more from sale yield
            if TYPE in ['expense','gift_out']:  metrics[LA]['realized_profit_and_loss'] -= LOSS_COST_BASIS  # Base loss cost is realized
            elif TYPE in ['sale','trade']:      metrics[LA]['realized_profit_and_loss'] += LOSS_VALUE - LOSS_COST_BASIS # Base loss cost is realized, but sale yields the loss value

            # CAPITAL GAINS TAX
            #Independent transfer fees are taxed as a 'sale'
            if TYPE in ['gift_out','transfer_out'] and FA != None:  metrics[FA]['tax_capital_gains'] += FEE_VALUE - FEE_COST_BASIS
            #Expenses taxed as a 'sale', trade treated as an immediate sale and purchase
            elif TYPE in ['sale','expense','trade']:                metrics[LA]['tax_capital_gains'] += (LOSS_VALUE - FEE_VALUE) - LOSS_COST_BASIS 

            # INCOME TAX
            if TYPE in ['card_reward','income']:    #This accounts for all transactions taxable as INCOME: card rewards, and staking rewards
                metrics[GA]['tax_income'] += GAIN_VALUE
                if tax_report=='1099-MISC':  
                    TEMP['taxes']['1099-MISC'] = TEMP['taxes']['1099-MISC'].append( {'Date acquired':DATE, 'Value of assets':str(GAIN_VALUE)}, ignore_index=True)
            
            #*** *** *** DONE FOR THIS TRANSACTION *** *** ***#
            
        #And that's it! We calculate the average buy price AFTER figuring out what tokens we have left.

        #ERRORS - applies error state to any asset with an erroneous transaction on its ledger.
        for t in transactions:
            if t.ERROR:     
                if t.get('loss_asset') != None: MAIN_PORTFOLIO.asset(t.get('loss_asset')).ERROR = True
                if t.get('fee_asset') != None:  MAIN_PORTFOLIO.asset(t.get('fee_asset')).ERROR =  True
                if t.get('gain_asset') != None: MAIN_PORTFOLIO.asset(t.get('gain_asset')).ERROR = True


        for a in MAIN_PORTFOLIO.assetkeys():
            TEMP['metrics'][a] = {}
            TEMP['metrics'][a]['cash_flow'] = metrics[a]['cash_flow']
            TEMP['metrics'][a]['realized_profit_and_loss'] = metrics[a]['realized_profit_and_loss']
            TEMP['metrics'][a]['tax_capital_gains'] = metrics[a]['tax_capital_gains']
            TEMP['metrics'][a]['tax_income'] = metrics[a]['tax_income']

            total_investment_value = precise(0)
            total_holdings = precise(0)
            wallet_holdings = {}
            for w in holdings[a]:
                wallet_holdings[w] = precise(0)
                for gain in holdings[a][w]:
                    total_investment_value  += gain[1]*gain[2]  #USD value of this gain
                    total_holdings          += gain[2]          #Single number for the total number of tokens
                    wallet_holdings[w]      += gain[2]          #Number of tokens within each wallet

            TEMP['metrics'][a]['holdings'] = total_holdings
            TEMP['metrics'][a]['wallets'] = wallet_holdings
            
            if mp.almosteq(total_holdings, 0):  TEMP['metrics'][a]['average_buy_price'] = 0
            else:                               TEMP['metrics'][a]['average_buy_price'] = total_investment_value / total_holdings

    def calculate_value(self, a):   #Calculates the overall value of this asset
        #Must be a try statement because it relies on market data
        asset = MAIN_PORTFOLIO.asset(a)
        try:    TEMP['metrics'][a]['value'] = asset.get('holdings') * asset.get('price')
        except: TEMP['metrics'][a]['value'] = MISSINGDATA
    def calculate_unrealized_profit_and_loss(self, a):
        #You need current market data for these bad boys
        asset = MAIN_PORTFOLIO.asset(a)
        average_buy_price = asset.get('average_buy_price')
        if average_buy_price == 0: TEMP['metrics'][a]['unrealized_profit_and_loss%'] = TEMP['metrics'][a]['unrealized_profit_and_loss'] = 0
        else:
            try:        
                TEMP['metrics'][a]['unrealized_profit_and_loss'] =     asset.get('value') - ( average_buy_price * asset.get('holdings') )
                TEMP['metrics'][a]['unrealized_profit_and_loss%'] = ( asset.get('price') /  average_buy_price )-1
            except:     TEMP['metrics'][a]['unrealized_profit_and_loss%'] = TEMP['metrics'][a]['unrealized_profit_and_loss'] = MISSINGDATA
    def calculate_changes(self, a): #Calculates the unrealized USD lost or gained in the last 24 hours, week, and month for this asset
        #Must be a try statement because it relies on market data
        asset = MAIN_PORTFOLIO.asset(a)
        value = asset.get('value')
        try:
            TEMP['metrics'][a]['day_change'] = value-(value / (1 + asset.get('day%')))
            TEMP['metrics'][a]['week_change'] = value-(value / (1 + asset.get('week%')))
            TEMP['metrics'][a]['month_change'] = value-(value / (1 + asset.get('month%')))
        except: pass
    def calculate_net_cash_flow(self, a): #Calculates what the cash flow would become if you sold everything right now
        asset = MAIN_PORTFOLIO.asset(a)
        #Must be a try statement because it relies on market data
        try: TEMP['metrics'][a]['net_cash_flow'] = asset.get('cash_flow') + asset.get('value') 
        except: TEMP['metrics'][a]['net_cash_flow'] = MISSINGDATA



    def calculate_portfolio_percentage(self, a): #Calculates how much of the value of your portfolio is this asset
        portfolio_value = TEMP['metrics'][' PORTFOLIO']['value']
        if portfolio_value == 0:    TEMP['metrics'][a]['portfolio%'] = precise(0)
        else:                       TEMP['metrics'][a]['portfolio%'] = MAIN_PORTFOLIO.asset(a).get('value')  / TEMP['metrics'][' PORTFOLIO']['value']


#BINDINGS
#=============================================================
    def _mousewheel(self, event):   #Scroll up and down the assets pane
        if self.grab_current() == self: #If any other window is open, then you can't do this
            if event.delta > 0:     self.comm_page_last()
            elif event.delta < 0:   self.comm_page_next()
    def _shift_mousewheel(self, event):  #UPDATE UPDATE UPDATE === Scroll left and right across the assets pane
        return
        if self.grab_current() == self: #If any other window is open, then you can't do this
            scrollDir = event.delta/120
            delta = settings('font')[1]*8    #bigger font size means faster scrolling!
            if self.GUI['assetFrame'].winfo_x() > -delta and scrollDir > 0:
                self.GUI['assetCanvas'].xview_moveto(0)
            else:
                self.GUI['assetCanvas'].xview_moveto( (-self.GUI['assetFrame'].winfo_x()-delta*scrollDir) / self.GUI['assetFrame'].winfo_width() )
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
                if MAIN_PORTFOLIO.hasAsset(self.asset): self.render(self.asset, True)
                else:                                   self.render(None, True)
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
                if MAIN_PORTFOLIO.hasAsset(self.asset): self.render(self.asset, True)
                else:                                   self.render(None, True)
    def _esc(self,event):    #Exit this window
        if self.grab_current() == self: #If any other window is open, then you can't do this
            if self.GRID_SELECTION != [-1, -1]:  self.GRID_clear_selection()
            elif self.asset == None:  self.comm_quit()        #If we're on the main page, exit the program
            else:                   self.render(None, True) #If we're looking at an asset, go back to the main page
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





