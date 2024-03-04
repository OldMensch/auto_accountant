#In-house
from AAlib import *
from AAmarketData import market_data, getMissingPrice
import AAimport
from AAmetrics import metrics 
from AAdialogs import *


#Default Python
import math
import threading


class AutoAccountant(QMainWindow): # Ideally, this ought just to be the GUI interface
    def __init__(self):
        super().__init__()
        
        self.setWindowIcon(icon('icon'))
        self.setWindowTitle('Portfolio Manager')
        
        self.current_undosave_index = 0 # index of the currently loaded undosave
        self.view = ViewState()
        self.page = 0 #This indicates which page of data we're on. If we have 600 assets and 30 per page, we will have 20 pages.
        self.sorted = [] # List of sorted and filtered assets
        #Sets the labels for timezone based on the timezone (So you will see Date (EST) instead of just Date)
        metric_formatting_lib['date']['name'] = metric_formatting_lib['date']['headername'] = metric_formatting_lib['date']['name'].split('(')[0]+'('+setting('timezone')+')'

        self.__init_gui__() # Most GUI elements
        self.__init_taskbar__() # Taskbar dropdown menus and options
        self.__init_menu__() # GUI elements for the main menu bar (underneath the taskbar)

        # LOAD MOST RECENT SAVE
        # Only applies if the setting is active, and file exists.
        if setting('startWithLastSaveDir') and os.path.isfile(setting('lastSaveDir')):  self.load(setting('lastSaveDir'))
        else:                                                                           self.new(first=True)

        self.__init_market_data__() # Loads market data from offline file, or directly from CoinMarketCap/YahooFinance
        self.__init_bindings__() # Key/mouse bindings for the program

        # PYINSTALLER - Closes splash screen now that the program is loaded
        try: exec("""import pyi_splash\npyi_splash.close()""") # exec() is used so that VSCode ignores the "I can't find this module error"
        except: pass

        self.render(self.view.PORTFOLIO, sort=True) # Sorts and renders portfolio for the first time
        self.showMaximized() # Maximizes window

        # AUTOMATIC GRID RESIZING FUNCTION
        self.waiting_to_resize = False
        self.installEventFilter(self)


    def eventFilter(self, obj:QObject, event:QEvent, *args):
        """Automatically resizes GRID font when program is resized"""
        if event.type() == QEvent.Resize:
            self.waiting_to_resize = True
        if self.waiting_to_resize and event.type() in (QEvent.HoverEnter, QEvent.NonClientAreaMouseButtonRelease):
            self.GUI['GRID'].doResizification()
            self.waiting_to_resize = False
        return QWidget.eventFilter(self, self, event)

        
# INIT SUB-FUNCTIONS
#=============================================================
    def __init_bindings__(self):
        """Initializes keyboard bindings for the main program window."""
        self.wheelEvent = self._mousewheel                                          # Last/Next page
        QShortcut(QKeySequence(self.tr("Ctrl+S")), self, self.save)                 # Save
        QShortcut(QKeySequence(self.tr("Ctrl+Shift+S")), self, p(self.save, True))        # Save As
        QShortcut(QKeySequence(self.tr("Ctrl+A")), self, self._ctrl_a)              # Select all rows of data
        QShortcut(QKeySequence(self.tr("Ctrl+Y")), self, self._ctrl_y)              # Undo
        QShortcut(QKeySequence(self.tr("Ctrl+Z")), self, self._ctrl_z)              # Redo
        QShortcut(QKeySequence(self.tr("Esc")), self, self._esc)                    # Unselect, close window
        QShortcut(QKeySequence(self.tr("Del")), self, self._del)                    # Delete selection
        QShortcut(QKeySequence(self.tr("F11")), self, self._f11)                    # Fullscreen
    def __init_market_data__(self):
        self.online_event = threading.Event()
        #Now that the hard data is loaded, we need market data
        if setting('offlineMode'):
            #If in Offline Mode, try to load any saved offline market data. If there is an issue, goes into online mode
            try:
                with open('OfflineMarketData.json', 'r') as file:
                    data = json.load(file)
                    data['_timestamp']
                    marketdatalib.update(data)
                self.GUI['timestamp_indicator'].setText('OFFLINE MODE - Data from ' + marketdatalib['_timestamp'][0:16])
                self.GUI['timestamp_indicator'].setStyleSheet(style('timestamp_indicator_offline'))
                self.market_metrics()
            except:
                self.toggle_offline_mode()
                print('||ERROR|| Failed to load offline market data! Going online.')
                self.GUI['timestamp_indicator'].setStyleSheet(style('timestamp_indicator_online'))
        else:
            self.online_event.set()
            self.GUI['timestamp_indicator'].setStyleSheet(style('timestamp_indicator_online'))

        #We always turn on the threads for gethering market data. Even without internet, they just wait for the internet to turn on.
        self.market_data = market_data(self, MAIN_PORTFOLIO, self.online_event)
        self.market_data.start_threads()



#TASKBAR & FUNCTIONS FOR TASKBAR AND MAIN MENU
#NOTE: Tax forms have been temporarily disabled to speed up boot time until I implement a better method
#=============================================================
    def __init_taskbar__(self):
        """Creates a taskbar for the program, which contains all kinds of settings, import menus, timezones, tax stuff, etc."""
        self.TASKBAR = {}
        taskbar = self.TASKBAR['taskbar'] = QMenuBar(self)     #The big white bar across the top of the window
        self.setMenuBar(taskbar)

        # FILE Tab
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

        # SETTINGS Tab
        settings = self.TASKBAR['settings'] = QMenu('Settings')
        taskbar.addMenu(settings)

        self.offlineMode = QAction('Offline Mode', parent=settings, triggered=self.toggle_offline_mode, checkable=True, checked=setting('offlineMode'))
        settings.addAction(self.offlineMode)

        # submenu - TIMEZONE
        def set_timezone(tz:str, *args, **kwargs):
            set_setting('timezone', tz)                         # Change the timezone setting itself
            for transaction in MAIN_PORTFOLIO.transactions():   # Recalculate the displayed ISO time on all of the transactions
                transaction.calc_iso_date()
            metric_formatting_lib['date']['name'] = metric_formatting_lib['date']['headername'] = metric_formatting_lib['date']['name'].split('(')[0]+'('+tz+')'
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

        # submenu - ACCOUNTING
        accountingmenu = self.TASKBAR['accounting'] = QMenu('Accounting Method')
        settings.addMenu(accountingmenu)
        def set_accounting_method(method, *args, **kwargs):
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

        # ABOUT
        about = self.TASKBAR['about'] = QMenu('About')
        taskbar.addMenu(about)
        about.addAction('MIT License', self.copyright)
        
        # METRICS
        metrics_menu =              self.TASKBAR['metrics'] = QMenu('Metrics')
        portfolio_metrics_menu =    self.TASKBAR['metrics_portfolio'] = QMenu('Portfolio View')
        grand_ledger_metrics_menu = self.TASKBAR['metrics_grand_ledger'] = QMenu('Grand Ledger View')
        asset_metrics_menu =        self.TASKBAR['metrics_asset'] = QMenu('Asset View')
        taskbar.addMenu(metrics_menu)
        metrics_menu.addMenu(portfolio_metrics_menu)
        metrics_menu.addMenu(grand_ledger_metrics_menu)
        metrics_menu.addMenu(asset_metrics_menu)
        
        # Adds a reset and toggleable list for all metrics
        self.metricactions = {}
        def reset_header(state, *args, **kwargs): # command to reset headers to default
            set_setting('header_'+state, list(default_headers[state]))
            for metric in default_headers[state]: self.metricactions[self.view.getState()][metric].setChecked(True)
            if self.view.getState() == state: self.render() # Only re-renders if we changed the headers for the current view
        for state in ('portfolio','grand_ledger','asset',):
            submenu = self.TASKBAR['metrics_'+state]
            reset = QAction('Reset to Default Metrics', parent=submenu, triggered=p(reset_header, state))
            submenu.addAction(reset)
            submenu.addSeparator()
            self.metricactions[state] = {
                header:QAction(metric_formatting_lib[header]['name'], parent=submenu, triggered=p(self.toggle_header, header), 
                               checkable=True, checked=header in setting('header_'+state)) for header in default_headers[state]
                }
            for action in self.metricactions[state].values():   submenu.addAction(action)

        # TAXES
        taxes = self.TASKBAR['taxes'] = QMenu('Taxes')
        taskbar.addMenu(taxes)
        taxes.addAction('Generate data for IRS Form 8949', self.tax_Form_8949)
        taxes.addAction('Generate data for IRS Form 1099-MISC', self.tax_Form_1099MISC)

        #'DEBUG' Tab
        DEBUG = self.TASKBAR['DEBUG'] = QMenu('DEBUG')
        taskbar.addMenu(DEBUG)
        DEBUG.addAction('DEBUG find all missing price data',     self.DEBUG_find_all_missing_prices)
        DEBUG.addAction('DEBUG report staking interest',     self.DEBUG_report_staking_interest)
        def return_report():    Message(self, 'Efficiency Report', ttt('report'), scrollable=True)
        DEBUG.addAction('DEBUG ttt efficiency report', return_report)
        DEBUG.addAction('DEBUG ttt reset',     p(ttt, 'reset'))

    def toggle_offline_mode(self):
        """Toggles if state is unspecified, sets to state if specified"""
        if setting('offlineMode'):  #Changed from Offline to Online Mode
            self.online_event.set()
            self.GUI['timestamp_indicator'].setText('Data being downloaded...')
            self.GUI['timestamp_indicator'].setStyleSheet(style('timestamp_indicator_online'))
        else:                       #Changed to from Online to Offline Mode
            if '_timestamp' in marketdatalib:   # Saves marketdatalib for offline use, if we have any data to save
                with open('OfflineMarketData.json', 'w') as file:
                    json.dump(marketdatalib, file, indent=4, sort_keys=True)
            else:                               # If we don't have data to save, try to load old data. If that fails... we're stuck in Online Mode
                try:
                    with open('OfflineMarketData.json', 'r') as file:
                        data = json.load(file)
                        data['_timestamp']
                        marketdatalib.update(data)
                except:
                    Message(self, 'Offline File Error', 'Failed to load offline market data cache. Staying in online mode.')
            self.online_event.clear()
            self.GUI['timestamp_indicator'].setText('OFFLINE MODE - Data from ' + marketdatalib['_timestamp'][0:16])
            self.GUI['timestamp_indicator'].setStyleSheet(style('timestamp_indicator_offline'))
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
            DATE = t.iso_date()
            missing = t.get_raw('missing')
            if 'loss_price' in missing:   t._data['loss_price'] = getMissingPrice(DATE, t._data['loss_asset'])
            if 'fee_price' in missing:    t._data['fee_price'] =  getMissingPrice(DATE, t._data['fee_asset'])
            if 'gain_price' in missing:   t._data['gain_price'] = getMissingPrice(DATE, t._data['gain_asset'])
            t.recalculate()
        self.metrics()
        self.render(sort=True)
    def DEBUG_report_staking_interest(self):
        DEBUGStakingReportDialog(self)

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
        self.metrics()
        self.render(state=self.view.PORTFOLIO, sort=True)
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
        self.metrics()
        self.render(state=self.view.PORTFOLIO, sort=True)
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
        self.metrics()
        self.render(state=self.view.PORTFOLIO, sort=True)
        self.undo_save()

    def quit(self, event=None):
        if event: event.ignore() # Prevents program from closing if you hit the main window's 'X' button, instead I control whether it closes here.
        def save_and_quit():
            self.save()
            app.exit()

        if self.isUnsaved():
            unsavedPrompt = Message(self, 'Unsaved Changes', 'Are you sure you want to quit?\nYour changes will be lost!', closeMenuButtonTitle='Cancel')
            unsavedPrompt.add_menu_button('Quit', app.exit, styleSheet=style('delete'))
            unsavedPrompt.add_menu_button('Save and Quit', save_and_quit, styleSheet=style('save'))
            unsavedPrompt.show()
        else:
            app.exit()

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
        """Creates QT widgets for all GUI elements in the main program window, including the GRID"""
        #GUI CREATION
        #==============================
        self.GUI = {}

        #Contains everything
        self.GUI['masterLayout'] = QGridLayout(spacing=0)
        self.GUI['masterLayout'].setContentsMargins(0,0,0,0)
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
        self.GUI['back'] = QPushButton('Return to\nPortfolio', clicked=p(self.render, self.view.PORTFOLIO, True))
        self.GUI['grand_ledger'] = QPushButton('Open\nGrand Ledger', clicked=p(self.render, self.view.GRAND_LEDGER, True))
        self.GUI['page_number'] = QLabel('Page XXX of XXX', alignment=Qt.AlignCenter)
        self.GUI['page_next'] = QPushButton(icon=icon('arrow_down'), iconSize=icon('size'), clicked=self.page_next)
        self.GUI['page_prev'] = QPushButton(icon=icon('arrow_up'), iconSize=icon('size'),  clicked=self.page_prev)
        #contains the buttons for opening editors, info displays, etc.
        self.GUI['buttonLayout'] = QHBoxLayout()
        self.GUI['buttonFrame'] = QWidget(layout=self.GUI['buttonLayout'])
        self.GUI['info'] = QPushButton(icon=icon('info'), iconSize=icon('size'),  clicked=self.portfolio_stats_and_info)
        self.GUI['edit'] = QPushButton(icon=icon('settings'), iconSize=icon('size'))
        #contains the list of assets/transactions
        self.GUI['GRID'] = GRID(self, self.set_sort, self._header_menu, self._left_click_row, self._right_click_row)
        #The little bar on the bottom
        self.GUI['bottomLayout'] = QHBoxLayout()
        self.GUI['bottomFrame'] = QFrame(layout=self.GUI['bottomLayout'])
        self.GUI['copyright'] = QPushButton('Copyright © 2024 Shane Evanson', clicked=self.copyright)
        self.GUI['timestamp_indicator'] = QLabel(' OFFLINE MODE ')
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
        self.GUI['sidePanelLayout'].addWidget(self.GUI['grand_ledger'], 4, 0, 1, 2)
        self.GUI['sidePanelLayout'].addWidget(self.GUI['back'], 5, 0, 1, 2)
        self.GUI['sidePanelLayout'].addWidget(self.GUI['page_number'], 6, 0, 1, 2)
        self.GUI['sidePanelLayout'].addWidget(self.GUI['page_prev'], 7, 0, 1, 1)
        self.GUI['sidePanelLayout'].addWidget(self.GUI['page_next'], 7, 1, 1, 1)

        #Button Frame - inside the side panel, contains info button and edit asset button
        self.GUI['buttonLayout'].addWidget(self.GUI['info'])
        self.GUI['buttonLayout'].addStretch(1)
        self.GUI['buttonLayout'].addWidget(self.GUI['edit'])
        
        #Bottom Frame - This could be replaced by the QStatusBar widget, which may be better suited for this use
        self.GUI['bottomLayout'].addWidget(self.GUI['copyright'])
        self.GUI['bottomLayout'].addWidget(self.GUI['progressBar'])
        self.GUI['bottomLayout'].addStretch(1)
        self.GUI['bottomLayout'].addWidget(self.GUI['timestamp_indicator'])

        self.GUI['sidePanelFrame'].raise_()

        #GUI TOOLTIPS
        #==============================
        tooltips = {
            'back':                 'Return to the main portfolio',
            'page_prev':            'Go to last page',
            'page_next':            'Go to next page',
        }
        for widget in tooltips:     self.GUI[widget].setToolTip(tooltips[widget])
    def __init_menu__(self):
        """Initializes the main menu bar at the top of the window, with common-use buttons like save, load, undo, redo, filter, etc."""
        #MENU CREATION
        #==============================
        self.MENU = {}

        self.MENU['new'] = QPushButton(icon=icon('new'), fixedSize=icon('size2'), iconSize=icon('size'), clicked=self.new)
        self.MENU['load'] = QPushButton(icon=icon('load'), fixedSize=icon('size2'), iconSize=icon('size'), clicked=self.load)
        self.MENU['save'] = QPushButton(icon=icon('save'), fixedSize=icon('size2'), iconSize=icon('size'), clicked=self.save)
        self.MENU['settings'] = QPushButton(icon=icon('settings'), fixedSize=icon('size2'), iconSize=icon('size'), clicked=p(Message, self, 'whoop',  'no settings menu implemented yet!'))

        self.MENU['undo'] = QPushButton(icon=icon('undo'), fixedSize=icon('size2'), iconSize=icon('size'), clicked=self._ctrl_z)
        self.MENU['redo'] = QPushButton(icon=icon('redo'), fixedSize=icon('size2'), iconSize=icon('size'), clicked=self._ctrl_y)

        self.MENU['new_transaction'] = QPushButton('New\n  Transaction  ', clicked=p(TransEditor, self), fixedHeight=icon('size2').height())
        self.MENU['wallets'] = QPushButton('Manage\n  Wallets  ', clicked=p(WalletManager, self), fixedHeight=icon('size2').height())
        self.MENU['filters'] = QPushButton(icon=icon('filter'), clicked=p(FilterManager, self), fixedSize=icon('size2'), iconSize=icon('size'))

        self.MENU['DEBUG_staking_report'] = QPushButton('DEBUG: Report\nStaking', clicked=p(DEBUGStakingReportDialog, self), fixedHeight=icon('size2').height())
        def return_report():    Message(self, 'Efficiency Report', ttt('report'), scrollable=True, wordWrap=False, size=.3)
        self.MENU['DEBUG_ttt_report'] = QPushButton('DEBUG: TTT\nReport', clicked=return_report, fixedHeight=icon('size2').height())
        self.MENU['DEBUG_ttt_reset'] = QPushButton('DEBUG: TTT\nReset', clicked=p(ttt, 'reset'), fixedHeight=icon('size2').height())

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
        self.GUI['menuLayout'].addWidget(self.MENU['new_transaction'])
        self.GUI['menuLayout'].addWidget(self.MENU['wallets'])
        self.GUI['menuLayout'].addWidget(self.MENU['filters'])
        self.GUI['menuLayout'].addSpacing(2*setting('font_size'))
        self.GUI['menuLayout'].addWidget(self.MENU['DEBUG_staking_report'])
        self.GUI['menuLayout'].addWidget(self.MENU['DEBUG_ttt_report'])
        self.GUI['menuLayout'].addWidget(self.MENU['DEBUG_ttt_reset'])
        self.GUI['menuLayout'].addStretch(1)

        #MENU TOOLTIPS
        #==============================
        tooltips = {
            'new':              'Create a new portfolio',
            'load':             'Load an existing portfolio',
            'save':             'Save this portfolio',
            'settings':         'Settings',

            'undo':             'Undo last action',
            'redo':             'Redo last action',

            'new_transaction':  'Create a new transaction',
            'wallets':          'Manage wallets',
            'filters':          'Manage filters',
            
            'DEBUG_staking_report':  'Report current total "staking rewards":\ntrue earnings since last report are\ncalculated, and saved as an income transaction',
        }
        for widget in tooltips:     self.MENU[widget].setToolTip(tooltips[widget])

# GRID column header functions
    def _header_menu(self, col, event=None):
        header = self.view.getHeaderID()
        info = setting(header)[col]
        m = QMenu(parent=self)
        m.addAction('Hide ' + metric_formatting_lib[info]['name'], self.metricactions[self.view.getState()][info].trigger)
        m.exec(event.globalPos())
    def move_header(self, info, index):
        header = self.view.getHeaderID()
        new = setting(header)
        new.remove(info)
        new.insert(setting(header).index(index), info)
        set_setting(header, new)
        self.render()
    def toggle_header(self, info, *args, **kwargs):
        header = self.view.getHeaderID()
        
        current_headers = setting(header)
        if info in setting(header):     current_headers.remove(info)
        else:                           current_headers.insert(0, info)
        set_setting(header, current_headers)
        self.render()

# GRID row functions
    def _left_click_row(self, GRID_ROW:int, event=None):
        """Opens asset view or transaction editor, when left-clicking a GRID row the second time"""
        i = self.page*setting('itemsPerPage')+GRID_ROW
        if i + 1 > len(self.sorted):  return  #Can't select something if it doesn't exist!
        self.GUI['GRID'].set_selection()
        if self.view.isPortfolio(): 
            self.view.setAsset(self.sorted[i].tickerclass())
            self.render(state=self.view.ASSET, sort=True)
        else:                               TransEditor(self, self.sorted[i])
    def _right_click_row(self, highlighted:int, selection1:int, selection2:int, event=None): # Opens up a little menu of stuff you can do to this asset/transaction
        """Opens a little menu, when you right click on a GRID row"""
        #we've right clicked with a selection of multiple items
        m = QMenu(parent=self)
        if selection1 != selection2:
            m.addAction('Delete selection', p(self.delete_selection, selection1, selection2))
        #We've clicked a single item, or nothing at all, popup is relevant to what we right click
        else:
            i = self.page*setting('itemsPerPage')+highlighted
            if i + 1 > len(self.sorted): return  #Can't select something if it doesn't exist!
            item = self.sorted[i]
            # Portfolio mode: items are assets.
            if self.view.isPortfolio():
                ID = item.tickerclass()
                ticker = item.ticker()
                def open_ledger(*args, **kwargs):
                    self.view.setAsset(ID)
                    self.render(state=self.view.ASSET, sort=True)
                m.addAction('Open ' + ticker + ' Ledger', open_ledger)
                m.addAction('Edit ' + ticker, p(AssetEditor, self, item))
                m.addAction('Show detailed info', p(self.asset_stats_and_info, ID))
            else:
                trans_title = item.iso_date() + ' ' + item.metric_to_str('type')
                m.addAction('Edit ' + trans_title, p(TransEditor, self, item))
                m.addAction('Copy ' + trans_title, p(TransEditor, self, item, True))
                m.addAction('Delete ' + trans_title, p(self.delete_selection, highlighted))
                if item.ERROR:
                    m.addSeparator()
                    m.addAction('ERROR information...', p(Message, self, 'Transaction Error!', item.ERR_MSG, scrollable=True))

        m.exec(event.globalPos())
    def delete_selection(self, GRID_ROW1:int, GRID_ROW2:int=None):
        """Deletes the specified items on the GRID"""
        if self.view.isPortfolio(): return # Deletion CURRENTLY only applies to the transaction views

        I1 = self.page*setting('itemsPerPage')+GRID_ROW1
        if GRID_ROW2 == None:   I2 = I1
        else:                   I2 = self.page*setting('itemsPerPage')+GRID_ROW2
        if I1 > len(self.sorted)-1: return
        if I2 > len(self.sorted)-1: I2 = len(self.sorted)-1
        for item in range(I1,I2+1):
            MAIN_PORTFOLIO.delete_transaction(self.sorted[item].get_hash())

        # Remove assets that no longer have transactions
        for a in list(MAIN_PORTFOLIO.assets()):
            if len(a._ledger) == 0:
                MAIN_PORTFOLIO.delete_asset(a)

        self.GUI['GRID'].set_selection()
        self.undo_save()
        self.metrics()
        self.render(sort=True)


# PORTFOLIO RENDERING
#=============================================================
    def set_state(self, state):
        """Prepares buttons/labels in side panel for new render state"""
        self.page = 0 #We return to the first page if changing rendering states
        self.GUI['info'].clicked.disconnect()
        self.view.state = state
        
        if self.view.isPortfolio() or self.view.isGrandLedger():
            if self.view.isPortfolio():
                self.GUI['title'].setText('Portfolio View')
                self.GUI['subtitle'].setText('All assets')
                self.GUI['grand_ledger'].show()
                self.GUI['back'].hide()
            elif self.view.isGrandLedger():
                self.GUI['title'].setText('Grand Ledger')
                self.GUI['subtitle'].setText('All transactions for all assets')
                self.GUI['grand_ledger'].hide()
                self.GUI['back'].show()
            
            # Portfolio/grand ledger have same sidepanel info
            self.GUI['info'].clicked.connect(self.portfolio_stats_and_info)
            self.GUI['info'].setToolTip('Detailed information about this portfolio')
            self.GUI['edit'].hide()
        elif self.view.isAsset():
            asset_to_render = MAIN_PORTFOLIO.asset(self.view.getAsset())
            
            self.GUI['title'].setText(asset_to_render.name())
            self.GUI['subtitle'].setText("Transactions for "+asset_to_render.ticker())
            
            self.GUI['info'].clicked.connect(p(self.asset_stats_and_info, asset_to_render.tickerclass()))
            self.GUI['info'].setToolTip('Detailed information about '+ asset_to_render.ticker())
            try: self.GUI['edit'].clicked.disconnect()
            except: pass
            self.GUI['edit'].clicked.connect(p(AssetEditor, self, asset_to_render))
            self.GUI['edit'].setToolTip('Edit '+ asset_to_render.ticker())
            self.GUI['edit'].show()
            self.GUI['grand_ledger'].hide()
            self.GUI['back'].show()
        

    def render(self, state:str=None, sort:bool=False, *args, **kwargs): #NOTE: Very fast! ~6.4138ms when switching panes (portfolio/grandledger), ~0.5337ms when switching pages
        '''Re-renders: Side panel and GRID
        \nRefreshes page if called without any input.
        \nRe-sorts/filters assets/transactions when "sort" called'''
        # Re-render misc GUI elements when state is changed
        if state and self.view.getState() != state:
            self.set_state(state)

        #If we're trying to render an asset that no longer exists, go back to the main portfolio instead
        if self.view.isAsset() and not MAIN_PORTFOLIO.hasAsset(self.view.getAsset()):   
            self.render(state=self.view.PORTFOLIO, sort=True)
            return

        # WORST OFFENDOR for rendering:
        if sort:  self.sort()     # Sorts the assets/transactions (10.9900ms for ~5300 transactions, when re-sorting in grand-ledger view).

        self.update_info_pane()     # Updates lefthand side panel metrics (basically 0)
        self.update_page_buttons()  # Enables/disables page flipping buttons (0.04540 when buttons are enabled/disabled)

        # Fills in the GRID with metrics
        self.GUI['GRID'].grid_render(self.view, self.sorted, self.page) # (1.4930ms for ~5300 transactions, switching panes (portfolio/grandledger))
    
    
    def update_info_pane(self): # Adds basic summary statistics on the lefthand side panel for easy viewing
        """Updates brief summary stats to be displayed in the lefthand side panel"""
        textbox = self.GUI['info_pane']
        toDisplay = '<meta name="qrichtext" content="1" />'
        
        for info in ('price', 'value','cash_flow','day%','unrealized_profit_and_loss%'):
            if self.view.isPortfolio() or self.view.isGrandLedger():
                if info == 'price': continue # Continues on if it's the spot price: this is only relevant to asset info_panes, not the overall portfolio
                formatted_info = list(MAIN_PORTFOLIO.pretty(info))
            elif self.view.isAsset():
                formatted_info = list(MAIN_PORTFOLIO.asset(self.view.getAsset()).pretty(info))    
            toDisplay += metric_formatting_lib[info]['headername'].replace('\n',' ')+'<br>'
            
            info_format = metric_formatting_lib[info]['format']
            if formatted_info[1] == '':     S = style('neutral')+style('info')
            else:                           S = formatted_info[1]+style('info')
            if info_format == 'percent':    ending = ' %'
            else:                           ending = ' USD'
            toDisplay += HTMLify(formatted_info[0].replace('%',''), S)+ending+'<br><br>'
        textbox.setText(toDisplay.removesuffix('<br><br>'))
    def update_page_buttons(self):
        """Turns page next/prev buttons on/off depending on current page"""
        maxpage = math.ceil(len(self.sorted)/setting('itemsPerPage'))-1
        if maxpage == -1: maxpage = 0
        if self.page < maxpage:     
            self.GUI['page_next'].setEnabled(True)
            self.GUI['page_next'].setStyleSheet(style('main_menu_button_enabled'))
        else:                       
            self.GUI['page_next'].setEnabled(False)
            self.GUI['page_next'].setStyleSheet(style('main_menu_button_disabled'))
        if self.page > 0:           
            self.GUI['page_prev'].setEnabled(True)
            self.GUI['page_prev'].setStyleSheet(style('main_menu_button_enabled'))
        else:                       
            self.GUI['page_prev'].setEnabled(False)
            self.GUI['page_prev'].setStyleSheet(style('main_menu_button_disabled'))
        self.GUI['page_number'].setText('Page ' + str(self.page+1) + ' of ' + str(maxpage+1))


    def set_sort(self, col:int): #Sets the sorting mode, then sorts and rerenders everything
        if self.view.isPortfolio():
            info = setting('header_portfolio')[col]
            if setting('sort_portfolio')[0] == info:    set_setting('sort_portfolio',[info, not setting('sort_portfolio')[1]])
            else:                                   set_setting('sort_portfolio',[info, False])
        elif self.view.isAsset():
            info = setting('header_asset')[col]
            if setting('sort_asset')[0] == info:    set_setting('sort_asset',[info, not setting('sort_asset')[1]])
            else:                                   set_setting('sort_asset',[info, False])
        elif self.view.isGrandLedger():
            info = setting('header_grand_ledger')[col]
            if setting('sort_grand_ledger')[0] == info:    set_setting('sort_grand_ledger',[info, not setting('sort_grand_ledger')[1]])
            else:                                   set_setting('sort_grand_ledger',[info, False])
        self.render(sort=True)
    def sort(self): #Sorts the assets or transactions by the metric defined in settings #NOTE: 7ms at worst for ~900 transactions on one ledger
        '''Sorts AND FILTERS the assets or transactions by the metric defined in settings'''
        #########################
        # SETUP
        #########################
        viewstate = self.view.getState()
        info = setting('sort_'+viewstate)[0]
        reverse = setting('sort_'+viewstate)[1]
        if self.view.isPortfolio():  #Assets
            unfiltered_unsorted = set(MAIN_PORTFOLIO.assets())
        elif self.view.isAsset():   #Transactions
            unfiltered_unsorted = set(MAIN_PORTFOLIO.asset(self.view.getAsset())._ledger.values()) #a dict of relevant transactions, this is a list of their keys.
        elif self.view.isGrandLedger(): # Grand ledger transactions
            unfiltered_unsorted = set(MAIN_PORTFOLIO.transactions()) #a dict of ALL transactions

        
        #########################
        # FILTERING
        #########################
        blacklist = set() # list of items that don't meet criteria
        for f in MAIN_PORTFOLIO.filters():
            # Ignore filter metrics, if the metric isn't in any column in the GRID
            if (self.view.isPortfolio() and f.metric() not in setting('header_portfolio')): continue
            if (self.view.isAsset() and f.metric() not in setting('header_asset')): continue
            if (self.view.isGrandLedger() and f.metric() not in setting('header_grand_ledger')): continue

            for item in unfiltered_unsorted: # could be assets or transactions
                if f.is_alpha() and f.metric() != 'date': # text metrics like ticker and class
                    item_state = item.get_raw(f.metric())
                    if  item_state != f.state():
                        blacklist.add(item)
                else: # numeric metrics
                    # When sorting by price/quantity/value for transactions, the data is stored weird, so we need to access it specially.
                    # These metrics are not present when in the Grand Ledger view
                    if f.metric() == 'date':
                        item_state = item.get_raw('date')
                    elif f.metric() in ('price','quantity','value'):
                        item_state = item.get_metric(f.metric(), self.view.getAsset())
                    else:
                        item_state = item.get_metric(f.metric())

                    match f.relation():
                        case '<':   
                            if item_state >= f.state(): blacklist.add(item)
                        case '=':   
                            if item_state != f.state(): blacklist.add(item)
                        case '>':   
                            if item_state <= f.state(): blacklist.add(item)
                    
        # items marked for removal removed from list
        filtered_unsorted = list(unfiltered_unsorted - blacklist)
            
        #########################
        # SORTING
        #########################
        # DEFAULT SORT pre-sorting for assets/transactions
        if self.view.isPortfolio():    
            def tickerclasskey(e):  return e.tickerclass()
            filtered_unsorted.sort(key=tickerclasskey)     # Assets base sort is by tickerclass
        elif self.view.isAsset() or self.view.isGrandLedger():       
            filtered_unsorted.sort(reverse=not reverse)    # Transactions base sort is by date mostly, but other minor conditional cases (integrated into sort function)
        
        # Sorting based on the column we've selected to sort by
        def alphaKey(e):    
            toReturn = e.get_metric(info)
            if toReturn is None:    return ''
            else:                   return e.get_metric(info).lower()
        def numericKey(e):
            toReturn = e.get_metric(info)
            if toReturn is None:    return (reverse-0.5)*float('inf') #Sends missing data values to the bottom of the sorted list
            else:                   return toReturn
        def value_quantity_price(e):
            return e.get_metric(info, self.view.getAsset())

        if   info == 'date':                        pass  #This is here to ensure that the default date order is newest to oldest. This means reverse alphaetical
        elif metric_formatting_lib[info]['format'] == 'alpha':                  filtered_unsorted.sort(reverse=reverse,     key=alphaKey)
        elif self.view.isAsset() and info in ('value','quantity','price','balance'):  filtered_unsorted.sort(reverse=not reverse, key=value_quantity_price)
        else:                                                                   filtered_unsorted.sort(reverse=not reverse, key=numericKey)

        # Applies the sorted & filtered results, to be used in the rendering pipeline
        self.sorted = filtered_unsorted  

    def set_page(self, new_page:int=None):
        if new_page==None: new_page=self.page # If no page is specified, we reload the current page
        maxpage = math.ceil(len(self.sorted)/setting('itemsPerPage'))-1

        if new_page > maxpage:  new_page = maxpage
        if new_page < 0:      new_page = 0

        if new_page != self.page: # Only re-renders if we actually change the page
            self.page = new_page
            self.GUI['GRID'].set_selection() #Clears GRID selection
            self.render()
    def page_next(self):   self.set_page(self.page + 1)
    def page_prev(self):   self.set_page(self.page - 1)
    def increase_page_length(self):
        self.GUI['GRID'].update_page_length(setting('itemsPerPage')+5)
        self.render()
    def decrease_page_length(self):
        self.GUI['GRID'].update_page_length(setting('itemsPerPage')-5)
        self.render()

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
        toDisplay += '\t*TOTAL*:\t' + HTMLify(format_general(MAIN_PORTFOLIO.get_metric('value'), 'alpha', 20), DEF_INFO_STYLE) + ' USD<br>'
        wallets = list(MAIN_PORTFOLIO.get_metric('wallets'))
        def sortByUSD(w):   return MAIN_PORTFOLIO.get_metric('wallets')[w]  #Wallets are sorted by their total USD value
        wallets.sort(reverse=True, key=sortByUSD)
        for w in wallets:    #Wallets, a list of wallets by name, and their respective net valuations
            quantity = MAIN_PORTFOLIO.get_metric('wallets')[w]
            if not zeroish_prec(quantity):
                width = QFontMetrics(testfont).horizontalAdvance(w+':') + 2
                if width > maxWidth: maxWidth = width
                toDisplay += '\t' + w + ':\t' + HTMLify(format_general(quantity, 'alpha', 20), DEF_INFO_STYLE) + ' USD<br>'

        # MASS INFORMATION
        for data in ('cash_flow', 'day_change','day%', 'week%', 'month%', 'unrealized_profit_and_loss', 'unrealized_profit_and_loss%'):
            info_format = metric_formatting_lib[data]['format']
            if MAIN_PORTFOLIO.get_metric_style(data) == '':    S = DEF_INFO_STYLE
            else:                   S = MAIN_PORTFOLIO.get_metric_style(data)+style('info')
            label = '• '+metric_formatting_lib[data]['name']+':'
            width = QFontMetrics(testfont).horizontalAdvance(label) + 2
            if width > maxWidth: maxWidth = width
            label += '\t\t'
            if info_format == 'percent':
                toDisplay += label + HTMLify(format_general(MAIN_PORTFOLIO.get_metric(data)*100, 'alpha', 20), S) + ' %<br>'
            else:
                toDisplay += label + HTMLify(format_general(MAIN_PORTFOLIO.get_metric(data), 'alpha', 20), S) + ' USD<br>'
        
        Message(self, 'Overall Stats and Information', toDisplay, size=.75, scrollable=True, tabStopWidth=maxWidth)
    
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
        toDisplay += '• Asset Class:\t\t' + HTMLify(asset.metric_to_str('class'), DEF_INFO_STYLE) + '<br>'

        # UNITS PER WALLET
        toDisplay += '• Total '+asset.ticker()+' by wallet:<br>'
        toDisplay += '\t*TOTAL*:\t' + HTMLify(format_general(asset.get_raw('balance'), 'alpha', 20), DEF_INFO_STYLE) + ' '+asset.ticker() + '\t' + HTMLify(format_general(asset.get_raw('value'), 'alpha', 20), DEF_INFO_STYLE) + 'USD<br>'
        wallets = list(MAIN_PORTFOLIO.asset(a).get_raw('wallets'))  
        def sortByUnits(w):   return MAIN_PORTFOLIO.asset(a).get_raw('wallets')[w]    #Wallets are sorted by their total # of units
        wallets.sort(reverse=True, key=sortByUnits)
        value = MAIN_PORTFOLIO.asset(a).get_metric('price') # gets asset price for this asset
        for w in wallets:
            quantity = MAIN_PORTFOLIO.asset(a).get_raw('wallets')[w] # gets quantity of tokens for this asset
            if not zeroish_prec(quantity):
                width = QFontMetrics(testfont).horizontalAdvance(w+':') + 2
                if width > maxWidth: maxWidth = width
                toDisplay += '\t' + w + ':\t' + HTMLify(format_general(quantity, 'alpha', 20), DEF_INFO_STYLE) + ' '+asset.ticker() + '\t' + HTMLify(format_general(quantity*value, 'alpha', 20), DEF_INFO_STYLE) + 'USD<br>'

        # MASS INFORMATION
        for data in ('price','value', 'marketcap', 'volume24h', 'cash_flow', 'day_change', 'day%', 'week%', 'month%', 'portfolio%','unrealized_profit_and_loss','unrealized_profit_and_loss%'):
            info_format = metric_formatting_lib[data]['format']
            if asset.get_metric_style(data) == '':     S = DEF_INFO_STYLE
            else:                           S = asset.get_metric_style(data)+style('info')
            label = '• '+ metric_formatting_lib[data]['name']+':'
            width = QFontMetrics(testfont).horizontalAdvance(label) + 2
            if width > maxWidth: maxWidth = width
            label += '\t\t'
            if data == 'price':
                toDisplay += label + HTMLify(format_general(asset.get_raw(data), 'alpha', 20), S) + ' USD/'+asset.ticker() + '<br>'
            elif info_format == 'percent':
                try:    toDisplay += label + HTMLify(format_general(asset.get_metric(data)*100, 'alpha', 20), S) + ' %<br>'
                except: pass
            else:
                toDisplay += label + HTMLify(format_general(asset.get_raw(data), 'alpha', 20), S) + ' USD<br>'

        Message(self, asset.name() + ' Stats and Information', toDisplay, size=.75, scrollable=True, tabStopWidth=maxWidth)


#METRICS
#=============================================================
    def metrics(self, tax_report:str=''): # Recalculates all metrics
        '''Calculates and renders all metrics for all assets and the portfolio.'''
        metrics(MAIN_PORTFOLIO, TEMP, self).calculate_all(tax_report)
    def market_metrics(self):   # Recalculates all market-dependent metrics
        metrics(MAIN_PORTFOLIO, TEMP, self).recalculate_market_dependent()


#PROGRESS BAR - a bunch of small useful functions for controlling the progress bar
#=============================================================
    def hide_progress_bar(self):            self.GUI['progressBar'].hide()
    def show_progress_bar(self):            self.GUI['progressBar'].show()
    def set_progress_range(self, min, max): self.GUI['progressBar'].setRange(min, max)
    def set_progress(self, value):          self.GUI['progressBar'].setValue(value)
        

# UNIVERSAL BINDINGS
#=============================================================
    def _mousewheel(self, event:QWheelEvent): # Controls all scrollwheel-related events.
        scroll_up = event.angleDelta().y() > 0
        scroll_down = event.angleDelta().y() < 0
        if app.keyboardModifiers() == Qt.ControlModifier: # Scrolling with CTRL pressed scales the page
            if scroll_up:     self.decrease_page_length()
            elif scroll_down:   self.increase_page_length()
        elif app.keyboardModifiers() == Qt.ShiftModifier: # Scrolling with SHIFT pressed scrolls horizontally
            if scroll_up:     self.GUI['gridScrollArea'].horizontalScrollBar().setValue(self.GUI['gridScrollArea'].horizontalScrollBar().value() - 100)
            elif scroll_down:   self.GUI['gridScrollArea'].horizontalScrollBar().setValue(self.GUI['gridScrollArea'].horizontalScrollBar().value() + 100)
        else:                                             # Scrolling alone changes the page
            if scroll_up:     self.page_prev()
            elif scroll_down:   self.page_next()
    def _esc(self):     # De-select stuff
        if self.GUI['GRID'].selection != [None, None]:  self.GUI['GRID'].set_selection()  #If anything is selected, deselect it
        elif self.view.isPortfolio():  self.quit()        #If we're on the main page, exit the program
        else:                   #If we're looking at an asset, go back to the main page
            self.render(state=self.view.PORTFOLIO, sort=True)
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
    def load_undo_save(self, index):
        # Can't load a save that doesn't exist! Also skips if index equal to currently loaded index.
        if index < 0 or index > len(TEMP['undo'])-1 or self.current_undosave_index == index:
            return

        self.current_undosave_index = index # Updates current_undosave_index to the currently loaded index

        # Actually loads the save and refreshes all visual elements
        MAIN_PORTFOLIO.loadJSON(TEMP['undo'][index])
        self.metrics()
        self.render(sort=True)

        self.undo_redo_vfx() # Adds/removes star, updates undo/redo button functionality
    def _ctrl_z(self):      self.load_undo_save(self.current_undosave_index-1)    #Undo your last action
    def _ctrl_y(self):      self.load_undo_save(self.current_undosave_index+1)    #Redo your last action
    def undo_save(self):        #Create a savepoint which can be returned to
        '''Saves current portfolio in the memory should the user wish to undo their last modification'''
        #######################################
        #NOTE: Undo savepoints are triggered when:
        # Loading a portfolio, creating a new portfolio, or merging portfolios causes an undosave
            # However, these major operations also delete all prior undosaves!
        # Importing transaction histories
        # Modifying/Creating/Deleting an: Address, Asset, Transaction, Wallet
        #######################################

        # Technical changes
        TEMP['undo'] = TEMP['undo'][0:self.current_undosave_index+1]      # Deletes all undosaves AFTER the currently loaded one, if we went back a bit. Does nothing if we haven't undone at all.
        TEMP['undo'].append(MAIN_PORTFOLIO.toJSON())        # Adds current savedata to a new save in the list
        if len(TEMP['undo'])>setting('max_undo_saves'):     TEMP['undo'].pop(0) # Remove oldest save, if we have too many saves
        
        self.current_undosave_index = len(TEMP['undo'])-1 # Sets this to the index of the most recent save
        
        # Visual changes
        self.undo_redo_vfx()
    
    def undo_redo_vfx(self):
        '''Puts a star in front of the window title, if the portfolio has been edited\n
        Enables/disables undo/redo buttons, if there are available saves to switch to'''
        saved = not self.isUnsaved()
        has_star = self.windowTitle()[0] == '*'
        if saved and has_star: # Remove star if this undosave matches the actual save
            self.setWindowTitle(self.windowTitle()[1:])
        elif not saved and not has_star: # Add star if this undosave differs from the actual save
            self.setWindowTitle('*'+self.windowTitle())

        # Change whether undo/redo buttons are visually and logically enabled
        if self.current_undosave_index == 0:
            self.MENU['undo'].setEnabled(False)
            self.MENU['undo'].setStyleSheet(style('main_menu_button_disabled'))
        else:
            self.MENU['undo'].setEnabled(True)
            self.MENU['undo'].setStyleSheet(style('main_menu_button_enabled'))

        if self.current_undosave_index == len(TEMP['undo'])-1:
            self.MENU['redo'].setEnabled(False)
            self.MENU['redo'].setStyleSheet(style('main_menu_button_disabled'))
        else:
            self.MENU['redo'].setEnabled(True)
            self.MENU['redo'].setStyleSheet(style('main_menu_button_enabled'))



# MISCELLANEOUS
#=============================================================
    def copyright(self):
        Message(self,
        'MIT License', 

        '''Copyright (c) 2024 Shane Evanson

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
    app.exec()
    print('||    PROGRAM  CLOSED    ||')
    saveSettings()





