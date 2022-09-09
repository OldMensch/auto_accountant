#In-house
from AAlib import *
from AAmarketData import getMissingPrice, startMarketDataLoops
import AAimport
from AAdialogs import *
import pandas as pd


#Default Python
import math

import threading


class AutoAccountant(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowIcon(icon('icon'))
        self.setWindowTitle('Portfolio Manager')
        
        self.undoRedo = [0, 0, 0]  #index of first undosave, index of last undosave, index of currently loaded undosave
        self.rendered = ('portfolio', None) #'portfolio' renders all the assets. 'asset' combined with the asset tickerclass renders that asset
        self.page = 0 #This indicates which page of data we're on. If we have 600 assets and 30 per page, we will have 20 pages.
        self.sorted = []
        #Sets the timezone to 
        info_format_lib['date']['name'] = info_format_lib['date']['headername'] = info_format_lib['date']['name'].split('(')[0]+'('+setting('timezone')+')'

        self.__init_gui__()
        self.__init_taskbar__()
        self.__init_menu__()

        #Try to load last-used JSON file, if the file works and we have it set to start with the last used portfolio
        if setting('startWithLastSaveDir') and os.path.isfile(setting('lastSaveDir')):  self.load(setting('lastSaveDir'))
        else:                                                                           self.new(first=True)

        self.online_event = threading.Event()
        #Now that the hard data is loaded, we need market data
        if setting('offlineMode'):
            #If in Offline Mode, try to load any saved offline market data. If there isn't a file... loads nothing.
            try:
                with open('#OfflineMarketData.json', 'r') as file:
                    data = json.load(file)
                    data['_timestamp']
                    marketdatalib.update(data)
                self.GUI['offlineIndicator'].setText('OFFLINE MODE - Data from ' + marketdatalib['_timestamp'][0:16])
                self.GUI['offlineIndicator'].show() #Turns on a bright red indicator, which lets you know you're in offline mode
                self.market_metrics()
            except:
                self.toggle_offline_mode()
                print('||ERROR|| Failed to load offline market data! Going online.')
        else:
            self.online_event.set()
            self.GUI['offlineIndicator'].hide()

        #We always turn on the threads for gethering market data. Even without internet, they just wait for the internet to turn on.
        startMarketDataLoops(self, self.online_event)

        #GLOBAL BINDINGS
        #==============================
        self.wheelEvent = self._mousewheel                                          # Last/Next page
        QShortcut(QKeySequence(self.tr("Ctrl+S")), self, self.save)   # Save
        QShortcut(QKeySequence(self.tr("Ctrl+A")), self, self._ctrl_a)              # Select all rows of data
        QShortcut(QKeySequence(self.tr("Ctrl+Y")), self, self._ctrl_y)              # Undo
        QShortcut(QKeySequence(self.tr("Ctrl+Z")), self, self._ctrl_z)              # Redo
        QShortcut(QKeySequence(self.tr("Esc")), self, self._esc)                    # Unselect, close window
        QShortcut(QKeySequence(self.tr("Del")), self, self._del)                    # Delete selection
        QShortcut(QKeySequence(self.tr("F11")), self, self._f11)                    # Fullscreen


        #Closes the PyInstaller splash screen now that the program is loaded
        try: exec("""import pyi_splash\npyi_splash.close()""") # exec() is used so that VSCode ignores the "I can't find this module error"
        except: pass

        self.render(sort=True) # Sorts and renders portfolio for the first time
        self.showMaximized()

        self.lastResizeTime = datetime.now()-timedelta(1)
        self.installEventFilter(self)

    def eventFilter(self, obj:QObject, event:QEvent, *args):
        if event.type() == QEvent.Resize:
            self.lastResizeTime = datetime.now()
        if event.type() in (QEvent.HoverEnter, QEvent.NonClientAreaMouseButtonRelease) and datetime.now()-self.lastResizeTime < timedelta(hours=1):
            self.GUI['GRID'].doResizification()
            self.lastResizeTime = datetime.now()-timedelta(1)
        return QWidget.eventFilter(self, self, event)

        

#NOTE: Tax forms have been temporarily disabled to speed up boot time until I implement a better method

#TASKBAR, LOADING SAVING MERGING and QUITTING
#=============================================================
    def __init_taskbar__(self):
        self.TASKBAR = {}
        taskbar = self.TASKBAR['taskbar'] = QMenuBar(self)     #The big white bar across the top of the window
        self.setMenuBar(taskbar)

        #'File' Tab
        file = self.TASKBAR['file'] = QMenu('File')
        taskbar.addMenu(file)
        file.addAction('New',               self.new)
        file.addAction('Load...',           self.load)
        file.addAction('Save',              self.save)
        file.addAction('Save As...',        p(self.save, True))
        file.addAction('Merge Portfolio',   self.merge)
        importmenu = QMenu('Import')
        file.addMenu(importmenu)
        importmenu.addAction('Import Binance History',      self.import_binance)
        importmenu.addAction('Import Coinbase History',     self.import_coinbase)
        importmenu.addAction('Import Coinbase Pro History', self.import_coinbase_pro)
        importmenu.addAction('Import Etherscan History',    self.import_etherscan)
        importmenu.addAction('Import Gemini History',       self.import_gemini)
        importmenu.addAction('Import Gemini Earn History',  self.import_gemini_earn)
        importmenu.addAction('Import Yoroi Wallet History', self.import_yoroi)
        file.addSeparator()
        file.addAction('QUIT', self.quit)

        #'Settings' Tab
        settings = self.TASKBAR['settings'] = QMenu('Settings')
        taskbar.addMenu(settings)

        self.offlineMode = QAction('Offline Mode', parent=settings, triggered=self.toggle_offline_mode, checkable=True, checked=setting('offlineMode'))
        settings.addAction(self.offlineMode)


        def set_timezone(tz:str):
            set_setting('timezone', tz)                         # Change the timezone setting itself
            for transaction in MAIN_PORTFOLIO.transactions():   # Recalculate the displayed ISO time on all of the transactions
                transaction.calc_iso_date()
            info_format_lib['date']['name'] = info_format_lib['date']['headername'] = info_format_lib['date']['name'].split('(')[0]+'('+tz+')'
            self.render()   #Only have to re-render w/o recalculating metrics, since metrics is based on the UNIX time
        timezonemenu = self.TASKBAR['timezone'] = QMenu('Timezone')
        settings.addMenu(timezonemenu)

        timezoneActionGroup = QActionGroup(timezonemenu)
        for tz in timezones:
            timezonemenu.addAction(QAction('('+tz+') '+timezones[tz][0], parent=timezonemenu, triggered=p(set_timezone, tz), actionGroup=timezoneActionGroup, checkable=True, checked=(setting('timezone') == tz)))

        def light_mode(): app.setStyleSheet('')
        def dark_mode():  app.setStyleSheet(qdarkstyle.load_stylesheet_pyside2())
        appearancemenu = self.TASKBAR['appearance'] = QMenu('Appearance')
        settings.addMenu(appearancemenu)
        appearancemenu.addAction('Light Mode', light_mode)
        appearancemenu.addAction('Dark Mode', dark_mode)

        #'Accounting' Submenu
        accountingmenu = self.TASKBAR['accounting'] = QMenu('Accounting Method')
        settings.addMenu(accountingmenu)
        def set_accounting_method(method):
            set_setting('accounting_method', method)
            self.metrics()
            self.render(sort=True)
        accountingactions = {}
        accountingActionGroup = QActionGroup(accountingmenu)
        accountingactions['fifo'] = QAction('First in First Out (FIFO)',   parent=accountingmenu, triggered=p(set_accounting_method, 'fifo'), actionGroup=accountingActionGroup, checkable=True)
        accountingactions['lifo'] = QAction('Last in First Out (LIFO)',    parent=accountingmenu, triggered=p(set_accounting_method, 'lifo'), actionGroup=accountingActionGroup, checkable=True)
        accountingactions['hifo'] = QAction('Highest in First Out (HIFO)', parent=accountingmenu, triggered=p(set_accounting_method, 'hifo'), actionGroup=accountingActionGroup, checkable=True)
        for method in accountingactions:
            accountingmenu.addAction(accountingactions[method])
            if setting('accounting_method') == method: accountingactions[method].setChecked(True)

        #'About' Tab
        about = self.TASKBAR['about'] = QMenu('About')
        taskbar.addMenu(about)
        about.addAction('MIT License', self.copyright)

        #'Info' Tab
        infomenu = self.TASKBAR['info'] = QMenu('Info')
        taskbar.addMenu(infomenu)
        
        self.infoactions = {
            info:QAction(info_format_lib[info]['name'], parent=infomenu, triggered=p(self.toggle_header, info), checkable=True, checked=(info in setting('header_portfolio'))) for info in assetinfolib
            }
        for action in self.infoactions:   infomenu.addAction(action)

        #'Taxes' Tab
        taxes = self.TASKBAR['taxes'] = QMenu('Taxes')
        taskbar.addMenu(taxes)
        taxes.addAction('Generate data for IRS Form 8949', self.tax_Form_8949)
        taxes.addAction('Generate data for IRS Form 1099-MISC', self.tax_Form_1099MISC)

        #'DEBUG' Tab
        DEBUG = self.TASKBAR['DEBUG'] = QMenu('DEBUG')
        taskbar.addMenu(DEBUG)
        DEBUG.addAction('DEBUG find all missing price data',     self.DEBUG_find_all_missing_prices)
        DEBUG.addAction('DEBUG delete all transactions, by wallet',     self.DEBUG_delete_all_of_asset)
        DEBUG.addAction('DEBUG increase page length',     self.DEBUG_increase_page_length)
        DEBUG.addAction('DEBUG decrease page length',     self.DEBUG_decrease_page_length)
        DEBUG.addAction('DEBUG time report',     p(ttt, 'average_report'))
        DEBUG.addAction('DEBUG time reset',     p(ttt, 'reset'))

    def toggle_offline_mode(self):
        if setting('offlineMode'):  #Changed from Offline to Online Mode
            self.online_event.set()
            self.GUI['offlineIndicator'].hide() #Removes the offline indicator
        else:                       #Changed to from Online to Offline Mode
            if '_timestamp' in marketdatalib:   # Saves marketdatalib for offline use, if we have any data to save
                with open('#OfflineMarketData.json', 'w') as file:
                    json.dump(marketdatalib, file, indent=4, sort_keys=True)
            else:                               # If we don't have data to save, try to load old data. If that fails... we're stuck in Online Mode
                try:
                    with open('#OfflineMarketData.json', 'r') as file:
                        data = json.load(file)
                        data['_timestamp']
                        marketdatalib.update(data)
                except:
                    Message(self, 'Offline File Error', 'Failed to load offline market data cache. Staying in online mode.')
            self.online_event.clear()
            self.GUI['offlineIndicator'].setText('OFFLINE MODE - Data from ' + marketdatalib['_timestamp'][0:16])
            self.GUI['offlineIndicator'].show() #Turns on a bright red indicator, which lets you know you're in offline mode
            self.metrics()
            self.render()
        set_setting('offlineMode',not setting('offlineMode'))
        self.offlineMode.setChecked(setting('offlineMode'))
        
    def tax_Form_8949(self):
        dir = QFileDialog.getOpenFileName(self, 'Save data for IRS Form 8949', setting('lastSaveDir'), "CSV Files (*.csv)")[0]
        if dir == '':   return
        self.metrics(tax_report='8949')
        with open(dir, 'w', newline='') as file:
            file.write(TEMP['taxes']['8949'].to_csv())
    def tax_Form_1099MISC(self):
        dir = QFileDialog.getOpenFileName(self, 'Save data for IRS Form 1099-MISC', setting('lastSaveDir'), "CSV Files (*.csv)")[0]
        if dir == '':   return
        self.metrics(tax_report='1099-MISC')
        with open(dir, 'w', newline='') as file:
            file.write(TEMP['taxes']['1099-MISC'].to_csv())

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
        self.GUI['GRID'].update_page_length(setting('itemsPerPage')+5)
        self.render()
    def DEBUG_decrease_page_length(self):
        self.GUI['GRID'].update_page_length(setting('itemsPerPage')-5)
        self.render()

    def import_binance(self, wallet=None):
        if wallet == None:    ImportationDialog(self, self.import_binance, 'Binance Wallet') 
        else:
            dir = QFileDialog.getOpenFileName(self, 'Import Binance Transaction History', setting('lastSaveDir'), "CSV Files (*.csv)")[0]
            if dir == '':   return
            AAimport.binance(self, dir, wallet)
    def import_coinbase(self, wallet=None):
        if wallet == None:    ImportationDialog(self, self.import_coinbase, 'Coinbase Wallet') 
        else:
            dir = QFileDialog.getOpenFileName(self, 'Import Coinbase Transaction History', setting('lastSaveDir'), "CSV Files (*.csv)")[0]
            if dir == '':   return
            AAimport.coinbase(self, dir, wallet)
    def import_coinbase_pro(self, wallet=None):
        if wallet == None:    ImportationDialog(self, self.import_coinbase_pro, 'Coinbase Pro Wallet') 
        else:
            dir = QFileDialog.getOpenFileName(self, 'Import Coinbase Pro Transaction History', setting('lastSaveDir'), "CSV Files (*.csv)")[0]
            if dir == '':   return
            AAimport.coinbase_pro(self, dir, wallet)
    def import_etherscan(self, wallet=None):
        if wallet == None:    ImportationDialog(self, self.import_etherscan, 'Ethereum Wallet') 
        else:
            ETHdir = QFileDialog.getOpenFileName(self, 'Import Etherscan ETH Transaction History', setting('lastSaveDir'), "CSV Files (*.csv)")[0]
            if ETHdir == '':   return
            ERC20dir = QFileDialog.getOpenFileName(self, 'Import Etherscan ERC-20 Transaction History', setting('lastSaveDir'), "CSV Files (*.csv)")[0]
            if ERC20dir == '':   return
            AAimport.etherscan(self, ETHdir, ERC20dir, wallet)
    def import_gemini(self, wallet=None):
        if wallet == None:    ImportationDialog(self, self.import_gemini, 'Gemini Wallet') 
        else:
            dir = QFileDialog.getOpenFileName(self, 'Import Gemini Transaction History', setting('lastSaveDir'), "XLSX Files (*.xlsx)")[0]
            if dir == '':   return
            AAimport.gemini(self, dir, wallet)
    def import_gemini_earn(self, wallet=None):
        if wallet == None:    ImportationDialog(self, self.import_gemini_earn, 'Gemini Earn Wallet') 
        else:
            dir = QFileDialog.getOpenFileName(self, 'Import Gemini Earn Transaction History', setting('lastSaveDir'), "XLSX Files (*.xlsx)")[0]
            if dir == '':   return
            AAimport.gemini_earn(self, dir, wallet)
    def import_yoroi(self, wallet=None):
        if wallet == None:    ImportationDialog(self, self.import_yoroi, 'Yoroi Wallet') 
        else:
            dir = QFileDialog.getOpenFileName(self, 'Import Yoroi Wallet Transaction History', setting('lastSaveDir'), "CSV Files (*.csv)")[0]
            if dir == '':   return
            AAimport.yoroi(self, dir, wallet)

    def save(self, saveAs=False):
        if saveAs or not os.path.isfile(setting('lastSaveDir')):
            dir = QFileDialog.getSaveFileName(self, 'Save Portfolio', setting('lastSaveDir'), "JSON Files (*.json)")[0]
        else:
            if not self.isUnsaved(): return
            dir = setting('lastSaveDir')
        if dir == '':
            return
        self.setWindowTitle('Portfolio Manager - ' + dir.split('/').pop())
        with open(dir, 'w') as file:
            json.dump(MAIN_PORTFOLIO.toJSON(), file, sort_keys=True)
        if saveAs:      set_setting('lastSaveDir', dir)
    def new(self, first=False):
        set_setting('lastSaveDir', '')
        MAIN_PORTFOLIO.clear()
        self.setWindowTitle('Portfolio Manager')
        self.profile = ''   #name of the currently selected profile. Always starts with no filter applied.
        self.metrics()
        self.render(('portfolio',None), True)
        if not first:   self.undo_save()
    def load(self, dir=None):
        if dir == None: dir = QFileDialog.getOpenFileName(self, 'Load Portfolio', setting('lastSaveDir'), "JSON Files (*.json)")[0]
        if dir == '':   return
        try:    
            with open(dir, 'r') as file:
                decompile = json.load(file)    #Attempts to load the file
        except:
            Message(self, 'Error!', 'File couldn\'t be loaded. Probably corrupt or something.' )
            self.new(first=True)
            return
        MAIN_PORTFOLIO.loadJSON(decompile)
        self.setWindowTitle('Portfolio Manager - ' + dir.split('/').pop())
        set_setting('lastSaveDir', dir)
        self.profile = ''   #name of the currently selected profile. Always starts with no filter applied.
        self.metrics()
        self.render(('portfolio',None), True)
        self.undo_save()  
    def merge(self): #Doesn't overwrite current portfolio by default.
        dir = QFileDialog.getOpenFileName(self, 'Load Portfolio for Merging', setting('lastSaveDir'), "JSON Files (*.json)")[0]
        if dir == '':
            return
        try:
            with open(dir, 'r') as file:
                decompile = json.load(file)    #Attempts to load the file
        except:
            Message(self, 'Error!', '\'file\' is an unparseable JSON file. Probably missing commas or brackets.' )
            return
        MAIN_PORTFOLIO.loadJSON(decompile, True, False)
        set_setting('lastSaveDir', '') #resets the savedir. who's to say where a merged portfolio should save to? why should it be the originally loaded file, versus any recently merged ones?
        self.setWindowTitle('Portfolio Manager')
        self.profile = ''   #name of the currently selected profile. Always starts with no filter applied.
        self.metrics()
        self.render(('portfolio',None), True)
        self.undo_save()

    def quit(self, event=None):
        if event: event.ignore() # Prevents program from closing if you hit the main window's 'X' button, instead I control whether it closes here.
        def save_and_quit():
            self.save()
            app.quit()

        if self.isUnsaved():
            unsavedPrompt = Prompt(self, 'Unsaved Changes', 'Are you sure you want to quit? This cannot be undone!')
            unsavedPrompt.add_menu_button('Quit', app.quit, styleSheet=style('delete'))
            unsavedPrompt.add_menu_button('Save and Quit', save_and_quit, styleSheet=style('save'))
            unsavedPrompt.show()
        else:
            app.quit()

    def isUnsaved(self):
        lastSaveDir = setting('lastSaveDir')
        if MAIN_PORTFOLIO.isEmpty(): #there is nothing to save, thus nothing is unsaved     
            return False
        elif lastSaveDir == '': 
            return True     #If you haven't saved anything yet, then yes, its 100% unsaved
        elif not os.path.isfile(lastSaveDir):
            return True     #Only happens if you deleted the file that the program was referencing, while using the program
        with open(lastSaveDir, 'r') as file:
            lastSaveHash = hash(json.dumps(json.load(file))) #hash for last loaded file
        currentDataHash = hash(json.dumps(MAIN_PORTFOLIO.toJSON(), sort_keys=True))
        if currentDataHash == lastSaveHash:
            return False    #Hashes are the same, file is most recent copy
        else:
            return True     #Hashes are different, file is modified


#OVERARCHING GUI FRAMEWORK
#=============================================================
    def __init_gui__(self):
        #GUI CREATION
        #==============================
        self.GUI = {}

        #Contains everything
        self.GUI['masterLayout'] = QGridLayout(spacing=0, margin=(0))
        self.GUI['masterFrame'] = QWidget(self, layout=self.GUI['masterLayout'])
        #contains the menu
        self.GUI['menuLayout'] = QHBoxLayout()
        self.GUI['menuFrame'] = QFrame(layout=self.GUI['menuLayout'])
        #contains the big title and overall stats for the portfolio/asset 
        self.GUI['sidePanelLayout'] = QGridLayout()
        self.GUI['sidePanelFrame'] = QFrame(layout=self.GUI['sidePanelLayout'], frameShape=QFrame.Panel, frameShadow=QFrame.Shadow.Plain, lineWidth=20, midLineWidth=20)
        self.GUI['title'] = QLabel('Auto-Accountant', alignment=Qt.AlignCenter, styleSheet=style('title'))
        self.GUI['subtitle'] = QLabel('Overall Portfolio', alignment=Qt.AlignCenter, styleSheet=style('subtitle'))
        self.GUI['info_pane'] = QLabel(alignment=Qt.AlignHCenter, styleSheet=style('info_pane'))
        self.GUI['back'] = QPushButton('Return to\nPortfolio', clicked=p(self.render, ('portfolio',None), True))
        self.GUI['page_number'] = QLabel('Page XXX of XXX', alignment=Qt.AlignCenter)
        self.GUI['page_next'] = QPushButton(icon=icon('arrow_down'), iconSize=icon('size'), clicked=self.page_next)
        self.GUI['page_prev'] = QPushButton(icon=icon('arrow_up'), iconSize=icon('size'),  clicked=self.page_prev)
        #contains the buttons for opening editors, info displays, etc.
        self.GUI['buttonLayout'] = QHBoxLayout()
        self.GUI['buttonFrame'] = QWidget(layout=self.GUI['buttonLayout'])
        self.GUI['info'] = QPushButton(icon=icon('info2'), iconSize=icon('size'),  clicked=self.portfolio_stats_and_info)
        self.GUI['edit'] = QPushButton(icon=icon('settings2'), iconSize=icon('size'))
        self.GUI['new_asset'] = QPushButton('+ Asset', clicked=p(AssetEditor, self), fixedHeight=icon('size2').height())
        self.GUI['new_transaction'] = QPushButton('+ Trans', clicked=p(TransEditor, self), fixedHeight=icon('size2').height())
        #contains the list of assets/transactions
        self.GUI['GRID'] = GRID(self, self.set_sort, self._header_menu, self._left_click_row, self._right_click_row)
        #The little bar on the bottom
        self.GUI['bottomLayout'] = QHBoxLayout()
        self.GUI['bottomFrame'] = QFrame(layout=self.GUI['bottomLayout'])
        self.GUI['copyright'] = QPushButton('Copyright © 2022 Shane Evanson', clicked=self.copyright)
        self.GUI['offlineIndicator'] = QLabel(' OFFLINE MODE ')
        self.GUI['progressBar'] = QProgressBar(fixedHeight=(self.GUI['copyright'].sizeHint().height()), styleSheet=style('progressBar'))

        #GUI PLACEMENT
        #==============================
        #Self - The main QApplication
        self.setCentralWidget(self.GUI['masterFrame']) #Makes the master frame fill the entire main window
        #Master Frame - Contains everything
        self.GUI['masterLayout'].setRowStretch(1, 1) # The side panel and GRID absorb vertical stretching
        self.GUI['masterLayout'].setColumnStretch(1, 1) # The GRID absorbs horizontal stretching
        self.GUI['masterLayout'].addWidget(self.GUI['menuFrame'], 0, 0, 1, 2)
        self.GUI['masterLayout'].addWidget(self.GUI['sidePanelFrame'], 1, 0)

        self.GUI['gridFrame'] = QWidget(layout=self.GUI['GRID'], contentsMargins=QMargins(0,0,0,0))
        #self.GUI['GRID'].setMargin(0)
        self.GUI['gridScrollArea'] = QScrollArea(widget=self.GUI['gridFrame'], widgetResizable=True, viewportMargins=QMargins(-2, -2, -2, 0), styleSheet=style('GRID'))
        # Prevents vertical scrollbar from appearing, even by accident, or while resizing the window
        self.GUI['gridScrollArea'].setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)


        self.GUI['masterLayout'].addWidget(self.GUI['gridScrollArea'], 1, 1)
        self.GUI['masterLayout'].addWidget(self.GUI['bottomFrame'], 2, 0, 1, 2)

        #Side Panel Frame - The side menu, which contains multiple buttons and things
        self.GUI['sidePanelLayout'].setRowStretch(3, 1) # The info panel absorbs vertical stretching
        self.GUI['sidePanelLayout'].addWidget(self.GUI['title'], 0, 0, 1, 2)
        self.GUI['sidePanelLayout'].addWidget(self.GUI['subtitle'], 1, 0, 1, 2)
        self.GUI['sidePanelLayout'].addWidget(self.GUI['buttonFrame'], 2, 0, 1, 2)
        self.GUI['sidePanelLayout'].addWidget(self.GUI['info_pane'], 3, 0, 1, 2)
        self.GUI['sidePanelLayout'].addWidget(self.GUI['back'], 4, 0, 1, 2)
        self.GUI['sidePanelLayout'].addWidget(self.GUI['page_number'], 5, 0, 1, 2)
        self.GUI['sidePanelLayout'].addWidget(self.GUI['page_prev'], 6, 0, 1, 1)
        self.GUI['sidePanelLayout'].addWidget(self.GUI['page_next'], 6, 1, 1, 1)

        #Button Frame - contains info button, new transaction, sometimes new asset, or edit asset
        self.GUI['buttonLayout'].addWidget(self.GUI['info'])
        self.GUI['buttonLayout'].addStretch(1)
        self.GUI['buttonLayout'].addWidget(self.GUI['edit'])
        self.GUI['buttonLayout'].addWidget(self.GUI['new_transaction'])
        self.GUI['buttonLayout'].addWidget(self.GUI['new_asset'])
        
        #Bottom Frame - This could be replaced by the QStatusBar widget, which may be better suited for this use
        self.GUI['bottomLayout'].addWidget(self.GUI['copyright'])
        self.GUI['bottomLayout'].addWidget(self.GUI['progressBar'])
        self.GUI['bottomLayout'].addStretch(1)
        self.GUI['bottomLayout'].addWidget(self.GUI['offlineIndicator'])

        self.GUI['sidePanelFrame'].raise_()

        #GUI TOOLTIPS
        #==============================
        tooltips = {
            'new_asset':            'Create a new asset',
            'new_transaction':      'Create a new transaction',

            'back':                 'Return to the main portfolio',
            'page_prev':            'Go to last page',
            'page_next':            'Go to next page',
        }
        for widget in tooltips:     self.GUI[widget].setToolTip(tooltips[widget])


#All the commands for reordering, showing, and hiding the info columns
    def _header_menu(self, col, event=None):
        if self.rendered[0] == 'asset':  return  #There is no menu for the transactions ledger view
        info = setting('header_portfolio')[col]
        m = QMenu(parent=self)
        if col != 0:                                      m.addAction('Move Left',          p(self.move_header, info, 'left'))
        if col != len(setting('header_portfolio'))-1:     m.addAction('Move Right',         p(self.move_header, info, 'right'))
        if col != 0:                                      m.addAction('Move to Beginning',  p(self.move_header, info, 'beginning'))
        if col != len(setting('header_portfolio'))-1:     m.addAction('Move to End',        p(self.move_header, info, 'end'))
        m.addSeparator()
        m.addAction('Hide ' + info_format_lib[info]['name'], self.infoactions[info].trigger)
        m.exec_(event.globalPos())
    def move_header(self, info, shift='beginning'):
        if   shift == 'beginning':  i = 0
        elif shift == 'right':      i = setting('header_portfolio').index(info) + 1
        elif shift == 'left':       i = setting('header_portfolio').index(info) - 1
        elif shift == 'end':        i = len(setting('header_portfolio'))
        else:   # We've dragged and dropped a header onto this one
            i = setting('header_portfolio').index(shift)
        new = setting('header_portfolio')
        new.remove(info)
        new.insert(i, info)
        set_setting('header_portfolio', new)
        self.render()
    def toggle_header(self, info):
        new = setting('header_portfolio')
        if info in setting('header_portfolio'): new.remove(info)
        else:                                   new.insert(0, info)
        set_setting('header_portfolio', new)
        self.render()


    def _left_click_row(self, GRID_ROW:int, event=None): # Opens up the asset subwindow, or transaction editor upon clicking a label within this row
        #if we double clicked on an asset/transaction, thats when we open it.
        i = self.page*setting('itemsPerPage')+GRID_ROW
        if i + 1 > len(self.sorted): return  #Can't select something if it doesn't exist!
        self.GUI['GRID'].set_selection()
        if self.rendered[0] == 'portfolio': self.render(('asset',self.sorted[i].tickerclass()), True)
        else:                               TransEditor(self, self.sorted[i])
    def _right_click_row(self, highlighted:int, selection1:int, selection2:int, event=None): # Opens up a little menu of stuff you can do to this asset/transaction
        #we've right clicked with a selection of multiple items
        m = QMenu(parent=self)
        if selection1 != selection2:
            m.addAction('Delete selection', p(self.delete_selection, selection1, selection2))
        #We've clicked a single item, or nothing at all, popup is relevant to what we right click
        else:
            i = self.page*setting('itemsPerPage')+highlighted
            if i + 1 > len(self.sorted): return  #Can't select something if it doesn't exist!
            item = self.sorted[i]
            if self.rendered[0] == 'portfolio':
                ID = item.tickerclass()
                ticker = item.ticker()
                m.addAction('Open ' + ticker + ' Ledger', p(self.render, ('asset',ID), True))
                m.addAction('Edit ' + ticker, p(AssetEditor, self, ID))
                m.addAction('Show detailed info', p(self.asset_stats_and_info, ID))
                m.addAction('Delete ' + ticker, p(self.delete_selection, highlighted))
            else:
                trans_title = item.date() + ' ' + item.prettyPrint('type')
                m.addAction('Edit ' + trans_title, p(TransEditor, self, item))
                m.addAction('Copy ' + trans_title, p(TransEditor, self, item, True))
                m.addAction('Delete ' + trans_title, p(self.delete_selection, highlighted))
                if item.ERROR:
                    m.addSeparator()
                    m.addAction('ERROR information...', p(Message, self, 'Transaction Error!', item.ERR_MSG))

        m.exec_(event.globalPos())

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


    def __init_menu__(self):
        #MENU CREATION
        #==============================
        self.MENU = {}

        self.MENU['new'] = QPushButton(icon=icon('new'), fixedSize=icon('size2'), iconSize=icon('size'), clicked=self.new)
        self.MENU['load'] = QPushButton(icon=icon('load'), fixedSize=icon('size2'), iconSize=icon('size'), clicked=self.load)
        self.MENU['save'] = QPushButton(icon=icon('save'), fixedSize=icon('size2'), iconSize=icon('size'), clicked=self.save)
        self.MENU['settings'] = QPushButton(icon=icon('settings2'), fixedSize=icon('size2'), iconSize=icon('size'), clicked=p(Message, self, 'whoop',  'no settings menu implemented yet!'))

        self.MENU['undo'] = QPushButton(icon=icon('undo'), fixedSize=icon('size2'), iconSize=icon('size'), clicked=p(self._ctrl_z))
        self.MENU['redo'] = QPushButton(icon=icon('redo'), fixedSize=icon('size2'), iconSize=icon('size'), clicked=p(self._ctrl_y))

        self.MENU['wallets'] = QPushButton('Wallets', clicked=p(WalletManager, self), fixedHeight=icon('size2').height())
        self.MENU['profiles'] = QPushButton(icon=icon('profiles'), fixedSize=icon('size2'), iconSize=icon('size'))

        #MENU RENDERING
        #==============================
        self.GUI['menuLayout'].addWidget(self.MENU['new'])
        self.GUI['menuLayout'].addWidget(self.MENU['load'])
        self.GUI['menuLayout'].addWidget(self.MENU['save'])
        self.GUI['menuLayout'].addWidget(self.MENU['settings'])
        self.GUI['menuLayout'].addSpacing(2*setting('font_size'))
        self.GUI['menuLayout'].addWidget(self.MENU['undo'])
        self.GUI['menuLayout'].addWidget(self.MENU['redo'])
        self.GUI['menuLayout'].addSpacing(2*setting('font_size'))
        self.GUI['menuLayout'].addWidget(self.MENU['wallets'])
        self.GUI['menuLayout'].addWidget(self.MENU['profiles'])
        self.GUI['menuLayout'].addStretch(1)

        #MENU TOOLTIPS
        #==============================
        tooltips = {
            'new':          'Create a new portfolio',
            'load':         'Load an existing portfolio',
            'save':         'Save this portfolio',
            'settings':     'Settings',

            'undo':         'Undo last action',
            'redo':         'Redo last action',

            'wallets':      'Manage wallets',
            'profiles':     'Manage filter profiles',
        }
        for widget in tooltips:     self.MENU[widget].setToolTip(tooltips[widget])


# PORTFOLIO RENDERING
#=============================================================
    def render(self, toRender:tuple=None, sort:bool=False): #NOTE: Very fast! ~30ms when switching panes, ~4ms when switching pages, ~11ms on average
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
                self.GUI['info'].clicked.disconnect()
                self.GUI['info'].clicked.connect(self.portfolio_stats_and_info)
                self.GUI['info'].setToolTip('Detailed information about this portfolio')
                self.GUI['edit'].hide()
                self.GUI['new_asset'].show()
                self.GUI['back'].hide()
            else:
                TICKER = MAIN_PORTFOLIO.asset(toRender[1]).ticker()
                self.GUI['info'].clicked.disconnect()
                self.GUI['info'].clicked.connect(p(self.asset_stats_and_info, toRender[1]))
                self.GUI['info'].setToolTip('Detailed information about '+ TICKER)
                try: self.GUI['edit'].clicked.disconnect()
                except: pass
                self.GUI['edit'].clicked.connect(p(AssetEditor, self, toRender[1]))
                self.GUI['edit'].setToolTip('Edit '+ TICKER)
                self.GUI['edit'].show()
                self.GUI['new_asset'].hide()
                self.GUI['back'].show()

            #Setting up stuff in the Primary Pane
            if toRender[0] == 'portfolio':
                self.GUI['title'].setText('Auto-Accountant')
                self.GUI['subtitle'].setText('Overall Portfolio')
            else:      
                self.GUI['title'].setText(MAIN_PORTFOLIO.asset(toRender[1]).name())
                self.GUI['subtitle'].setText(MAIN_PORTFOLIO.asset(toRender[1]).ticker())
            
            #Sets the asset - 0ms
            self.rendered = toRender

        #Updates the information panel on the lefthand side
        self.update_info_pane()

        #Sorts the assets/transactions
        if sort:    self.sort() #NOTE: This is fast (~7ms for ~900 transactions). It could be faster with Radix Sort... but why? It's insanely fast already!

        #Appropriately enabled/diables the page-setting buttons - 0ms
        maxpage = math.ceil(len(self.sorted)/setting('itemsPerPage'))-1
        if maxpage == -1: maxpage = 0
        if self.page < maxpage:     self.GUI['page_next'].setEnabled(True)
        else:                       self.GUI['page_next'].setEnabled(False)
        if self.page > 0:           self.GUI['page_prev'].setEnabled(True)
        else:                       self.GUI['page_prev'].setEnabled(False)
        self.GUI['page_number'].setText('Page ' + str(self.page+1) + ' of ' + str(maxpage+1))

        #Appropriately renames the headers
        if self.rendered[0] == 'portfolio': header = setting('header_portfolio')
        else:                               header = setting('header_asset')

        #Fills in the page with info
        self.GUI['GRID'].grid_render(header, self.sorted, self.page, self.rendered[1])
        
    def update_info_pane(self):
        textbox = self.GUI['info_pane']
        toDisplay = '<meta name="qrichtext" content="1" />'
        
        for info in ('value','day%','unrealized_profit_and_loss','unrealized_profit_and_loss%'):
            if self.rendered[0] == 'portfolio':
                formatted_info = list(MAIN_PORTFOLIO.pretty(info))
            else:
                formatted_info = list(MAIN_PORTFOLIO.asset(self.rendered[1]).pretty(info))    
            toDisplay += info_format_lib[info]['headername'].replace('\n',' ')+'<br>'
            
            info_format = info_format_lib[info]['format']
            if formatted_info[1] == '':     S = style('neutral')+style('info')
            else:                           S = formatted_info[1]+style('info')
            if info_format == 'percent':    ending = ' %'
            else:                           ending = ' USD'
            toDisplay += HTMLify(formatted_info[0].replace('%',''), S)+ending+'<br><br>'
        textbox.setText(toDisplay.removesuffix('<br><br>'))

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
        elif self.rendered[0] == 'asset' and info in ('value','quantity','price'):  sorted.sort(reverse=not reverse, key=value_quantity_price)
        else:                                                                       sorted.sort(reverse=not reverse, key=numericKey)

        self.sorted = sorted  

    def set_page(self, page:int=None):
        if page==None: page=self.page
        if self.rendered[0] == 'portfolio':  maxpage = math.ceil(len(MAIN_PORTFOLIO.assets())/setting('itemsPerPage')-1)
        else:                   maxpage = math.ceil(len(MAIN_PORTFOLIO.asset(self.rendered[1])._ledger)/setting('itemsPerPage')-1)

        if page < 0:          page = 0
        elif page > maxpage:    page = maxpage

        if page != self.page:
            self.page = page
            self.GUI['GRID'].set_selection() #Clears GRID selection
            self.render()
    def page_next(self):   self.set_page(self.page + 1)
    def page_prev(self):   self.set_page(self.page - 1)

#STATS AND INFO SUMMARY MESSAGES
#=============================================================

    def portfolio_stats_and_info(self): #A wholistic display of all relevant information to the overall portfolio 
        toDisplay = '<meta name="qrichtext" content="1" />' # VERY IMPORTANT: This makes the \t characters actually work
        DEF_INFO_STYLE = style('neutral') + style('info')
        maxWidth = 1
        testfont = QFont('Calibri')
        testfont.setPixelSize(20)

        # NUMBER OF TRANSACTIONS, NUMBER OF ASSETS
        to_insert = MAIN_PORTFOLIO.pretty('number_of_transactions')
        toDisplay += '• ' + HTMLify(to_insert[0], DEF_INFO_STYLE)
        to_insert = MAIN_PORTFOLIO.pretty('number_of_assets')
        toDisplay += ' transactions loaded under ' + HTMLify(to_insert[0], DEF_INFO_STYLE) + ' assets<br>'

        # USD PER WALLET
        toDisplay += '• Total USD by wallet:<br>'
        toDisplay += '\t*TOTAL*:\t' + HTMLify(format_general(MAIN_PORTFOLIO.get('value'), 'alpha', 20), DEF_INFO_STYLE) + ' USD<br>'
        wallets = list(MAIN_PORTFOLIO.get('wallets'))
        def sortByUSD(w):   return MAIN_PORTFOLIO.get('wallets')[w]  #Wallets are sorted by their total USD value
        wallets.sort(reverse=True, key=sortByUSD)
        for w in wallets:    #Wallets, a list of wallets by name, and their respective net valuations
            quantity = MAIN_PORTFOLIO.get('wallets')[w]
            if not zeroish_prec(quantity):
                width = QFontMetrics(testfont).horizontalAdvance(w+':') + 2
                if width > maxWidth: maxWidth = width
                toDisplay += '\t' + w + ':\t' + HTMLify(format_general(quantity, 'alpha', 20), DEF_INFO_STYLE) + ' USD<br>'

        # MASS INFORMATION
        for data in ('day_change','day%', 'week%', 'month%', 'unrealized_profit_and_loss', 'unrealized_profit_and_loss%'):
            info_format = info_format_lib[data]['format']
            if MAIN_PORTFOLIO.style(data) == '':    S = DEF_INFO_STYLE
            else:                   S = MAIN_PORTFOLIO.style(data)+style('info')
            label = '• '+info_format_lib[data]['name']+':'
            width = QFontMetrics(testfont).horizontalAdvance(label) + 2
            if width > maxWidth: maxWidth = width
            label += '\t\t'
            if info_format == 'percent':
                toDisplay += label + HTMLify(format_general(MAIN_PORTFOLIO.get(data)*100, 'alpha', 20), S) + ' %<br>'
            else:
                toDisplay += label + HTMLify(format_general(MAIN_PORTFOLIO.get(data), 'alpha', 20), S) + ' USD<br>'
        
        Message2(self, 'Overall Stats and Information', toDisplay, tabStopWidth=maxWidth)
    
    def asset_stats_and_info(self, a:str): #A wholistic display of all relevant information to an asset 
        toDisplay = '<meta name="qrichtext" content="1" />' # VERY IMPORTANT: This makes the \t characters actually work
        asset = MAIN_PORTFOLIO.asset(a)
        DEF_INFO_STYLE = style('neutral') + style('info')
        maxWidth = 1
        testfont = QFont('Calibri')
        testfont.setPixelSize(20)

        # NUMBER OF TRANSACTIONS
        toDisplay += '• ' + HTMLify(str(len(MAIN_PORTFOLIO.asset(a)._ledger)), DEF_INFO_STYLE) + ' transactions loaded under ' + HTMLify(asset.ticker(), DEF_INFO_STYLE) + '<br>'
        # ASSET CLASS
        toDisplay += '• Asset Class:\t\t' + HTMLify(asset.prettyPrint('class'), DEF_INFO_STYLE) + '<br>'

        # UNITS PER WALLET
        toDisplay += '• Total '+asset.ticker()+' by wallet:<br>'
        toDisplay += '\t*TOTAL*:\t' + HTMLify(format_general(asset.get('holdings'), 'alpha', 20), DEF_INFO_STYLE) + ' '+asset.ticker() + '<br>'
        wallets = list(MAIN_PORTFOLIO.asset(a).get('wallets'))  
        def sortByUnits(w):   return MAIN_PORTFOLIO.asset(a).get('wallets')[w]    #Wallets are sorted by their total # of units
        wallets.sort(reverse=True, key=sortByUnits)
        for w in wallets:
            quantity = MAIN_PORTFOLIO.asset(a).get('wallets')[w]
            if not zeroish_prec(quantity):
                width = QFontMetrics(testfont).horizontalAdvance(w+':') + 2
                if width > maxWidth: maxWidth = width
                toDisplay += '\t' + w + ':\t' + HTMLify(format_general(quantity, 'alpha', 20), DEF_INFO_STYLE) + ' '+asset.ticker() + '<br>'

        # MASS INFORMATION
        for data in ('price','value', 'marketcap', 'volume24h', 'day_change', 'day%', 'week%', 'month%', 'portfolio%','unrealized_profit_and_loss','unrealized_profit_and_loss%'):
            info_format = info_format_lib[data]['format']
            if asset.style(data) == '':     S = DEF_INFO_STYLE
            else:                           S = asset.style(data)+style('info')
            label = '• '+ info_format_lib[data]['name']+':'
            width = QFontMetrics(testfont).horizontalAdvance(label) + 2
            if width > maxWidth: maxWidth = width
            label += '\t\t'
            if data == 'price':
                toDisplay += label + HTMLify(format_general(asset.get(data), 'alpha', 20), S) + ' USD/'+asset.ticker() + '<br>'
            elif info_format == 'percent':
                toDisplay += label + HTMLify(format_general(asset.precise(data)*100, 'alpha', 20), S) + ' %<br>'
            else:
                toDisplay += label + HTMLify(format_general(asset.get(data), 'alpha', 20), S) + ' USD<br>'

        Message2(self, asset.name() + ' Stats and Information', toDisplay, tabStopWidth=maxWidth)


#METRICS
#=============================================================
    def metrics(self, tax_report:str=''): # Recalculates all metrics
        '''Calculates and renders all static metrics for all assets, and the overall portfolio'''
        self.GUI['progressBar'].show()
        self.GUI['progressBar'].setMinimum(0)
        self.GUI['progressBar'].setMaximum(len(MAIN_PORTFOLIO.transactions()))
        if tax_report:
            TEMP['taxes'] = { 
                '8949':     pd.DataFrame(columns=['Description of property','Date acquired','Date sold or disposed of','Proceeds','Cost or other basis','Gain or (loss)']) ,
                '1099-MISC':pd.DataFrame(columns=['Date acquired', 'Value of assets']),
                }
        self.perform_automatic_accounting(tax_report) # TODO: Laggiest part of the program! (~116ms for ~12000 transactions)
        for asset in MAIN_PORTFOLIO.assets():
            self.calculate_average_buy_price(asset)
        self.metrics_PORTFOLIO() #~0ms, since its just a few O(1) operations
        self.market_metrics() #Only like 2 ms
        self.GUI['progressBar'].hide()

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

        # ERRORS - We assume all transactions have no errors until proven erroneous
        for t in transactions:      t.ERROR = False

        ###################################
        # TRANSFER LINKING - #NOTE: Lag is ~16ms for 159 transfer pairs under ~12000 transactions
        ###################################
        #Before we can iterate through all of our transactions, we need to pair up transfer_IN and transfer_OUTs, otherwise we lose track of cost basis which is BAD
        transfer_IN = [t for t in transactions if t.type() == 'transfer_in' and not t.get('missing')[0]]    #A list of all transfer_INs, chronologically ordered
        transfer_OUT = [t for t in transactions if t.type() == 'transfer_out' and not t.get('missing')[0]]  #A list of all transfer_OUTs, chronologically ordered

        #Then, iterating through all the transactions, we pair them up. 
        for t_out in list(transfer_OUT):
            for t_in in list(transfer_IN): #We have to look at all the t_in's
                # We pair them up if they have the same asset, occur within 5 minutes of eachother, and if their quantities are within 0.1% of eachother
                if t_in.get('gain_asset') == t_out.get('loss_asset') and acceptableTimeDiff(t_in.unix_date(),t_out.unix_date(),300) and acceptableDifference(t_in.precise('gain_quantity'), t_out.precise('loss_quantity'), 0.1):
                        #SUCCESS - We've paired this t_out with a t_in!
                        t_out._data['dest_wallet'] = t_in.wallet() #We found a partner for this t_out, so set its _dest_wallet variable to the t_in's wallet

                        # Two transfers have been paired. Remove them from their respective lists
                        transfer_IN.remove(t_in)
                        transfer_OUT.remove(t_out)
        
        # We have tried to find a partner for all transfers: any remaining transfers are erroneous
        for t in transfer_IN + transfer_OUT:
            t.ERROR = True
            if t.type() == 'transfer_in':
                t.ERR_MSG = 'Failed to automatically find a \'Transfer Out\' transaction under '+t.get('gain_asset')[:-2]+' that pairs with this \'Transfer In\'.'
            else:
                t.ERR_MSG = 'Failed to automatically find a \'Transfer In\' transaction under '+t.get('loss_asset')[:-2]+' that pairs with this \'Transfer Out\'.'
                        

        ###################################
        # AUTO-ACCOUNTING
        ###################################
        #Transfers linked. It's showtime. Time to perform the Auto-Accounting!
        # INFO VARIABLES - data we collect as we account for every transaction #NOTE: Lag is 0ms for ~12000 transactions
        metrics = {
            asset:{'cash_flow':0, 'realized_profit_and_loss': 0, 'tax_capital_gains': 0,'tax_income': 0,} for asset in MAIN_PORTFOLIO.assetkeys()
        }
        
        # HOLDINGS - The data structure which tracks asset's original price across sales #NOTE: Lag is 0ms for ~12000 transactions
        accounting_method = setting('accounting_method')
        # Holdings is a dict of all assets, under which is a dict of all wallets, and each wallet is a priority heap which stores our transactions
        # We use a min/max heap to decide which transactions are "sold" when assets are sold, to determine what the capital gains actually is
        holdings = {asset:{wallet:gain_heap(accounting_method) for wallet in MAIN_PORTFOLIO.walletkeys()} for asset in MAIN_PORTFOLIO.assetkeys()}

        # STORE and DISBURSE QUANTITY - functions which add, or remove a 'gain', to the HOLDINGS data structure.
        def disburse_quantity(t:Transaction, quantity:Decimal, a:str, w:str, w2:str=None):  #NOTE: Lag is ~50ms for ~231 disbursals with ~2741 gains moved on average, or ~5 disbursals/ms, or ~54 disbursed gains/ms
            '''Removes, quantity of asset from specified wallet, then returns cost basis of removed quantity.\n
                If wallet2 \'w2\' specified, instead moves quantity into w2.'''
            result = holdings[a][w].disburse(quantity)     #NOTE - Lag is ~40ms for ~12000 transactions
            if not zeroish_prec(result[0]):  #NOTE: Lag is ~0ms
                t.ERROR,t.ERR_MSG = True,'User disbursed more ' + a.split('z')[0] + ' than they owned from the '+w+' wallet, with ' + str(result[0]) + ' remaining to disburse.'

            #NOTE - Lag is ~27ms including store_quantity, 11ms excluding
            cost_basis = 0
            for gain in result[1]: #Result[1] is a list of gain objects that were just disbursed
                cost_basis += gain._price*gain._quantity
                if tax_report == '8949': tax_8949(t, gain, quantity)
                if w2: holdings[a][w2].store_direct(gain)   #Moves transfers into the other wallet, using the gains objects we already just created
            return cost_basis
            
        def tax_8949(t:Transaction, gain:gain_obj, total_disburse:Decimal):
            ################################################################################################
            # This might still be broken. ALSO: Have to separate the transactions into short- and long-term
            ################################################################################################
            if zeroish_prec(gain._quantity):     return
            if t.type() == 'transfer_out':  return 
            store_date = MAIN_PORTFOLIO.transaction(gain._hash).date()  # Date of aquisition - note: we do this so we don't have to convert the gain's date from UNIX to ISO
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

        progBarIndex = 0
        for t in transactions:  # Lag is ~135ms for ~12000 transactions
            progBarIndex+=1
            self.GUI['progressBar'].setValue(progBarIndex)
            if t.get('missing')[0]:  t.ERROR,t.ERR_MSG = True,t.prettyPrint('missing')   #NOTE: Lag ~9ms for ~12000 transactions
            if t.ERROR: continue    #If there is an ERROR with this transaction, ignore it to prevent crashing. User expected to fix this immediately.

            #NOTE: Lag ~35ms for ~12000 transactions
            HASH,TYPE,WALLET = t.get_hash(),t.type(),t.wallet()
            WALLET2 = t.get('dest_wallet')
            LA,FA,GA = t.get('loss_asset'),         t.get('fee_asset'),         t.get('gain_asset')
            LQ,FQ,GQ = t.precise('loss_quantity'),  t.precise('fee_quantity'),  t.precise('gain_quantity')
            LV,FV,GV = t.precise('loss_value'),     t.precise('fee_value'),     t.precise('gain_value')
            LOSS_COST_BASIS,FEE_COST_BASIS = 0,0
            COST_BASIS_PRICE = t.precise('basis_price')
            

            # COST BASIS CALCULATION    #NOTE: Lag ~250ms for ~12000 transactions. 

            # NOTE: We have to do the gain, then the fee, then the loss, because some Binance trades incur a fee in the crypto you just bought
            # GAINS - We gain assets one way or another     #NOTE: Lag ~180ms, on average
            if COST_BASIS_PRICE:    holdings[GA][WALLET].store(HASH, COST_BASIS_PRICE, GQ, t.unix_date())
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
            if TYPE in ('card_reward','income'):    #This accounts for all transactions taxable as INCOME: card rewards, and staking rewards
                metrics[GA]['tax_income'] += GV
                if tax_report=='1099-MISC':  
                    TEMP['taxes']['1099-MISC'] = TEMP['taxes']['1099-MISC'].append( {'Date acquired':t.date(), 'Value of assets':str(GV)}, ignore_index=True)

            #*** *** *** DONE FOR THIS TRANSACTION *** *** ***#

        #ERRORS - applies error state to any asset with an erroneous transaction on its ledger.
        # We initially assume that no asset has any errors
        for a in MAIN_PORTFOLIO.assets():   a.ERROR = False
        # Then we check all transactions for an ERROR state, and apply that to its parent asset(s)
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
                wallet_holdings[w] = 0 # Initializes total wallet holdings for wallet to be 0$
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
        wallets = {wallet:0 for wallet in MAIN_PORTFOLIO.walletkeys()}  #Creates a dictionary of wallets, defaulting to 0$ within each
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


# UNIVERSAL BINDINGS
#=============================================================
    def _mousewheel(self, event:QWheelEvent): # Controls all scrollwheel-related events.
        if app.keyboardModifiers() == Qt.ControlModifier: # Scrolling with CTRL pressed scales the page
            if(event.angleDelta().y() > 0):     self.DEBUG_decrease_page_length()
            elif(event.angleDelta().y() < 0):   self.DEBUG_increase_page_length()
        elif app.keyboardModifiers() == Qt.ShiftModifier: # Scrolling with SHIFT pressed scrolls horizontally
            if(event.angleDelta().y() > 0):     self.GUI['gridScrollArea'].horizontalScrollBar().setValue(self.GUI['gridScrollArea'].horizontalScrollBar().value() - 100)
            elif(event.angleDelta().y() < 0):   self.GUI['gridScrollArea'].horizontalScrollBar().setValue(self.GUI['gridScrollArea'].horizontalScrollBar().value() + 100)
        else:                                             # Scrolling alone changes the page
            if(event.angleDelta().y() > 0):     self.page_prev()
            elif(event.angleDelta().y() < 0):   self.page_next()
    def _esc(self):     # De-select stuff
        if self.GUI['GRID'].selection != [None, None]:  self.GUI['GRID'].set_selection()  #If anything is selected, deselect it
        elif self.rendered[0] == 'portfolio':  self.quit()        #If we're on the main page, exit the program
        else:                   self.render(('portfolio',None), True)  #If we're looking at an asset, go back to the main page
    def _del(self):     # Delete any selected items
        cur_selection = self.GUI['GRID'].selection
        if cur_selection != [None, None]:  self.delete_selection(cur_selection[0],cur_selection[1])
    def _f11(self):     # Fullscreen
        if self.isFullScreen(): self.showMaximized()
        else:                   self.showFullScreen()
        QTimer.singleShot(10, self.GUI['GRID'].doResizification)
    def _ctrl_a(self):  # Select all rows
        self.GUI['GRID'].set_selection(0, self.GUI['GRID'].pagelength-1)
        self.render()

# UNDO REDO
#=============================================================
    def _ctrl_z(self):    #Undo your last action
        lastAction = (self.undoRedo[2]-1)%len(TEMP['undo'])
        #If there actually IS a previous action, load that
        if (self.undoRedo[1] > self.undoRedo[0] and lastAction >= self.undoRedo[0] and lastAction <= self.undoRedo[1]) or (self.undoRedo[1] < self.undoRedo[0] and (lastAction >= self.undoRedo[0] or lastAction <= self.undoRedo[1])):
                if lastAction == self.undoRedo[0]:  self.MENU['undo'].setEnabled(False)
                else:                               self.MENU['undo'].setEnabled(True)
                self.MENU['redo'].setEnabled(True)
                self.undoRedo[2] = (self.undoRedo[2]-1)%len(TEMP['undo'])
                MAIN_PORTFOLIO.loadJSON(TEMP['undo'][lastAction])
                self.profile = ''   #name of the currently selected profile. Always starts with no filter applied.
                self.metrics()
                self.render(sort=True)
    def _ctrl_y(self):    #Redo your last action
        nextAction = (self.undoRedo[2]+1)%len(TEMP['undo'])
        #If there actually IS a next action, load that
        if (self.undoRedo[1] > self.undoRedo[0] and nextAction >= self.undoRedo[0] and nextAction <= self.undoRedo[1]) or (self.undoRedo[1] < self.undoRedo[0] and (nextAction >= self.undoRedo[0] or nextAction <= self.undoRedo[1])):
                if nextAction == self.undoRedo[1]:  self.MENU['redo'].setEnabled(False)
                else:                               self.MENU['redo'].setEnabled(True)
                self.MENU['undo'].setEnabled(True)
                self.undoRedo[2] = (self.undoRedo[2]+1)%len(TEMP['undo'])
                MAIN_PORTFOLIO.loadJSON(TEMP['undo'][nextAction])    #9ms to merely reload the data into memory
                self.profile = ''   #name of the currently selected profile. Always starts with no filter applied.
                self.metrics()
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
        self.MENU['redo'].setEnabled(False)
        self.MENU['undo'].setEnabled(True)

        TEMP['undo'][(self.undoRedo[2]+1)%len(TEMP['undo'])] = MAIN_PORTFOLIO.toJSON()

        if self.undoRedo[1] - self.undoRedo[0] <= 0 and self.undoRedo[1] != self.undoRedo[0]:
            self.undoRedo[0] = (self.undoRedo[0]+1)%len(TEMP['undo'])
        self.undoRedo[2] = (self.undoRedo[2]+1)%len(TEMP['undo'])
        self.undoRedo[1] = self.undoRedo[2]



# MISCELLANEOUS
#=============================================================
    def copyright(self):
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
SOFTWARE.''')






if __name__ == '__main__':
    print('||    AUTO-ACCOUNTANT    ||')
    loadSettings()
    global app
    app = QApplication(sys.argv + ['-platform', 'windows:darkmode=1']) #Applies windows darkmode to base application
    loadIcons() #~50ms on startup

    #Applies more stylish darkmode to the rest of the application
    import qdarkstyle
    qdarkstyle.load_stylesheet_pyside2() #~50ms on startup
    app.setStyleSheet(AAstylesheet.get_custom_qdarkstyle())
    app.setFont(QFont('Calibri', 10))

    
    w = AutoAccountant()
    w.closeEvent = w.quit #makes closing the window identical to hitting cancel
    app.exec_()
    print('||    PROGRAM  CLOSED    ||')
    saveSettings()





