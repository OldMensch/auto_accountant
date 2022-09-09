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
        self.ToolTips = ToolTipWindow(self.get_mouse_pos)
        self.mouse_pos = (0,0)

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
                self.GUI['offlineIndicator'].pack(side='right',fill='y') #Turns on a bright red indicator, which lets you know you're in offline mode
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
        self.bind('<Motion>', self._mouse)
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
                self.GUI['offlineIndicator'].pack(side='right',fill='y') #Turns on a bright red indicator, which lets you know you're in offline mode
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
            if info in setting('header_portfolio'):    self.hide_header(info)
            else:                                       self.show_header(info)

        self.TASKBAR['info'].values = {}
        for info in assetinfolib:
            self.TASKBAR['info'].values[info] = tk.BooleanVar(value=info in setting('header_portfolio')) #Default value true if in the header list
            self.TASKBAR['info'].add_checkbutton(label=info_format_lib[info]['name'], command=p(toggle_header, info), variable=self.TASKBAR['info'].values[info])

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
        self.TASKBAR['DEBUG'].add_command(label='DEBUG find all missing price data',     command=self.DEBUG_find_all_missing_prices)
        self.TASKBAR['DEBUG'].add_command(label='DEBUG delete all transactions, by wallet',     command=self.DEBUG_delete_all_of_asset)
        self.TASKBAR['DEBUG'].add_command(label='DEBUG increase page length',     command=self.DEBUG_increase_page_length)
        self.TASKBAR['DEBUG'].add_command(label='DEBUG decrease page length',     command=self.DEBUG_decrease_page_length)
        self.TASKBAR['DEBUG'].add_command(label='DEBUG grayify',     command=self.DEBUG_grayify)
        self.TASKBAR['DEBUG'].add_command(label='DEBUG time report',     command=p(ttt, 'average_report'))
        self.TASKBAR['DEBUG'].add_command(label='DEBUG time reset',     command=p(ttt, 'reset'))

        
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
    def DEBUG_increase_page_length(self):
        self.GUI['GRID'].update_page_length(setting('itemsPerPage')+1)
        self.render()
    def DEBUG_decrease_page_length(self):
        self.GUI['GRID'].update_page_length(setting('itemsPerPage')-1)
        self.render()
    def DEBUG_grayify(self):
        self.GUI['GRID'].force_formatting(palette('neutral'),palette('menudark'), None, 'center')

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
        self.GUI['GRID'] = GRID(self, self.set_sort, self._header_menu, self._left_click_row, self._right_click_row)
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
        
        self.GUI['GRID']            .grid(column=1,row=1, sticky='NSEW')
        
        self.GUI['bottomFrame']     .grid(column=0,row=2, columnspan=2, sticky='EW')
        self.GUI['copyright']       .pack(side='left')

        #GUI TOOLTIPS
        #==============================
        tooltips = {
            'edit':                 'Edit this asset',
            'new_asset':            'Create a new asset',
            'new_transaction':      'Create a new transaction',

            'back':                 'Return to the main portfolio',
            'page_last':            'Go to last page',
            'page_next':            'Go to next page',
        }
        for widget in tooltips:
            self.ToolTips.SetToolTip(self.GUI[widget] ,tooltips[widget])


#All the commands for reordering, showing, and hiding the info columns
    def _header_menu(self, i, event):
        if self.rendered[0] == 'asset':  return  #There is no menu for the transactions ledger view
        info = setting('header_portfolio')[i]
        m = tk.Menu(self, tearoff = 0)
        if i != 0:                                      m.add_command(label ='Move Left', command=p(self.move_header, info, 'left'))
        if i != len(setting('header_portfolio'))-1:     m.add_command(label ='Move Right', command=p(self.move_header, info, 'right'))
        if i != 0:                                      m.add_command(label ='Move to Beginning', command=p(self.move_header, info, 'beginning'))
        if i != len(setting('header_portfolio'))-1:     m.add_command(label ='Move to End', command=p(self.move_header, info, 'end'))
        m.add_separator()
        m.add_command(label ='Hide ' + info_format_lib[info]['name'], command=p(self.hide_header, info))
        m.tk_popup(self.mouse_pos[0],self.mouse_pos[1])
    def move_header(self, info, shift='beginning'):
        if   shift == 'beginning':  i = 0
        elif shift == 'right':      i = setting('header_portfolio').index(info) + 1
        elif shift == 'left':       i = setting('header_portfolio').index(info) - 1
        elif shift == 'end':        i = len(setting('header_portfolio'))
        new = setting('header_portfolio')
        new.remove(info)
        new.insert(i, info)
        set_setting('header_portfolio', new)
        self.render()
    def hide_header(self, info):
        new = setting('header_portfolio')
        new.remove(info)
        set_setting('header_portfolio', new)
        self.TASKBAR['info'].values[info].set(False)
        self.render()
    def show_header(self, info):
        new = setting('header_portfolio')
        new.insert(0, info)
        set_setting('header_portfolio', new)
        self.TASKBAR['info'].values[info].set(True)
        self.render()

    def _left_click_row(self, GRID_ROW:int): # Opens up the asset subwindow, or transaction editor upon clicking a label within this row
        #if we double clicked on an asset/transaction, thats when we open it.
        i = self.page*setting('itemsPerPage')+GRID_ROW
        if i + 1 > len(self.sorted): return  #Can't select something if it doesn't exist!
        self.GUI['GRID'].set_selection()
        if self.rendered[0] == 'portfolio': self.render(('asset',self.sorted[i].tickerclass()), True)
        else:                               TransEditor(self, self.sorted[i].get_hash())
    def _right_click_row(self, GRID_ROW1:int, GRID_ROW2:int, GRID_ROW3:int): # Opens up a little menu of stuff you can do to this asset/transaction
        #we've right clicked with a selection of multiple items
        if GRID_ROW2 != GRID_ROW3:
            m = tk.Menu(self, tearoff = 0)
            m.bind('<Motion>', self._mouse)
            m.add_command(label ='Delete selection', command=p(self.delete_selection, GRID_ROW2, GRID_ROW3))
            m.tk_popup(self.mouse_pos[0],self.mouse_pos[1])
        #We've clicked a single item, or nothing at all, popup is relevant to what we right click
        else:
            i = self.page*setting('itemsPerPage')+GRID_ROW1
            if i + 1 > len(self.sorted): return  #Can't select something if it doesn't exist!
            item = self.sorted[i]
            m = tk.Menu(self, tearoff = 0)
            m.bind('<Motion>', self._mouse)
            if self.rendered[0] == 'portfolio':
                ID = item.tickerclass()
                ticker = item.ticker()
                m.add_command(label ='Open ' + ticker + ' Ledger', command=p(self.render, ('asset',ID), True))
                m.add_command(label ='Edit ' + ticker, command=p(AssetEditor, self, ID))
                m.add_command(label ='Show detailed info', command=p(self.comm_asset_info, ID))
                m.add_command(label ='Delete ' + ticker, command=p(self.delete_selection, GRID_ROW1))
            else:
                trans_title = item.date() + ' ' + item.prettyPrint('type')
                m.add_command(label ='Edit ' + trans_title, command=p(TransEditor, self, item.get_hash()))
                m.add_command(label ='Copy ' + trans_title, command=p(TransEditor, self, item.get_hash(), True))
                m.add_command(label ='Delete ' + trans_title, command=p(self.delete_selection, GRID_ROW1))
                if item.ERROR:
                    m.add_separator()
                    m.add_command(label ='ERROR information...', command=p(Message, self, 'Transaction Error!', item.ERR_MSG))
            m.tk_popup(self.mouse_pos[0],self.mouse_pos[1])

    def delete_selection(self, GRID_ROW1:int, GRID_ROW2:int=None):
        I1 = self.page*setting('itemsPerPage')+GRID_ROW1
        if GRID_ROW2 == None:   I2 = I1
        else:                   I2 = self.page*setting('itemsPerPage')+GRID_ROW2
        if I1 > len(self.sorted)-1: return
        if I2 > len(self.sorted)-1: I2 = len(self.sorted)-1
        for item in range(I1,I2+1):
            if self.rendered[0] == 'asset':     MAIN_PORTFOLIO.delete_transaction(self.sorted[item].get_hash())
            else:
                Message(self, 'Unimplemented', 'You can\'t delete assets from here, for now.')
                return
        self.GUI['GRID'].set_selection()
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


# PORTFOLIO RENDERING
#=============================================================
    def render(self, toRender:str=None, sort:bool=False): #NOTE: Very fast! ~30ms when switching panes, ~4ms when switching pages, ~11ms on average
        '''Call to render the portfolio, or a ledger
        \nRefreshes page if called without any input.
        \ntoRender - tuple of portfolio/asset, and asset name if relevant.'''
        #If we're trying to render an asset that no longer exists, go back to the main portfolio instead
        if toRender == None:
            if self.rendered[0] == 'asset' and not MAIN_PORTFOLIO.hasAsset(self.rendered[1]):   toRender = ('portfolio',None)
        elif   toRender[0] == 'asset' and not MAIN_PORTFOLIO.hasAsset(toRender[1]):             toRender = ('portfolio',None)

        #These are things that don't need to change unless we're changing the level from PORTFOLIO to ASSET or vice versa
        if toRender != None:
            self.page = 0 #We return to the first page if changing from portfolio to asset or vice versa
            if toRender[0] == 'portfolio':
                self.GUI['info'].configure(command=self.comm_portfolio_info)
                self.ToolTips.SetToolTip(self.GUI['info'], 'Detailed information about this portfolio')
                self.GUI['edit'].pack_forget()
                self.GUI['new_asset'].pack(side='right')
                self.GUI['back'].grid_forget()
            else:
                self.GUI['info'].configure(command=p(self.comm_asset_info, toRender[1]))
                self.ToolTips.SetToolTip(self.GUI['info'], 'Detailed information about this asset')
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
        if sort:    self.sort() #NOTE: This is fast (~7ms for ~900 transactions). It could be faster with Radix Sort... but why? It's insanely fast already!

        #Appropriately enabled/diables the page-setting buttons - 0ms
        maxpage = math.ceil(len(self.sorted)/setting('itemsPerPage'))-1
        if maxpage == -1: maxpage = 0
        if self.page < maxpage:     self.GUI['page_next'].configure(state='normal')
        else:                       self.GUI['page_next'].configure(state='disabled')
        if self.page > 0:           self.GUI['page_last'].configure(state='normal')
        else:                       self.GUI['page_last'].configure(state='disabled')
        self.GUI['page_number'].configure(text='Page ' + str(self.page+1) + ' of ' + str(maxpage+1))

        #Appropriately renames the headers
        if self.rendered[0] == 'portfolio': header = setting('header_portfolio')
        else:                               header = setting('header_asset')

        #Fills in the page with info
        self.GUI['GRID'].grid_render(header, self.sorted, self.page, self.rendered[1])

    def update_info_pane(self):
        textbox = self.GUI['info_pane']
        textbox.clear()

        for info in ['value','day%','unrealized_profit_and_loss','unrealized_profit_and_loss%']:
            if self.rendered[0] == 'portfolio':
                formatted_info = list(MAIN_PORTFOLIO.pretty(info))
            else:
                formatted_info = list(MAIN_PORTFOLIO.asset(self.rendered[1]).pretty(info, ignoreError=True))    
            textbox.insert_text(info_format_lib[info]['headername'].replace('\n',' '), justify='center')
            textbox.newline()
            info_format = info_format_lib[info]['format']
            if formatted_info[1] == None:   formatted_info[1] = palette('neutral')
            if info_format == 'percent':    ending = ' %'
            else:                           ending = ' USD'
            textbox.insert_triplet('',formatted_info[0].replace('%',''), ending, fg=formatted_info[1], justify='center', font=setting('font2',1.5))
            textbox.newline()

    def set_sort(self, col:int): #Sets the sorting mode, sorts the assets by it, then rerenders everything
        if self.rendered[0] == 'portfolio':
            info = setting('header_portfolio')[col]
            if setting('sort_asset')[0] == info:    set_setting('sort_asset',[info, not setting('sort_asset')[1]])
            else:                                   set_setting('sort_asset',[info, False])
        else:
            info = setting('header_asset')[col]
            if setting('sort_trans')[0] == info:    set_setting('sort_trans',[info, not setting('sort_trans')[1]])
            else:                                   set_setting('sort_trans',[info, False])
        self.render(sort=True)
    def sort(self): #Sorts the assets or transactions by the metric defined in settings #NOTE: 7ms at worst for ~900 transactions on one ledger
        '''Sorts the assets or transactions by the metric defined in settings'''
        if self.rendered[0] == 'portfolio':  #Assets
            info = setting('sort_asset')[0]    #The info we're sorting by
            reverse = setting('sort_asset')[1] #Whether or not it is in reverse order

            sorted = list(MAIN_PORTFOLIO.assets())
            def tickerclasskey(e):  return e.tickerclass()
            sorted.sort(key=tickerclasskey) #Sorts the assets alphabetically by their tickerclass first. This is the default.
        else:   #Transactions
            info = setting('sort_trans')[0]    #The info we're sorting by
            reverse = setting('sort_trans')[1] #Whether or not it is in reverse order

            sorted = list(MAIN_PORTFOLIO.asset(self.rendered[1])._ledger.values()) #a dict of relevant transactions, this is a list of their keys.
            sorted.sort(reverse=not reverse)    #By default, we sort by the special sorting algorithm (date, then type, then wallet, etc. etc.)
            
        def alphaKey(e):    return e.get(info).lower()
        def numericKey(e):
            n = e.get(info)
            try: return float(n)
            except: return (reverse-0.5)*float('inf') #Sends missing data values to the bottom of the sorted list
        def value_quantity_price(e):
            return e.get(info, self.rendered[1])

        if   self.rendered[0] == 'asset' and info == 'date':                        pass  #This is here to ensure that the default date order is newest to oldest. This means reverse alphaetical
        elif info_format_lib[info]['format'] == 'alpha':                            sorted.sort(reverse=reverse,     key=alphaKey)
        elif self.rendered[0] == 'asset' and info in ['value','quantity','price']:  sorted.sort(reverse=not reverse, key=value_quantity_price)
        else:                                                                       sorted.sort(reverse=not reverse, key=numericKey)

        self.sorted = sorted  

    def comm_page_next(self):
        if self.rendered[0] == 'portfolio':  maxpage = math.ceil(len(MAIN_PORTFOLIO.assets())/setting('itemsPerPage')-1)
        else:                   maxpage = math.ceil(len(MAIN_PORTFOLIO.asset(self.rendered[1])._ledger)/setting('itemsPerPage')-1)
        if self.page < maxpage: 
            self.page += 1
            self.GUI['GRID'].set_selection()
            self.render()
    def comm_page_last(self):
        if self.page > 0: 
            self.page -= 1
            self.GUI['GRID'].set_selection()
            self.render()

#INFO FUNCTIONS
#=============================================================

    def comm_portfolio_info(self): #A wholistic display of all relevant information to the overall portfolio 
        message = Message(self, 'Overall Stats and Information', '', font=setting('font'), width=80, height=20)
        DEFCOLOR, DEFFONT = palette('neutral'), setting('font2')

        # NUMBER OF TRANSACTIONS, NUMBER OF ASSETS
        to_insert = MAIN_PORTFOLIO.pretty('number_of_transactions')
        message.insert_triplet('• ', to_insert[0], '', fg=to_insert[1], font=to_insert[2], newline=False)
        to_insert = MAIN_PORTFOLIO.pretty('number_of_assets')
        message.insert_triplet(' transactions loaded under ', to_insert[0], ' assets', fg=to_insert[1], font=to_insert[2])

        # USD PER WALLET
        message.insert('• Total USD by wallet:')
        message.insert_triplet('\t*TOTAL*:\t\t\t', format_general(MAIN_PORTFOLIO.get('value'), 'alpha', 20), ' USD', fg=DEFCOLOR, font=DEFFONT)
        wallets = list(MAIN_PORTFOLIO.get('wallets'))
        def sortByUSD(w):   return MAIN_PORTFOLIO.get('wallets')[w]  #Wallets are sorted by their total USD value
        wallets.sort(reverse=True, key=sortByUSD)
        for w in wallets:    #Wallets, a list of wallets by name, and their respective net valuations
            quantity = MAIN_PORTFOLIO.get('wallets')[w]
            if not zeroish_mpf(quantity):
                message.insert_triplet('\t'+w+':\t\t\t', format_general(quantity, 'alpha', 20), ' USD', fg=DEFCOLOR, font=DEFFONT)

        # MASS INFORMATION
        for data in ['day_change','day%', 'week%', 'month%', 'unrealized_profit_and_loss', 'unrealized_profit_and_loss%']:
            info_format = info_format_lib[data]['format']
            fg_color = MAIN_PORTFOLIO.color(data)[0] #Returns the foreground color we want for this info bit, if it has one
            if fg_color == None: fg_color = palette('neutral')
            text1 = '• '+info_format_lib[data]['name']+':\t\t\t\t'
            if info_format == 'percent':
                message.insert_triplet(text1, format_general(MAIN_PORTFOLIO.get(data)*100, 'alpha', 20), ' %', fg=fg_color, font=DEFFONT)
            else:
                message.insert_triplet(text1, format_general(MAIN_PORTFOLIO.get(data), 'alpha', 20), ' USD', fg=fg_color, font=DEFFONT)
    
    def comm_asset_info(self, a:str): #A wholistic display of all relevant information to an asset 
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
            if not zeroish_mpf(quantity):
                message.insert_triplet('\t' + w + ':\t\t\t', format_general(quantity, 'alpha', 20), ' '+asset.ticker(), fg=DEFCOLOR, font=DEFFONT)

        # MASS INFORMATION
        for data in ['price','value', 'marketcap', 'volume24h', 'day_change', 'day%', 'week%', 'month%', 'portfolio%','unrealized_profit_and_loss','unrealized_profit_and_loss%']:
            info_format = info_format_lib[data]['format']
            fg_color = asset.color(data)[0] #Returns the foreground color we want for this info bit, if it has one
            if fg_color == None: fg_color = DEFCOLOR
            text1 = '• '+ info_format_lib[data]['name']+':\t\t\t\t'
            if data == 'price':
                message.insert_triplet(text1, format_general(asset.get(data), 'alpha', 20), ' USD/'+asset.ticker(), fg=fg_color, font=DEFFONT)
            elif info_format == 'percent':
                message.insert_triplet(text1, format_general(asset.get(data)*100, 'alpha', 20), ' %', fg=fg_color, font=DEFFONT)
            else:
                message.insert_triplet(text1, format_general(asset.get(data), 'alpha', 20), ' USD', fg=fg_color, font=DEFFONT)


#METRICS
#=============================================================
    def metrics(self, tax_report:str=''): # Recalculates all metrics
        '''Calculates and renders all static metrics for all assets, and the overall portfolio'''
        if tax_report:
            TEMP['taxes'] = { 
                '8949':     pd.DataFrame(columns=['Description of property','Date acquired','Date sold or disposed of','Proceeds','Cost or other basis','Gain or (loss)']) ,
                '1099-MISC':pd.DataFrame(columns=['Date acquired', 'Value of assets']),
                }
        ttt('start')
        self.perform_automatic_accounting(tax_report) # TODO: LAGGY! (~222ms for ~12000 transactions)
        ttt('avg_end')
        for asset in MAIN_PORTFOLIO.assets():
            self.calculate_average_buy_price(asset)
        self.metrics_PORTFOLIO() #~0ms, since its just a few O(1) operations
        self.market_metrics() #Only like 2 ms

    def metrics_PORTFOLIO(self): #Recalculates all non-market metrics, for the overall portfolio
        '''Calculates all metrics for the overall portfolio'''
        MAIN_PORTFOLIO._metrics['number_of_transactions'] = len(MAIN_PORTFOLIO.transactions())
        MAIN_PORTFOLIO._metrics['number_of_assets'] = len(MAIN_PORTFOLIO.assets())

    def market_metrics(self):   # Recalculates all market-dependent metrics
        for asset in MAIN_PORTFOLIO.assets():    
            self.calculate_value(asset)
            self.calculate_unrealized_profit_and_loss(asset)
            self.calculate_changes(asset)
            self.calculate_net_cash_flow(asset)
        self.market_metrics_PORTFOLIO()
    def market_metrics_PORTFOLIO(self): #Recalculates all market-dependent metrics, for the overall portfolio

        self.calculate_portfolio_value()
        for asset in MAIN_PORTFOLIO.assets():
            self.calculate_percentage_of_portfolio(asset)
        self.calculate_portfolio_value()
        self.calculate_portfolio_changes()
        self.calculate_portfolio_percents()
        self.calculate_portfolio_value_by_wallet()
        self.calculate_portfolio_unrealized_profit_and_loss()

            
    def perform_automatic_accounting(self, tax_report:str=''):   #Dependent on the Accounting Method, calculates the Holdings per Wallet, Total Holdings, Average Buy Price, Real P&L (Capital Gains)
        
        #Creates a list of all transactions, sorted chronologically #NOTE: Lag is ~18ms for ~12000 transactions
        transactions = list(MAIN_PORTFOLIO.transactions()) #0ms
        transactions.sort()

        ###################################
        # TRANSFER LINKING - #NOTE: Lag is ~16ms for 159 transfer pairs under ~12000 transactions
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
                if t_in.get('gain_asset') == t_out.get('loss_asset') and acceptableTimeDiff(t_in.date(),t_out.date(),300) and acceptableDifference(t_in.precise('gain_quantity'), t_out.precise('loss_quantity'), 0.1):
                        #SUCCESS - We've paired this t_out with a t_in!
                        transfer_IN.remove(t_in) # Remove it from the transfer_IN list.
                        t_out._data['dest_wallet'] = t_in.wallet() #We found a partner for this t_out, so set its _dest_wallet variable to the t_in's wallet
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
        accounting_method = setting('accounting_method')
        holdings = {}
        for asset in MAIN_PORTFOLIO.assetkeys():
            MAIN_PORTFOLIO.asset(asset).ERROR = False # Assume assets are free of error at first. We check all transactions later.
            holdings[asset] = {}
            for wallet in MAIN_PORTFOLIO.walletkeys():
                #Removing these transactions is literally just a priority queue, for which heaps are basically the best implementation
                holdings[asset][wallet] = gain_heap(accounting_method) 

        # STORE and DISBURSE QUANTITY - functions which add, or remove a 'gain', to the HOLDINGS data structure.
        def store_quantity(hash:int, price:mpf, quantity:mpf, date:str, a:str, w:str):   #NOTE: Lag is ~45 ms for ~13779 stores, almost identical to performance of gain_heap itself
            '''Adds specified gaining transaction to specified wallet.'''
            holdings[a][w].store(hash, price, quantity, date)
        def disburse_quantity(t:Transaction, quantity:mpf, a:str, w:str, w2:str=None):  #NOTE: Lag is ~50ms for ~231 disbursals with ~2741 gains moved on average, or ~5 disbursals/ms, or ~54 disbursed gains/ms
            '''Removes, quantity of asset from specified wallet, then returns cost basis of removed quantity.\n
                If wallet2 \'w2\' specified, instead moves quantity into w2.'''
            result = holdings[a][w].disburse(quantity)     #NOTE - Lag is ~40ms for ~12000 transactions
            if not zeroish_mpf(result[0]):  #NOTE: Lag is ~0ms
                t.ERROR,t.ERR_MSG = True,'User disbursed more ' + a.split('z')[0] + ' than they owned from the '+w+' wallet, with ' + str(result[0]) + ' remaining to disburse.'

            #NOTE - Lag is ~27ms including store_quantity, 11ms excluding
            cost_basis = 0
            for gain in result[1]: #Result[1] is a list of gain objects that were just disbursed
                cost_basis += gain._price*gain._quantity
                if tax_report == '8949': tax_8949(t, gain, quantity)
                if w2: store_quantity(gain._hash, gain._price, gain._quantity, gain._date, a, w2)   #Moves transfers into the other wallet
            return cost_basis
            
        def tax_8949(t:Transaction, gain:gain_obj, total_disburse:mpf):
            ################################################################################################
            # This might still be broken. ALSO: Have to separate the transactions into short- and long-term
            ################################################################################################
            if zeroish_mpf(gain._quantity):     return
            if t.type() == 'transfer_out':  return 
            store_date = MAIN_PORTFOLIO.transaction(gain._hash).date()  # Date of aquisition
            disburse_date = t.date()                                    # Date of disposition
            cost_basis = gain._price*gain._quantity
            #The 'post-fee-value' is the sales profit, after fees, weighted to the actual quantity sold 
            post_fee_value = (t.precise('gain_value')-t.precise('fee_value'))*(gain._quantity/total_disburse)
            if post_fee_value < 0:  post_fee_value = 0     #If we gained nothing and there was a fee, it will be negative. We can't have negative proceeds.
            form8949 = {
                'Description of property':      str(gain._quantity) + ' ' + MAIN_PORTFOLIO.transaction(gain._hash).get('gain_asset').split('z')[0],  # 0.0328453 ETH
                'Date acquired':                store_date[5:7]+'/'+store_date[8:10]+'/'+store_date[:4],            # 11/12/2021    month, day, year
                'Date sold or disposed of':     disburse_date[5:7]+'/'+disburse_date[8:10]+'/'+disburse_date[:4],   # 6/23/2022     month, day, year
                'Proceeds':                     str(post_fee_value),    # to value gained from this sale/trade/expense/gift_out. could be negative if its a gift_out with a fee.
                'Cost or other basis':          str(cost_basis),        # the cost basis of these tokens
                'Gain or (loss)':               str(post_fee_value - cost_basis)  # the Capital Gains from this. The P&L. 
                }
            TEMP['taxes']['8949'] = TEMP['taxes']['8949'].append(form8949, ignore_index=True)

        for t in transactions:  # Lag is ~135ms for ~12000 transactions
            if t.get('missing')[0]:  t.ERROR,t.ERR_MSG = True,t.prettyPrint('missing')   #NOTE: Lag ~9ms for ~12000 transactions
            if t.ERROR: continue    #If there is an ERROR with this transaction, ignore it to prevent crashing. User expected to fix this immediately.

            #NOTE: Lag ~35ms for ~12000 transactions
            HASH,DATE,TYPE,WALLET = t.get_hash(),t.date(),t.type(),t.wallet()
            WALLET2 = t.get('dest_wallet')
            LA,FA,GA = t.get('loss_asset'),         t.get('fee_asset'),         t.get('gain_asset')
            LQ,FQ,GQ = t.precise('loss_quantity'),  t.precise('fee_quantity'),  t.precise('gain_quantity')
            LV,FV,GV = t.precise('loss_value'),     t.precise('fee_value'),     t.precise('gain_value')
            LOSS_COST_BASIS,FEE_COST_BASIS = 0,0
            COST_BASIS_PRICE = t.precise('basis_price')
            

            # COST BASIS CALCULATION    #NOTE: Lag ~250ms for ~12000 transactions. 

            # NOTE: We have to do the gain, then the fee, then the loss, because some Binance trades incur a fee in the crypto you just bought
            # GAINS - We gain assets one way or another     #NOTE: Lag ~180ms, on average
            if COST_BASIS_PRICE:    store_quantity(HASH, COST_BASIS_PRICE, GQ, DATE, GA, WALLET) # Purchase price includes fee
            # FEE LOSS - We lose assets because of a fee     #NOTE: Lag ~70ms, on average
            if FA:                  FEE_COST_BASIS =  disburse_quantity(t, FQ, FA, WALLET)
            # LOSS - We lose assets one way or another.
            if LA:                  LOSS_COST_BASIS = disburse_quantity(t, LQ, LA, WALLET, WALLET2)


            # METRIC CALCULATION    #NOTE: Lag is ~44ms for ~12000 transactions
            
            # CASH FLOW - Only sales/purchases/trades affect cash_flow. trades, because it makes more sense to have them than not, even though they are independent of USD.
            if TYPE in ('purchase','purchase_crypto_fee'):  metrics[GA]['cash_flow'] -= GV + FV
            elif TYPE  == 'sale':                           metrics[LA]['cash_flow'] += LV - FV
            elif TYPE == 'trade':   # Trades are a sort of 'indirect purchase/sale' of an asset. For them, the fee is lumped with the sale, not the purchase
                metrics[LA]['cash_flow'] += LV - FV
                metrics[GA]['cash_flow'] -= GV
            
            # REALIZED PROFIT AND LOSS - Sales and trades sometimes profit, whereas gift_outs, expenses, as well as any fees always incur a loss
            # Fees are always a realized loss, if there is one
            if FA:                              metrics[FA]['realized_profit_and_loss'] -= FEE_COST_BASIS   # Base fee cost is realized
            elif TYPE == 'purchase':            metrics[GA]['realized_profit_and_loss'] -= FV        # Base fee cost is realized to asset bought
            elif TYPE == 'sale':                metrics[LA]['realized_profit_and_loss'] -= FV        # Base fee cost is realized to asset sold
            #Expenses and gift_outs are a complete realized loss. Sales and trades we already lost the fee, but hopefully gain more from sale yield
            if TYPE in ('expense','gift_out'):  metrics[LA]['realized_profit_and_loss'] -= LOSS_COST_BASIS  # Base loss cost is realized
            elif TYPE in ('sale','trade'):      metrics[LA]['realized_profit_and_loss'] += LV - LOSS_COST_BASIS # Base loss cost is realized, but sale yields the loss value

            # CAPITAL GAINS TAX
            #Independent transfer fees are taxed as a 'sale'
            if TYPE in ('gift_out','transfer_out','transfer_in') and FA: metrics[FA]['tax_capital_gains'] += FV - FEE_COST_BASIS
            #Expenses taxed as a 'sale', trade treated as an immediate sale and purchase
            elif TYPE in ('sale','trade'):                               metrics[LA]['tax_capital_gains'] += (LV - FV) - LOSS_COST_BASIS 
            elif TYPE == 'expense':                                      metrics[LA]['tax_capital_gains'] += (LV + FV) - LOSS_COST_BASIS 

            # INCOME TAX
            if TYPE in ['card_reward','income']:    #This accounts for all transactions taxable as INCOME: card rewards, and staking rewards
                metrics[GA]['tax_income'] += GV
                if tax_report=='1099-MISC':  
                    TEMP['taxes']['1099-MISC'] = TEMP['taxes']['1099-MISC'].append( {'Date acquired':DATE, 'Value of assets':str(GV)}, ignore_index=True)

            #*** *** *** DONE FOR THIS TRANSACTION *** *** ***#

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
                for gain in holdings[a][w]._heap:
                    total_cost_basis        += gain._price*gain._quantity   #cost basis of this gain
                    total_holdings          += gain._quantity               #Single number for the total number of tokens
                    wallet_holdings[w]      += gain._quantity               #Number of tokens within each wallet

            asset._metrics['cost_basis'] =  total_cost_basis
            asset._metrics['holdings'] =    total_holdings
            asset._metrics['wallets'] =     wallet_holdings
            
    def calculate_average_buy_price(self, asset:Asset):
        try:    asset._metrics['average_buy_price'] = asset.precise('cost_basis') / asset.precise('holdings')
        except: asset._metrics['average_buy_price'] = 0
    def calculate_value(self, asset:Asset):   #Calculates the overall value of this asset
        #Must be a try statement because it relies on market data
        try:    asset._metrics['value'] = asset.precise('holdings') * asset.precise('price')
        except: asset._metrics['value'] = MISSINGDATA
    def calculate_unrealized_profit_and_loss(self, asset:Asset):
        #You need current market data for these bad boys
        average_buy_price = asset.precise('average_buy_price')
        try:        
            asset._metrics['unrealized_profit_and_loss'] =      asset.precise('value') - ( average_buy_price * asset.precise('holdings') )
            asset._metrics['unrealized_profit_and_loss%'] =   ( asset.precise('price') /  average_buy_price )-1
        except:     asset._metrics['unrealized_profit_and_loss%'] = asset._metrics['unrealized_profit_and_loss'] = 0
    def calculate_changes(self, asset:Asset): #Calculates the unrealized USD lost or gained in the last 24 hours, week, and month for this asset
        #Must be a try statement because it relies on market data
        value = asset.precise('value')
        try:    asset._metrics['day_change'] =   value-(value / (1 + asset.precise('day%')))
        except: asset._metrics['day_change'] =   0
        try:    asset._metrics['week_change'] =  value-(value / (1 + asset.precise('week%')))
        except: asset._metrics['week_change'] =  0
        try:    asset._metrics['month_change'] = value-(value / (1 + asset.precise('month%')))
        except: asset._metrics['month_change'] = 0
    def calculate_net_cash_flow(self, asset:Asset): #Calculates what the cash flow would become if you sold everything right now
        #Must be a try statement because it relies on market data
        try:    asset._metrics['net_cash_flow'] = asset.precise('cash_flow') + asset.precise('value') 
        except: asset._metrics['net_cash_flow'] = 0
    def calculate_percentage_of_portfolio(self, asset:str): #Calculates how much of the value of your portfolio is this asset - NOTE: must be done after total portfolio value calculated
        try:    asset._metrics['portfolio%'] = asset.get('value')  / MAIN_PORTFOLIO.get('value')
        except: asset._metrics['portfolio%'] = 0

    def calculate_portfolio_value(self):
        value = 0
        for a in MAIN_PORTFOLIO.assets():    #Compiles complete list of all wallets used in the portfolio
            try: value += a.get('value') #Adds the total value of this asset to the overall portfolio value. If no price data can be found we assume this asset it worthless.
            except: None
        MAIN_PORTFOLIO._metrics['value'] = value
    def calculate_portfolio_changes(self):
        MAIN_PORTFOLIO._metrics.update({'day_change':0,'week_change':0,'month_change':0})
        for a in MAIN_PORTFOLIO.assets():
            try:
                MAIN_PORTFOLIO._metrics['day_change'] += a.get('day_change')
                MAIN_PORTFOLIO._metrics['week_change'] += a.get('week_change')
                MAIN_PORTFOLIO._metrics['month_change'] += a.get('month_change')
            except: pass
    def calculate_portfolio_percents(self):
        try:    MAIN_PORTFOLIO._metrics['day%'] =   MAIN_PORTFOLIO.get('day_change') /   (MAIN_PORTFOLIO.get('value') - MAIN_PORTFOLIO.get('day_change'))
        except: MAIN_PORTFOLIO._metrics['day%'] = 0
        try:    MAIN_PORTFOLIO._metrics['week%'] =  MAIN_PORTFOLIO.get('week_change') /  (MAIN_PORTFOLIO.get('value') - MAIN_PORTFOLIO.get('week_change'))
        except: MAIN_PORTFOLIO._metrics['week%'] = 0
        try:    MAIN_PORTFOLIO._metrics['month%'] = MAIN_PORTFOLIO.get('month_change') / (MAIN_PORTFOLIO.get('value') - MAIN_PORTFOLIO.get('month_change'))
        except: MAIN_PORTFOLIO._metrics['month%'] = 0
    def calculate_portfolio_value_by_wallet(self):    #For the overall portfolio, calculates the total value held within each wallet
        wallets = {}
        for wallet in MAIN_PORTFOLIO.walletkeys():     #Creates a list of wallets, defaulting to 0$ within each
            wallets[wallet] = 0
        for asset in MAIN_PORTFOLIO.assets():       #Then, for every asset, we look at its 'wallets' dictionary, and sum up the value of each wallet's tokens by wallet
            for wallet in asset.get('wallets'):
                # Asset wallet list is total units by wallet, multiply by asset price to get value
                try:    wallets[wallet] += asset.get('wallets')[wallet] * asset.precise('price')
                except: pass
        MAIN_PORTFOLIO._metrics['wallets'] = wallets
    def calculate_portfolio_unrealized_profit_and_loss(self):
        total_unrealized_profit = 0
        for asset in MAIN_PORTFOLIO.assets():
            try:    total_unrealized_profit += asset.precise('unrealized_profit_and_loss')
            except: continue    #Just ignore assets missing price data
        try:        
            MAIN_PORTFOLIO._metrics['unrealized_profit_and_loss'] = total_unrealized_profit
            MAIN_PORTFOLIO._metrics['unrealized_profit_and_loss%'] = total_unrealized_profit / (MAIN_PORTFOLIO.get('value') - total_unrealized_profit)
        except:
            MAIN_PORTFOLIO._metrics['unrealized_profit_and_loss'] = MAIN_PORTFOLIO._metrics['unrealized_profit_and_loss%'] = 0


#BINDINGS
#=============================================================
    def _mouse(self, event):        #Tracks your mouse position
        self.mouse_pos = (event.x_root, event.y_root)
    def _mousewheel(self, event):   #Scroll up and down the assets pane
        if self.grab_current() == self: #If any other window is open, then you can't do this
            if event.delta > 0:     self.comm_page_last()
            elif event.delta < 0:   self.comm_page_next()
    def _esc(self,event):    #Exit this window
        if self.grab_current() == self: #If any other window is open, then you can't do this
            if self.GUI['GRID'].selection != [None, None]:  self.GUI['GRID'].set_selection()  #If anything is selected, deselect it
            elif self.rendered[0] == 'portfolio':  self.comm_quit()        #If we're on the main page, exit the program
            else:                   self.render(('portfolio',None), True)  #If we're looking at an asset, go back to the main page
    def _del(self,event):    #Delete any selected items
        if self.grab_current() == self: #If any other window is open, then you can't do this
            cur_selection = self.GUI['GRID'].selection
            if cur_selection != [None, None]:  self.delete_selection(cur_selection[0],cur_selection[1])

# UNDO REDO
#=============================================================
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
    def undo_save(self):        #Create a savepoint which can be returned to
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



# MISCELLANEOUS
#=============================================================
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

    def get_mouse_pos(self):    return self.mouse_pos





if __name__ == '__main__':
    print('||    AUTO-ACCOUNTANT    ||')
    AutoAccountant().mainloop()





