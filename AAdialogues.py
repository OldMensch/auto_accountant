
from AAdialogue import *
from AAobjects import *


class Message(Dialogue): #Simple text popup, can add text with colors to it
    def __init__(self, upper, title, message, width=32, height=8, fg=palette('entrycursor'), bg=palette('dark'), font=setting('font', 0.75)):
        super().__init__(upper, title)
        self.textbox = self.add_text_display(0, 0, message, fg, bg, font, width, height)
        self.add_menu_button('Ok', command=self.close)
        self.center_dialogue()
    
    def insert(self, text, fg=None, bg=None, font=None, newline=True):
        self.textbox.insert_text(text, fg, bg, font)
        if newline: self.newline()
    
    def insert_triplet(self, text1, text2, text3, fg=None, bg=None, font=None, newline=True):
        '''An easy way to insert text, where some middle part is colored/different font from its surroundings'''
        self.textbox.insert_text(text1)
        self.textbox.insert_text(text2, fg, bg, font)
        self.textbox.insert_text(text3)
        if newline: self.newline()

    def newline(self):
        self.textbox.newline()


class Prompt(Dialogue): #Simple text popup, doesn't center menu, waiting for user to add more menu buttons before user then centers the menu
    def __init__(self, upper, title, message, width=32, height=8):
        super().__init__(upper, title)
        self.add_text_display(0, 0, message, width=width, height=height)
        self.add_menu_button('Cancel', command=self.close)


class AssetEditor(Dialogue):    #For editing an asset's name, title, class, and description
    def __init__(self, upper, asset=''):
        self.asset = asset

        self.AssetClasses = {} #Dictionary of all the classes, by longname, not ID
        for c in assetclasslib:
            self.AssetClasses[assetclasslib[c]['name']] = c
        if asset == '':   
            super().__init__(upper, 'Create Asset')
            self.ENTRY_ticker =     self.add_entry(1,0,'',width=24,charLimit=24)
            self.ENTRY_name =       self.add_entry(1,1,'',width=24,charLimit=24)
            self.DROPDOWN_class =   self.add_dropdown_list(1, 2, self.AssetClasses, '-SELECT CLASS-')
            self.ENTRY_desc =       self.add_entry(1,3,'',format='description',width=24)
        else:               
            super().__init__(upper, 'Edit ' + asset)
            self.ENTRY_ticker =     self.add_entry(1,0,self.asset.split('z')[0],width=24,charLimit=24)
            self.ENTRY_name =       self.add_entry(1,1,MAIN_PORTFOLIO.asset(asset).name(),width=24,charLimit=24)
            self.DROPDOWN_class =   self.add_dropdown_list(1, 2, self.AssetClasses, '-SELECT CLASS-', assetclasslib[asset.split('z')[1]]['name'])
            self.ENTRY_desc =       self.add_entry(1,3,MAIN_PORTFOLIO.asset(asset).desc(),format='description',width=24)
        self.add_label(0,0,'Ticker')
        self.add_label(0,1,'Name')
        self.add_label(0,2,'Class')
        self.add_label(0,3,'Description')

        self.add_menu_button('Cancel', command=self.close)
        self.add_menu_button('Save', '#0088ff', command=self.save)
        if asset != '': self.add_menu_button('Delete', "#ff0000", command=self.delete)

        self.center_dialogue()

    def save(self):
        #DATA CULLING AND CONVERSION PART I
        #==============================
        try:
            TICKERCLASS = self.ENTRY_ticker.entry().upper()+'z'+self.AssetClasses[self.DROPDOWN_class.entry()]
            CLASS = self.AssetClasses[self.DROPDOWN_class.entry()]
        except: #User hasn't selected an asset class
            Message(self, 'ERROR!', 'Must select an asset class')
            return
        #Temporary representation of what our asset will look like
        NAME = self.ENTRY_name.entry()
        DESC = self.ENTRY_desc.entry()
        if self.asset == '':    LEDGER = {} #If we rename the asset, we need to keep its ledger!
        else:                   LEDGER = MAIN_PORTFOLIO.asset(self.asset)._ledger

        # CHECKS
        #==============================
        #new ticker will be unique?
        if TICKERCLASS != self.asset and MAIN_PORTFOLIO.hasAsset(TICKERCLASS):
            Message(self, 'ERROR!', 'This asset already exists!')
            return
        #Can't change ticker or class if there are transactions for this asset.
        if self.asset not in ['',TICKERCLASS]:
            if len(MAIN_PORTFOLIO.asset(self.asset)._ledger) > 0:
                Message(self, 'ERROR!', 'Cannot modify asset ticker or class, due to existing transactions. Delete the transactions to modify this asset.')
                return
        #Ticker isn't an empty string?
        if TICKERCLASS == '':
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
        if self.asset not in ['',TICKERCLASS]:  MAIN_PORTFOLIO.delete_asset(self.asset)

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

class TransEditor(Dialogue):    #The most important, and most complex editor. For editing transactions' date, type, wallet, second wallet, tokens, price, usd, and description.
    def __init__(self, upper, transaction:Transaction=None, copy=False):
        if not transaction or copy:     self.t = None
        else:                           self.t = transaction

        # DIALOGUE INITIALIZATION
        if not transaction:     super().__init__(upper, 'Create Transaction')
        elif copy:              super().__init__(upper, 'Edit Copied Transaction')
        else:                   super().__init__(upper, 'Edit Transaction')

        self.ENTRIES = {}

        # LABELS AND ENTRY BOXES - all containing their default inputs
        self.add_label(0,0,'',rowspan=3)  #Empty label for decor purposes only
        self.add_label(1,0,'Date (' + setting('timezone') + ')',columnspan=2)
        self.ENTRIES['date'] = self.add_entry(1, 1, str(datetime.now()).split('.')[0], width=24, format='date',columnspan=2)
        self.add_label(3,0,'Type')
        self.ENTRIES['type'] =  self.add_dropdown_list(3, 1, pretty_trans.values(), ' -TYPE- ', selectCommand=self.select_type)
        self.add_label(4,0,'Wallet')
        self.ENTRIES['wallet']= self.add_dropdown_list(4, 1, MAIN_PORTFOLIO.walletkeys(), ' -WALLET- ')
        self.add_label(1,2,'Asset',columnspan=2)
        self.ENTRIES['loss_class'] = self.add_dropdown_list(1, 3, prettyClasses(), 'Fiat')
        self.ENTRIES['fee_class'] =  self.add_dropdown_list(1, 4, prettyClasses(), '-NO FEE-')
        self.ENTRIES['gain_class'] = self.add_dropdown_list(1, 5, prettyClasses(), 'Fiat')
        self.ENTRIES['loss_asset'] = self.add_entry(2, 3, 'USD', width=24, charLimit=24, format='')
        self.ENTRIES['fee_asset'] =  self.add_entry(2, 4, 'USD', width=24, charLimit=24, format='')
        self.ENTRIES['gain_asset'] = self.add_entry(2, 5, 'USD', width=24, charLimit=24, format='')
        self.add_label(3,2,'Quantity')
        self.ENTRIES['loss_quantity'] = self.add_entry(3, 3, '', width=24, format='pos_float')
        self.ENTRIES['fee_quantity'] =  self.add_entry(3, 4, '', width=24, format='pos_float')
        self.ENTRIES['gain_quantity'] = self.add_entry(3, 5, '', width=24, format='pos_float')
        self.add_label(4,2,'Price (USD)')
        self.ENTRIES['loss_price'] = self.add_entry(4, 3, '', width=24, format='pos_float')
        self.ENTRIES['fee_price'] =  self.add_entry(4, 4, '', width=24, format='pos_float')
        self.ENTRIES['gain_price'] = self.add_entry(4, 5, '', width=24, format='pos_float')
        self.add_label(0,3,'Loss')
        self.add_label(0,4,'Fee')
        self.add_label(0,5,'Gain')
        self.add_label(0,6,'Desc.')
        self.ENTRIES['description'] = self.add_entry(1,6,'', height=8, format='description', columnspan=4)

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
        self.ENTRIES['loss_quantity'].text.trace('w', lambda name, index, mode: self.auto_purchase_sale_price())
        self.ENTRIES['gain_quantity'].text.trace('w', lambda name, index, mode: self.auto_purchase_sale_price())
        self.ENTRIES['loss_price'].text.trace('w', lambda name, index, mode: self.auto_purchase_sale_price())

        #Menu buttons
        self.add_menu_button('Cancel', command=self.close)
        self.add_menu_button('Save', '#0088ff', command=self.save)
        if transaction and not copy:   self.add_menu_button('Delete', "#ff0000", command=self.delete)

        #Runs 'select_type' to appropriately preset the color and existing entry boxes/labels, when editing an existing transaction
        if not transaction:     self.select_type(self.ENTRIES['type'].defaultItem)
        else:                   self.select_type(pretty_trans[transaction.type()])
        
    
    def auto_purchase_sale_price(self): #Updates purchase/sale price when loss_quantity changes for a purchase/sale
        try:
            TYPE = uglyTrans(self.ENTRIES['type'].entry())
            LQ = mpf(self.ENTRIES['loss_quantity'].entry())
            GQ = mpf(self.ENTRIES['gain_quantity'].entry())
            if TYPE == 'purchase':
                self.ENTRIES['gain_price'].set(str(LQ/GQ))
            elif TYPE == 'sale':
                self.ENTRIES['loss_price'].set(str(GQ/LQ))
            elif TYPE == 'trade':
                LP = mpf(self.ENTRIES['loss_price'].entry())
                self.ENTRIES['gain_price'].set(str(LQ*LP/GQ))
        except: return

    def select_type(self, selection):
        type = uglyTrans(selection)
        #COLOR CHANGES
        if selection == self.ENTRIES['type'].defaultItem:
            self.ENTRIES['type'].configure(bg='#000000')
            self.GUI['mainFrame'].configure(bg=palette('accentdark'))
            self.GUI['title'].configure(bg=palette('accentdark'))
        else:
            self.ENTRIES['type'].configure(bg=palette(type))
            self.GUI['mainFrame'].configure(bg=palette(type+'text'))
            self.GUI['title'].configure(bg=palette(type+'text'))
        
        #ENABLING AND DISABLING
        if selection == self.ENTRIES['type'].defaultItem:
            for entry in self.ENTRIES:
                if entry != 'type': self.ENTRIES[entry].disable()
        else:
            for entry in self.ENTRIES:
                if entry == 'type': continue
                elif entry[-6:] == '_class':   
                    if entry[:-6]+'_asset' in valid_transaction_data_lib[type]: self.ENTRIES[entry].enable() #Enable class selection only if asset selection possible
                    else: self.ENTRIES[entry].disable()
                elif entry in valid_transaction_data_lib[type]:   self.ENTRIES[entry].enable()
                else:                                           self.ENTRIES[entry].disable()
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

        self.center_dialogue()

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
        if self.ENTRIES['fee_class'].entry() == self.ENTRIES['fee_class'].defaultItem:
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
        if self.ENTRIES['type'].entry() == self.ENTRIES['type'].defaultItem:
            Message(self, 'ERROR!', 'No transaction type was selected.')    #Message and return here otherwise code breaks w/o a type selected
            return
        #valid datetime format? - NOTE: This also converts the date to unix time
        try:        
            print(TO_SAVE['date'])
            TO_SAVE['date'] = timezone_to_unix(TO_SAVE['date'])
            print(TO_SAVE['date'],'\n\n')
        except:     error = 'Invalid date!'
        #selected a wallet? (start out with nothing selected)
        if TO_SAVE['wallet'] == self.ENTRIES['wallet'].defaultItem: error = 'No wallet was selected.'

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
        has_hash = MAIN_PORTFOLIO.hasTransaction(NEWHASH)
        if (not self.t and has_hash) or (NEWHASH != OLDHASH and has_hash):
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



class WalletManager(Dialogue): #For selecting wallets to edit
    '''Creates a small window for selecting wallets to edit, or creating new wallets'''
    def __init__(self, upper):
        super().__init__(upper, 'Manage Wallets')
        self.walletlist = self.add_selection_list(0, 0, MAIN_PORTFOLIO.walletkeys(), False, False, width=24, button_command=self.edit_wallet)
        self.add_menu_button('Cancel', command=self.close)
        self.add_menu_button('+ Wallet', palette('purchase'), '#000000', command=p(WalletEditor, self))
        self.center_dialogue()
    
    def edit_wallet(self, item, selectionList): #Command executed when button is pressed in the manager
        WalletEditor(self, item)

    def refresh_wallets(self):
        self.walletlist.update_items(MAIN_PORTFOLIO.walletkeys())
        
class WalletEditor(Dialogue): #For editing Wallets
    def __init__(self, walletManager, wallet=''):
        self.wallet = wallet
        if wallet == '': #New wallet
            super().__init__(walletManager, 'Create Wallet')
            self.ENTRY_desc = self.add_entry(1,1,'',format='description',width=24)
        else:
            super().__init__(walletManager, 'Edit '+ wallet +' Wallet')
            self.ENTRY_desc = self.add_entry(1,1,MAIN_PORTFOLIO.wallet(wallet).desc(),format='description',width=24)
        #Wallet Name Entry
        self.add_label(0,0,'Name')
        self.ENTRY_name = self.add_entry(1,0,wallet, width=24, charLimit=24)
        #Wallet Description Entry
        self.add_label(0,1,'Description')
        self.add_menu_button('Cancel', command=self.close)
        self.add_menu_button('Save', '#0088ff', command=self.save)
        if wallet != '':    self.add_menu_button('Delete', "#ff0000", command=self.delete)
        self.center_dialogue()

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
        # CHECKS
        #==============================
        #new ticker will be unique?
        if MAIN_PORTFOLIO.hasWallet(NAME) and NAME != self.wallet:
            Message(self, 'ERROR!', 'A wallet already exists with this name!')
            return
        #Name isn't an empty string?
        if NAME == '':
            Message(self, 'ERROR!', 'Must enter a name for this wallet')
            return

        #WALLET SAVING AND OVERWRITING
        #==============================
        MAIN_PORTFOLIO.add_wallet(Wallet(NAME, DESC))   #Creates the new wallet, or overwrites the existing one's description

        if self.wallet not in ['', NAME]:   #WALLET RE-NAMED
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


class ImportationDialogue(Dialogue): #For selecting wallets to import transactions to
    '''Allows user to specify one or two wallets which transactions will be imported to, for Gemini, Gemini Earn, Coinbase, etc.'''
    def __init__(self, upper, continue_command, wallet_name):
        super().__init__(upper, 'Manage Addresses')
        self.add_label(0,0,wallet_name)
        self.wallet = self.add_dropdown_list(1, 0, MAIN_PORTFOLIO.walletkeys(), ' -SELECT WALLET- ')
        self.add_menu_button('Cancel', command=self.close)
        self.add_menu_button('Import', palette('purchase'), '#000000', command=p(self.complete, continue_command, wallet_name))
        self.center_dialogue()
    
    def complete(self, continue_command, wallet_name):
        result = self.wallet.entry()
        if result == self.wallet.defaultItem:   
            Message(self, 'ERROR!','Must select a '+wallet_name+'.')
            return
        self.close()
        continue_command(result)   #Runs the comm_importGemini or comm_importCoinbase, or whatever command again, but with wallet data
    


##########################################################################################
# TODO TODO TODO - The profile manager needs a total rework with the removal of profiles
##########################################################################################

class ProfileManager(Dialogue):
    def __init__(self, upper):
        super().__init__(upper, 'Manage Profiles')

        #Used when closing, to check whether we should re-render the main portfolio
        self.hashold = hash(json.dumps(MAIN_PORTFOLIO.toJSON(), sort_keys=True))

        self.LIST_profiles = self.add_selection_list(0,0,MAIN_PORTFOLIO.profilekeys(), True, False, 'Select a Profile', width=24, height=10, button_command=self.select_profile)
        self.editProfileButton = self.LIST_profiles.add_menu_button('Rename', palette('transfer'), '#000000', command=self.edit_profile)
        self.LIST_profiles.menu_buttons[1].configure(state='disabled')
        self.LIST_wallets = self.add_selection_list(1,0,MAIN_PORTFOLIO.walletkeys(), True, True, 'Filter by Wallet', width=24, height=10, button_command=self.select_wallet)
        self.LIST_assets = self.add_selection_list(2,0,self.assets_nice_print(MAIN_PORTFOLIO.assetkeys()), True, True, 'Filter by Asset', width=24, height=10, button_command=self.select_asset)
        self.LIST_classes = self.add_selection_list(3,0,self.classes_nice_print(assetclasslib), True, True, 'Filter by Class', width=24, height=10, button_command=self.select_class)
        self.LIST_wallets.add_menu_button('Clear All', command=self.LIST_wallets.clear_selection)
        self.LIST_assets.add_menu_button('Clear All', command=self.LIST_assets.clear_selection)
        self.LIST_classes.add_menu_button('Clear All', command=self.LIST_classes.clear_selection)
        self.LIST_wallets.disable()
        self.LIST_assets.disable()
        self.LIST_classes.disable()
        
        self.add_menu_button('Close', command=self.close)

        self.center_dialogue()

    def select_profile(self, item, selectionList):
        if item in selectionList:
            self.LIST_wallets.set_selection(MAIN_PORTFOLIO.profile(item).wallets())
            self.LIST_assets.set_selection(self.assets_nice_print(MAIN_PORTFOLIO.profile(item).assets()))
            self.LIST_classes.set_selection(self.classes_nice_print(MAIN_PORTFOLIO.profile(item).classes()))
            self.LIST_wallets.enable()
            self.LIST_assets.enable()
            self.LIST_classes.enable()
            self.LIST_profiles.menu_buttons[1].configure(state='normal')
        else:
            self.LIST_wallets.clear_selection()
            self.LIST_assets.clear_selection()
            self.LIST_classes.clear_selection()
            self.LIST_wallets.disable()
            self.LIST_assets.disable()
            self.LIST_classes.disable()
            self.LIST_profiles.menu_buttons[1].configure(state='disabled')
    def select_wallet(self, item, selectionList):
        if item in selectionList:   MAIN_PORTFOLIO.profile(self.LIST_profiles.selection[0]).wallets().append(item)
        else:                       MAIN_PORTFOLIO.profile(self.LIST_profiles.selection[0]).wallets().remove(item)
    def select_asset(self, item, selectionList):
        ID = item.split(' ')[0]+'z'+item.split(' ')[1][1]
        if item in selectionList:   MAIN_PORTFOLIO.profile(self.LIST_profiles.selection[0]).assets().append(ID)
        else:                       MAIN_PORTFOLIO.profile(self.LIST_profiles.selection[0]).assets().remove(ID)
    def select_class(self, item, selectionList):
        for c in assetclasslib:
            if assetclasslib[c]['name'] == item:    ID = c
        if item in selectionList:   MAIN_PORTFOLIO.profile(self.LIST_profiles.selection[0]).classes().append(ID)
        else:                       MAIN_PORTFOLIO.profile(self.LIST_profiles.selection[0]).classes().remove(ID)

    def classes_nice_print(self, toBeNiced):
        niceList = []
        for c in list(toBeNiced):
            niceList.append(assetclasslib[c]['name'])
        return niceList
    def assets_nice_print(self, toBeNiced):
        niceList = []
        for asset in list(toBeNiced):
            niceList.append(asset.split('z')[0] + ' (' + asset.split('z')[1] + ')')
        return niceList

    def refresh_profiles(self):
        self.LIST_profiles.update_items(MAIN_PORTFOLIO.profilekeys())
        self.select_profile(None, [])   #Effectively just clears and disables the whole interface

    def close(self):
        #resets the selected profile, if it was deleted/renamed
        if not MAIN_PORTFOLIO.hasProfile(self.upper.profile):   self.upper.profile = ''
        
        #Re-renders the portfolio, if we've actually made changes
        hashnew = hash(json.dumps(MAIN_PORTFOLIO.toJSON(), sort_keys=True))
        if self.hashold != hashnew:
            self.upper.create_PROFILE_MENU()    #Redoes the dropdown filtered list
            self.upper.metrics()
            self.upper.render()
            self.upper.undo_save()

        self.upper.grab_set()
        self.upper.focus_set()
        self.destroy()




