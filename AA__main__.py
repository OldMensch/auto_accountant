#Default Python
import math
import threading

#In-house
from AAlib import *
from AAmarketData import market_data_thread, getMissingPrice
import AAimport
from AAmetrics import metrics 
from AAdialogs import *




class AutoAccountant(QMainWindow): # Ideally, this ought just to be the GUI interface
    # NON_INSTANCED VARIABLES
    current_undosave_index = 0 # index of the currently loaded undosave
    view = ViewState()
    PORTFOLIO = Portfolio() # Our currently loaded portfolio
    page = 0 #This indicates which page of data we're on. If we have 600 assets and 30 per page, we will have 20 pages.
    sorted = [] # List of sorted and filtered assets
    market_data = {class_code:{} for class_code in class_lib.keys()} # Used in AAmetrics to update asset market info
    UNDO = [] # Undo memento stack
    REDO = [] # Redo memento stack
    loaded_data_hash = None # Reduces performance: if our current portfolio's hash is equal to this, then we haven't modified our data at all.
    TAXES = {} # Dictionary of tax forms

    def __init__(self): # 700ms w/ 5600
        # NOTE: LAG PROFILE:::
        #  self.GUI['gridScrollArea'].setWidget(): 159 ms ALWAYS due to first draw-resizing of QScrollArea
        # self.load(): 283 ms w/ 5600, due to transactions, ~50% due to [FORMAT_METRIC]
        # self.metrics(): 80ms w/ 5600, 20ms due to auto_account(), 20ms due to reformat_all() [FORMAT_METRIC]
        # self.showMaximized(): 40ms w/ 5600 due to first draw/resizing of all widgets, 140ms due to first draw-resizing of QScrollArea
        
        super().__init__(windowIcon=icon('logo'), windowTitle='Portfolio Manager') # NOTE: 2ms ALWAYS
        
        # Changes timezone labels from 'Date' to 'Date (Your Timezone)' NOTE: 0ms ALWAYS
        metric_formatting_lib['date']['name'] = metric_formatting_lib['date']['headername'] = metric_formatting_lib['date']['name'].split('(')[0]+'('+setting('timezone')+')'

        # GUI init: NOTE: 11ms ALWAYS
        self.__init_gui__()         # NOTE: 8ms ALWAYS
        self.__init_place_gui__()   # NOTE: 2ms ALWAYS
        self.__init_taskbar__()     # NOTE: 4ms ALWAYS
        self.__init_menu__()        # NOTE: 1ms ALWAYS
        self.__init_place_menu__()  # NOTE: 0ms ALWAYS
        self.__init_bindings__()    # NOTE: 0ms ALWAYS

        # LOAD MOST RECENT SAVE - must be loaded BEFORE market data 
        # NOTE: 2ms for new, 283ms for load w/ 5300
        if setting('startWithLastSaveDir') and os.path.isfile(setting('lastSaveDir')):  self.load(setting('lastSaveDir'), suppressMetricsAndRendering=True, ignore_sure=True)
        else:                                                                           self.new(suppressMetricsAndRendering=True, ignore_sure=True)

        # NOTE: 1ms ALWAYS
        self.__init_market_data__() # Loads market data from file or internet

        # First metrics and rendering calculation.
        self.metrics() # NOTE: 80ms w/ 5600
        self.render(state=self.view.PORTFOLIO, sort=True) # NOTE: 8ms w/ 38 assets in portfolio view

        # PYINSTALLER - Closes splash screen now that the program is loaded
        # TODO TODO TODO: Uncomment this when compiling!!!
        # try:
        #     import pyi_splash
        #     pyi_splash.close()
        # except: pass   

        self.showMaximized() # NOTE: 45ms w/ 5300
        # Have to set QScrollArea widget AFTER showMaximized is called, otherwise the 140ms lag happens TWICE
        # self.GUI['gridScrollArea'].setWidget(self.GUI['gridFrame']) # NOTE: 135ms w/ 5300

        # AUTOMATIC GRID RESIZING FUNCTION NOTE: 0ms always
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

        
# INIT - MISC FUNCTIONS
#=============================================================
    def __init_bindings__(self):
        """Initializes keyboard bindings for the main program window."""
        self.wheelEvent = self._mousewheel                                          # Last/Next page
        QShortcut(QKeySequence(self.tr("Ctrl+S")), self, self.save)                 # Save
        QShortcut(QKeySequence(self.tr("Ctrl+Shift+S")), self, p(self.save, True))  # Save As
        QShortcut(QKeySequence(self.tr("Ctrl+A")), self, self._ctrl_a)              # Select all rows of data
        QShortcut(QKeySequence(self.tr("Ctrl+Z")), self, p(self.load_memento, 'undo'))  # Undo
        QShortcut(QKeySequence(self.tr("Ctrl+Y")), self, p(self.load_memento, 'redo'))  # Redo
        QShortcut(QKeySequence(self.tr("Esc")), self, self._esc)                    # Unselect, close window
        QShortcut(QKeySequence(self.tr("Del")), self, self._del)                    # Delete selection
        QShortcut(QKeySequence(self.tr("F11")), self, self._f11)                    # Fullscreen
    def __init_market_data__(self):
        self.online_event = threading.Event()
        #Now that the hard data is loaded, we need market data
        self.set_offline_mode(setting('is_offline'), True) # NOTE: This is 500ms!!!

        #We always turn on the threads for gethering market data. Even without internet, they just wait for the internet to turn on.
        self.market_data_thread = market_data_thread(self, self.PORTFOLIO, self.online_event)
        self.market_data_thread.start_threads()

    def toggle_offline_mode(self):
        self.set_offline_mode(not setting('is_offline'))
    def set_offline_mode(self, set_to_offline:bool, suppressMetricsAndRendering=False):
        """Attempts to set offline/online state. Defaults to online."""

        if set_to_offline: # Set to Offline
            if '_timestamp' in self.market_data:   # market_data -> JSON, if we have any data
                with open('OfflineMarketData.json', 'w') as file:
                    decimals_as_strings = {
                        class_code:{
                            ticker:{
                                metric:str(data) 
                                for metric,data in self.market_data[class_code][ticker].items()} 
                            for ticker in self.market_data[class_code].keys()} 
                        for class_code in class_lib.keys()}
                    decimals_as_strings['_timestamp'] = self.market_data['_timestamp']
                    json.dump(decimals_as_strings, file, indent=4)
            try: # change to offline successful
                with open('OfflineMarketData.json', 'r') as file:
                    offline_market_data = json.load(file)
                for class_code in class_lib:
                    for ticker in offline_market_data[class_code]:
                        for metric,data in offline_market_data[class_code][ticker].items():
                            try:    offline_market_data[class_code][ticker][metric] = Decimal(data)
                            except: pass
                offline_market_data['_timestamp'] = offline_market_data['_timestamp']
                self.market_data.update(offline_market_data)
                self.GUI['timestamp_indicator'].setText(f'OFFLINE MODE - Data from {self.market_data['_timestamp'][0:16]}')
                self.GUI['timestamp_indicator'].setStyleSheet(css('timestamp_indicator_offline'))
                self.online_event.clear()
            except:  # change to offline not successful, continue in online mode
                Message(self, 'Offline File Error', 'Failed to load offline market data cache. Staying in online mode.')
                return
        else:  # Set to Online
            if '_timestamp' in self.market_data:
                self.GUI['timestamp_indicator'].setText(f'Data from {self.market_data['_timestamp'][0:16]}')
            self.online_event.set()
            self.GUI['timestamp_indicator'].setStyleSheet(css('timestamp_indicator_online'))
        
        if not suppressMetricsAndRendering:
            self.market_metrics()
            self.render(sort=True)
        set_setting('is_offline', set_to_offline)
        self.offlineMode.setChecked(set_to_offline)
    

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
        file.addAction('New',               self.new)
        file.addAction('Load...',           self.load)
        file.addAction('Save',              self.save)
        file.addAction('Save As...',        p(self.save, True))
        file.addAction('Merge Portfolio',   self.merge)
        importmenu = QMenu('Import')
        file.addMenu(importmenu)
        for src in third_party_source_lib:
            importmenu.addAction(f'Import {src} History', p(self.import_3rd_party_data, source=src))
        file.addSeparator()
        file.addAction('QUIT', self.quit)

        # SETTINGS Tab
        settings = self.TASKBAR['settings'] = QMenu('Settings')

        self.offlineMode = QAction('Offline Mode', parent=settings, triggered=self.toggle_offline_mode, checkable=True, checked=setting('is_offline'))
        settings.addAction(self.offlineMode)

        # submenu - TIMEZONE
        def set_timezone(tz:str, *args, **kwargs):
            set_setting('timezone', tz)                         # Change the timezone setting itself
            for transaction in self.PORTFOLIO.transactions():   # Recalculate the formatted timestamp on all of the transactions with new timezone
                transaction.recalc_iso_date()
            metric_formatting_lib['date']['name'] = metric_formatting_lib['date']['headername'] = metric_formatting_lib['date']['name'].split('(')[0]+'('+tz+')'
            self.render()   #Only have to re-render w/o recalculating metrics, since metrics is based on the UNIX time
        timezonemenu = self.TASKBAR['timezone'] = QMenu('Timezone')
        settings.addMenu(timezonemenu)

        timezoneActionGroup = QActionGroup(timezonemenu)
        for tz in timezones:
            timezonemenu.addAction(QAction('('+tz+') '+timezones[tz][0], parent=timezonemenu, triggered=p(set_timezone, tz), actionGroup=timezoneActionGroup, checkable=True, checked=(setting('timezone') == tz)))

        def light_mode(): app.setStyleSheet('')
        def dark_mode():  app.setStyleSheet(AAstylesheet.get_custom_master_stylesheet())
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
        about.addAction('MIT License', self.copyright)
        
        # METRICS
        metrics_menu =              self.TASKBAR['metrics'] = QMenu('Metrics')
        portfolio_metrics_menu =    self.TASKBAR['metrics_portfolio'] = QMenu('Portfolio View')
        grand_ledger_metrics_menu = self.TASKBAR['metrics_grand_ledger'] = QMenu('Grand Ledger View')
        asset_metrics_menu =        self.TASKBAR['metrics_asset'] = QMenu('Asset View')
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
                header:QAction(metric_formatting_lib[header]['name'], parent=submenu, triggered=p(self._header_left_click, header), 
                               checkable=True, checked=header in setting('header_'+state)) for header in default_headers[state]
                }
            for action in self.metricactions[state].values():   submenu.addAction(action)

        # TAXES
        taxes = self.TASKBAR['taxes'] = QMenu('Taxes')
        taxes.addAction('Generate data for IRS Form 8949', self.tax_Form_8949)
        taxes.addAction('Generate data for IRS Form 1099-MISC', self.tax_Form_1099MISC)

        #'ERRORS' Tab
        ERRORS = self.TASKBAR['DEBUG'] = QMenu('Errors')
        ERRORS.addAction('Report',          self.error_report)
        ERRORS.addSeparator()
        ERRORS.addAction('Download missing price data',     self.errors_download_missing_prices)

        # Add all menus to taskbar
        taskbar.addMenu(file)
        taskbar.addMenu(metrics_menu)
        taskbar.addMenu(taxes)
        taskbar.addMenu(ERRORS)
        taskbar.addMenu(settings)
        taskbar.addMenu(about)


    def tax_Form_8949(self):
        dir = QFileDialog.getOpenFileName(self, 'Save data for IRS Form 8949', setting('lastSaveDir'), "CSV Files (*.csv)")[0]
        if dir == '':   return
        self.metrics(tax_report='8949')
        with open(dir, 'w', newline='') as file:
            file.write(self.TAXES['8949'].to_csv())
    def tax_Form_1099MISC(self):
        dir = QFileDialog.getOpenFileName(self, 'Save data for IRS Form 1099-MISC', setting('lastSaveDir'), "CSV Files (*.csv)")[0]
        if dir == '':   return
        self.metrics(tax_report='1099-MISC')
        with open(dir, 'w', newline='') as file:
            file.write(self.TAXES['1099-MISC'].to_csv())

    def error_report(self):
        # dict of {error type : # errors of that type}
        errors = {}
        missing_data_totals = {}
        for t in self.PORTFOLIO.transactions():
            if not t.ERROR: continue
            if t.ERROR_TYPE not in errors: errors[t.ERROR_TYPE] = 0
            errors[t.ERROR_TYPE] += 1
            if t.ERROR_TYPE == 'data':
                for missing_data in t.get_metric('missing'):
                    if missing_data not in missing_data_totals: missing_data_totals[missing_data] = 0
                    missing_data_totals[missing_data] += 1
        toDisplay = ''
        # No errors:
        if len(errors) == 0: toDisplay += 'No errors to report!'
        # missing data error handled independently
        if 'data' in errors:
            toDisplay += f'• {errors['data']} \'data\' errors\n'
            for error,count in missing_data_totals.items():
                toDisplay += f'        • {count} transactions missing \'{error}\'\n'
        # display all errors and their counts
        for error,count in errors.items():
            if error=='data': continue
            toDisplay += f'• {count} \'{error}\' errors\n'

        Message(self, 'Error Report', toDisplay, scrollable=True, size=0.5)
    def errors_download_missing_prices(self):
        total_attempts = 0
        total_successes = 0
        for t in self.PORTFOLIO.transactions():
            DATE = t.iso_date()
            MISSING = t.get_metric('missing')
            for part in ('loss_','fee_','gain_'):
                if part+'price' in MISSING:   
                    new_price = getMissingPrice(DATE, t.get_raw(part+'ticker'), t.get_raw(part+'class'))
                    t._data[part+'price'] = new_price
                    total_attempts += 1
                    if new_price is not None: total_successes += 1
            t.precalculate()
        if total_attempts == 0:
            Message(self, 'Fixed Missing Prices', f'No missing price data found')
        else:
            Message(self, 'Fixed Missing Prices', f'Successfully replaced {total_successes}/{total_attempts} instances of missing price data')
        self.metrics()
        self.render(sort=True)

    def import_3rd_party_data(self, wallet=None, source=None):
        # Query user to specify wallet to import into
        if wallet == None:    
            ImportationDialog(self, source, self.import_3rd_party_data, f'{source} Wallet') 
            return
        
        # Data dependent on 3rd party platform
        fileFormat = third_party_source_lib[source]['openFileFormat']
        twoFiles = 'twoFileAddendum' in third_party_source_lib[source]
        twoFileAddendums = ('','')
        if twoFiles: twoFileAddendums = third_party_source_lib[source]['twoFileAddendum']

        # Query user for file directory(ies) to import data from
        dir = QFileDialog.getOpenFileName(self, f'Import {source}{twoFileAddendums[0]} Transaction History', setting('lastSaveDir'), fileFormat)[0]
        if dir == '':   
            Message(self, 'Import Cancelled')
            return
        if twoFiles:
            dir2 = QFileDialog.getOpenFileName(self, f'Import {source}{twoFileAddendums[1]} Transaction History', setting('lastSaveDir'), fileFormat)[0]
            if dir2 == '':   
                Message(self, 'Import Cancelled')
                return

        match source:
            case 'Binance':             AAimport.binance(self, dir, wallet.name())
            case 'Coinbase':            AAimport.coinbase(self, dir, wallet.name())
            case 'Coinbase Pro':        AAimport.coinbase_pro(self, dir, wallet.name())
            case 'Etherscan':           AAimport.etherscan(self, dir, dir2, wallet.name()) # ETH history, then ERC-20 history
            case 'Gemini':              AAimport.gemini(self, dir, wallet.name())
            case 'Gemini Earn/Grow':    AAimport.gemini_earn(self, dir, wallet.name())
            case 'Yoroi':               AAimport.yoroi(self, dir, wallet.name())
            case other:                 raise Exception(f'||ERROR|| Unrecognized transaction history source, \'{source}\'.')

    def save(self, saveAs=False, *args, **kwargs):
        if saveAs or not os.path.isfile(setting('lastSaveDir')):
            dir = QFileDialog.getSaveFileName(self, 'Save Portfolio', setting('lastSaveDir'), "JSON Files (*.json)")[0]
        else:
            if not self.isUnsaved(): return # don't bother saving if file is identical
            dir = setting('lastSaveDir')
        if dir == '':
            return
        self.setWindowTitle('Portfolio Manager - ' + dir.split('/').pop())
        current_to_JSON = self.PORTFOLIO.toJSON()
        with open(dir, 'w') as file:
            json.dump(current_to_JSON, file)
        self.loaded_data_hash = hash(self.PORTFOLIO)
        if saveAs:      set_setting('lastSaveDir', dir)
    def new(self, suppressMetricsAndRendering=False, ignore_sure=False, *args, **kwargs):
        if not ignore_sure and self.isUnsaved():
            unsavedPrompt = Message(self, 'Unsaved Changes', 'Are you sure you want to create a new portfolio?\nYour changes will be lost!', closeMenuButtonTitle='Cancel')
            def continue_new():
                self.new(ignore_sure=True)
                unsavedPrompt.close()
            unsavedPrompt.add_menu_button('Create New Portfolio', continue_new, styleSheet=css('save'))
            return
        set_setting('lastSaveDir', '')
        self.PORTFOLIO.clear()
        self.setWindowTitle('Portfolio Manager')
        if not suppressMetricsAndRendering:
            self.metrics()
            self.render(state=self.view.PORTFOLIO, sort=True)
        self.loaded_data_hash = hash(self.PORTFOLIO)
        self.clear_mementos()
    def load(self, dir=None, suppressMetricsAndRendering=False, ignore_sure=False, *args, **kwargs):
        if not ignore_sure and self.isUnsaved():
            unsavedPrompt = Message(self, 'Unsaved Changes', 'Are you sure you want to load?\nYour changes will be lost!', closeMenuButtonTitle='Cancel')
            def continue_load():
                self.load(ignore_sure=True)
                unsavedPrompt.close()
            unsavedPrompt.add_menu_button('Continue Loading', continue_load, styleSheet=css('save'))
            return
        
        if dir == None: dir = QFileDialog.getOpenFileName(self, 'Load Portfolio', setting('lastSaveDir'), "JSON Files (*.json)")[0]
        if dir == '':   return
        try:    
            with open(dir, 'r') as file:
                decompile = json.load(file)    #Attempts to load the file
        except:
            Message(self, 'Error!', 'File couldn\'t be loaded. Probably corrupt or something.' )
            self.new()
            return
        self.PORTFOLIO.loadJSON(decompile)
        self.setWindowTitle('Portfolio Manager - ' + dir.split('/').pop())
        set_setting('lastSaveDir', dir)
        if not suppressMetricsAndRendering:
            self.metrics()
            self.render(state=self.view.PORTFOLIO, sort=True)
        self.loaded_data_hash = hash(self.PORTFOLIO) # NOTE: 2ms w/ 5600
        self.clear_mementos()  
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
        TO_MERGE = Portfolio()
        TO_MERGE.loadJSON(decompile)
        new_transactions = [t for t in TO_MERGE.transactions() 
                            if not self.PORTFOLIO.hasTransaction(t.get_hash())]
        for trans in new_transactions:
            self.PORTFOLIO.add_transaction(trans)
        set_setting('lastSaveDir', '') #resets the savedir. who's to say where a merged portfolio should save to? why should it be the originally loaded file, versus any recently merged ones?
        self.setWindowTitle('Portfolio Manager')
        self.create_memento(None, new_transactions) # Unlike new/load, this creates a memento, instead of resetting them
        self.metrics()
        self.render(state=self.view.PORTFOLIO, sort=True)

    def quit(self, event=None):
        if event: event.ignore() # Prevents program from closing if you hit the main window's 'X' button, instead I control whether it closes here.

        if self.isUnsaved():
            def save_and_quit():
                self.save()
                app.exit()
            unsavedPrompt = Message(self, 'Unsaved Changes', 'Are you sure you want to quit?\nYour changes will be lost!', closeMenuButtonTitle='Cancel')
            unsavedPrompt.add_menu_button('Quit', app.exit, styleSheet=css('delete'))
            unsavedPrompt.add_menu_button('Save and Quit', save_and_quit, styleSheet=css('save'))
        else:
            app.exit()

    def isUnsaved(self) -> bool:
        """True if portfolio has not been changed from originally loaded file"""
        return self.loaded_data_hash != hash(self.PORTFOLIO)


# RENDERING: WIDGET INSTANTIATION
#=============================================================
    def __init_gui__(self):
        """Creates QT widgets for all GUI elements in the main program window, including the GRID"""
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
        self.GUI['title'] = QLabel('Auto-Accountant', alignment=Qt.AlignCenter, styleSheet=css('title'))
        self.GUI['subtitle'] = QLabel('Overall Portfolio', alignment=Qt.AlignCenter, styleSheet=css('subtitle'))
        self.GUI['info_pane'] = QLabel(alignment=Qt.AlignHCenter, styleSheet=css('info_pane'))
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
        self.GUI['GRID'] = GRID(self, self.set_sort, self._header_right_click, self._row_left_click, self._row_right_click)
        #The little bar on the bottom
        self.GUI['bottomLayout'] = QHBoxLayout()
        self.GUI['bottomFrame'] = QFrame(layout=self.GUI['bottomLayout'])
        self.GUI['copyright'] = QPushButton('Copyright © 2024 Shane Evanson', clicked=self.copyright)
        self.GUI['timestamp_indicator'] = QLabel(' OFFLINE MODE ')
        self.GUI['progressBar'] = QProgressBar(fixedHeight=(self.GUI['copyright'].sizeHint().height()), styleSheet=css('progressBar'), hidden=True)

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
        self.MENU = {}

        self.MENU['new'] = QPushButton(icon=icon('new'), fixedSize=icon('size2'), iconSize=icon('size'), clicked=self.new)
        self.MENU['load'] = QPushButton(icon=icon('load'), fixedSize=icon('size2'), iconSize=icon('size'), clicked=p(self.load, None))
        self.MENU['save'] = QPushButton(icon=icon('save'), fixedSize=icon('size2'), iconSize=icon('size'), clicked=p(self.save, False))
        self.MENU['settings'] = QPushButton(icon=icon('settings'), fixedSize=icon('size2'), iconSize=icon('size'), clicked=p(Message, self, 'whoop',  'no settings menu implemented yet!'))

        self.MENU['undo'] = QPushButton(icon=icon('undo'), fixedSize=icon('size2'), iconSize=icon('size'), clicked=p(self.load_memento, 'undo'))
        self.MENU['redo'] = QPushButton(icon=icon('redo'), fixedSize=icon('size2'), iconSize=icon('size'), clicked=p(self.load_memento, 'redo'))

        def new_trans(*args, **kwargs):     TransEditor(self)
        self.MENU['new_transaction'] = QPushButton(icon=icon('new_transaction'), iconSize=icon('size'), clicked=new_trans, fixedHeight=icon('size2').height())
        self.MENU['wallets'] = QPushButton(icon=icon('wallet'), iconSize=icon('size'), clicked=p(WalletManager, self), fixedHeight=icon('size2').height())
        self.MENU['filters'] = QPushButton(icon=icon('filter'), iconSize=icon('size'), clicked=p(FilterManager, self), fixedSize=icon('size2'))

        self.MENU['DEBUG_staking_report'] = QPushButton(':DEBUG:\nReport Staking', clicked=p(DEBUGStakingReportDialog, self), fixedHeight=icon('size2').height())
        def return_report(*args, **kwargs):    Message(self, 'Efficiency Report', ttt('report'), scrollable=True, wordWrap=False, size=.3)
        self.MENU['DEBUG_ttt_report'] = QPushButton(':DEBUG:\nTTT Report', clicked=return_report, fixedHeight=icon('size2').height())
        self.MENU['DEBUG_ttt_reset'] = QPushButton(':DEBUG:\nTTT Reset', clicked=p(ttt,'reset'), fixedHeight=icon('size2').height())

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
    def _header_left_click(self, info, *args, **kwargs):
        """On header left-click: Triggers re-sort"""
        header = self.view.getHeaderID()
        
        current_headers = setting(header)
        if info in setting(header):     current_headers.remove(info)
        else:                           current_headers.insert(0, info)
        set_setting(header, current_headers)
        self.render()
    def _header_right_click(self, col, event=None):
        """On header right-click: Triggers menu popup, based on metric"""
        header = self.view.getHeaderID()
        metric = setting(header)[col]
        m = QMenu(parent=self)
        m.addAction(f'Hide {metric_formatting_lib[metric]['name']}', self.metricactions[self.view.getState()][metric].trigger)
        m.addAction(f'Filter by {metric_formatting_lib[metric]['name']}...', p(FilterEditor, self, self, new_forced=metric))
        def clearFilters():
            self.PORTFOLIO._filters = {}
            self.MENU['filters'].setStyleSheet('') #Turn off filtering indicator if deleted all filters
            self.render(sort=True)
        if len(self.PORTFOLIO.filters()) > 0:
            m.addAction(f'Clear all filters', clearFilters)
                
        m.exec(event.globalPos())
    def move_header(self, metric, other_metric):
        """Places header \'metric\' at position of other header \'other_metric\'"""
        header = self.view.getHeaderID()
        new = setting(header)
        index_to_insert_at = setting(header).index(other_metric) # must calculate this BEFORE length of setting(header) is changed
        new.remove(metric)
        new.insert(index_to_insert_at, metric)
        set_setting(header, new)
        self.render()

    # GRID row functions
    def _row_left_click(self, GRID_ROW:int, event=None):
        """Controlled by GRID:
        \n - On row left-click: Select/deselect item at index GRID_ROW
        \n - On row shift-left-click: Select all items between GRID_ROW and prev.-selected index, or reset selection to GRID_ROW
        \nThis function:
        \n - On row double-left-click: Open asset ledger, wallet ledger, or transaction editor
        """
        i = self.page*setting('itemsPerPage')+GRID_ROW
        if i + 1 > len(self.sorted):  return  #Can't select something if it doesn't exist!
        self.GUI['GRID'].set_selection()
        if self.view.isPortfolio(): 
            self.view.setAsset(self.sorted[i].ticker(), self.sorted[i].class_code())
            self.render(state=self.view.ASSET, sort=True)
        else:                               TransEditor(self, self.sorted[i])
    def _row_right_click(self, highlighted:int, selection1:int, selection2:int, event=None): # Opens up a little menu of stuff you can do to this asset/transaction
        """On row right-click: Triggers menu popup, based on row content"""
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
                def open_ledger(*args, **kwargs):
                    self.view.setAsset(item.ticker(), item.class_code())
                    self.render(state=self.view.ASSET, sort=True)
                m.addAction(f'Open {item.ticker()} Ledger', open_ledger)
                m.addAction(f'Show {item.ticker()} info/stats', p(self.asset_stats_and_info, item.ticker(), item.class_code()))
                m.addAction(f'Edit {item.ticker()}', p(AssetEditor, self, item))
                m.addSeparator()
                if item.class_code() == 'c' and item.get_metric('cmc_name') != None:
                    m.addAction(f'Open {item.ticker()} on CoinMarketCap.com', 
                                p(webbrowser.open, f'https://coinmarketcap.com/currencies/{item.get_metric('cmc_name')}/'))
                if item.class_code() == 's':
                    m.addAction(f'Open {item.ticker()} on StockAnalysis.com', 
                                p(webbrowser.open, f'https://stockanalysis.com/stocks/{item.ticker().lower()}/'))
                m.addAction(f'Open {item.ticker()} on YahooFinance.com', 
                            p(webbrowser.open, f'https://finance.yahoo.com/quote/{item.ticker()}{class_lib[item.class_code()]['yahooFinanceSuffix']}'))

                    
            else:
                trans_title = item.iso_date() + ' ' + item.type()
                m.addAction('Edit ' + trans_title, p(TransEditor, self, old_transaction=item, copy=False))
                m.addAction('Copy ' + trans_title, p(TransEditor, self, old_transaction=item, copy=True))
                m.addAction('Delete ' + trans_title, p(self.delete_selection, highlighted))
                if item.ERROR:
                    m.addSeparator()
                    m.addAction('ERROR information...', p(Message, self, 'Transaction Error!', item.ERR_MSG, scrollable=True))

        m.exec(event.globalPos())
    def delete_selection(self, GRID_ROW1:int, GRID_ROW2:int=None):
        """Deletes all items, from GRID_ROW1 to GRIDROW_2"""
        if self.view.isPortfolio(): return # Deletion CURRENTLY only applies to the transaction views

        I1 = self.page*setting('itemsPerPage')+GRID_ROW1
        if GRID_ROW2 == None:   I2 = I1
        else:                   I2 = self.page*setting('itemsPerPage')+GRID_ROW2
        if I1 > len(self.sorted)-1: return
        if I2 > len(self.sorted)-1: I2 = len(self.sorted)-1

        transactions_to_delete = self.sorted[I1:I2+1] # for memento
        for item in range(I1,I2+1):
            self.PORTFOLIO.delete_transaction(self.sorted[item])

        # Remove assets that no longer have transactions
        for a in list(self.PORTFOLIO.assets()):
            if len(a._ledger) == 0:
                self.PORTFOLIO.delete_asset(a)

        self.GUI['GRID'].set_selection()
        self.create_memento(transactions_to_delete, None, f'Delete {I2-I1+1} transactions') # Delete list of transactions
        self.metrics()
        self.render(sort=True)

# RENDERING: STATIC WIDGET LAYOUT
#=============================================================
    def __init_place_gui__(self):#Self - The main QApplication
        """Places QT widgets, for the overarching GUI"""
        #Master Frame - Contains EVERYTHING
        self.setCentralWidget(self.GUI['masterFrame']) #Makes the master frame fill the entire main window
        self.GUI['masterLayout'].setRowStretch(1, 1) # The side panel and GRID absorb vertical stretching
        self.GUI['masterLayout'].setColumnStretch(1, 1) # The GRID absorbs horizontal stretching
        self.GUI['masterLayout'].addWidget(self.GUI['menuFrame'], 0, 0, 1, 2)
        self.GUI['masterLayout'].addWidget(self.GUI['sidePanelFrame'], 1, 0)

        self.GUI['gridFrame'] = QWidget(layout=self.GUI['GRID'], contentsMargins=QMargins(0,0,0,0))
        # NOTE: gridFrame NOT placed into gridScrollArea here, because it causes 159ms extra lag on __init__
        self.GUI['gridScrollArea'] = QScrollArea(widget=self.GUI['gridFrame'], widgetResizable=True, viewportMargins=QMargins(-2, -2, -2, 0), styleSheet=css('GRID'))
        # Prevents vertical scrollbar from appearing, even by accident, or while resizing the window
        self.GUI['gridScrollArea'].setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)


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
    def __init_place_menu__(self):
        """Places QT widgets, for the Menu Bar at the top of the screen"""
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

# RENDERING: DYNAMIC WIDGETS
#=============================================================
    def render(self, state:str=None, sort:bool=False, *args, **kwargs): #NOTE: Very fast! ~6.4138ms when switching panes (portfolio/grandledger), ~0.5337ms when switching pages
        '''Re-renders: Side panel and GRID
        \n If called without any variables, only GRID is re-rendered
        \n - state: sets view to specified state
        \n - sort: re-filters & re-sorts displayed items
        '''
        # Re-render misc GUI elements when view is changed
        if state and self.view.getState() != state:
            self.page = 0 # Always return to first page when view-state triggered
            self.GUI['info'].clicked.disconnect()
            self.view.state = state
            self.update_side_panel_widgets()

        #If we're trying to render an asset that no longer exists, go back to the main portfolio instead
        if not self.view.getState() or (self.view.isAsset() and not self.PORTFOLIO.hasAsset(self.view.getAsset()[0], self.view.getAsset()[1])):   
            self.render(state=self.view.PORTFOLIO, sort=True)
            return

        # WORST OFFENDER for rendering:
        if sort:  self.filter_and_sort()     # Sorts the assets/transactions (10.9900ms for ~5300 transactions, when re-sorting in grand-ledger view).

        self.update_side_panel_stats()     # Updates lefthand side panel metrics (basically 0)
        self.update_page_buttons()  # Enables/disables page flipping buttons (0.04540 when buttons are enabled/disabled)

        # Fills in the GRID with metrics
        self.GUI['GRID'].grid_render(self.view, self.sorted, self.page) # (1.4930ms for ~5300 transactions, switching panes (portfolio/grandledger))
    
    def update_side_panel_widgets(self):
        """On view change: Updates widgets to be displayed on the lefthand side panel"""
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
            asset_to_render = self.PORTFOLIO.asset(self.view.getAsset()[0], self.view.getAsset()[1])
            
            self.GUI['title'].setText(asset_to_render.name())
            self.GUI['subtitle'].setText("Transactions for "+asset_to_render.ticker())
            
            self.GUI['info'].clicked.connect(p(self.asset_stats_and_info, asset_to_render.ticker(), asset_to_render.class_code()))
            self.GUI['info'].setToolTip('Detailed information about '+ asset_to_render.ticker())
            try: self.GUI['edit'].clicked.disconnect()
            except: pass
            self.GUI['edit'].clicked.connect(p(AssetEditor, self, asset_to_render))
            self.GUI['edit'].setToolTip('Edit '+ asset_to_render.ticker())
            self.GUI['edit'].show()
            self.GUI['grand_ledger'].hide()
            self.GUI['back'].show()
    def update_side_panel_stats(self): # Separate from 'update_side_panel_widgets', so that side panel metrics update whenever metrics change. 
        """On re-render: Updates stats to be displayed on the lefthand side panel"""
        textbox = self.GUI['info_pane']
        toDisplay = '<meta name="qrichtext" content="1" />'
        
        for metric in ('price', 'value','cost_basis','unrealized_profit_and_loss%','day%'):
            colorFormat = metric_formatting_lib[metric]['color']
            if self.view.isPortfolio() or self.view.isGrandLedger():
                if metric == 'price': continue # price doesnt exist for portfolio
                formatted_info = self.PORTFOLIO.get_formatted(metric)
            elif self.view.isAsset():
                formatted_info = self.PORTFOLIO.asset(self.view.getAsset()[0], self.view.getAsset()[1]).get_formatted(metric)
            else: raise Exception(f'Unknown viewState {self.view.getState()}')
            toDisplay += metric_formatting_lib[metric]['headername'].replace('\n',' ')+'<br>'
            
            info_format = metric_formatting_lib[metric]['format']
            if colorFormat is None:         S = css('neutral')+css('info')
            else:                           S = css('info')
            if info_format == 'percent':    ending = ' %'
            else:                           ending = ' USD'
            toDisplay += HTMLify(formatted_info.replace('%',''), S)+ending+'<br><br>'
        textbox.setText(toDisplay.removesuffix('<br><br>'))
    def update_page_buttons(self):
        """Turns page next/prev buttons on/off depending on current page"""
        maxpage = math.ceil(len(self.sorted)/setting('itemsPerPage'))-1
        if maxpage == -1: maxpage = 0
        if self.page < maxpage:     
            self.GUI['page_next'].setEnabled(True)
            self.GUI['page_next'].setStyleSheet('')
        else:                       
            self.GUI['page_next'].setEnabled(False)
            self.GUI['page_next'].setStyleSheet(css('main_menu_button_disabled'))
        if self.page > 0:           
            self.GUI['page_prev'].setEnabled(True)
            self.GUI['page_prev'].setStyleSheet('')
        else:                       
            self.GUI['page_prev'].setEnabled(False)
            self.GUI['page_prev'].setStyleSheet(css('main_menu_button_disabled'))
        self.GUI['page_number'].setText('Page ' + str(self.page+1) + ' of ' + str(maxpage+1))


    def set_sort(self, col:int): #Sets the sorting mode, then sorts and rerenders everything
        """Left-click on GRID headers."""
        metric = self.view.getHeaders()[col]
        view_state_code = self.view.state
        # Reverse sort if we're currently sorting my that column, otherwise, do normal sort by metric
        if setting(f'sort_{view_state_code}')[0] == metric:     set_setting(f'sort_{view_state_code}',[metric, not setting(f'sort_{view_state_code}')[1]])
        else:                                                   set_setting(f'sort_{view_state_code}',[metric, False])
        self.render(sort=True)
    def filter_and_sort(self): #Sorts the assets or transactions by the metric defined in settings
        '''Sorts AND FILTERS the assets or transactions by the metric defined in settings'''
        #########################
        # SETUP
        #########################
        viewstate = self.view.getState()
        info = setting('sort_'+viewstate)[0]
        reverse = setting('sort_'+viewstate)[1]
        if self.view.isPortfolio():  #Assets
            unfiltered_unsorted = set(self.PORTFOLIO.assets())
        elif self.view.isAsset():   #Transactions
            unfiltered_unsorted = set(self.PORTFOLIO.asset(self.view.getAsset()[0], self.view.getAsset()[1])._ledger.values()) #a dict of relevant transactions, this is a list of their keys.
        elif self.view.isGrandLedger(): # Grand ledger transactions
            unfiltered_unsorted = set(self.PORTFOLIO.transactions()) #a dict of ALL transactions

        
        #########################
        # FILTERING
        #########################
        blacklist = set() # list of items that don't meet criteria
        for f in self.PORTFOLIO.filters():
            METRIC, RELATION, STATE = f.metric(),f.relation(),f.state()
            # Ignore filter metrics, if the metric isn't in any column in the GRID
            if METRIC not in setting('header_'+self.view.getState()) and METRIC != 'ERROR': 
                continue

            for item in unfiltered_unsorted: # could be assets or transactions
                if METRIC == 'ERROR':    
                    if not item.ERROR: blacklist.add(item)
                    continue
                elif METRIC in ('price','quantity','value'):
                    item_state = item.get_metric(METRIC, self.view.getAsset())
                elif f.is_alpha() or METRIC == 'date': # alpha metrics - equals only
                    item_state = item.get_metric(METRIC)
                else: # numeric metrics 
                    item_state = item.get_metric(METRIC) 
                
                if item_state is None: continue # Missing/empty data not filtered out

                match RELATION:
                    case '<':   
                        if item_state >= STATE: blacklist.add(item)
                    case '!=':   
                        if item_state == STATE: blacklist.add(item)
                    case '=':   
                        if item_state != STATE: blacklist.add(item)
                    case '>':   
                        if item_state <= STATE: blacklist.add(item)
                    
        # items marked for removal removed from list
        filtered_unsorted = list(unfiltered_unsorted - blacklist)
            
        #########################
        # SORTING
        #########################
        # DEFAULT SORT
        # Assets base sort is by ticker, then class
        # Transactions base sort is by date, then by type (based on type sorting priorities)
        filtered_unsorted.sort(reverse=not reverse)     
        
        # Sorting based on the column we've selected to sort by
        def alpha_key(e):    
            toReturn = e.get_metric(info)
            if toReturn:    return toReturn.lower()
            else:           return ''
        def numeric_key(e):
            toReturn = e.get_metric(info, self.view.getAsset())
            if toReturn:    return toReturn
            else:           return (reverse-0.5)*float('inf') #Sends missing data values to the bottom of the sorted list

        if   info == 'date': pass  # We already sorted by date
        elif metric_formatting_lib[info]['format'] in ('alpha','type','desc','class'):      
            filtered_unsorted.sort(reverse=reverse, key=alpha_key)
        else:                                                       
            filtered_unsorted.sort(reverse=not reverse, key=numeric_key) 

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
        DEFAULT_FORMAT = css('neutral') + css('info')
        maxWidth = 1
        testfont = QFont('Calibri')
        testfont.setPixelSize(20)

        # NUMBER OF TRANSACTIONS, NUMBER OF ASSETS
        to_insert = self.PORTFOLIO.get_formatted('number_of_transactions')
        toDisplay += '• ' + HTMLify(to_insert, DEFAULT_FORMAT)
        to_insert = self.PORTFOLIO.get_formatted('number_of_assets')
        toDisplay += ' transactions loaded under ' + HTMLify(to_insert, DEFAULT_FORMAT) + ' assets<br>'

        # USD PER WALLET
        toDisplay += '• Total USD by wallet:<br>'
        toDisplay += '\t*TOTAL*:\t' + HTMLify(self.PORTFOLIO.get_formatted('value', charLimit=20), DEFAULT_FORMAT) + ' USD<br>'
        wallets = list(self.PORTFOLIO.get_metric('wallets'))
        def sortByUSD(w):   return self.PORTFOLIO.get_metric('wallets')[w]  #Wallets are sorted by their total USD value
        wallets.sort(reverse=True, key=sortByUSD)
        for w in wallets:    #Wallets, a list of wallets by name, and their respective net valuations
            quantity = self.PORTFOLIO.get_metric('wallets')[w]
            if not zeroish_prec(quantity):
                width = QFontMetrics(testfont).horizontalAdvance(w+':') + 2
                if width > maxWidth: maxWidth = width
                toDisplay += '\t' + w + ':\t' + format_metric(quantity, 'currency', charLimit=20, styleSheet=DEFAULT_FORMAT)+ ' USD<br>'

        # MASS INFORMATION
        for data in ('cash_flow', 'day%', 'week%', 'month%', 'unrealized_profit_and_loss', 'unrealized_profit_and_loss%'):
            textFormat, colorFormat = metric_formatting_lib[data]['format'], metric_formatting_lib[data]['color']
            if colorFormat:     S = css('info')
            else:               S = DEFAULT_FORMAT
            label = '• '+metric_formatting_lib[data]['name']+':'
            width = QFontMetrics(testfont).horizontalAdvance(label) + 2
            if width > maxWidth: maxWidth = width
            toDisplay += label + '\t\t' + HTMLify(self.PORTFOLIO.get_formatted(data, charLimit=20), S)
            if textFormat == 'percent':
                toDisplay += ' %<br>'
            else:
                toDisplay += ' USD<br>'
        
        Message(self, 'Overall Stats and Information', toDisplay, size=.75, scrollable=True, tabStopWidth=maxWidth)  
    def asset_stats_and_info(self, ticker:str, class_code:str): #A wholistic display of all relevant information to an asset 
        toDisplay = '<meta name="qrichtext" content="1" />' # VERY IMPORTANT: This makes the \t characters actually work
        asset = self.PORTFOLIO.asset(ticker, class_code)
        DEFAULT_FORMAT = css('neutral') + css('info')
        maxWidth = 1
        testfont = QFont('Calibri')
        testfont.setPixelSize(20)

        # NUMBER OF TRANSACTIONS
        toDisplay += '• ' + HTMLify(str(len(asset._ledger)), DEFAULT_FORMAT) + ' transactions loaded under ' + HTMLify(asset.ticker(), DEFAULT_FORMAT) + '<br>'
        # ASSET CLASS
        toDisplay += '• Asset Class:\t\t' + HTMLify(asset.get_formatted('class'), DEFAULT_FORMAT) + '<br>'

        # UNITS PER WALLET
        toDisplay += '• Total '+asset.ticker()+' by wallet:<br>'
        toDisplay += '\t*TOTAL*:\t' + format_metric(asset.get_metric('balance'), 'currency', charLimit=20, styleSheet=DEFAULT_FORMAT) + ' '+asset.ticker() + '\t' + format_metric(asset.get_metric('value'), 'currency', charLimit=20, styleSheet=DEFAULT_FORMAT) + 'USD<br>'
        wallets = list(asset.get_metric('wallets'))  
        def sortByUnits(w):   return asset.get_metric('wallets')[w]    #Wallets are sorted by their total # of units
        wallets.sort(reverse=True, key=sortByUnits)
        value = asset.get_metric('price') # gets asset price for this asset
        for w in wallets:
            quantity = asset.get_metric('wallets')[w] # gets quantity of tokens for this asset
            if not zeroish_prec(quantity) and value:
                width = QFontMetrics(testfont).horizontalAdvance(w+':') + 2
                if width > maxWidth: maxWidth = width
                toDisplay += '\t' + w + ':\t' + format_metric(quantity, 'currency', charLimit=20, styleSheet=DEFAULT_FORMAT) + ' '+asset.ticker() + '\t' + format_metric(quantity*value, 'currency', charLimit=20, styleSheet=DEFAULT_FORMAT) + 'USD<br>'

        # MASS INFORMATION
        for data in ('price','value', 'marketcap', 'volume24h', 'cash_flow', 'day%', 'week%', 'month%', 'portfolio%','unrealized_profit_and_loss','unrealized_profit_and_loss%'):
            textFormat, colorFormat = metric_formatting_lib[data]['format'], metric_formatting_lib[data]['color']
            if colorFormat:     S = css('info')
            else:               S = DEFAULT_FORMAT
            label = '• '+ metric_formatting_lib[data]['name']+':'
            width = QFontMetrics(testfont).horizontalAdvance(label) + 2
            if width > maxWidth: maxWidth = width
            label += '\t\t'
            if data == 'price':
                toDisplay += label + HTMLify(format_metric(asset.get_metric(data), 'currency', colorFormat, charLimit=20), S) + ' USD/'+asset.ticker() + '<br>'
            elif textFormat == 'percent':
                toDisplay += label + HTMLify(format_metric(asset.get_metric(data), 'percent', colorFormat, charLimit=20), S) + ' %<br>'
            else:
                toDisplay += label + HTMLify(format_metric(asset.get_metric(data), 'currency', colorFormat, charLimit=20), S) + ' USD<br>'

        Message(self, asset.name() + ' Stats and Information', toDisplay, size=.75, scrollable=True, tabStopWidth=maxWidth)


#METRICS
#=============================================================
    def metrics(self, tax_report:str=''): # Recalculates all dynamic metrics
        '''Calculates and renders all metrics (including market metrics) for all assets and the portfolio.'''
        metr = metrics(self.PORTFOLIO, self.TAXES, self)
        metr.recalculate_all(tax_report) #NOTE 22ms w/ 5300
        metr.reformat_all() # ~20ms w/ 5600 
    def market_metrics(self):   # Recalculates only all market-dependent metrics
        metr = metrics(self.PORTFOLIO, self.TAXES, self)
        metr.recalculate_market_dependent()
        metr.reformat_all()


#PROGRESS BAR
#=============================================================
    def hide_progress(self):                self.GUI['progressBar'].hide()
    def show_progress(self):                self.GUI['progressBar'].show()
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

# UNDO/REDO CARETAKER
#=============================================================
    def load_memento(self, undo_or_redo:str, *args, **kwargs):
        # Retrieves memento from undo or redo stack
        if undo_or_redo == 'undo':
            if len(self.UNDO) == 0: return # can't undo if there's nothing to go to 
            memento = self.UNDO.pop() # retrieve memento
            self.REDO.append(memento) # add memento to 'redo' stack
        elif undo_or_redo == 'redo':
            if len(self.REDO) == 0: return # can't redo if there's nothing to go to 
            memento = self.REDO.pop() # retrieve memento
            self.UNDO.append(memento) # add memento to 'undo' stack
        else: Exception(f'||ERROR|| Unknown undo/redo setting, \'{undo_or_redo}\'. Must specify \'undo\' or \'redo\'.')

        # Converts before/after state into to_add/to_delete. Undo and redo are opposite of eachother
        if undo_or_redo == 'undo':
            to_add,to_delete,message = memento[0],memento[1],memento[2]
        else:
            to_delete,to_add,message = memento[0],memento[1],memento[2]
        
        if undo_or_redo == "undo":  print(f'||MEMENTO|| UN-did: \"{message}\"')
        else:                       print(f'||MEMENTO|| RE-did: \"{message}\"')
        
        # Gets the type of object we're dealing with
        if to_add is not None:  obj_type = type(to_add)
        else:                   obj_type = type(to_delete)

        # Intuitive booleans
        is_creation, is_deletion, is_modification = False,False,False
        if to_delete == None:   is_creation = True # undo/redo only creates smthg
        elif to_add == None:    is_deletion = True # undo/redo only creates smthg
        else:                   is_modification = True # undo/redo only creates smthg

        # DETERMINE ORIGINATOR: (the type of object created/modified/deleted)
        # ASSET (modification ONLY)
        if obj_type == Asset:
            if is_modification:
                self.PORTFOLIO.delete_asset(to_delete)
                self.PORTFOLIO.add_asset(to_add)
            else: raise Exception(f'||ERROR|| Mementos for creation/deletion of assets unsupported')
            self.update_side_panel_widgets() # Name change affects side panel
            # name/description change doesn't affect metrics
        # WALLET (creation/deletion/modification)
        elif obj_type == Wallet:
            if is_creation:
                self.PORTFOLIO.add_wallet(to_add)
            elif is_deletion:
                self.PORTFOLIO.delete_wallet(to_delete)
            elif is_modification:
                # Names different: have to rename all transactions
                if to_delete.name() != to_add.name():
                    # Automatically adds/deletes wallets for us
                    self.PORTFOLIO.rename_wallet(to_delete.name(), to_add.name())
                    self.metrics()
                else:
                    self.PORTFOLIO.delete_wallet(to_delete)
                    self.PORTFOLIO.add_wallet(to_add)
        # TRANSACTION (creation/deletion/modification)
        elif obj_type == Transaction:
            if is_creation:
                self.PORTFOLIO.add_transaction(to_add)
            elif is_deletion:
                self.PORTFOLIO.delete_transaction(to_delete)
            elif is_modification:
                self.PORTFOLIO.delete_transaction(to_delete)
                self.PORTFOLIO.add_transaction(to_add)
            self.metrics()
        # TRANSACTION - MULTIPLE AT ONCE (creation/deletion ONLY)
        elif obj_type == list:
            if is_creation:
                for transaction in to_add:
                    self.PORTFOLIO.add_transaction(transaction)
            elif is_deletion:
                for transaction in to_delete:
                    self.PORTFOLIO.delete_transaction(transaction)
            else: raise Exception(f'||ERROR|| Mementos for modification of multiple transactions unsupported')
            self.metrics()
        # UNKNOWN MEMENTO TYPE
        else: raise TypeError(f'||ERROR|| Invalid memento type \'{obj_type}\'')
        
        self.render(sort=True) # Always always (always!) need to re-render

        self.memento_vfx() # Adds/removes star, undo/redo button functionality
    def create_memento(self, obj_before:None|Asset|Wallet|Transaction|List[Transaction], obj_after:None|Asset|Wallet|Transaction|List[Transaction], message:str):
        '''Save copy of object before/after it was changed.
        \nSupports saving: Asset, Wallet, Transaction, or a list of Transactions
        \nMust specify message, indicating what changed during this memento.
        '''
        #######################################
        #NOTE: Memento savepoints are triggered when:
        # Loading a portfolio, creating a new portfolio, or merging portfolios causes an undosave
            # However, these major operations also delete all prior undosaves!
        # Importing transaction histories
        # ONLY Modifying an: Asset
        # Modifying/Creating/Deleting an: Transaction, Wallet
        # Creating/Deleting: Imported transactions (multiple at once)
        #######################################

        # DETERMINE ORIGINATOR: (the type of object created/modified/deleted)

        # CHECK - before/after cannot BOTH be "None" type
        if obj_before==obj_after==None:
            raise TypeError(f'||ERROR|| Invalid memento type: Memento before/after cannot both be \'{type(None)}\'')
        # CHECK - before/after must be same type, unless one type is "None" (None if object created/deleted)
        if type(None) not in (type(obj_before), type(obj_after)) and type(obj_before) != type(obj_after):
            raise TypeError(f'||ERROR|| Invalid memento type: Memento before/after are not the same type: \'{type(obj_before)}\' and \'{type(obj_after)}\'')
        # CHECK - type must be a supported type
        for obj in (obj_before, obj_after):
            obj_classes = [type(None),Asset,Wallet,Transaction,list]
            if type(obj) == list: # Lists invalid if: empty, or contain non-transactions
                if len(obj) == 0:
                    raise TypeError(f'||ERROR|| Invalid memento type: Empty list')
                for item in obj:
                    if type(item) != Transaction: 
                        raise TypeError(f'||ERROR|| Invalid memento type: List contains \'{type(item)}\', and should only contain Transaction objects.')
            if type(obj) not in obj_classes:
                raise TypeError(f'||ERROR|| Invalid memento type: Unsavable memento type: \'{type(obj)}\'')
        
        # Technical changes
        self.UNDO.append((obj_before, obj_after, message))
        self.REDO = [] # When a new memento is created, delete all redo history

        # Visual changes
        self.memento_vfx() # Adds/removes star, undo/redo button functionality
    def clear_mementos(self):
        """For new/load/merge operations: Clears whole memento history"""
        self.UNDO = []
        self.REDO = []
        self.memento_vfx()

    def memento_vfx(self):
        '''Puts a star in front of the window title, if the portfolio has been edited\n
        Enables/disables undo/redo buttons appropriately'''
        # Add/remove star if the portfolio has been modified
        is_same_as_local_file = not self.isUnsaved()
        has_star = self.windowTitle()[0] == '*'
        if is_same_as_local_file and has_star: # Remove star if unmodified
            self.setWindowTitle(self.windowTitle()[1:])
        elif not is_same_as_local_file and not has_star: # Add star if modified
            self.setWindowTitle('*'+self.windowTitle())

        # Change whether undo/redo buttons are visually and logically enabled
        if len(self.UNDO) == 0:
            self.MENU['undo'].setEnabled(False)
            self.MENU['undo'].setStyleSheet(css('main_menu_button_disabled'))
        else:
            self.MENU['undo'].setEnabled(True)
            self.MENU['undo'].setStyleSheet('')

        if len(self.REDO) == 0:
            self.MENU['redo'].setEnabled(False)
            self.MENU['redo'].setStyleSheet(css('main_menu_button_disabled'))
        else:
            self.MENU['redo'].setEnabled(True)
            self.MENU['redo'].setStyleSheet('')



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

    # Applies universal stylesheet
    app.setStyleSheet(AAstylesheet.get_custom_master_stylesheet())
    app.setFont(QFont('Calibri', 10))
    
    w = AutoAccountant()
    w.closeEvent = w.quit #makes closing the window identical to hitting cancel
    app.exec()
    print('||    PROGRAM  CLOSED    ||')
    saveSettings()





