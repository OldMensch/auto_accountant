#In-house
from AAlib import *
from AAmarketData import startMarketDataLoops, marketdatalib
from AAimport import *

from AAdialogues import *

from AAtooltip import CreateToolTip

#3rd party libraries
from mpmath import mpf as precise
from mpmath import mp
mp.dps = 50

#Default Python
import tkinter as tk
from functools import partial as p
from tkinter.filedialog import *
import os
import copy
import math

from threading import Thread

class Portfolio(tk.Tk):
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
        
        self.create_taskbar()
        self.create_GUI()
        self.create_MENU()

        #Load the last-opened portfolio, if the file exists and we set that in settings. Otherwise, start a new portfolio.
        if settings('startWithLastSaveDir') and os.path.isfile(settings('lastSaveDir')):    self.comm_loadPortfolio(settings('lastSaveDir'))
        else:                                                                               self.comm_newPortfolio(first=True)

        #Now that the hard data is loaded, we load market data
        if settings('offlineMode'):
            #If in Offline Mode, try to load any saved offline market data. If there isn't a file, revert to using the internet.
            global marketdatalib
            #try:
            marketdatalib = json.load(open('#OfflineMarketData.json', 'r'))
            print('||INFO|| OFFLINE MODE - NOT USING REAL MARKET DATA')
            print('||INFO|| Data is from ' + marketdatalib['_timestamp'])
            self.market_metrics()
            self.render(None, True)
            #except:
            #    settingslib['offlineMode'] = False
            #    print('||ERROR|| Failed to load offline market data, data file not found! Reverting to online mode.')
        #If online, we just turn on data production
        else:   startMarketDataLoops(self, settings('offlineMode'))

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
        taskbar = tk.Menu(self, tearoff=0)     #The big white bar across the top of the window
        self.configure(menu=taskbar)

        #'File' Tab
        filemenu = tk.Menu(self, tearoff=0)
        taskbar.add_cascade(menu=filemenu, label='File')
        filemenu.add_command(label='New',     command=self.comm_newPortfolio)
        filemenu.add_command(label='Load...',    command=self.comm_loadPortfolio)
        filemenu.add_command(label='Save',    command=self.comm_savePortfolio)
        filemenu.add_command(label='Save As...', command=p(self.comm_savePortfolio, True))
        filemenu.add_command(label='Merge Portfolio', command=self.comm_mergePortfolio)
        importmenu = tk.Menu(self, tearoff=0)
        filemenu.add_cascade(menu=importmenu, label='Import')
        importmenu.add_command(label='Import Coinbase/Coinbase Pro History', command=self.comm_importCoinbase)
        importmenu.add_command(label='Import Gemini/Gemini Earn History', command=self.comm_importGemini)
        importmenu.add_command(label='Import Etherscan History', command=self.comm_importEtherscan)
        filemenu.add_separator()
        filemenu.add_command(label='QUIT', command=self.comm_quit)

        #'Settings' Tab
        settingsmenu = tk.Menu(self, tearoff=0)
        taskbar.add_cascade(menu=settingsmenu, label='Settings')
        settingsmenu.add_command(label='Restore Default Settings', command=self.restoreDefaultSettings)

        #'About' Tab
        aboutmenu = tk.Menu(self, tearoff=0)
        taskbar.add_cascade(menu=aboutmenu, label='About')
        aboutmenu.add_command(label='MIT License', command=self.comm_copyright)

        #'Info' Tab
        infomenu = tk.Menu(self, tearoff=0)
        taskbar.add_cascade(menu=infomenu, label='Info')

        self.assetheadermenu = {}
        def toggle_header(info):
            if info in settings('header_portfolio'):
                self.hide_info(info)
            else:
                self.show_info(info)

        for info in assetinfolib:
            self.assetheadermenu[info] = tk.BooleanVar()
            if info in settings('header_portfolio'):
                self.assetheadermenu[info].set(True)
            infomenu.add_checkbutton(label=assetinfolib[info]['name'], command=p(toggle_header, info), onvalue = True,offvalue = False,variable=self.assetheadermenu[info])

        #'Accounting' Tab
        accountingmenu = tk.Menu(self, tearoff=0)
        taskbar.add_cascade(menu=accountingmenu, label='Accounting')
        def set_accounting_method(method):
            settingslib['accounting_method'] = method
            self.metrics()
            self.render(self.asset, True)
        self.accounting_method = tk.StringVar()
        self.accounting_method.set(settings('accounting_method'))
        accountingmenu.add_radiobutton(label='First in First Out (FIFO)',       variable=self.accounting_method, value='fifo',    command=p(set_accounting_method, 'fifo'))
        accountingmenu.add_radiobutton(label='Last in First Out (LIFO)',        variable=self.accounting_method, value='lifo',    command=p(set_accounting_method, 'lifo'))
        accountingmenu.add_radiobutton(label='Highest in First Out (HIFO)',     variable=self.accounting_method, value='hifo',    command=p(set_accounting_method, 'hifo'))

        #'Taxes' Tab
        taxmenu = tk.Menu(self, tearoff=0)
        taskbar.add_cascade(menu=taxmenu, label='Taxes')
        taxmenu.add_command(label='Generate data for IRS Form 8949', command=self.tax_Form_8949)
        taxmenu.add_command(label='Generate data for IRS Form 1099-MISC', command=self.tax_Form_1099MISC)

        #'DEBUG' Tab
        debugmenu = tk.Menu(self, tearoff=0)
        taskbar.add_cascade(menu=debugmenu, label='DEBUG')
        debugmenu.add_command(label='Export PERM to DEBUG.json',     command=self.DEBUG_print_PERM)
        debugmenu.add_command(label='Export TEMP to DEBUG.json',     command=self.DEBUG_print_TEMP)
        debugmenu.add_command(label='Export Market Data for Offline Mode.json',     command=self.DEBUG_save_marketdatalib)
        debugmenu.add_command(label='DEBUG dialogue box',     command=self.DEBUG_dialogue)
        #debugmenu.add_command(label='Restart Auto-Accountant',     command=self.DEBUG_restart_test)

    def restoreDefaultSettings(self):
        Message(self, 'Error!', 'This would restart the program... but this seems to cause crashing. Will fix eventually.')
        return
        settingslib.clear()
        settingslib.update(defsettingslib)
        saveSettings()
        self.destroy()
        
    def tax_Form_8949(self):
        dir = asksaveasfilename( defaultextension='.CSV', filetypes={('CSV','.csv')}, title='Save data for IRS Form 8949')
        if dir == '':
            return
        open(dir, 'w', newline='').write(TEMP['taxes']['8949'].to_csv())

    def tax_Form_1099MISC(self):
        dir = asksaveasfilename( defaultextension='.CSV', filetypes={('CSV','.csv')}, title='Save data for IRS Form 1099-MISC')
        if dir == '':
            return
        open(dir, 'w', newline='').write(TEMP['taxes']['1099-MISC'].to_csv())


    def DEBUG_print_PERM(self):
        json.dump(PERM, open('DEBUG.json', 'w'), sort_keys=True, indent=4)
    def DEBUG_print_TEMP(self):
        toWrite = str(TEMP).replace('<','\'').replace('>','\'').replace('\'','\'')
        open('DEBUG.json', 'w').write(toWrite)
        toDump = json.load(open('DEBUG.json', 'r'))
        json.dump(toDump, open('DEBUG.json', 'w'), sort_keys=True, indent=4)
    def DEBUG_save_marketdatalib(self):
        json.dump(marketdatalib, open('#OfflineMarketData.json', 'w'), indent=4, sort_keys=True)
    def DEBUG_dialogue(self):
        testdialogue = Dialogue(self, "Dialogue Title")
        testdialogue.add_menu_button("close", command=testdialogue.close)
        testdialogue.add_label(0, 0, "dayte:")
        testdialogue.add_label(0, 1, "positive float: ")
        testdialogue.add_label(0, 2, "float: ")
        testdialogue.add_label(0, 3, "one-liner:")
        testdialogue.add_label(0, 4, "description:")
        date = testdialogue.add_entry(1, 0, '0000/00/00 00:00:00', format='date')
        posfloat = testdialogue.add_entry(1, 1, '', format='pos_float', charLimit=16)
        float = testdialogue.add_entry(1, 2, '', format='float', charLimit=16)
        text = testdialogue.add_entry(1, 3, '', charLimit=10)
        desc = testdialogue.add_entry(1, 4, 'a\nb\nc', format='description')
        def printdata():    print(desc.entry())
        testdialogue.add_menu_button("print data", command=printdata)
        testdialogue.center_dialogue()
    def DEBUG_restart_test(self):
        self.destroy()

    def comm_importCoinbase(self):  #Imports COINBASE transaction history into the portfolio
        dir = askopenfilename( filetypes={('CSV','.csv')}, title='Import Coinbase/Coinbase Pro Transaction History')
        if dir == '':   return
        import_coinbase(self, dir)
    def comm_importGemini(self):    #imports GEMINI transaction history into the portfolio
        dir = askopenfilename( filetypes={('XLSX','.xlsx')}, title='Import Gemini/Gemini Earn Transaction History')
        if dir == '':   return
        import_gemini(self, dir)
    def comm_importEtherscan(self): #imports ETHERSCAN transaction history into the portfolio
        dir = askopenfilename( filetypes={('CSV','.csv')}, title='Import Etherscan ETH/ERC-20 Transaction History')
        if dir == '':   return
        import_etherscan(self, dir)

    def comm_savePortfolio(self, saveAs=False, secondary=None):
        if saveAs or settings('lastSaveDir') == '':
            dir = asksaveasfilename( defaultextension='.JSON', filetypes={('JSON','.json')}, title='Save Portfolio')
        else:
            dir = settings('lastSaveDir')
        if dir == '':
            return
        self.title('Portfolio Manager - ' + dir)
        
        json.dump(PERM, open(dir, 'w'), sort_keys=True)
        if secondary != None:   secondary()
        if saveAs:              settingslib['lastSaveDir'] = dir
    def comm_newPortfolio(self, first=False):
        settingslib['lastSaveDir'] = ''
        self.init_PERM()
        self.title('Portfolio Manager')
        self.profile = ''   #name of the currently selected profile. Always starts with no filter applied.
        self.create_PROFILE_MENU()
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
        self.init_PERM(decompile)
        self.title('Portfolio Manager - ' + dir)
        settingslib['lastSaveDir'] = dir
        self.profile = ''   #name of the currently selected profile. Always starts with no filter applied.
        self.metrics()
        self.render(None, True)   
        self.create_PROFILE_MENU()   
        self.undo_save()  
    def comm_mergePortfolio(self):
        dir = askopenfilename( filetypes={('JSON','.json')}, title='Load Portfolio for Merging')
        if dir == '':
            return
        try:
            decompile = json.load(open(dir, 'r'))    #Attempts to load the file
        except:
            Message(self, 'Error!', '\'file\' is an unparseable JSON file. Probably missing commas or brackets.' )
            return
        self.init_PERM(decompile, True)
        settingslib['lastSaveDir'] = '' #resets the savedir. who's to say where a merged portfolio should save to? why should it be the originally loaded file, versus any recently merged ones?
        self.title('Portfolio Manager')
        self.profile = ''   #name of the currently selected profile. Always starts with no filter applied.
        self.create_PROFILE_MENU()
        self.metrics()
        self.render(None, True)
        self.undo_save()

    def comm_quit(self, finalize=False):
        '''Quits the program. Set finalize to TRUE to skip the \'are you sure?' prompt.'''
        if not finalize:   
            if self.isUnsaved():
                unsavedPrompt = Prompt(self, 'Unsaved Changes', 'Are you sure you want to quit? This cannot be undone!')
                unsavedPrompt.add_menu_button('Quit', bg="#ff0000", command=p(self.comm_quit, True) )
                unsavedPrompt.add_menu_button('Save and Quit', bg="#0088ff", command=p(self.comm_savePortfolio, secondary=p(self.comm_quit, True)))
                unsavedPrompt.center_dialogue()
            else:
                self.comm_quit(True)
        else:
            #also, closing the program always saves the settings!
            saveSettings()
            exit(1)

    def init_PERM(self, toLoad=None, merge=False):
        if not merge:           #LOADING and NEW
            PERM.clear()
            PERM.update({
            'addresses' : {},
            'assets' : {},
            'wallets' : {},
            'profiles' : {}
            })
        if toLoad != None:
            errorMsg = ''
            try:    toLoad['addresses']
            except: errorMsg += 'addresses, '
            try:    toLoad['assets']
            except: errorMsg += 'assets, '
            try:    toLoad['wallets']
            except: errorMsg += 'wallets, '
            try:    toLoad['profiles']
            except: errorMsg += 'profiles, '
            if errorMsg != '':  Message(self, 'Load Warning!', 'File contains no ' + errorMsg + '.')

            if not merge:     #LOADING
                PERM.update(toLoad)
            else:             #MERGING
                #Merges assets and transactions. If transactions are of the same ID, the old portfolio is overwritten
                try:    PERM['addresses'].update(toLoad['addresses'])   
                except: None
                try:
                    for asset in list(toLoad['assets']):
                        if asset not in PERM['assets']:
                            PERM['assets'][asset] = toLoad['assets'][asset]
                        else:
                            PERM['assets'][asset]['trans'].update( toLoad['assets'][asset]['trans'] )
                except: None
                try:    PERM['wallets'].update(toLoad['wallets'])       
                except: None
                try:    PERM['profiles'].update(toLoad['profiles'])     
                except: None

    def isUnsaved(self):
        lastSaveDir = settings('lastSaveDir')
        if {} == PERM['wallets'] == PERM['profiles'] == PERM['assets']: #there is nothing to save, thus nothing is unsaved     
            return False
        elif lastSaveDir == '': 
            return True     #If you haven't saved anything yet, then yes, its 100% unsaved
        elif not os.path.isfile(lastSaveDir):
            return True     #Only happens if you deleted the file that the program was referencing, while using the program
        lastSaveHash = hash(json.dumps(json.load(open(lastSaveDir, 'r')))) #hash for last loaded file
        currentDataHash = hash(json.dumps(PERM, sort_keys=True))
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
        self.GUI['add'] = tk.Button(self.GUI['buttonFrame'], text='+',  bg=palette('entry'), fg=palette('entrycursor'), font=settings('font'), command=p(AssetEditor, self))
        self.GUI['summary'] = tk.Label(self.GUI['primaryFrame'], font=settings('font', 0.5), fg=palette('entrycursor'),  bg=palette('accent'))
        self.GUI['back'] = tk.Button(self.GUI['primaryFrame'], text='Return to\nPortfolio', font=settings('font', 0.5),  fg=palette('entrycursor'), bg=palette('entry'), command=p(self.render, None, True))
        self.GUI['page_number'] = tk.Label(self.GUI['primaryFrame'], text='Page XXX of XXX', font=settings('font', 0.5), fg=palette('entrycursor'),  bg=palette('accentdark'))
        self.GUI['page_next'] = tk.Button(self.GUI['primaryFrame'], image=icons('arrow_down'), bg=palette('entry'), command=self.comm_page_next)
        self.GUI['page_last'] = tk.Button(self.GUI['primaryFrame'], image=icons('arrow_up'), bg=palette('entry'), command=self.comm_page_last)
        #contains the list of assets/transactions
        self.GUI['secondaryFrame'] = tk.Frame(self, bg=palette('dark'))
        #The little bar on the bottom
        self.GUI['bottomFrame'] = tk.Frame(self, bg=palette('accent'))
        self.GUI['bottomLabel'] = tk.Button(self.GUI['bottomFrame'], bd=0, bg=palette('accent'), text='Copyright © 2022 Shane Evanson', fg=palette('entrycursor'), font=settings('font',0.4), command=self.comm_copyright)

        #GUI RENDERING
        #==============================
        self.GUI['menuFrame']       .grid(column=0,row=0, columnspan=2, sticky='EW')

        self.GUI['primaryFrame']    .grid(column=0,row=1, sticky='NS')
        self.GUI['title']           .grid(column=0,row=0, columnspan=2)
        self.GUI['subtitle']        .grid(column=0,row=1, columnspan=2, sticky='EW')
        self.GUI['buttonFrame']     .grid(column=0,row=2, columnspan=2, sticky='EW')
        self.GUI['info']            .pack(side='left')
        self.GUI['add']        .pack(side='right')
        self.GUI['summary']         .grid(column=0,row=3, columnspan=2, sticky='NSEW')
        self.GUI['primaryFrame'].rowconfigure(3, weight=1)
        self.GUI['page_number']     .grid(column=0,row=5, columnspan=2, sticky='SEW')
        self.GUI['page_last']       .grid(column=0,row=6, sticky='SE')
        self.GUI['page_next']       .grid(column=1,row=6, sticky='SW')
        
        self.GUI['secondaryFrame']  .grid(column=1,row=1, sticky='NSEW')
        
        self.GUI['bottomFrame']     .grid(column=0,row=2, columnspan=2, sticky='EW')
        self.GUI['bottomLabel']     .pack(side='left')

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
                else:                   TransEditor(self, self.asset, self.sorted[i])
            except: return
            self.clear_selection()
        else:
            self.clear_selection()
            self.GRID_SELECTION = [GRID_ROW, GRID_ROW]
    def _right_click_row(self, GRID_ROW, event): # Opens up a little menu of stuff you can do to this asset/transaction
        #we've right clicked with a selection of multiple items
        if self.GRID_SELECTION != [-1, -1] and self.GRID_SELECTION[0] != self.GRID_SELECTION[1]:
            m = tk.Menu(tearoff = 0)
            m.add_command(label ='Delete selection', command=p(self.comm_delete_selection, self.GRID_SELECTION))
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
                m.add_command(label ='Open ' + self.printInfo('ticker', asset) + ' Ledger', command=p(self.render, self.sorted[i], True))
                m.add_command(label ='Edit ' + self.printInfo('ticker', asset), command=p(AssetEditor, self, asset))
                m.add_command(label ='Show detailed info', command=p(self.comm_asset_info, asset))
                m.add_command(label ='Delete ' + self.printInfo('ticker', asset), command=p(self.comm_delete_selection, [GRID_ROW, GRID_ROW]))
            else:
                m.add_command(label ='Edit ' +  self.printInfo('date', self.asset, trans), command=p(TransEditor, self, self.asset, self.sorted[i]))
                m.add_command(label ='Delete ' + self.printInfo('date', self.asset, trans), command=p(self.comm_delete_selection, [GRID_ROW, GRID_ROW]))
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

    def clear_selection(self):
        if self.GRID_SELECTION == [-1, -1]: return
        oldsel = self.GRID_SELECTION
        self.GRID_SELECTION = [-1, -1]
        for row in range(oldsel[0], oldsel[1]+1):   self.color_row(row)

    def comm_delete_selection(self, toDelete, *kwargs):
        for item_index in range( self.page*settings('itemsPerPage')+toDelete[0]-1, self.page*settings('itemsPerPage')+toDelete[1]):
            try:
                if self.asset == None:  PERM['assets'].pop(self.sorted[item_index])
                else:                   PERM['assets'][self.asset]['trans'].pop(self.sorted[item_index])
            except: continue
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
        
        #MENU TOOLTIPS
        #==============================
        tooltips = {
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
            CreateToolTip(self.MENU[button] ,tooltips[button])

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

    def create_PROFILE_MENU(self):
        '''Creates the little dropdown for selecting a profile to filter by'''
        def alphaKey(e):        #creates a sorted list of all the current profiles
                return e.lower()
        profilesList = []
        for prof in PERM['profiles']:
            profilesList.append(prof)
        profilesList.sort(key=alphaKey)
        profilesList.insert(0, '-NO FILTER-')

        if 'profileSelect' in self.MENU:
            self.MENU['profileSelect'].destroy()

        if self.profile == '':
            self.MENU['profileSelectValue'] = tk.StringVar(self, profilesList[0])
        else:
            self.MENU['profileSelectValue'] = tk.StringVar(self, profilesList[profilesList.index(self.profile)])

        self.MENU['profileSelect'] = tk.OptionMenu(self.GUI['menuFrame'], self.MENU['profileSelectValue'], *profilesList, command=self.comm_applyProfile)
        self.MENU['profileSelect'].configure(bg=palette('entry'), fg=palette('entrycursor'), font=settings('font'), highlightthickness=0)

        
        self.MENU['profileSelect']      .grid(column=10,row=0, sticky='NS')

    def comm_applyProfile(self, *kwargs):
        if kwargs[0] == '-NO FILTER-':  self.profile = ''
        else:                           self.profile = kwargs[0]
        self.metrics()
        self.render(self.asset, True)

    def comm_page_next(self):
        if self.asset == None:  maxpage = math.ceil(len(PERM['assets'])/settings('itemsPerPage')-1)
        else:                   maxpage = math.ceil(len(PERM['assets'][self.asset]['trans'])/settings('itemsPerPage')-1)
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
            self.clear_selection()  #Clear the selection too. 
            if asset == None:
                self.GRID_set_col(len(settings('header_portfolio')))
                self.GUI['info'].configure(command=self.comm_portfolio_info)
                self.GUI['edit'].pack_forget()
                self.GUI['add'].configure(command=p(AssetEditor, self))
                self.GUI['back'].grid_forget()
            else:
                self.GRID_set_col(len(settings('header_asset')))
                self.GUI['info'].configure(command=p(self.comm_asset_info, asset))
                self.GUI['edit'].configure(command=p(AssetEditor, self, asset))
                self.GUI['edit'].pack(side='left')
                self.GUI['add'].configure(command=p(TransEditor, self, asset))
                self.GUI['back'].grid(row=4, column=0, columnspan=2)

        #Setting up stuff in the Primary Pane
        if asset == None:
            self.GUI['title'].configure(text='Auto-Accountant')
            self.GUI['subtitle'].configure(text='Overall Portfolio')
        else:      
            self.GUI['title'].configure(text=self.printInfo('name', asset))
            self.GUI['subtitle'].configure(text=self.printInfo('ticker', asset))

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
            #Row Number ### 2-10 ms, kinda weird and random
            TEMP['GRID'][GRID_ROW][0].configure(text=row+1)
            
            #Filling the GRID text
            try:    entry = self.sorted[row]
            except: entry = None
            if self.asset == None:  headers = settings('header_portfolio')
            else:                   headers = settings('header_asset')
            for info in headers:
                label = TEMP['GRID'][GRID_ROW][headers.index(info)+1]
                label.configure(font=settings('font')) #0-40 ms for 
                if entry == None:           label.configure(text='')
                elif self.asset == None:    label.configure(text=self.printInfo(info, entry))
                else:                       label.configure(text=self.printInfo(info, self.asset, entry))

            #Filling the GRID color
            self.color_row(GRID_ROW)

    def color_row(self, GRID_ROW, fg=None, bg=None, *kwargs):    #Function that colors the nth row, visual_row, 
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

            #MISSINGWALLET Background color override
            if   self.asset == None and entry != None and TEMP['metrics'][entry][' MISSINGWALLET']:        
                label.configure(fg=palette(' MISSINGWALLETtext'), bg=palette(' MISSINGWALLET'))
                continue
            elif self.asset != None and entry != None and ' MISSINGWALLET' in [self.info('wallet', self.asset, entry), self.info('wallet2', self.asset, entry)]:
                label.configure(fg=palette(' MISSINGWALLETtext'), bg=palette(' MISSINGWALLET'))
                continue

            #Gathering data that coloring is contingent upon
            if entry != None:
                if self.asset == None:  
                    labeldata = self.info(info, entry)
                    labeltext = self.printInfo(info, entry)
                else:                   
                    labeldata = self.info(info, self.asset, entry)
                    labeltext = self.printInfo(info, self.asset, entry)
                color = self.infoLib(self.asset, info, 'color')
            else:
                color = labeltext = None

            #Foreground Coloring
            if labeltext == MISSINGDATA:        label.configure(fg=palette('error'))
            elif color == 'profitloss':
                if labeldata < 0:               label.configure(fg=palette('loss'))
                elif labeldata > 0:             label.configure(fg=palette('profit'))
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
        self.assetheadermenu[info].set(False)
        self.GRID_remove_col()
        self.render()
    def show_info(self, info):
        settingslib['header_portfolio'].insert(0,info)
        self.assetheadermenu[info].set(True)
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
        if self.asset == None:
            info = settings('sort_asset')[0]    #The info we're sorting by
            reverse = settings('sort_asset')[1] #Whether or not it is in reverse order

            sorted = list(PERM['assets'])
            sorted.sort() #Sorts the assets by their ticker first. This is the default.
            def alphaKey(e):    return self.info(info, e).lower()
            def numericKey(e):
                n = self.info(info, e)
                try: return float(n)
                except: return (reverse-0.5)*float('inf') #Sends missing data values to the bottom of the sorted list
        else:
            info = settings('sort_trans')[0]    #The info we're sorting by
            reverse = settings('sort_trans')[1] #Whether or not it is in reverse order

            sorted = list(PERM['assets'][self.asset]['trans'])
            sorted.sort(reverse=True) #Sorts the transactions by their date first. This is the default.
            def alphaKey(e):    return self.info(info, self.asset, e).lower()
            def numericKey(e):
                n = self.info(info, self.asset, e)
                try: return float(n)
                except: return (reverse-0.5)*float('inf') #Sends missing data values to the bottom of the sorted list
        
        if self.asset != None and info == 'date':                   sorted.sort(reverse=not reverse, key=alphaKey)  #This is here to ensure that the default date order is newest to oldest. This means reverse alphaetical
        elif self.infoLib(self.asset, info, 'format') == 'alpha':   sorted.sort(reverse=reverse, key=alphaKey)
        else:                                                       sorted.sort(reverse=not reverse, key=numericKey)

        self.sorted = sorted        



#INFO ACCESS FUNCTIONS
#=============================================================

    def info(self, info, a, t=None):  #A single command for accessing information
        if t == None:
            try:
                if info == 'ticker':        return a.split('z')[0]
                elif info == 'name':        return PERM['assets'][a]['name']
                elif info == 'class':       return assetclasslib[a.split('z')[1]]['name']
                elif info in ['price', 'marketcap', 'volume24h', 'day%', 'week%', 'month%']:    return precise(marketdatalib[a][info])
                elif info in assetinfolib:  return precise(TEMP['metrics'][a][info])
            except: return MISSINGDATA
            quit('||ERROR|| Unknown asset info ' + info)
        else:
            type = PERM['assets'][a]['trans'][t]['type']
            try:
                if info == 'date':      return t
                elif info == 'type':    return type
                elif info == 'tokens':  return precise(PERM['assets'][a]['trans'][t]['tokens'])
                elif info == 'usd':    
                    if type in ['purchase', 'sale']:    return precise(PERM['assets'][a]['trans'][t]['usd'])
                    elif type in ['gift', 'expense']:   return precise(PERM['assets'][a]['trans'][t]['price'])*precise(PERM['assets'][a]['trans'][t]['tokens'])
                    else:                               return ''
                elif info == 'price':
                    if type in ['purchase', 'sale']:    return precise(PERM['assets'][a]['trans'][t]['usd'])/precise(PERM['assets'][a]['trans'][t]['tokens'])
                    elif type in ['gift', 'expense']:   return precise(PERM['assets'][a]['trans'][t]['price'])
                    else:                               return ''
                elif info == 'wallet':  return PERM['assets'][a]['trans'][t]['wallet']
                elif info == 'wallet2': return PERM['assets'][a]['trans'][t]['wallet2']
                elif info == 'wallets':     
                    if type == 'transfer':  return 'From ' + self.info('wallet', a, t) + ' to ' + self.info('wallet2', a, t)
                    else:                   return self.info('wallet', a, t)
            except: return MISSINGDATA
            quit('||ERROR|| Unknown transaction info ' + info)

    def printInfo(self, info, a, t=None):  #A single command for formatting info
        '''Returns a formatted string for the respective info bit'''
        if t == None:
            if assetinfolib[info]['format'] == 'alpha' or self.info(info, a) in ['', MISSINGDATA]:         return self.info(info, a)
            elif assetinfolib[info]['format'] == 'percent':     return format_number(self.info(info, a)*100, '.2f') + '%'
            elif assetinfolib[info]['format'] == '':            return format_number(self.info(info, a))
            else:                                               return format_number(self.info(info, a), assetinfolib[info]['format'])
        else:
            if transinfolib[info]['format'] == 'alpha' or self.info(info, a, t) in ['', MISSINGDATA]:         return self.info(info, a, t)
            elif transinfolib[info]['format'] == '':            return format_number(self.info(info, a, t))
            else:                                               return format_number(self.info(info, a, t), transinfolib[info]['format'])

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
        #ASSET CLASS
        displayInfo = 'Asset Class: ' + self.printInfo('class', a)

        #WALLETS and their HOLDINGS
        walletsTokensString = ''
        for w in self.whitelisted_wallets():
            if w in TEMP['metrics'][a]['wallets']:
                walletsTokensString +=  ', ' + w + ':' + str(TEMP['metrics'][a]['wallets'][w])
        displayInfo += '\nWallets: ' + walletsTokensString[2:]

        for info in ['holdings', 'price', 'value', 'marketcap', 'volume24h', 'day_change', 'day%', 'week%', 'month%', 'portfolio%']:
            displayInfo += '\n' + assetinfolib[info]['name'] + ': ' + str(self.info(info, a))


        Message(self, a.split('z')[0] + ' Stats and Information', displayInfo, width=100, height=25)


#METRICS
#=============================================================
    def metrics(self): # Recalculates all static metrics for all assets and the overall protfolio
        '''Calculates and renders all static metrics for all assets, and the overall portfolio'''
        if 'metrics' not in TEMP:   TEMP['metrics'] = {} #To remove metrics for assets that may no longer exist
        TEMP['taxes'] = { 
            '8949':     pd.DataFrame(columns=['Description of property','Date acquired','Date sold or disposed of','Proceeds','Cost or other basis','Gain or (loss)']) ,
            '1099-MISC':pd.DataFrame(columns=['Date acquired', 'Value of assets']),
            }

        for a in PERM['assets']:    self.metrics_ASSET(a, False)
        self.metrics_PORTFOLIO()
        self.market_metrics()

    def market_metrics(self):   # Recalculates all dynamic metrics based on data recovered from the internet
        for a in PERM['assets']:    self.market_metrics_ASSET(a, False)
        self.market_metrics_PORTFOLIO()

    def market_metrics_PORTFOLIO(self): #Recalculates all dynamic market metrics for the overall portfolio
        value = precise(0)
        for a in PERM['assets']:    #Compiles complete list of all wallets used in the portfolio
            try: value += self.info('value', a) #Adds the total value of this asset to the overall portfolio value. If no price data can be found we assume this asset it worthless.
            except: None
        TEMP['metrics'][' PORTFOLIO']['value'] = value

        #Has to be a separate loop so that the total portfolio value is actually the total
        TEMP['metrics'][' PORTFOLIO']['day_change'] = precise(0)
        TEMP['metrics'][' PORTFOLIO']['week_change'] = precise(0)
        TEMP['metrics'][' PORTFOLIO']['month_change'] = precise(0)
        for a in PERM['assets']:
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
        wallets = set()
        number_of_transactions = 0
        for a in PERM['assets']:    #Compiles complete list of all wallets used in the portfolio
            wallets.update(set(TEMP['metrics'][a]['wallets']))
            number_of_transactions += len(PERM['assets'][a]['trans'])
        TEMP['metrics'][' PORTFOLIO']['wallets'] = wallets
        TEMP['metrics'][' PORTFOLIO']['number_of_transactions'] = number_of_transactions
        TEMP['metrics'][' PORTFOLIO']['number_of_assets'] = len(PERM['assets'])
    def metrics_ASSET(self,a, updatePortfolio=True): #Recalculates all static metrics for asset 'a'
        '''Calculates all metrics for asset \'a\'
        \n By default, this will also update the overall portfolio metrics'''
        TEMP['metrics'][a] = {}
        self.perform_automatic_accounting(a)
        self.calculate_cash_flow(a)

        if updatePortfolio:
            self.metrics_PORTFOLIO()
            
    def perform_automatic_accounting(self, a):   #Dependent on the Accounting Method, calculates the Holdings per Wallet, Total Holdings, Average Buy Price, Real P&L (Capital Gains)
        #PURCHASES are their purchase price including fees
        #GIFTS are their reception price. Basically the same as purchases.
        #SALES are based on the accounting method 
        #EXPENSES are treated as sales by the IRS currently. We treat them as such, based on the accounting method.
        #TRANSFERS are based on the accounting method

        #Creates a sorted list of all of the transactions for this asset, to be iterated chronologically
        transactions = list(PERM['assets'][a]['trans']) #0ms
        transactions.sort()

        #Creates a dictionary of wallets and their respective holdings, each of which has entries containing prices and the amount of tokens bought for each price.
        holdings = {}   #A dictionary of wallets, each a dictionary of transactions keeping track of the number of tokens 'left' that haven't been sold
        purchases_and_gifts = {}      #A dictionary of wallets, each an ordered list of transactions keeping track of which assets will be sold first
        for wallet in PERM['wallets']: 
            holdings[wallet] = {}
            purchases_and_gifts[wallet] = []
        prices = {}

        accounting_method = settings('accounting_method')
        capital_gains = precise(0)
        
        TEMP['metrics'][a][' MISSINGWALLET'] = False

        def insert_PG(trans, wallet):   #Takes ~150 ms for around 2222 transactions
            price = self.info('price', a, trans)
            if   accounting_method == 'fifo':   purchases_and_gifts[wallet].append(trans)                     #Oldest first, newest appended to the end
            elif accounting_method == 'lifo':   purchases_and_gifts[wallet].insert(0, trans)                  #Newest first, newest inserted at the beginning
            elif accounting_method == 'hifo':                                                                 #Most expensive first, newest inserted prior to first transaction with lower price
                for PG in purchases_and_gifts[wallet]:
                    if prices[PG] < price:  #Using a dictionary called 'prices' is faster than the 'self.info' command, for whatever reason. 
                        purchases_and_gifts[wallet].insert(purchases_and_gifts[wallet].index(PG), trans)   
                        return
                purchases_and_gifts[wallet].append(trans)


        for t in transactions:  #The transaction's time/date is its SPECID
            trans_type = self.info('type', a, t)
            usd = self.info('usd', a, t)
            tokens = self.info('tokens', a, t)
            wallet = self.info('wallet', a, t)
            wallet2 = self.info('wallet2', a, t)

            #Sometimes we imported a transaction and don't know where the assets came from. 
            #We need to alert the user that this issue exists, so that they can fix it.
            if ' MISSINGWALLET' in [wallet, wallet2]:   
                TEMP['metrics'][a][' MISSINGWALLET'] = True
                continue    #Transactions with ' MISSINGWALLET's are ignored so that the program doesn't crash. User is expected to fix this issue as soon as possible 

            #Purchases/Gifts/Sales/Expenses/Transfers
            if trans_type in ['purchase', 'gift']:      #Purchases and gifts always add the transaction and its tokens to the respective wallet.
                holdings[wallet][t] = tokens
                insert_PG(t, wallet)
                prices[t] = self.info('price', a, t)

                # if trans_type == 'gift':    #This adds all 'gifts' to the 1099-MISC. 
                #     #######################################################################################
                #     # PROBLEMS WITH THIS IMPLEMENTATION: 
                #     # Note that, with the current version of this program, that includes Coinbase quiz gifts, gifts from Mom, and any other gifts unrelated to stakin interest (THIS IS WRONG!)
                #     #######################################################################################
                #     TEMP['taxes']['1099-MISC'] = TEMP['taxes']['1099-MISC'].append( {'Date acquired':t,  'Value of assets':usd}, ignore_index=True)

            elif trans_type in ['sale', 'expense']: 
                #Tokens are always, obviously, removed from the wallet from which they were sold. 
                #The accounting method automatically tells us exactly which assets are first to be sold, as each wallet has now been sorted by the accounting method

                #This is also where we can assess capital gains/loss, AKA realized profit. - 14 ms
                cost_basis = precise(0)
                for PG in list(purchases_and_gifts[wallet]):
                    PG_tokens = holdings[wallet][PG]
                    #If we're selling more tokens than can be found in this transaction we have to keep iterating through the sorted list
                    if mp.almosteq(tokens, PG_tokens) or tokens > PG_tokens:
                        cost_basis += self.info('usd', a, PG)    #10 ms
                        holdings[wallet][PG] = precise(0)
                        tokens -= precise(PG_tokens)    #2 ms
                        #If we have sold all the tokens from a specific transaction, remove it
                        purchases_and_gifts[wallet].remove(PG)

                        #IRS form 8949 report for this sale/expense
                        # form8949 = {
                        #     'Description of property':      str(PG_tokens) + ' ' + self.info('ticker', a),
                        #     'Date acquired':                PG,
                        #     'Date sold or disposed of':     t,
                        #     'Proceeds':                     usd * PG_tokens / self.info('tokens', a, t),
                        #     'Cost or other basis':          self.info('usd', a, PG),   
                        #     }
                        # form8949['Gain or (loss)'] = precise(form8949['Proceeds']) - precise(form8949['Cost or other basis'])
                        # TEMP['taxes']['8949'] = TEMP['taxes']['8949'].append(form8949, ignore_index=True)

                    #If we're selling equal to or less than this transactions's # of tokens, just remove it from this one and end the loop
                    else:
                        cost_basis += tokens * self.info('price', a, PG) #0 ms
                        holdings[wallet][PG] -= tokens

                        # #IRS form 8949 report for this sale/expense
                        # form8949 = {
                        #     'Description of property':      str(tokens) + ' ' + self.info('ticker', a),
                        #     'Date acquired':                PG,
                        #     'Date sold or disposed of':     t,
                        #     'Proceeds':                     usd * tokens / self.info('tokens', a, t),
                        #     'Cost or other basis':          tokens * self.info('price', a, PG),   
                        #     }
                        # form8949['Gain or (loss)'] = precise(form8949['Proceeds']) - precise(form8949['Cost or other basis'])
                        # TEMP['taxes']['8949'] = TEMP['taxes']['8949'].append(form8949, ignore_index=True)

                        break     

                #THE CAPITAL GAINS FOR THIS SALE/EXPENSE
                capital_gains += usd - cost_basis

            elif trans_type == 'transfer':
                for PG in list(purchases_and_gifts[wallet]):
                    PG_tokens = holdings[wallet][PG]
                    #If we're transferring more tokens than can be found in this transaction we have to keep iterating through the sorted list
                    if mp.almosteq(tokens, PG_tokens) or tokens > PG_tokens:
                        holdings[wallet][PG] = precise(0)
                        if PG not in holdings[wallet2]:   holdings[wallet2][PG] =  PG_tokens    #We transfer this transaction fully to the other wallet
                        else:                             holdings[wallet2][PG] += PG_tokens  #0 ms
                        if PG not in purchases_and_gifts[wallet2]:      insert_PG(PG, wallet2)
                        tokens -= precise(PG_tokens)    #2 ms
                        #We have transferred all the tokens from a specific transaction, so remove it
                        purchases_and_gifts[wallet].remove(PG)
                    #If we're transferring less than this transactions's # of tokens, just remove it from this one and end the loop
                    else:
                        holdings[wallet][PG] -= precise(tokens)
                        if PG not in holdings[wallet2]:   holdings[wallet2][PG] =  tokens    #We transfer the remaining tokens to the other wallet
                        else:                             holdings[wallet2][PG] += tokens #0 ms
                        if PG not in purchases_and_gifts[wallet2]:      insert_PG(PG, wallet2)
                        break    

                
            #And that's it! We calculate the average buy price AFTER figuring out what tokens we have left.

        TEMP['metrics'][a]['realized_profit_and_loss'] = capital_gains

        total_investment_value = precise(0)
        total_holdings = precise(0)
        wallet_holdings = {}
        for wallet in holdings:
            wallet_holdings[wallet] = precise(0)
            for t in holdings[wallet]:
                total_investment_value +=   holdings[wallet][t] * self.info('price', a, t)  #USD value of the investment 
                total_holdings +=           holdings[wallet][t]                             #Single number for the total number of tikens
                wallet_holdings[wallet] +=  holdings[wallet][t]                             #Number of tokens within each wallet

        TEMP['metrics'][a]['holdings'] = total_holdings
        TEMP['metrics'][a]['wallets'] = wallet_holdings
        
        if total_holdings == 0:     TEMP['metrics'][a]['average_buy_price'] = 0
        else:                       TEMP['metrics'][a]['average_buy_price'] = total_investment_value / self.info('holdings', a)

    def calculate_value(self, a):   #Calculates the overall value of this asset
        #Must be a try statement because it relies on market data
        try:    TEMP['metrics'][a]['value'] = self.info('holdings', a) * self.info('price', a)
        except: TEMP['metrics'][a]['value'] = MISSINGDATA
    def calculate_unrealized_profit_and_loss(self, a):
        #You need current market data for these bad boys
        average_buy_price = self.info('average_buy_price', a)
        if average_buy_price == 0: TEMP['metrics'][a]['unrealized_profit_and_loss%'] = TEMP['metrics'][a]['unrealized_profit_and_loss'] = 0
        else:
            try:        
                TEMP['metrics'][a]['unrealized_profit_and_loss'] =     self.info('value', a) - ( average_buy_price * self.info('holdings', a) )
                TEMP['metrics'][a]['unrealized_profit_and_loss%'] = ( self.info('price', a) /  average_buy_price )-1
            except:     TEMP['metrics'][a]['unrealized_profit_and_loss%'] = TEMP['metrics'][a]['unrealized_profit_and_loss'] = MISSINGDATA
    def calculate_changes(self, a): #Calculates the unrealized USD lost or gained in the last 24 hours, week, and month for this asset
        #Must be a try statement because it relies on market data
        value = TEMP['metrics'][a]['value']
        try:
            TEMP['metrics'][a]['day_change'] = value-(value / (1 + self.info('day%', a)))
            TEMP['metrics'][a]['week_change'] = value-(value / (1 + self.info('week%', a)))
            TEMP['metrics'][a]['month_change'] = value-(value / (1 + self.info('month%', a)))
        except: pass
    def calculate_cash_flow(self, a): #Calculates the amount of USD that has gone through the investment
        cash_flow = 0
        for t in PERM['assets'][a]['trans']:
            type = PERM['assets'][a]['trans'][t]['type']
            #PURCHASES are a negative flow from your bank account, 
            #SALES are a positive flow into your bank account,
            #GIFTS, EXPENSES, and TRANSFERS are 'costless' since they dont affect your bank account
            if type in ['purchase']:            cash_flow -= self.info('usd', a, t)
            elif type in ['sale']:              cash_flow += self.info('usd', a, t)
        TEMP['metrics'][a]['cash_flow'] = cash_flow
    def calculate_net_cash_flow(self, a): #Calculates what the cash flow would become if you sold everything right now
        #Must be a try statement because it relies on market data
        try: TEMP['metrics'][a]['net_cash_flow'] = self.info('cash_flow', a) + self.info('value', a)
        except: TEMP['metrics'][a]['net_cash_flow'] = MISSINGDATA



    def calculate_portfolio_percentage(self, a): #Calculates how much of the value of your portfolio is this asset
        portfolio_value = TEMP['metrics'][' PORTFOLIO']['value']
        if portfolio_value == 0:    TEMP['metrics'][a]['portfolio%'] = precise(0)
        else:                       TEMP['metrics'][a]['portfolio%'] = self.info('value', a) / TEMP['metrics'][' PORTFOLIO']['value']


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
                PERM.clear()
                PERM.update(copy.deepcopy(TEMP['undo'][lastAction]))
                self.profile = ''   #name of the currently selected profile. Always starts with no filter applied.
                self.metrics()
                self.render(self.asset, True)
                self.create_PROFILE_MENU()  
    def _ctrl_y(self,event):    #Redo your last action
        if self.grab_current() == self: #If any other window is open, then you can't do this
            nextAction = (self.undoRedo[2]+1)%len(TEMP['undo'])
            #If there actually IS a next action, load that
            if (self.undoRedo[1] > self.undoRedo[0] and nextAction >= self.undoRedo[0] and nextAction <= self.undoRedo[1]) or (self.undoRedo[1] < self.undoRedo[0] and (nextAction >= self.undoRedo[0] or nextAction <= self.undoRedo[1])):
                if nextAction == self.undoRedo[1]:  self.MENU['redo'].configure(state='disabled')
                else:                               self.MENU['redo'].configure(state='normal')
                self.MENU['undo'].configure(state='normal')
                self.undoRedo[2] = (self.undoRedo[2]+1)%len(TEMP['undo'])
                global PERM
                PERM = copy.deepcopy(TEMP['undo'][nextAction])    #9ms to merely reload the data into memory
                self.profile = ''   #name of the currently selected profile. Always starts with no filter applied.
                self.metrics()  #2309 ms holy fuck
                self.render(self.asset, True) #100ms
                self.create_PROFILE_MENU()  
    def _esc(self,event):    #Exit this window
        if self.grab_current() == self: #If any other window is open, then you can't do this
            if self.GRID_SELECTION != [-1, -1]:  self.clear_selection()
            elif self.asset == None:  self.comm_quit()        #If we're on the main page, exit the program
            else:                   self.render(None, True) #If we're looking at an asset, go back to the main page
    def _del(self,event):    #Delete any selected items
        if self.grab_current() == self: #If any other window is open, then you can't do this
            if self.GRID_SELECTION != [-1, -1]:  self.comm_delete_selection(self.GRID_SELECTION)
#USEFUL COMMANDS
#=============================================================
    def undo_save(self):
        '''Saves current portfolio in the memory should the user wish to undo their last modification'''
        #############
        #NOTE: Undo savepoints are triggered when:
        ###############3
        # Loading a portfolio, creating a new portfolio, or merging portfolios causes an undosave
        # Importing transaction histories causes an undosave
        # Modifying/Creating a(n): Asset, Transaction, Wallet, Profile
        #overwrites the cur + 1th slot with data
        self.MENU['redo'].configure(state='disabled')
        self.MENU['undo'].configure(state='normal')

        TEMP['undo'][(self.undoRedo[2]+1)%len(TEMP['undo'])] = copy.deepcopy(PERM)

        if self.undoRedo[1] - self.undoRedo[0] <= 0 and self.undoRedo[1] != self.undoRedo[0]:
            self.undoRedo[0] = (self.undoRedo[0]+1)%len(TEMP['undo'])
        self.undoRedo[2] = (self.undoRedo[2]+1)%len(TEMP['undo'])
        self.undoRedo[1] = self.undoRedo[2]

    def whitelisted_wallets(self):        #OLD OLD OLD
        '''Returns list of whitelisted wallets under current profile'''
        #If the profile whitelists no wallets, then all wallets are whitelisted
        if self.profile == '' or len(PERM['profiles'][self.profile]['wallets']) == 0:    return list(PERM['wallets'])
        else:                                                                            return PERM['profiles'][self.profile]['wallets']

    def trans_filtered(self, a):        #OLD OLD OLD
        if self.profile == '' or len(PERM['profiles'][self.profile]['wallets']) == 0:
            return PERM['assets'][a]['trans']
        else:
            filteredTrans = []
            for t in PERM['assets'][a]['trans']:
                if PERM['assets'][a]['trans'][t]['wallet'] in self.whitelisted_wallets(): #If this transaction's wallet is on the whitelist, then add it to the filtered list
                    filteredTrans.append(t) 
                elif PERM['assets'][a]['trans'][t]['type'] == 'transfer' and PERM['assets'][a]['trans'][t]['wallet2'] in self.whitelisted_wallets(): #if its a transfer and wallet2 is on the whitelist:
                    filteredTrans.append(t)
            return filteredTrans
    def assets_filtered(self):        #OLD OLD OLD
        '''Returns a list of whitelisted assets under the current filter profile (Filters by Wallet, Asset, and Class)'''
        if self.profile == '':
            return set(PERM['assets'])
        #Raw profile filter data
        walletList =  set(PERM['profiles'][self.profile]['wallets'])
        classList = set(PERM['profiles'][self.profile]['classes'])

        #Whitelists, in the form of assets
        whitelistedWallets = set()
        whitelistedAssets = set(PERM['profiles'][self.profile]['assets'])
        whitelistedClasses = set()

        #Adds whitelisted wallets
        if walletList != set():    #If we're actually using this filter...
            for a in PERM['assets']:     #Then for every asset in the portfolio....
                for applicableWallet in TEMP['metrics'][a]['wallets']:  #and for every wallet relevant to that asset...
                    if applicableWallet in walletList:  #If that wallet is whitelisted:
                        whitelistedWallets.add(a)          #add this asset to the whitelist
                        break   #skips to the next asset
        else:
            whitelistedWallets = set(PERM['assets'])
        #Whitelisted assets already added, this was very easy to do. Still need to fix it if one is empty
        if whitelistedAssets == set():
            whitelistedAssets = set(PERM['assets'])
        #Adds whitelisted classes
        if classList != set():    #If we're actually using this filter...
            for a in PERM['assets']:     #Then for every asset in the portfolio....
                if a.split('z')[1] in classList:     #If the class of this asset is whitelisted...
                    whitelistedClasses.add(a)   #Add it to the class whitelist
        else:
            whitelistedClasses = set(PERM['assets'])

        #The true whitelist is the interection of all three whitelists
        return whitelistedWallets.intersection(whitelistedAssets).intersection(whitelistedClasses)
               

    def refreshScrollbars(self):        #OLD OLD OLD
        self.GUI['assetFrame'].update()    #takes 500 milliseconds for 585 transactions... gross
        self.GUI['assetCanvas'].configure(scrollregion=self.GUI['assetFrame'].bbox('ALL'))  #0ms!!!!




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
    #While true loop means that the program will automatically restart, if we destroy the Portfolio
    while True:
        Portfolio().mainloop()





