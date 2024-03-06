
from AAdialog import *
from AAobjects import *

 
class Message(Dialog): #Simple text popup, can add text with colors to it
    """Simple textbox popup for displaying a message
    \ncloseMenuButtonTitle - title of the button for closing the window. Default is 'Ok', typically also 'Cancel'
    \nscrollable - set to false for brief messages, true for large messages or ones you want the user to be able to copy
    \nbig - when true, window set to 75% of the user's monitor size vertically/horizontally
    \ntabStopWidth - size of tab intentation in characters
    """
    def __init__(self, upper, title, message, closeMenuButtonTitle='Ok', scrollable=False, size=None, tabStopWidth=None, wordWrap=True, *args, **kwargs):
        super().__init__(upper, title)

        if scrollable:  self.text = self.add_scrollable_text(message, 0, 0, styleSheet=style('displayFont'), wordWrap=wordWrap)
        else:           self.text = self.add_label(message, 0, 0, styleSheet=style('displayFont'), wordWrap=wordWrap)

        if size is not None:         
            availableSpace = QGuiApplication.primaryScreen().availableGeometry()
            self.setFixedSize(availableSpace.width()*size, availableSpace.height()*size)
        
        if tabStopWidth: self.text.setTabStopDistance(tabStopWidth)


        self.add_menu_button(closeMenuButtonTitle, self.close)
        self.show()
    
    def setText(self, text): self.text.setText(text)


class AssetEditor(Dialog):    #For editing an asset's name and description ONLY. The user NEVER creates assets, the program does this automatically
    '''Opens dialog for editing assets' name/description. Asset creation/deletion is managed by the program automatically.'''
    def __init__(self, upper, asset:Asset):
        self.asset = asset

        super().__init__(upper, 'Edit ' + asset.ticker())

        # FAKE entry box for displaying the ticker
        self.add_label('Ticker',0,0)
        self.ENTRY_ticker =     self.add_entry(self.asset.ticker(),1,0,maxLength=24,)
        self.ENTRY_ticker.setReadOnly(True)

        # Entry box to write the name
        self.add_label('Name',0,1)
        self.ENTRY_name =       self.add_entry(self.asset.name(),1,1,maxLength=24)

        # FAKE entry box for displaying the asset class
        self.add_label('Class',0,2)
        self.ENTRY_class =     self.add_entry(assetclasslib[self.asset.assetClass()]['name'],1,2,maxLength=24,)
        self.ENTRY_class.setReadOnly(True)

        # Entry box to write a description
        self.add_label('Description',0,3)
        self.ENTRY_desc =       self.add_entry('',1,3, format='description')
        if asset:               self.ENTRY_desc.set(self.asset.desc())

        self.add_menu_button('Cancel', self.close)
        self.add_menu_button('Save', self.save, styleSheet=style('save'))

        self.show()

    def save(self):
        NAME = self.ENTRY_name.entry()
        DESC = self.ENTRY_desc.entry()

        #Name isn't an empty string?
        if NAME == '':
            self.display_error('[ERROR] Must enter a name')
            return

        #ASSET SAVING AND OVERWRITING
        #==============================
        self.asset._name = NAME # Set existing asset name to saved name
        self.asset._description = DESC # Set existing asset description to saved description

        self.upper.render(sort=True)
        self.upper.undo_save()
        self.close()

class TransEditor(Dialog):    #The most important, and most complex editor. For editing transactions' date, type, wallet, second wallet, tokens, price, usd, and description.
    """Opens dialog for creating/editing transactions"""
    def __init__(self, upper, transaction:Transaction=None, copy=False, *args, **kwargs):
        if not transaction or copy:     self.t = None
        else:                           self.t = transaction

        # DIALOGUE INITIALIZATION
        if not transaction:     super().__init__(upper, 'Create Transaction')
        elif copy:              super().__init__(upper, 'Edit Copied Transaction')
        else:                   super().__init__(upper, 'Edit Transaction')

        self.ENTRIES = {}

        # LABELS AND ENTRY BOXES - all containing their default inputs
        self.add_label('', 0,0, rowspan=3)  #Empty label for decor purposes only
        self.add_label('Date (' + setting('timezone') + ')', 1,0,columnspan=2)
        self.ENTRIES['date'] = self.add_entry(str(datetime.now()).split('.')[0], 1, 1, columnspan=2, format='date')
        self.add_label('Type',3,0)
        self.ENTRIES['type'] =  self.add_dropdown_list({pretty_trans[id]:id for id in pretty_trans}, 3, 1, default=' -TYPE- ', selectCommand=self.update_entry_interactability)
        self.add_label('Wallet',4,0)
        self.ENTRIES['wallet']= self.add_dropdown_list({w.name():w for w in MAIN_PORTFOLIO.wallets()}, 4, 1, default=' -WALLET- ')
        self.add_label('Asset Class',1,2)
        all_classes_dict = {assetclasslib[c]['name']:c for c in assetclasslib}
        self.ENTRIES['loss_class'] = self.add_dropdown_list(all_classes_dict, 1, 3, current='f')
        self.ENTRIES['fee_class'] =  self.add_dropdown_list(all_classes_dict, 1, 4, default='-NO FEE-')
        self.ENTRIES['gain_class'] = self.add_dropdown_list(all_classes_dict, 1, 5, current='f')
        self.add_label('Ticker',2,2)
        self.ENTRIES['loss_asset'] = self.add_entry('USD', 2, 3, maxLength=24)
        self.ENTRIES['fee_asset'] =  self.add_entry('USD', 2, 4, maxLength=24)
        self.ENTRIES['gain_asset'] = self.add_entry('USD', 2, 5, maxLength=24)
        self.add_label('Quantity',3,2)
        self.ENTRIES['loss_quantity'] = self.add_entry('', 3, 3, format='pos_float')
        self.ENTRIES['fee_quantity'] =  self.add_entry('', 3, 4, format='pos_float')
        self.ENTRIES['gain_quantity'] = self.add_entry('', 3, 5, format='pos_float')
        self.add_label('Price (USD)',4,2)
        self.ENTRIES['loss_price'] = self.add_entry('', 4, 3, format='pos_float')
        self.ENTRIES['fee_price'] =  self.add_entry('', 4, 4, format='pos_float')
        self.ENTRIES['gain_price'] = self.add_entry('', 4, 5, format='pos_float')
        self.add_label('Loss',0,3)
        self.add_label('Fee',0,4)
        self.add_label('Gain',0,5)
        self.add_label('Desc.',0,6)
        self.ENTRIES['description'] = self.add_entry('', 1, 6, columnspan=4, format='description')

        # ENTRY BOX DATA - When editing, puts existing data in entry boxes
        if transaction:
            for data in valid_transaction_data_lib[transaction.type()]:
                tdata = transaction.get_raw(data) # raw data from the JSON
                if tdata == None:    continue       #Ignores missing data. Usually data is omitted to save space in memory, but not always
                
                #Update entry box with known data.
                if data == 'date':
                    self.ENTRIES[data].set(unix_to_local_timezone(tdata))
                elif data[-6:] == '_asset': # the asset, which for transactions, is stored as the tickerclass combo variable: gotta separate that
                    a = MAIN_PORTFOLIO.asset(tdata)
                    self.ENTRIES[data].set(a.ticker())                      #Set asset ticker entry to ticker
                    self.ENTRIES[data[:-6]+'_class'].set(a.assetClass())    #Set asset class dropdown to class
                elif data == 'wallet':
                    self.ENTRIES[data].set(MAIN_PORTFOLIO.wallet(tdata))
                else:
                    self.ENTRIES[data].set(str(tdata))

        # Traced, automatically fill in gain/loss price, for purchases, sales, and trades
        self.ENTRIES['loss_quantity'].textChanged.connect(self.auto_purchase_sale_price)
        self.ENTRIES['gain_quantity'].textChanged.connect(self.auto_purchase_sale_price)
        self.ENTRIES['loss_price'].textChanged.connect(self.auto_purchase_sale_price)

        #Menu buttons
        self.add_menu_button('Cancel', self.close)
        self.add_menu_button('Save', self.save, styleSheet=style('save'))
        if transaction and not copy: self.add_menu_button('Delete', self.delete, styleSheet=style('delete'))

        self.update_entry_interactability(self.ENTRIES['type'].entry())

        self.auto_purchase_sale_price() # Initializes the autoprice boxes with something
        self.show()
    
    def auto_purchase_sale_price(self):
        '''Updates visual-only price information where entering the price directly is not neccessary'''
        try:
            TYPE = self.ENTRIES['type'].entry()
            LQ = Decimal(self.ENTRIES['loss_quantity'].entry())
            GQ = Decimal(self.ENTRIES['gain_quantity'].entry())
            match TYPE:
                case 'purchase':
                    self.ENTRIES['gain_price'].set(str(LQ/GQ))
                    self.ENTRIES['gain_price'].setCursorPosition(0)
                case 'sale':
                    self.ENTRIES['loss_price'].set(str(GQ/LQ))
                    self.ENTRIES['loss_price'].setCursorPosition(0)
                case 'trade':
                    LP = Decimal(self.ENTRIES['loss_price'].entry())
                    self.ENTRIES['gain_price'].set(str(LQ*LP/GQ))
                    self.ENTRIES['gain_price'].setCursorPosition(0)
        except: return

    def update_entry_interactability(self, TYPE):
        '''Appropriately sets the color and functionality of all entry boxes/labels, based on transaction type'''
        #COLOR CHANGES
        if TYPE == None:    self.ENTRIES['type'].setStyleSheet(style('entry'))
        else:               self.ENTRIES['type'].setStyleSheet(style('entry')+style(TYPE+'text'))
        
        #ENABLING AND DISABLING
        if TYPE == None: # No type is selected: disable all other entry boxes
            for entry in self.ENTRIES:
                if entry != 'type': self.ENTRIES[entry].setReadOnly(True)
        else: # Set functionality based on whether entry box is warranted for transaction type
            for entry in self.ENTRIES:
                if entry == 'type': continue
                elif entry[-6:] == '_class':   
                    if entry[:-6]+'_asset' in valid_transaction_data_lib[TYPE]: self.ENTRIES[entry].setReadOnly(False) #Enable class selection only if asset selection possible
                    else: self.ENTRIES[entry].setReadOnly(True)
                elif entry in valid_transaction_data_lib[TYPE]:   self.ENTRIES[entry].setReadOnly(False)
                else:                                           self.ENTRIES[entry].setReadOnly(True)
            if TYPE == 'purchase':  
                self.ENTRIES['loss_class'].set('f')
                self.ENTRIES['fee_class'].set('f')

                self.ENTRIES['loss_asset'].set('USD')
                self.ENTRIES['fee_asset'].set('USD')
            elif TYPE == 'sale':    
                self.ENTRIES['gain_class'].set('f')
                self.ENTRIES['fee_class'].set('f')

                self.ENTRIES['gain_asset'].set('USD')
                self.ENTRIES['fee_asset'].set('USD')
            elif TYPE == 'purchase_crypto_fee':    
                self.ENTRIES['fee_class'].set('c')

    def delete(self):
        MAIN_PORTFOLIO.delete_transaction(self.t)  #deletes the transaction

        # Remove assets that no longer have transactions
        for a in list(MAIN_PORTFOLIO.assets()):
            if len(a._ledger) == 0:
                print("deleted asset",a)
                MAIN_PORTFOLIO.delete_asset(a)

        self.upper.undo_save()          #creates a savepoint after deleting this
        self.upper.metrics()            #recalculates metrics for this asset w/o this transaction
        self.upper.render(sort=True)    #re-renders the main portfolio w/o this transaction
        self.close()

    def save(self):
        ################################
        # CHECKS 1
        ################################
        # Asset type selected
        if not self.ENTRIES['type'].entry():
            self.display_error('[ERROR] Must select transaction type!')
            return
        # Wallet selected
        if not self.ENTRIES['wallet'].entry():
            self.display_error('[ERROR] Must select wallet!')
            return

        ################################
        #DATA CULLING AND CONVERSION
        ################################
        TO_SAVE = {}
        for entry in self.ENTRIES:
            data = self.ENTRIES[entry].entry()
            if entry[-6:] == '_asset':  # Asset and class are one variable: we merge them here
                try:    TO_SAVE[entry] = Asset.calc_join_tickerclass(None, data.upper(), self.ENTRIES[entry[:-6]+'_class'].entry())
                except: TO_SAVE[entry] = None
            elif entry == 'wallet':     TO_SAVE['wallet'] = data.name() # wallet is an actual wallet object here, we only save the name
            else:                       TO_SAVE[entry] = data

        # Cull unneccessary data according to valid_transaction_data_lib
        TYPE = TO_SAVE['type']
        for data in list(TO_SAVE.keys()):
            if data not in valid_transaction_data_lib[TYPE]:
                TO_SAVE[data] = None # Invalid data is set to None

        # Cull fee data if 'no fee' was selected
        if self.ENTRIES['fee_class'].entry() == None:
            TO_SAVE['fee_asset'] =    None
            TO_SAVE['fee_quantity'] = None
            TO_SAVE['fee_price'] =    None

        # Short quick-access variables
        LA,LQ,LP = TO_SAVE['loss_asset'],TO_SAVE['loss_quantity'],TO_SAVE['loss_price']
        FA,FQ,FP = TO_SAVE['fee_asset'], TO_SAVE['fee_quantity'], TO_SAVE['fee_price']
        GA,GQ,GP = TO_SAVE['gain_asset'],TO_SAVE['gain_quantity'],TO_SAVE['gain_price']

        ################################
        # CHECKS 2
        ################################
        error = None

        # CONVERT DATE TO VALID UNIX CODE
        #valid datetime format? - NOTE: This also converts the date to unix time
        try:        TO_SAVE['date'] = timezone_to_unix(TO_SAVE['date'])
        except:     error = 'Invalid date!'

        valids = valid_transaction_data_lib[TYPE]

        ######################################################
        # NOTE: Currently, checking for missing price input is ignored
        # We allow the user to automatically get price data from YahooFinance, if they don't know it
        ######################################################

        # Valid loss?
        if 'loss_quantity' in valids and zeroish(LQ):                     error = 'Loss quantity must be non-zero.'
        #if 'loss_price' in valids and    zeroish(LP):                     error = 'Loss price must be non-zero.' # NOTE: See above
        # Valid fee?
        if FA: #Fee asset will be 'USDzf' for purchases and sales, until that data removed later on.
            if        'fee_asset' in valids  and   not MAIN_PORTFOLIO.hasAsset(FA): error = 'Fee asset does not exist in portfolio.'
            if FQ and 'fee_quantity' in valids and zeroish(FQ):                     error = 'Fee quantity must be non-zero.'
            #if FP and 'fee_price' in valids and    zeroish(FP):                     error = 'Fee price must be non-zero.'
        # Valid gain?
        if 'gain_quantity' in valids and zeroish(GQ):                     error = 'Gain quantity must be non-zero.'
        #if 'gain_price' in valids and    zeroish(GP):                     error = 'Gain price must be non-zero.' # NOTE: See above

        # If loss/fee asset identical, or fee/gain asset identical, then the loss/fee or fee/gain price MUST be identical
        if 'loss_price' in valids and FA and LA==FA and not appxEq(LP,FP): error = 'If the loss and fee assets are the same, their price must be the same.'
        if 'gain_price' in valids and FA and GA==FA and not appxEq(GP,FP): error = 'If the fee and gain assets are the same, their price must be the same.'

        # The loss and gain assets can't be identical, that's retarted. That means you would have sold something to buy itself... huh?
        if 'loss_asset' in valids and 'gain_asset' in valids and LA==GA:    error = 'Loss and Gain asset cannot be the same... right?'


        if error:
            self.display_error('[ERROR] ' + error)
            return


        # TRANSACTION SAVING AND OVERWRITING
        #==============================
        #Creates the new transaction or overwrites the old one
        NEWHASH = Transaction.calc_hash(None, TO_SAVE)
        if self.t:      OLDHASH = self.t.get_hash()
        else:           OLDHASH = None

        # FINAL CHECK - transaction will be unique?
        #transaction already exists if: 
        #   hash already in transactions - and we're not just saving an unmodified transaction over itself!
        has_hash = MAIN_PORTFOLIO.hasTransaction(NEWHASH)
        if has_hash and not (self.t and NEWHASH == OLDHASH):
            self.display_error('[ERROR] This is too similar to an existing transaction!')
            return

        # ACTUALLY SAVING THE TRANSACTION
        MAIN_PORTFOLIO.add_transaction(Transaction(MAIN_PORTFOLIO, TO_SAVE))           # Add the new transaction, or overwrite the old
        if OLDHASH != None and NEWHASH != OLDHASH:
            MAIN_PORTFOLIO.delete_transaction(self.t)      # Delete the old transaction if it's hash will have changed
        
        # Remove assets that no longer have transactions
        for a in list(MAIN_PORTFOLIO.assets()):
            if len(a._ledger) == 0:
                MAIN_PORTFOLIO.delete_asset(a)


        self.upper.undo_save()
        self.upper.metrics()
        self.upper.render(sort=True)
        self.close()

class WalletManager(Dialog): #For selecting wallets to edit
    '''Opens dialog with list of current wallets to edit, and a button for creating new wallets'''
    def __init__(self, upper, *args, **kwargs):
        super().__init__(upper, 'Manage Wallets')
        self.wallet_list = self.add_list_entry(None, 0, 0, selectCommand=self.edit_wallet, sortOptions=True)
        self.add_menu_button('Ok', self.close)
        self.add_menu_button('+ Wallet', self.new_wallet, styleSheet=style('new'))
        self.refresh_wallets()
        self.show()
    
    def new_wallet(self): # Opens dialog to create new wallet
        WalletEditor(self)

    def edit_wallet(self, wallet_name): # Opens dialog to edit existing wallet
        WalletEditor(self, wallet_name)

    def refresh_wallets(self):
        self.wallet_list.update_dict({wallet.name():wallet for wallet in MAIN_PORTFOLIO.wallets()})
        
class WalletEditor(Dialog): #For creating/editing Wallets
    """Opens dialog for creating/editing wallets"""
    def __init__(self, walletManager, wallet_to_edit:Wallet=None):
        self.wallet_to_edit = wallet_to_edit
        if wallet_to_edit == None: #New wallet
            super().__init__(walletManager, 'Create Wallet')
        else: # Edit existing wallet
            super().__init__(walletManager, 'Edit '+ wallet_to_edit.name() +' Wallet')
        # Name
        self.add_label('Name',0,0)
        self.ENTRY_name = self.add_entry('', 1, 0, maxLength=24)
        if self.wallet_to_edit: self.ENTRY_name.set(wallet_to_edit.name())

        # Description
        self.add_label('Description',0,1)
        self.ENTRY_desc = self.add_entry('', 1, 1, format='description')
        if self.wallet_to_edit: self.ENTRY_desc.set(wallet_to_edit.desc())

        self.add_menu_button('Cancel', self.close)
        self.add_menu_button('Save', self.save, styleSheet=style('save'))
        if wallet_to_edit != None:    self.add_menu_button('Delete', self.delete, styleSheet=style('delete'))
        self.show()

    def delete(self):
        # Only possible when editing an existing wallet
        # CHECK - Make sure this wallet has no transactions under it
        for t in MAIN_PORTFOLIO.transactions():
            if t.wallet() == self.wallet_to_edit.name():   #is the wallet you're deleting used anywhere in the portfolio?
                self.display_error('[ERROR] You cannot delete this wallet, as it is used by existing transactions.') # If so, you can't delete it. 
                return

        MAIN_PORTFOLIO.delete_wallet(self.wallet_to_edit)  #destroy the old wallet
        #Don't need to recalculate metrics or rerender AA, since you can only delete wallets if they're not in use
        self.upper.refresh_wallets()
        self.upper.upper.undo_save()
        self.close()

    def save(self):
        NAME = self.ENTRY_name.entry()
        DESC = self.ENTRY_desc.entry()

        new_wallet = Wallet(NAME, DESC)

        # CHECKS
        #==============================
        #new ticker will be unique?
        if MAIN_PORTFOLIO.hasWallet(new_wallet.name()) and NAME != self.wallet_to_edit.name():
            self.display_error('[ERROR] A wallet already exists with this name!')
            return
        #Name isn't an empty string?
        if NAME == '':
            self.display_error('[ERROR] Must enter a name for this wallet')
            return

        #WALLET SAVING AND OVERWRITING
        #==============================
        MAIN_PORTFOLIO.add_wallet(new_wallet)   #Creates the new wallet, or overwrites the existing one's description

        if self.wallet_to_edit != None and self.wallet_to_edit.name() != NAME:   #WALLET RE-NAMED
            #destroy the old wallet
            MAIN_PORTFOLIO.delete_wallet(self.wallet_to_edit) 
            for t in list(MAIN_PORTFOLIO.transactions()):   #sets wallet name to the new name for all relevant transactions
                if t.wallet() == self.wallet_to_edit.name():      
                    new_trans = t.toJSON()
                    MAIN_PORTFOLIO.delete_transaction(t) #Changing the wallet name changes the transactions HASH, so we HAVE to remove and re-add it
                    new_trans['wallet'] = NAME 
                    MAIN_PORTFOLIO.add_transaction(Transaction(MAIN_PORTFOLIO, new_trans))
        
            #Only reload metrics and rerender, if we rename a wallet
            self.upper.upper.metrics()
            self.upper.upper.render(sort=True)

        self.upper.refresh_wallets()
        self.upper.upper.undo_save()
        self.close()

# Filters are in-memory only
class FilterManager(Dialog): #For selecting filter rules to edit
    '''Opens dialog with list of current filters to edit, and a button for creating new filters'''
    def __init__(self, upper, *args, **kwargs):
        super().__init__(upper, 'Manage Filters')
        self.filterlist = self.add_list_entry(None, 0, 0, selectCommand=self.edit_filter, sortOptions=True)
        self.add_menu_button('Ok', self.close)
        self.add_menu_button('+ Rule', self.new_filter, styleSheet=style('new'))
        self.refresh_filters()
        self.show()
    
    def new_filter(self): # Opens dialog to create new filter
        FilterEditor(self)

    def edit_filter(self, filter_name): # Opens dialog to edit existing filter
        FilterEditor(self, filter_name)

    def refresh_filters(self):
        self.filterlist.update_dict({filter.get_rule_name():filter for filter in MAIN_PORTFOLIO.filters()})
        
class FilterEditor(Dialog): #For creating/editing filters
    """Opens dialog for creating/editing filters"""
    def __init__(self, filterManager, filter_to_edit:Filter=None):
        self.filter_to_edit = filter_to_edit
        if filter_to_edit == None: #New filter
            super().__init__(filterManager, 'Create Filter')
        else: # Edit existing filter
            super().__init__(filterManager, 'Edit Filter')

        # Metric
        self.add_label('Metric',0,0)
        all_filterable_metrics = set(default_headers['portfolio'] + default_headers['asset'] + default_headers['grand_ledger'])
        all_filterable_metrics.add('ERROR')
        self.DROPDOWN_metric = self.add_dropdown_list({metric_formatting_lib[metric]['name']:metric for metric in all_filterable_metrics}, 1, 0, sortOptions=True)
        self.DROPDOWN_metric.currentTextChanged.connect(self.change_metric_effect) # When metric is changed, if date, it needs a special entry box.

        # Relation
        self.add_label('Relation',0,1)
        self.DROPDOWN_relation = self.add_dropdown_list({r:r for r in ('<','=','>')}, 1, 1, current='=')

        # State
        self.add_label('State',0,2,rowspan=2)
        self.ENTRY_state = self.add_entry('', 1, 2)
        self.ENTRY_date = self.add_entry(str(datetime.now()).split('.')[0], 1, 3, format='date')
        
        # EDITING - Autofill info in when editing
        if self.filter_to_edit:
            self.DROPDOWN_metric.set(filter_to_edit.metric())
            self.DROPDOWN_metric.setReadOnly(True) # Can't change metric when editing
            self.DROPDOWN_relation.set(filter_to_edit.relation())
            if filter_to_edit.metric() == 'date':
                self.ENTRY_date.set(unix_to_local_timezone(filter_to_edit.state()))
            else:
                self.ENTRY_state.set(str(filter_to_edit.state()))

        self.change_metric_effect()
        self.add_menu_button('Cancel', self.close)
        self.add_menu_button('Save', self.save, styleSheet=style('save'))
        if filter_to_edit:    self.add_menu_button('Delete', self.delete, styleSheet=style('delete'))
        self.show()

    def change_metric_effect(self):
        """Enables date entry box when date is selected, disables other boxes when ERROR selected"""
        metric = self.DROPDOWN_metric.entry()
        isDate = metric == 'date'
        isERROR = metric == 'ERROR'

        self.ENTRY_state.setHidden(isDate)
        self.ENTRY_date.setHidden(not isDate)
        self.ENTRY_state.setDisabled(isERROR)
        self.DROPDOWN_relation.setDisabled(isERROR)
        if isERROR:
            self.ENTRY_state.setStyleSheet(style('disabledEntry'))
            self.DROPDOWN_relation.setStyleSheet(style('disabledEntry'))
        else:
            self.ENTRY_state.setStyleSheet(style('entry'))
            self.DROPDOWN_relation.setStyleSheet(style('entry'))


    def delete(self):
        # Only possible when editing an existing filter
        MAIN_PORTFOLIO.delete_filter(self.filter_to_edit)  #destroy the old filter

        if len(MAIN_PORTFOLIO.filters()) == 0: self.upper.upper.MENU['filters'].setStyleSheet(style('')) #Turn off filtering indicator
        self.upper.upper.render(sort=True) # Always re-render when filters are applied/removed
        self.upper.refresh_filters()
        self.close()

    def save(self):
        METRIC = self.DROPDOWN_metric.entry()
        RELATION = self.DROPDOWN_relation.entry()
        STATE = self.ENTRY_state.entry()
        DATE = self.ENTRY_date.entry()

        # CHECKS
        #==============================
        if METRIC == 'ERROR':
            new_filter = Filter('ERROR', '=', 'True')
        else: #Only do these checks when not ERROR
            # CONVERT DATE TO VALID UNIX CODE, SET STATE TO DATE IF RELEVANT
            # If relevant, valid datetime format? - NOTE: This also converts the date to unix time
            if METRIC == 'date':
                try:        STATE = timezone_to_unix(DATE)
                except:     
                    self.display_error('[ERROR] Invalid date!')
                    return
            #State isn't an empty string?
            if STATE == '':
                self.display_error('[ERROR] Must enter a state for this filter')
                return
            #State is a valid float, if metric is numeric?
            metric_is_numeric = metric_formatting_lib[METRIC]['format'] != 'alpha'
            if metric_is_numeric:
                try: 
                    new_filter = Filter(METRIC, RELATION, float(STATE)) # try to parse the state as float
                except:
                    self.display_error('[ERROR] State must be a parsable float')
                    return
            else:
                new_filter = Filter(METRIC, RELATION, STATE)
            # Not using a non-equals, if metric is alpha?
            if not metric_is_numeric and RELATION != '=' and METRIC != 'date':
                self.display_error('[ERROR] Relation must be \'=\' for text metrics')
                return
        # Identical filter doesn't already exist?
        if new_filter is not self.filter_to_edit and new_filter in MAIN_PORTFOLIO.filters():
            self.display_error('[ERROR] Identical filter already exists')
            return

        # SAVING
        #==============================
        MAIN_PORTFOLIO.add_filter(new_filter)   #Creates the new filter, or overwrites the existing one
        if self.filter_to_edit: MAIN_PORTFOLIO.delete_filter(self.filter_to_edit)
        
        self.upper.upper.MENU['filters'].setStyleSheet(style('main_menu_filtering'))
        self.upper.upper.render(sort=True)  # Always render and re-sort when filters are applied/removed
        self.upper.refresh_filters()
        self.close()


class ImportationDialog(Dialog): #For selecting wallets to import transactions to
    '''Opens dialog for specifying one or two wallets to which transactions will be imported, for Gemini, Gemini Earn, Coinbase, etc.'''
    def __init__(self, upper, continue_command, wallet_name):
        super().__init__(upper, 'Import to Wallet')
        self.add_label(wallet_name,0,0)
        self.wallet_to_edit_dropdown = self.add_dropdown_list({w.name():w for w in MAIN_PORTFOLIO.wallets()}, 1, 0, default=' -SELECT WALLET- ')
        self.add_menu_button('Cancel', self.close)
        self.add_menu_button('Import', p(self.complete, continue_command, wallet_name), styleSheet=style('new'))
        self.show()
    
    def complete(self, continue_command, wallet_name, *args, **kwargs):
        result = self.wallet_to_edit_dropdown.entry()
        if result == None:   
            self.display_error('[ERROR] Must select a '+wallet_name+'.')
            return
        self.close()
        continue_command(result)   #Runs the importGemini or importCoinbase, or whatever command again, but with wallet data

class DEBUGStakingReportDialog(Dialog):
    '''Opens dialog for reporting my current interest quantity of AMP/ALCX without having to do math'''
    def __init__(self, upper, *args, **kwargs):
        super().__init__(upper, 'Import to Wallet')
        self.add_label('Crypto Ticker',0,0)
        self.ENTRY_asset = self.add_entry('', 1, 0, maxLength=24)
        self.add_label('Staking Wallet',0,1)
        self.DROPDOWN_wallet = self.add_dropdown_list({w.name():w for w in MAIN_PORTFOLIO.wallets()}, 1, 1, default=' -SELECT WALLET- ')
        self.add_label('Crypto Ticker',0,2)
        self.ENTRY_quantity = self.add_entry('', 1, 2, format='pos_float')
        self.add_menu_button('Cancel', self.close)
        self.add_menu_button('Report', self.report, styleSheet=style('new'))
        self.show()

    def report(self):
        TICKER = self.ENTRY_asset.entry().upper()
        WALLET = self.DROPDOWN_wallet.entry()
        QUANTITY = self.ENTRY_quantity.entry()

        # CHECKS
        # Asset is in portfolio?
        if not MAIN_PORTFOLIO.hasAsset(TICKER+'zc'):
            self.display_error('[ERROR] Cryptocurrency \'TICKER\' not found in portfolio.')
            return
        # Selected a wallet?
        if WALLET == None:   
            self.display_error('[ERROR] Must select a staking wallet.')
            return
        # Quantity parsable as a decimal?
        try: QUANTITY = Decimal(QUANTITY)
        except:
            self.display_error('[ERROR] Failed to parse quantity as float.')
            return
        # Quantity is > 0?
        if QUANTITY <= 0:   
            self.display_error('[ERROR] Must enter a positive, non-0 quantity.')
            return

        
        # Add up all income transactions in this wallet for this asset
        total_staking_income_thus_far = Decimal(0)
        this_asset = MAIN_PORTFOLIO.asset(TICKER+'zc')
        for transaction in this_asset._ledger.values():
            if transaction.type() == 'income':
                total_staking_income_thus_far += transaction.get_metric('gain_quantity')

        # Quantity is < income thus far?
        if QUANTITY < total_staking_income_thus_far:   
            self.display_error(f'[ERROR] Staking quantity ({QUANTITY}) less than current total staking income earned ({total_staking_income_thus_far}).')
            return
        new_transaction = Transaction(MAIN_PORTFOLIO, {
                                      'date':timezone_to_unix(str(datetime.now()).split('.')[0]), 
                                      'type':'income', 
                                      'wallet':WALLET.name(), 
                                      'gain_asset': TICKER+'zc', 
                                      'gain_quantity':str(QUANTITY-total_staking_income_thus_far), 
                                      'gain_price':str(this_asset.get_metric('price')) 
                                      }
                                      )
        MAIN_PORTFOLIO.add_transaction(new_transaction)

        self.upper.undo_save()
        self.upper.metrics()
        self.upper.render(sort=True)
        self.close()
