
from AAdialog import *
from AAobjects import *

 
class Message(Dialog): #Simple text popup, can add text with colors to it
    """Simple textbox popup for displaying a message
    \ncloseMenuButtonTitle - title of the button for closing the window. Default is 'Ok', typically also 'Cancel'
    \nscrollable - set to false for brief messages, true for large messages or ones you want the user to be able to copy
    \nbig - when true, window set to 75% of the user's monitor size vertically/horizontally
    \ntabStopWidth - size of tab intentation in characters
    """
    def __init__(self, upper, title, message='', closeMenuButtonTitle='Ok', scrollable=False, size=None, tabStopWidth=None, wordWrap=True, *args, **kwargs):
        super().__init__(upper, title)

        if message:
            if scrollable:  self.text = self.add_scrollable_text(message, 0, 0, styleSheet=style('displayFont'), wordWrap=wordWrap)
            else:           self.text = self.add_label(message, 0, 0, styleSheet=style('displayFont'), wordWrap=wordWrap)

        if size is not None:         
            availableSpace = QGuiApplication.primaryScreen().availableGeometry()
            self.setFixedSize(availableSpace.width()*size, availableSpace.height()*size)
        
        if tabStopWidth: self.text.setTabStopDistance(tabStopWidth)


        self.add_menu_button(closeMenuButtonTitle, self.close)
        self.show()


class AssetEditor(Dialog):    #For editing an asset's name and description ONLY. The user NEVER creates assets, the program does this automatically
    '''Opens dialog for editing assets' name/description. Asset creation/deletion is managed by the program automatically.'''
    def __init__(self, upper, old_asset:Asset):
        self.old_asset = old_asset

        super().__init__(upper, 'Edit ' + old_asset.ticker())

        # FAKE entry box for displaying the ticker
        self.add_label('Ticker',0,0)
        self.ENTRY_ticker =     self.add_entry(self.old_asset.ticker(),1,0,maxLength=24,)
        self.ENTRY_ticker.setReadOnly(True)

        # Entry box to write the name
        self.add_label('Name',0,1)
        self.ENTRY_name =       self.add_entry(self.old_asset.name(),1,1,maxLength=24)

        # FAKE entry box for displaying the asset class
        self.add_label('Class',0,2)
        self.ENTRY_class =     self.add_entry(class_lib[self.old_asset.class_code()]['name'],1,2,maxLength=24,)
        self.ENTRY_class.setReadOnly(True)

        # Entry box to write a description
        self.add_label('Description',0,3)
        self.ENTRY_desc =       self.add_entry('',1,3, format='description')
        if old_asset:           self.ENTRY_desc.set(self.old_asset.desc())

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
        old_asset = copy.deepcopy(self.old_asset) # copy for memento
        # we just overwrite data of current asset, then recalc static formatting
        # this preserves metrics calculations so we don't have to run that again
        self.old_asset._data['name'] = NAME
        self.old_asset._data['description'] = DESC
        self.old_asset.calc_formatting_static()
        new_asset = copy.deepcopy(self.old_asset) # copy for memento
        
        self.upper.create_memento(old_asset, new_asset, 'Modify asset') # Modified asset
        self.upper.update_side_panel_widgets()
        self.upper.render(sort=True)
        self.close()

class TransEditor(Dialog):    #The most important, and most complex editor. For editing transactions' date, type, wallet, second wallet, tokens, price, usd, and description.
    """Opens dialog for creating/editing transactions"""
    def __init__(self, upper, old_transaction:Transaction=None, copy=False, *args, **kwargs):
        # self.old_transaction is used for finally saving the transaction
        if copy:    self.old_transaction = None
        else:       self.old_transaction = old_transaction

        # DIALOGUE INITIALIZATION
        if not old_transaction:     super().__init__(upper, 'Create Transaction')
        elif copy:              super().__init__(upper, 'Edit Copied Transaction')
        else:                   super().__init__(upper, 'Edit Transaction')

        self.ENTRIES = {}

        # LABELS AND ENTRY BOXES - all containing their default inputs
        self.add_label('', 0,0, rowspan=3)  #Empty label for decor purposes only
        self.add_label('Date (' + setting('timezone') + ')', 1,0,columnspan=2)
        self.ENTRIES['date'] = self.add_entry(str(datetime.now()).split('.')[0], 1, 1, columnspan=2, format='date')
        self.add_label('Type',3,0)
        self.ENTRIES['type'] =  self.add_dropdown_list({trans_type_formatting_lib[t_type]['name']:t_type for t_type in trans_type_formatting_lib}, 3, 1, default=' -TYPE- ', selectCommand=self.update_entry_interactability)
        self.add_label('Wallet',4,0)
        self.ENTRIES['wallet']= self.add_dropdown_list({w.name():w.name() for w in self.upper.PORTFOLIO.wallets()}, 4, 1, default=' -WALLET- ', selectCommand=self.update_entry_interactability)
        self.add_label('Asset Class',1,2)
        all_classes_dict = {class_lib[c]['name']:c for c in class_lib}
        self.ENTRIES['loss_class'] = self.add_dropdown_list(all_classes_dict, 1, 3, current='f', selectCommand=self.update_entry_interactability)
        self.ENTRIES['fee_class'] =  self.add_dropdown_list(all_classes_dict, 1, 4, default='-NO FEE-', selectCommand=self.update_entry_interactability)
        self.ENTRIES['gain_class'] = self.add_dropdown_list(all_classes_dict, 1, 5, current='f', selectCommand=self.update_entry_interactability)
        self.add_label('Ticker',2,2)
        self.ENTRIES['loss_ticker'] = self.add_entry('USD', 2, 3, maxLength=24, capsLock=True)
        self.ENTRIES['fee_ticker'] =  self.add_entry('USD', 2, 4, maxLength=24, capsLock=True)
        self.ENTRIES['gain_ticker'] = self.add_entry('USD', 2, 5, maxLength=24, capsLock=True)
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

        # ENTRY BOX DATA - If editing, fills entry boxes with existing transaction data
        if old_transaction:
            for metric,data in old_transaction._data.items():
                # Ignore missing/irrelevant data
                if metric not in trans_type_minimal_set[old_transaction.type()] or data is None: continue
                #Update entry box with known data.
                if metric == 'date':  self.ENTRIES[metric].set(unix_to_local_timezone(data))
                else:               self.ENTRIES[metric].set(data)

        # Interacting with any entry boxes causes window to re-render boxes, inference data where possible, etc.
        for metric in self.ENTRIES:
            if metric == 'date': 
                self.ENTRIES[metric].timeChanged.connect(self.update_entry_interactability)
            elif metric in ('type','wallet','loss_class','fee_class','gain_class'):
                pass # already connected above
            else:
                self.ENTRIES[metric].textChanged.connect(self.update_entry_interactability)

        #Menu buttons
        self.add_menu_button('Cancel', self.close)
        self.add_menu_button('Save', self.save, styleSheet=style('save'))
        if old_transaction and not copy: self.add_menu_button('Delete', self.delete, styleSheet=style('delete'))

        self.update_entry_interactability()
        self.show()
    
    def update_entry_interactability(self, *args, **kwargs):
        '''Appropriately sets the color and functionality of all entry boxes/labels, depending on what is selected'''
        TYPE,WALLET = self.ENTRIES['type'].entry(), self.ENTRIES['wallet'].entry()

        # TYPE - Only 'type' enabled when no type selected
        if TYPE is None:
            self.ENTRIES['type'].setStyleSheet(style('entry'))
            for metric in self.ENTRIES: 
                self.ENTRIES[metric].setReadOnly(metric != 'type') # disables all entries, except type
            return
        self.ENTRIES['type'].setStyleSheet(style('entry')+style(TYPE+'_dark'))

        # WALLET - Only 'wallet'/'type' enabled when type, but no wallet selected
        if WALLET is None:
            for metric in self.ENTRIES: 
                self.ENTRIES[metric].setReadOnly(metric not in ('type','wallet')) # disables all entries, except type and wallet
            return
    
        # Set all entries to enabled/disabled, based on the trans_type_minimal_set
        for metric in self.ENTRIES:
            self.ENTRIES[metric].setReadOnly(metric not in trans_type_minimal_set[TYPE])
        # Disable fee data, when fee class is "no fee"
        if self.ENTRIES['fee_class'].entry() is None:
            for metric in ('fee_ticker','fee_quantity','fee_price'):
                self.ENTRIES[metric].setReadOnly(True)

        # STATIC INFERENCES
        for metric in trans_type_static_inference[TYPE]:
            self.ENTRIES[metric].set(str(trans_type_static_inference[TYPE][metric]))

        # DYNAMIC INFERENCES
        # loss_price
        if TYPE == 'sale':
            try:    inferred_loss_price = ((self.ENTRIES['gain_quantity'].entry_decimal() - self.ENTRIES['fee_quantity'].entry_decimal()) /
                                            self.ENTRIES['loss_quantity'].entry_decimal())
            except: inferred_loss_price = 0
            if inferred_loss_price > 0:
                    self.ENTRIES['loss_price'].set(inferred_loss_price)
            else:   self.ENTRIES['loss_price'].set(' ')
            self.ENTRIES['loss_price'].setCursorPosition(0)
        # gain_price
        if TYPE in ('purchase','purchase_crypto_fee','trade'):
            try:    inferred_gain_price =  ((self.ENTRIES['loss_quantity'].entry_decimal() * self.ENTRIES['loss_price'].entry_decimal() +
                                             self.ENTRIES['fee_quantity'].entry_decimal()  * self.ENTRIES['fee_price'].entry_decimal()) /
                                             self.ENTRIES['gain_quantity'].entry_decimal())
            except: inferred_gain_price = 0
            if inferred_gain_price > 0:
                    self.ENTRIES['gain_price'].set(inferred_gain_price)
            else:   self.ENTRIES['gain_price'].set(' ')
            self.ENTRIES['gain_price'].setCursorPosition(0)


    def delete(self):
        self.upper.PORTFOLIO.delete_transaction(self.old_transaction)  #deletes the transaction

        # Remove assets that no longer have transactions
        for a in list(self.upper.PORTFOLIO.assets()):
            if len(a._ledger) == 0:
                print("deleted asset",a)
                self.upper.PORTFOLIO.delete_asset(a)

        self.upper.create_memento(self.old_transaction, None, 'Delete transaction') # Deleted transaction
        self.upper.metrics()            #recalculates metrics for this asset w/o this transaction
        self.upper.render(sort=True)    #re-renders the main portfolio w/o this transaction
        self.close()

    def save(self):
        ################################
        # CHECKS 1
        ################################
        # Asset type selected
        TYPE = self.ENTRIES['type'].entry()
        if not TYPE:
            self.display_error('[ERROR] Must select transaction type!')
            return
        # Wallet selected
        WALLET = self.ENTRIES['wallet'].entry()
        if not WALLET:
            self.display_error('[ERROR] Must select wallet!')
            return
        ################################
        #DATA CULLING AND CONVERSION
        ################################
        # Creates dictionary of all data, and removes any data not in the minimal dataset for this transaction type
        TO_SAVE = {metric:entry.entry() for metric,entry in self.ENTRIES.items()}

        # CONVERT DATE TO VALID UNIX CODE
        #valid datetime format? - NOTE: This also converts the date to unix time
        try:        TO_SAVE['date'] = timezone_to_unix(TO_SAVE['date'])
        except:     error = 'Invalid date!'

        # Cull fee data if 'no fee' was selected
        if self.ENTRIES['fee_class'].entry() == None:
            TO_SAVE['fee_ticker'] =    None
            TO_SAVE['fee_quantity'] = None
            TO_SAVE['fee_price'] =    None

        # Short quick-access variables
        LT,LC,LQ,LP = TO_SAVE['loss_ticker'],TO_SAVE['loss_class'],TO_SAVE['loss_quantity'],TO_SAVE['loss_price']
        FT,FC,FQ,FP = TO_SAVE['fee_ticker'], TO_SAVE['fee_class'], TO_SAVE['fee_quantity'], TO_SAVE['fee_price']
        GT,GC,GQ,GP = TO_SAVE['gain_ticker'],TO_SAVE['gain_class'],TO_SAVE['gain_quantity'],TO_SAVE['gain_price']

        # Cull irrelevant data
        for metric in TO_SAVE:
            if metric not in trans_type_minimal_set[TO_SAVE['type']]:
                TO_SAVE[metric] = None

        ################################
        # CHECKS 2
        ################################
        error = None
        valids = trans_type_minimal_set[TYPE]
        
        # MUST HAVE BOTH TICKER AND CLASS
        if (LT and not LC) or (not LT and LC):  
            self.display_error('[ERROR] Must have loss ticker AND class if one is specified')
            return
        if (FT and not FC) or (not FT and FC):  
            self.display_error('[ERROR] Must have fee ticker AND class if one is specified')
            return
        if (GT and not GC) or (not GT and GC):  
            self.display_error('[ERROR] Must have gain ticker AND class if one is specified')
            return

        # Valid loss?
        if 'loss_quantity' in valids and zeroish(LQ):                     error = 'Loss quantity must be non-zero.'
        if 'loss_price' in valids and    zeroish(LP):                     error = 'Loss price must be non-zero.' # NOTE: See above
        # Valid fee?
        if FT: #Fee asset will be 'USDzf' for purchases and sales, until that data removed later on.
            if FQ and 'fee_quantity' in valids and zeroish(FQ):                     error = 'Fee quantity must be non-zero.'
            #if FP and 'fee_price' in valids and    zeroish(FP):                     error = 'Fee price must be non-zero.'
        # Valid gain?
        if 'gain_quantity' in valids and zeroish(GQ):                     error = 'Gain quantity must be non-zero.'
        if 'gain_price' in valids and    zeroish(GP):                     error = 'Gain price must be non-zero.' # NOTE: See above

        # If loss/fee asset identical, or fee/gain asset identical, then the loss/fee or fee/gain price MUST be identical
        if 'loss_price' in valids and FT and LT==FT and not appxEq(LP,FP): error = 'If the loss and fee assets are the same, their price must be the same.'
        if 'gain_price' in valids and FT and GT==FT and not appxEq(GP,FP): error = 'If the fee and gain assets are the same, their price must be the same.'

        # The loss and gain assets can't be identical, that's retarted. That means you would have sold something to buy itself... huh?
        if 'loss_ticker' in valids and 'gain_ticker' in valids and LT==GT:    error = 'Loss and Gain asset cannot be the same... right?'


        if error:
            self.display_error('[ERROR] ' + error)
            return


        # TRANSACTION SAVING AND OVERWRITING
        #==============================
        #Creates the new transaction or overwrites the old one
        NEWHASH = Transaction.calc_hash(None, TO_SAVE)
        if self.old_transaction:      OLDHASH = self.old_transaction.get_hash()
        else:           OLDHASH = None

        # FINAL CHECK - transaction will be unique?
        #transaction already exists if: 
        #   hash already in transactions - and we're not just saving an unmodified transaction over itself!
        has_hash = self.upper.PORTFOLIO.hasTransaction(NEWHASH)
        if has_hash and not (self.old_transaction and NEWHASH == OLDHASH):
            self.display_error('[ERROR] This is too similar to an existing transaction!')
            return

        # ACTUALLY SAVING THE TRANSACTION
        TO_SAVE = {metric:TO_SAVE[metric] for metric in trans_type_minimal_set[TYPE]} # Clean the transaction of useless data
        new_transaction = Transaction(TO_SAVE)
        if self.old_transaction: self.upper.PORTFOLIO.delete_transaction(self.old_transaction)  # Delete the old version, if there is one
        self.upper.PORTFOLIO.add_transaction(new_transaction)     # Save the new version
        
    
        self.upper.create_memento(self.old_transaction, new_transaction, 'Create/modify transaction') # Created/modified transaction
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
        self.wallet_list.update_dict({wallet.name():wallet for wallet in self.upper.PORTFOLIO.wallets()})
        
class WalletEditor(Dialog): #For creating/editing Wallets
    """Opens dialog for creating/editing wallets"""
    def __init__(self, walletManager:WalletManager, wallet_to_edit:Wallet=None):
        self.wallet_to_edit = wallet_to_edit
        self.walletManager = walletManager
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
        # No delete button: empty wallets are deleted when the program starts.
        self.show()

    def save(self):
        NAME = self.ENTRY_name.entry()
        DESC = self.ENTRY_desc.entry()

        # CHECKS
        #==============================
        # Name isn't an empty string?
        if NAME == '':
            self.display_error('[ERROR] Must enter a name for this wallet')
            return
        # Name is unique?
        if self.walletManager.upper.PORTFOLIO.hasWallet(NAME) and NAME != self.wallet_to_edit.name():
            self.display_error('[ERROR] A wallet already exists with this name!')
            return

        #WALLET SAVING AND OVERWRITING
        #==============================
        if self.wallet_to_edit == None: # Creating whole new wallet
            new = Wallet(NAME, DESC)
            self.walletManager.upper.PORTFOLIO.add_wallet(new)
            self.walletManager.upper.create_memento(None, new, 'Create wallet') # Created wallet
        else:
            old_name, old_desc = self.wallet_to_edit.name(),self.wallet_to_edit.desc()
            if old_name != NAME or old_desc != DESC:   # NAME/DESCRIPTION modified
                if old_name != NAME:
                    # Create new, delete old wallet (part of "rename_wallet" function), and...
                    # ...Rename wallet for all relevant transactions
                    old, new = self.walletManager.upper.PORTFOLIO.rename_wallet(old_name, NAME)
                if old_desc != DESC:
                    old = self.walletManager.upper.PORTFOLIO.wallet(old_name)
                    new = Wallet(NAME, DESC)
                    self.walletManager.upper.PORTFOLIO.delete_wallet(old)
                    self.walletManager.upper.PORTFOLIO.add_wallet(new)

                self.walletManager.upper.create_memento(old, new, 'Modify wallet') # Modified wallet
                #Only reload metrics and rerender, if we rename a wallet
                self.walletManager.upper.metrics()
                self.walletManager.upper.render(sort=True)


        self.walletManager.refresh_wallets()
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
        self.filterlist.update_dict({filter.get_rule_name():filter for filter in self.upper.PORTFOLIO.filters()})
        
class FilterEditor(Dialog): #For creating/editing filters
    """Opens dialog for creating/editing filters"""
    def __init__(self, filterManager:FilterManager, filter_to_edit:Filter=None):
        self.filter_to_edit = filter_to_edit
        self.filterManager = filterManager
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
        self.DROPDOWN_relation = self.add_dropdown_list({r:r for r in ('<','!=','=','>')}, 1, 1, current='=')

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
        self.ENTRY_state.setReadOnly(isERROR)
        self.DROPDOWN_relation.setReadOnly(isERROR)


    def delete(self):
        # Only possible when editing an existing filter
        self.filterManager.upper.PORTFOLIO.delete_filter(self.filter_to_edit)  #destroy the old filter

        if len(self.filterManager.upper.PORTFOLIO.filters()) == 0: self.upper.upper.MENU['filters'].setStyleSheet('') #Turn off filtering indicator
        self.filterManager.upper.page = 0 # adding filter resets rendered page to 0
        self.filterManager.upper.render(sort=True) # Always re-render and re-sort when filters are applied/removed
        self.filterManager.refresh_filters()
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
            metric_is_numeric = metric_formatting_lib[METRIC]['format'] not in ('alpha','type','desc','class','date')
            if metric_is_numeric:
                try: 
                    new_filter = Filter(METRIC, RELATION, float(STATE)) # try to parse the state as float
                except:
                    self.display_error('[ERROR] State must be a parsable float')
                    return
            else:
                new_filter = Filter(METRIC, RELATION, STATE)
            # Not using a non-equals, if metric is alpha?
            if not metric_is_numeric and RELATION not in ('=','!=') and METRIC != 'date':
                self.display_error('[ERROR] Relation must be \'=\' or \'!=\' for text metrics')
                return
        # Identical filter doesn't already exist?
        if new_filter is not self.filter_to_edit and new_filter in self.filterManager.upper.PORTFOLIO.filters():
            self.display_error('[ERROR] Identical filter already exists')
            return

        # SAVING
        #==============================
        self.filterManager.upper.PORTFOLIO.add_filter(new_filter)   #Creates the new filter, or overwrites the existing one
        if self.filter_to_edit: self.filterManager.upper.PORTFOLIO.delete_filter(self.filter_to_edit)
        
        self.filterManager.upper.MENU['filters'].setStyleSheet(style('main_menu_filtering'))
        self.filterManager.upper.page = 0 # adding filter resets rendered page to 0
        self.filterManager.upper.render(sort=True)  # Always render and re-sort when filters are applied/removed
        self.filterManager.refresh_filters()
        self.close()


class ImportationDialog(Dialog): #For selecting wallets to import transactions to
    '''Opens dialog for specifying one or two wallets to which transactions will be imported, for Gemini, Gemini Earn, Coinbase, etc.'''
    def __init__(self, upper, source, import_command, wallet_name):
        super().__init__(upper, 'Import to Wallet')
        self.source = source
        self.add_label(wallet_name,0,0)
        self.wallet_to_edit_dropdown = self.add_dropdown_list({w.name():w for w in self.upper.PORTFOLIO.wallets()}, 1, 0, default=' -SELECT WALLET- ')
        self.add_menu_button('Cancel', self.close)
        self.add_menu_button('Import', p(self.complete, import_command, wallet_name), styleSheet=style('new'))
        self.show()
    
    def complete(self, import_command, wallet_name, *args, **kwargs):
        wallet_for_import = self.wallet_to_edit_dropdown.entry()
        if wallet_for_import == None:   
            self.display_error('[ERROR] Must select a '+wallet_name+'.')
            return
        self.close()
        import_command(wallet_for_import, self.source)   #Runs the importGemini or importCoinbase, or whatever command again, but with wallet data

class DEBUGStakingReportDialog(Dialog):
    '''Opens dialog for reporting my current interest quantity of AMP/ALCX without having to do math'''
    def __init__(self, upper, *args, **kwargs):
        super().__init__(upper, 'Report Staking Interest')
        self.add_label('Crypto Ticker',0,0)
        self.ENTRY_asset = self.add_entry('', 1, 0, maxLength=24, capsLock=True)
        self.add_label('Staking Wallet',0,1)
        self.DROPDOWN_wallet = self.add_dropdown_list({w.name():w.name() for w in self.upper.PORTFOLIO.wallets()}, 1, 1, default=' -SELECT WALLET- ')
        self.add_label('Quantity',0,2)
        self.ENTRY_quantity = self.add_entry('', 1, 2, format='pos_float')
        self.add_menu_button('Cancel', self.close)
        self.add_menu_button('Report', self.report, styleSheet=style('new'))
        self.show()

    def report(self):
        TICKER = self.ENTRY_asset.entry()
        WALLET = self.DROPDOWN_wallet.entry()
        QUANTITY = self.ENTRY_quantity.entry()

        # CHECKS
        # Asset is in portfolio?
        if not self.upper.PORTFOLIO.hasAsset(TICKER, 'c'):
            self.display_error('[ERROR] Cryptocurrency \'{TICKER}\' not found in portfolio.')
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
        this_asset = self.upper.PORTFOLIO.asset(TICKER, 'c')
        for transaction in this_asset._ledger.values():
            # Only count transactions: income, from same wallet
            if transaction.type() == 'income' and transaction.wallet() == WALLET:
                total_staking_income_thus_far += transaction.get_metric('gain_quantity')

        # Quantity is < income thus far?
        if QUANTITY < total_staking_income_thus_far:   
            self.display_error(f'[ERROR] Staking quantity ({QUANTITY}) less than current total staking income earned ({total_staking_income_thus_far}).')
            return
        new_transaction = Transaction({
                                      'date':timezone_to_unix(str(datetime.now()).split('.')[0]), 
                                      'type':'income', 
                                      'wallet':WALLET, 
                                      'gain_ticker': TICKER, 
                                      'gain_class': 'c',
                                      'gain_quantity':str(QUANTITY-total_staking_income_thus_far), 
                                      'gain_price':str(this_asset.get_metric('price')),
                                      'description':'Manually reported staking interest using AutoAccountant', 
                                      }
                                      )
        self.upper.PORTFOLIO.add_transaction(new_transaction)

        self.upper.create_memento(None, new_transaction, 'Automatically create staking transaction') # Added staking transaction
        self.upper.metrics()
        self.upper.render(sort=True)
        self.close()
