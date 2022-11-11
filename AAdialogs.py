
from AAdialog import *
from AAobjects import *


class Message(Dialog): #Simple text popup, can add text with colors to it
    def __init__(self, upper, title, message):
        super().__init__(upper, title)
        self.text = self.add_label(message, 0, 0, styleSheet=style('displayFont'), wordWrap=True)
        self.add_menu_button('Ok', self.close)
        self.show()
    
    def setText(self, text): self.text.setText(text)

class Message2(Dialog): #Simple text popup, can add text with colors to it
    def __init__(self, upper, title, message, tabStopWidth=None):
        super().__init__(upper, title)
        availableSpace = QDesktopWidget().availableGeometry()
        self.setFixedSize(availableSpace.width()*.70, availableSpace.height()*.8)
        self.text = self.add_scrollable_text(message, 0, 0, styleSheet=style('displayFont'))
        if tabStopWidth: self.text.setTabStopWidth(tabStopWidth)
        self.add_menu_button('Ok', self.close)
        self.show()
    
    def setText(self, text): self.text.setText(text)


class Prompt(Dialog): #Simple text popup, doesn't display, waits for additional buttons to be added before .show() has to be called
    def __init__(self, upper, title, message):
        super().__init__(upper, title)
        self.add_label(message, 0, 0, styleSheet=style('displayFont'))
        self.add_menu_button('Cancel', self.close)


class AssetEditor(Dialog):    #For editing an asset's name, title, class, and description
    def __init__(self, upper, asset=''):
        self.asset = asset

        self.AssetClasses = {assetclasslib[c]['name']:c for c in assetclasslib} #Dictionary of all the classes, keyed by their by longname, not internal ID
        if asset == '':   
            super().__init__(upper, 'Create Asset')
            self.ENTRY_ticker =     self.add_entry('',1,0,maxLength=24)
            self.ENTRY_name =       self.add_entry('',1,1,maxLength=24)
            self.DROPDOWN_class =   self.add_dropdown_list(self.AssetClasses, 1, 2, default='-SELECT CLASS-')
            self.ENTRY_desc =       self.add_entry('',1,3,format='description')
        else:               
            super().__init__(upper, 'Edit ' + asset)
            self.ENTRY_ticker =     self.add_entry(self.asset.split('z')[0],1,0,maxLength=24)
            self.ENTRY_name =       self.add_entry(MAIN_PORTFOLIO.asset(asset).name(),1,1,maxLength=24)
            self.DROPDOWN_class =   self.add_dropdown_list(self.AssetClasses, 1, 2, default='-SELECT CLASS-', current=assetclasslib[asset.split('z')[1]]['name'])
            self.ENTRY_desc =       self.add_entry(MAIN_PORTFOLIO.asset(asset).desc(),1,3,format='description')
        self.add_label('Ticker',0,0)
        self.add_label('Name',0,1)
        self.add_label('Class',0,2)
        self.add_label('Description',0,3)

        self.add_menu_button('Cancel', self.close)
        self.add_menu_button('Save', self.save, styleSheet=style('save'))
        if asset != '': self.add_menu_button('Delete', self.delete, styleSheet=style('delete'))

        self.show()

    def save(self):
        #DATA CULLING AND CONVERSION PART I
        #==============================
        try:
            TICKER = self.ENTRY_ticker.entry().upper()
            CLASS = self.AssetClasses[self.DROPDOWN_class.entry()]
            TICKERCLASS = TICKER+'z'+CLASS
        except: #User hasn't selected an asset class
            Message(self, 'ERROR!', 'Must select an asset class')
            return
        #Temporary representation of what our asset will look like
        NAME = self.ENTRY_name.entry()
        DESC = self.ENTRY_desc.entry()
        if self.asset == '':    LEDGER = {} 
        else:                   LEDGER = MAIN_PORTFOLIO.asset(self.asset)._ledger   #If we rename the asset, we need to keep its ledger!

        # CHECKS
        #==============================
        #new ticker will be unique?
        if TICKERCLASS != self.asset and MAIN_PORTFOLIO.hasAsset(TICKERCLASS):
            Message(self, 'ERROR!', 'This asset already exists!')
            return
        #Can't change ticker or class if there are transactions for this asset.
        if self.asset not in ('',TICKERCLASS):
            if len(MAIN_PORTFOLIO.asset(self.asset)._ledger) > 0:
                Message(self, 'ERROR!', 'Cannot modify asset ticker or class, due to existing transactions. Delete the transactions to modify this asset.')
                return
        #Ticker isn't an empty string?
        if TICKER == '':
            Message(self, 'ERROR!', 'Must enter a ticker')
            return
        #Name isn't an empty string?
        if NAME == '':
            Message(self, 'ERROR!', 'Must enter a name')
            return

        #ASSET SAVING AND OVERWRITING
        #==============================
        #Create a NEW asset, or overwrite the old one
        MAIN_PORTFOLIO.add_asset(Asset(TICKERCLASS, NAME, DESC))
        MAIN_PORTFOLIO.asset(TICKERCLASS)._ledger = LEDGER

        #ID CHANGE: The ID was modified.
        if self.asset not in ('',TICKERCLASS):  MAIN_PORTFOLIO.delete_asset(self.asset)

        self.upper.metrics()
        self.upper.render(sort=True)
        self.upper.undo_save()
        self.close()

    def delete(self):
        #Not allowed to delete an asset with 
        if len(MAIN_PORTFOLIO.asset(self.asset)._ledger) > 0:
            Message(self, 'ERROR!', 'Cannot modify asset ticker or class, due to existing transactions. Delete the transactions to modify this asset.')
            return
        MAIN_PORTFOLIO.delete_asset(self.asset) #removal from portfolio
        self.upper.metrics()
        self.upper.render(sort=True)
        self.upper.undo_save()
        self.close()

class TransEditor(Dialog):    #The most important, and most complex editor. For editing transactions' date, type, wallet, second wallet, tokens, price, usd, and description.
    def __init__(self, upper, transaction:Transaction=None, copy=False):
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
        self.ENTRIES['type'] =  self.add_dropdown_list(pretty_trans.values(), 3, 1, default=' -TYPE- ', selectCommand=self.select_type)
        self.add_label('Wallet',4,0)
        self.ENTRIES['wallet']= self.add_dropdown_list(MAIN_PORTFOLIO.walletkeys(), 4, 1, default=' -WALLET- ')
        self.add_label('Asset',1,2,columnspan=2)
        self.ENTRIES['loss_class'] = self.add_dropdown_list(prettyClasses(), 1, 3, current='Fiat')
        self.ENTRIES['fee_class'] =  self.add_dropdown_list(prettyClasses(), 1, 4, default='-NO FEE-')
        self.ENTRIES['gain_class'] = self.add_dropdown_list(prettyClasses(), 1, 5, current='Fiat')
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

        # ENTRY BOX DATA - if editing, overwrites entry boxes with transaction data
        if transaction:
            for data in valid_transaction_data_lib[transaction.type()]:
                tdata = transaction.get(data)
                if tdata == None:    continue       #Ignores missing data. Usually data is missing to save space in JSON.
                
                #Update entry box with known data.
                if data == 'date':
                    self.ENTRIES[data].set(unix_to_local_timezone(tdata))
                elif data == 'type':
                    self.ENTRIES[data].set(pretty_trans[tdata])
                elif data[-6:] == '_asset':
                    a = MAIN_PORTFOLIO.asset(tdata)
                    self.ENTRIES[data].set(a.ticker())                              #Set asset ticker entry to ticker
                    self.ENTRIES[data[:-6]+'_class'].set(a.prettyPrint('class'))    #Set asset class dropdown to class
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

        #Runs 'select_type' to appropriately preset the color and existing entry boxes/labels, when editing an existing transaction
        if not transaction:     self.select_type(self.ENTRIES['type'].entry())
        else:                   self.select_type(pretty_trans[transaction.type()])

        self.auto_purchase_sale_price() # Initializes the autoprice boxes with something
        self.show()
        
    
    def auto_purchase_sale_price(self): #Updates purchase/sale price when loss_quantity changes for a purchase/sale
        try:
            TYPE = uglyTrans(self.ENTRIES['type'].entry())
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

    def select_type(self, selection):
        type = uglyTrans(selection)
        #COLOR CHANGES
        if self.ENTRIES['type'].isDefault():    self.ENTRIES['type'].setStyleSheet(style('entry'))
        else:                                   self.ENTRIES['type'].setStyleSheet(style('entry')+style(type+'text'))
        
        #ENABLING AND DISABLING
        if self.ENTRIES['type'].isDefault():
            for entry in self.ENTRIES:
                if entry != 'type': self.ENTRIES[entry].setReadOnly(True)
        else:
            for entry in self.ENTRIES:
                if entry == 'type': continue
                elif entry[-6:] == '_class':   
                    if entry[:-6]+'_asset' in valid_transaction_data_lib[type]: self.ENTRIES[entry].setReadOnly(False) #Enable class selection only if asset selection possible
                    else: self.ENTRIES[entry].setReadOnly(True)
                elif entry in valid_transaction_data_lib[type]:   self.ENTRIES[entry].setReadOnly(False)
                else:                                           self.ENTRIES[entry].setReadOnly(True)
            if type == 'purchase':  
                self.ENTRIES['loss_class'].set('Fiat')
                self.ENTRIES['fee_class'].set('Fiat')
                self.ENTRIES['loss_asset'].set('USD')
                self.ENTRIES['fee_asset'].set('USD')
            elif type == 'sale':    
                self.ENTRIES['gain_class'].set('Fiat')
                self.ENTRIES['fee_class'].set('Fiat')
                self.ENTRIES['gain_asset'].set('USD')
                self.ENTRIES['fee_asset'].set('USD')

    def delete(self):
        MAIN_PORTFOLIO.delete_transaction(self.t.get_hash())  #deletes the transaction
        self.upper.undo_save()          #creates a savepoint after deleting this
        self.upper.metrics()            #recalculates metrics for this asset w/o this transaction
        self.upper.render(sort=True)    #re-renders the main portfolio w/o this transaction
        self.close()

    def save(self):
        #DATA CULLING AND CONVERSION
        #==============================
        TO_SAVE = {}
        for entry in self.ENTRIES:
            data = self.ENTRIES[entry].entry()
            if entry[-6:] == '_asset':  
                try:    TO_SAVE[entry] = data.upper() + 'z' + uglyClass(self.ENTRIES[entry[:-6]+'_class'].entry())
                except: TO_SAVE[entry] = None
            elif entry == 'type':       TO_SAVE['type'] = uglyTrans(self.ENTRIES['type'].entry())
            else:                       TO_SAVE[entry] = data

        #If 'no fee' was selected, cull all other fee data.
        if self.ENTRIES['fee_class'].isDefault():
            TO_SAVE['fee_asset'] =    None
            TO_SAVE['fee_quantity'] = None
            TO_SAVE['fee_price'] =    None
        
        #For now, USDzf is the default currency, and is just converted to "None", as well as its corresponding price
        for asset in ('loss','fee','gain'):
            if TO_SAVE[asset+'_asset'] == 'USDzf':  TO_SAVE[asset+'_asset'] = None
            if TO_SAVE[asset+'_asset'] == None:     TO_SAVE[asset+'_price'] = None

        # Short quick-access variables
        TYPE = TO_SAVE['type']
        LA,LQ,LP = TO_SAVE['loss_asset'],TO_SAVE['loss_quantity'],TO_SAVE['loss_price']
        FA,FQ,FP = TO_SAVE['fee_asset'], TO_SAVE['fee_quantity'], TO_SAVE['fee_price']
        GA,GQ,GP = TO_SAVE['gain_asset'],TO_SAVE['gain_quantity'],TO_SAVE['gain_price']

        ################################
        # CHECKS
        ################################
        error = None

        #selected a type?
        if self.ENTRIES['type'].isDefault():
            Message(self, 'ERROR!', 'No transaction type was selected.')    #Message and return here otherwise code breaks w/o a type selected
            return
        #valid datetime format? - NOTE: This also converts the date to unix time
        try:        TO_SAVE['date'] = timezone_to_unix(TO_SAVE['date'])
        except:     error = 'Invalid date!'
        #selected a wallet? (start out with nothing selected)
        if self.ENTRIES['wallet'].isDefault(): error = 'No wallet was selected.'

        valids = valid_transaction_data_lib[TYPE]

        ######################################################
        # NOTE: Currently, checking for missing price input is ignored
        # We allow the user to automatically get price data from YahooFinance, if they don't know it
        ######################################################

        # Valid loss?
        if 'loss_asset' in valids and    not MAIN_PORTFOLIO.hasAsset(LA): error = 'Loss asset does not exist in portfolio.'
        if 'loss_quantity' in valids and zeroish(LQ):                     error = 'Loss quantity must be non-zero.'
        #if 'loss_price' in valids and    zeroish(LP):                     error = 'Loss price must be non-zero.'
        # Valid fee?
        if FA: #Fee asset will be 'USDzf' for purchases and sales, until that data removed later on.
            if        'fee_asset' in valids  and   not MAIN_PORTFOLIO.hasAsset(FA): error = 'Fee asset does not exist in portfolio.'
            if FQ and 'fee_quantity' in valids and zeroish(FQ):                     error = 'Fee quantity must be non-zero.'
            #if FP and 'fee_price' in valids and    zeroish(FP):                     error = 'Fee price must be non-zero.'
        # Valid gain?
        if 'gain_asset' in valids and    not MAIN_PORTFOLIO.hasAsset(GA): error = 'Gain asset does not exist in portfolio.'
        if 'gain_quantity' in valids and zeroish(GQ):                     error = 'Gain quantity must be non-zero.'
        #if 'gain_price' in valids and    zeroish(GP):                     error = 'Gain price must be non-zero.'

        # If loss/fee asset identical, or fee/gain asset identical, then the loss/fee or fee/gain price MUST be identical
        if 'loss_price' in valids and FA and LA==FA and not appxEq(LP,FP): error = 'If the loss and fee assets are the same, their price must be the same.'
        if 'gain_price' in valids and FA and GA==FA and not appxEq(GP,FP): error = 'If the fee and gain assets are the same, their price must be the same.'

        # The loss and gain assets can't be identical, that's retarted. That means you would have sold something to buy itself... huh?
        if 'loss_asset' in valids and 'gain_asset' in valids and LA==GA:    error = 'Loss and Gain asset cannot be the same.'


        if error:
            Message(self, 'ERROR!', error)
            return

        # TRANSACTION SAVING AND OVERWRITING
        #==============================
        #Creates the new transaction or overwrites the old one
        new_trans = trans_from_dict(TO_SAVE)
        NEWHASH = new_trans.get_hash()
        OLDHASH = None
        if self.t:    OLDHASH = self.t.get_hash()

        #transaction will be unique?
        #transaction already exists if: 
        #   hash already in transactions, and we're not just saving an unmodified transaction over itself
        has_hash = MAIN_PORTFOLIO.hasTransaction(NEWHASH)
        if has_hash and not (self.t and NEWHASH == OLDHASH):
            Message(self, 'ERROR!', 'This is too similar to an existing transaction!')
            return

        print('||INFO|| Saved transaction. ')
        MAIN_PORTFOLIO.add_transaction(new_trans)                   # Add the new transaction, or overwrite the old
        if OLDHASH != None and NEWHASH != OLDHASH:
            MAIN_PORTFOLIO.delete_transaction(OLDHASH)    # Delete the old transaction if it's hash will have changed
            
        self.upper.undo_save()
        self.upper.metrics()
        self.upper.render(sort=True)
        self.close()



class WalletManager(Dialog): #For selecting wallets to edit
    '''Creates a small window for selecting wallets to edit, or creating new wallets'''
    def __init__(self, upper):
        super().__init__(upper, 'Manage Wallets')
        self.walletlist = self.add_list_entry(MAIN_PORTFOLIO.walletkeys(), 0, 0, selectCommand=self.edit_wallet)
        self.add_menu_button('Cancel', self.close)
        self.add_menu_button('+ Wallet', p(WalletEditor, self), styleSheet=style('new'))
        self.show()
    
    def edit_wallet(self, item): #Command executed when button is pressed in the manager
        WalletEditor(self, item)

    def refresh_wallets(self):
        self.walletlist.update_items(MAIN_PORTFOLIO.walletkeys())
        
class WalletEditor(Dialog): #For editing Wallets
    def __init__(self, walletManager, wallet=''):
        self.wallet = wallet
        if wallet == '': #New wallet
            super().__init__(walletManager, 'Create Wallet')
            self.ENTRY_desc = self.add_entry('', 1, 1, format='description')
        else:
            super().__init__(walletManager, 'Edit '+ wallet +' Wallet')
            self.ENTRY_desc = self.add_entry(MAIN_PORTFOLIO.wallet(wallet).desc(), 1, 1,format='description')
        #Wallet Name Entry
        self.add_label('Name',0,0)
        self.ENTRY_name = self.add_entry(wallet, 1, 0, maxLength=24)
        #Wallet Description Entry
        self.add_label('Description',0,1)
        self.add_menu_button('Cancel', self.close)
        self.add_menu_button('Save', self.save, styleSheet=style('save'))
        if wallet != '':    self.add_menu_button('Delete', self.delete, styleSheet=style('delete'))
        self.show()

    def delete(self):
        #You can only delete a wallet if its name is not used by any transaction in the portfolio
        for t in MAIN_PORTFOLIO.transactions():
            if t.wallet() == self.wallet:   #is the wallet you're deleting used anywhere in the portfolio?
                Message(self, 'Error!', 'You cannot delete this wallet, as it is used by existing transactions.') # If so, you can't delete it. 
                return

        MAIN_PORTFOLIO.delete_wallet(self.wallet)  #destroy the old wallet
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
        if MAIN_PORTFOLIO.hasWallet(new_wallet.get_hash()) and NAME != self.wallet:
            Message(self, 'ERROR!', 'A wallet already exists with this name!')
            return
        #Name isn't an empty string?
        if NAME == '':
            Message(self, 'ERROR!', 'Must enter a name for this wallet')
            return

        #WALLET SAVING AND OVERWRITING
        #==============================
        MAIN_PORTFOLIO.add_wallet(new_wallet)   #Creates the new wallet, or overwrites the existing one's description

        if self.wallet not in ('', NAME):   #WALLET RE-NAMED
            #destroy the old wallet
            MAIN_PORTFOLIO.delete_wallet(self.wallet) 
            for t in list(MAIN_PORTFOLIO.transactions()):   #sets wallet name to the new name for all relevant transactions
                if t.wallet() == self.wallet:      
                    new_trans = t.toJSON()
                    MAIN_PORTFOLIO.delete_transaction(t.get_hash()) #Changing the wallet name changes the transactions HASH, so we have to remove and re-add it
                    new_trans['wallet'] = NAME 
                    MAIN_PORTFOLIO.add_transaction(trans_from_dict(new_trans))
        
            #Only reload metrics and rerender, if we rename a wallet
            self.upper.upper.metrics()
            self.upper.upper.render(sort=True)

        self.upper.refresh_wallets()
        self.upper.upper.undo_save()
        self.close()


class ImportationDialog(Dialog): #For selecting wallets to import transactions to
    '''Allows user to specify one or two wallets which transactions will be imported to, for Gemini, Gemini Earn, Coinbase, etc.'''
    def __init__(self, upper, continue_command, wallet_name):
        super().__init__(upper, 'Import to Wallet')
        self.add_label(wallet_name,0,0)
        self.wallet = self.add_dropdown_list(MAIN_PORTFOLIO.walletkeys(), 1, 0, default=' -SELECT WALLET- ')
        self.add_menu_button('Cancel', self.close)
        self.add_menu_button('Import', p(self.complete, continue_command, wallet_name), styleSheet=style('new'))
        self.show()
    
    def complete(self, continue_command, wallet_name):
        result = self.wallet.entry()
        if self.wallet.isDefault():   
            Message(self, 'ERROR!','Must select a '+wallet_name+'.')
            return
        self.close()
        continue_command(result)   #Runs the importGemini or importCoinbase, or whatever command again, but with wallet data
    

