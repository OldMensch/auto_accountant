from AAlib import *
from AAdialogue import *
from datetime import datetime

from functools import partial as p
from mpmath import mpf as precise
from mpmath import mp


class Message(Dialogue): #Simple text popup
    def __init__(self, upper, title, message, width=32, height=8):
        super().__init__(upper, title)
        self.add_text_display(0, 0, message, width=width, height=height)
        self.add_menu_button('Ok', command=self.close)
        self.center_dialogue()

class Prompt(Dialogue): #Simple text popup, doesn't center menu, waiting for user to add more menu buttons before user then centers the menu
    def __init__(self, upper, title, message, width=32, height=8):
        super().__init__(upper, title)
        self.add_text_display(0, 0, message, width=width, height=height)
        self.add_menu_button('Cancel', command=self.close)


class AssetEditor(Dialogue):    #For editing an asset's name, title, class, and description
    def __init__(self, upper, asset=''):
        self.upper = upper
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
            self.ENTRY_name =       self.add_entry(1,1,PERM['assets'][asset]['name'],width=24,charLimit=24)
            self.DROPDOWN_class =   self.add_dropdown_list(1, 2, self.AssetClasses, '-SELECT CLASS-', assetclasslib[asset.split('z')[1]]['name'])
            self.ENTRY_desc =       self.add_entry(1,3,PERM['assets'][asset]['desc'],format='description',width=24)
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
            TICKER = self.ENTRY_ticker.entry()+'z'+self.AssetClasses[self.DROPDOWN_class.entry()]
        except: #User hasn't selected an asset class
            Message(self, 'ERROR!', 'Must select an asset class')
            return
        #Temporary representation of what our asset will look like
        NAME = self.ENTRY_name.entry()
        DESC = self.ENTRY_desc.entry()
        if self.asset == '':    TRANS = {}
        else:                   TRANS = PERM['assets'][self.asset]['trans']

        # CHECKS
        #==============================
        #new ticker will be unique?
        if TICKER in PERM['assets'] and TICKER != self.asset:
            Message(self, 'ERROR!', 'An asset already exists with the same ticker and asset class!')
            return
        #Ticker isn't an empty string?
        if TICKER == '':
            Message(self, 'ERROR!', 'Must enter a ticker')
            return
        #If not new and the asset class has been changed, make sure all old transactions are still valid under the new asset class
        if self.asset != '' and self.asset.split('z')[1] != TICKER.split('z')[1]:
            for t in PERM['assets'][self.asset]['trans']:
                if PERM['assets'][self.asset]['trans'][t]['type'] not in assetclasslib[TICKER.split('z')[1]]['validTrans']:    #if transaction t's trans. type is NOT one of the valid types...
                    Message(self, 'ERROR!', 'This asset contains transactions which are impossible for asset class \'' + assetclasslib[TICKER.split('z')[1]]['name'] + '\'.')
                    return
        #Name isn't an empty string?
        if NAME == '':
            Message(self, 'ERROR!', 'Must enter a name')
            return


        #ASSET SAVING AND OVERWRITING
        #==============================
        #Create a NEW asset, or overwrite the old one
        PERM['assets'][TICKER] = {'name':NAME, 'desc':DESC, 'trans':TRANS,}

        if self.asset not in ['',TICKER]: #ID CHANGE: The ID was modified. Deletes the old asset
            PERM['assets'].pop(self.asset)  #removal of old asset
            self.updateProfileAssets(TICKER)  #renaming of instances of this asset within profiles

        self.upper.metrics_ASSET(TICKER)
        self.upper.render(self.upper.asset, True)
        self.upper.undo_save()
        self.close()

    def delete(self):
        PERM['assets'].pop(self.asset)      #removal from permanent data
        self.updateProfileAssets()        #removal from profiles
        self.upper.metrics()
        self.upper.render(None, True)
        self.upper.undo_save()
        self.close()

    def updateProfileAssets(self, newID=None):    #Deletes instances of this asset from profiles. Adds 'newID' back into those profiles, if specified
        '''If an asset name is modified, or An asset is deleted, that change has to be applied to profiles. This does that.'''
        profiles = PERM['profiles']
        for p in profiles:
            if self.asset in profiles[p]['assets']:    #if this asset is in there, pop it
                profiles[p]['assets'].pop(profiles[p]['assets'].index(self.asset))
                if newID != None:
                    profiles[p]['assets'].append(newID)

class TransEditor(Dialogue):    #The most important, and most complex editor. For editing transactions' date, type, wallet, second wallet, tokens, price, usd, and description.
    def __init__(self, portfolio, asset=None, transaction=''):
        if asset == None:   raise NameError('||ERROR|| Called \'TransactionEditor\' without specifying \'asset\'')
        self.portfolio, self.asset, self.transaction = portfolio, asset, transaction

        if transaction == '':   
            super().__init__(portfolio, 'Create ' + asset.split('z')[0] + ' Transaction')
            self.DROPDOWN_type = self.add_dropdown_list(1, 0, assetclasslib[asset.split('z')[1]]['validTrans'], '-SELECT TRANS TYPE-', selectCommand=self.select_type)
            self.ENTRY_date = self.add_entry(1, 1, #inserts the current datetime for a new transaction
                    str(datetime.now())[0:4]+'/'
                    +str(datetime.now())[5:7]+'/'
                    +str(datetime.now())[8:10]+' '
                    +str(datetime.now())[11:13]+':'
                    +str(datetime.now())[14:16]+':'
                    +str(datetime.now())[17:19],
                    width=24, format='date')
            self.DROPDOWN_wallets= self.add_dropdown_list(1, 2, PERM['wallets'], '-SELECT SOURCE WALLET-')
            self.DROPDOWN_wallets2 = DropdownList(self.GUI['primaryFrame'], PERM['wallets'], '-SELECT DEST. WALLET-')
            self.ENTRY_tokens = self.add_entry(1,4,'', width=24, format='pos_float')
            self.ENTRY_usd =    EntryBox(self.GUI['primaryFrame'], '', width=24, format='pos_float')
            self.ENTRY_price =  EntryBox(self.GUI['primaryFrame'], '', width=24, format='pos_float')
            self.ENTRY_desc =   self.add_entry(1,7,'', height=8, format='description')
        else:               
            super().__init__(portfolio, 'Edit ' + asset.split('z')[0] + ' Transaction')
            currentTransaction = PERM['assets'][asset]['trans'][transaction]
            self.DROPDOWN_type = self.add_dropdown_list(1, 0, assetclasslib[asset.split('z')[1]]['validTrans'], '-SELECT TRANS TYPE-', currentTransaction['type'], selectCommand=self.select_type)
            self.ENTRY_date = self.add_entry(1, 1, transaction, width=24, format='date')
            self.DROPDOWN_wallets= self.add_dropdown_list(1, 2, PERM['wallets'], '-SELECT SOURCE WALLET-', currentTransaction['wallet'])
            self.ENTRY_tokens = self.add_entry(1,4,currentTransaction['tokens'], width=24, format='pos_float')
            self.ENTRY_desc =   self.add_entry(1,7,currentTransaction['desc'], height=8, format='description')

            #Type-conditional initializations
            if currentTransaction['type'] in ['purchase','sale']:
                self.ENTRY_usd =    EntryBox(self.GUI['primaryFrame'], currentTransaction['usd'], width=24, format='pos_float')
            else:
                self.ENTRY_usd =    EntryBox(self.GUI['primaryFrame'], '', width=24, format='pos_float')
            
            if currentTransaction['type'] in ['gift','expense']:
                self.ENTRY_price =  EntryBox(self.GUI['primaryFrame'], currentTransaction['price'], width=24, format='pos_float')
            else:
                self.ENTRY_price =  EntryBox(self.GUI['primaryFrame'], '', width=24, format='pos_float')

            if currentTransaction['type'] == 'transfer':
                self.DROPDOWN_wallets2 = DropdownList(self.GUI['primaryFrame'], PERM['wallets'], '-SELECT DEST. WALLET-', currentTransaction['wallet2'])
            else:
                self.DROPDOWN_wallets2 = DropdownList(self.GUI['primaryFrame'], PERM['wallets'], '-SELECT DEST. WALLET-')
        
        #Auto price and use always initialized without anything inside them
        self.AUTO_price =   AutoEntryBox(self.GUI['primaryFrame'], '', fg='#ffffff', bg=palette('dark'), width=24, format='auto')
        self.AUTO_usd =     AutoEntryBox(self.GUI['primaryFrame'], '', fg='#ffffff', bg=palette('dark'), width=24, format='auto')

        self.update_auto_price()    #Initializes the boxes to contain the expected information
        self.update_auto_usd()

        #Makes it so editing text in the ENTRY boxes automatically updates the values in the AUTO boxes
        self.ENTRY_tokens.text.trace('w', lambda name, index, mode: self.update_auto_price())
        self.ENTRY_tokens.text.trace('w', lambda name, index, mode: self.update_auto_usd())
        self.ENTRY_usd.text.trace('w', lambda name, index, mode: self.update_auto_price())
        self.ENTRY_price.text.trace('w', lambda name, index, mode: self.update_auto_usd())

        #All of the labels
        self.add_label(0,0,'Type')
        self.add_label(0,1,'Date')
        self.label_wallet = self.add_label(0,2,'Wallet')
        self.label_wallet2 = self.add_label(0,3,'Dest. Wallet')
        self.add_label(0,4,asset.split('z')[0])
        self.label_usd = self.add_label(0,5,'USD')
        self.label_price = self.add_label(0,6,'Price')
        self.add_label(0,7,'Description')

        #Menu buttons
        self.add_menu_button('Cancel', command=self.close)
        self.add_menu_button('Save', '#0088ff', command=self.save)
        if transaction != '':   self.add_menu_button('Delete', "#ff0000", command=self.delete)

        #Runs 'select_type' to appropriately preset the color and existing entry boxes/labels, when editing an existing transaction
        if transaction == '':   self.select_type(self.DROPDOWN_type.defaultItem)
        else:                   self.select_type(currentTransaction['type'])
    
    def update_auto_price(self):
        tokens = self.ENTRY_tokens.entry()
        usd = self.ENTRY_usd.entry()
        if mp.almosteq(precise(tokens),precise(0)):     return  #We have to stop the calculation if tokens == 0, cause then we'd divide by 0
        self.AUTO_price.text.set(precise(usd)/precise(tokens))
    def update_auto_usd(self):
        tokens = self.ENTRY_tokens.entry()
        price = self.ENTRY_price.entry()
        self.AUTO_usd.text.set(precise(tokens)*precise(price))

    def select_type(self, type):
        #COLOR CHANGES
        if type == self.DROPDOWN_type.defaultItem:
            self.DROPDOWN_type.configure(bg='#000000')
            self.GUI['mainFrame'].configure(bg=palette('accentdark'))
            self.GUI['title'].configure(bg=palette('accentdark'))
        else:
            self.DROPDOWN_type.configure(bg=palette(type))
            self.GUI['mainFrame'].configure(bg=palette(type+'text'))
            self.GUI['title'].configure(bg=palette(type+'text'))
        
        #ENTRY BOX & LABEL CHANGES
        if type == 'transfer':
            self.label_wallet.configure(text='Source Wallet')
            self.label_wallet2.grid(column=0, row=3, sticky='NSEW')
            self.DROPDOWN_wallets2.grid(column=1, row=3, sticky='EW')
        else:
            self.label_wallet.configure(text='Wallet')
            self.label_wallet2.grid_forget()
            self.DROPDOWN_wallets2.grid_forget()
        
        if type in ['purchase','sale','gift','expense']:
            self.label_usd.grid(column=0,row=5,sticky='NSEW')
            self.label_price.grid(column=0,row=6,sticky='NSEW')
        else:
            self.label_usd.grid_forget()
            self.label_price.grid_forget()

        if type in ['purchase','sale']:
            self.ENTRY_usd.grid(column=1,row=5,sticky='EW')
            self.AUTO_price.grid(column=1,row=6,sticky='EW')
        else:
            self.ENTRY_usd.grid_forget()
            self.AUTO_price.grid_forget()
        
        if type in ['gift','expense']:
            self.AUTO_usd.grid(column=1,row=5,sticky='EW')
            self.ENTRY_price.grid(column=1,row=6,sticky='EW')
        else:
            self.AUTO_usd.grid_forget()
            self.ENTRY_price.grid_forget()
            
        self.center_dialogue()

    def delete(self):
        PERM['assets'][self.asset]['trans'].pop(self.transaction)  #deletes the transaction
        self.upper.undo_save()                          #creates a savepoint after deleting this
        self.upper.metrics_ASSET(self.asset)            #recalculates metrics for this asset w/o this transaction
        self.upper.market_metrics_ASSET(self.asset)     #recalculates market-based metrics for this asset, w/o this transaction
        self.upper.render(self.asset, True)             #re-renders the main portfolio w/o this transaction
        self.close()
    def save(self):
        #DATA CULLING AND CONVERSION
        #==============================
        DATE = self.ENTRY_date.entry()
        TO_SAVE = {
            'type' : self.DROPDOWN_type.entry(),
            'wallet' : self.DROPDOWN_wallets.entry(),
            'wallet2' : self.DROPDOWN_wallets2.entry(),
            'tokens' : self.ENTRY_tokens.entry(),
            'usd' : self.ENTRY_usd.entry(),
            'price' : self.ENTRY_price.entry(),
            'desc' : self.ENTRY_desc.entry(),
        }

        #selected a type? (has to be checked for prior to removing irrelevant data)
        if TO_SAVE['type'] == self.DROPDOWN_type.defaultItem:
            Message(self, 'ERROR!', 'No transaction type was selected')
            return

        #Removes data irrelevant to this specific transaction type
        for data in list(TO_SAVE):
            if data not in translib[TO_SAVE['type']]:
                TO_SAVE.pop(data)

        # CHECKS
        #==============================
        error = None
        #datetime will be unique?
        if DATE in PERM['assets'][self.asset]['trans'] and DATE != self.transaction:
            error = p(Message, self, 'ERROR!', 'A transaction already exists with this exact time and date for '+self.asset.split('z')[0]+'!')

        #valid datetime format?
        try:        datetime( int(DATE[:4]), int(DATE[5:7]), int(DATE[8:10]), int(DATE[11:13]), int(DATE[14:16]), int(DATE[17:19]) )
        except:     error = p(Message, self, 'ERROR!', 'Invalid date!')

        #selected a wallet? (start out with nothing selected)
        if TO_SAVE['wallet'] == self.DROPDOWN_wallets.defaultItem:
            error = p(Message, self, 'ERROR!', 'No wallet was selected')
        #selected a wallet2? (start out with nothing selected)
        if TO_SAVE['type'] == 'transfer':
            if TO_SAVE['wallet2'] == self.DROPDOWN_wallets2.defaultItem:
                error = p(Message, self, 'ERROR!', 'No destination wallet was selected')
            if TO_SAVE['wallet2'] == TO_SAVE['wallet']:
                error = p(Message, self, 'ERROR!', 'You cannot transfer from a wallet to itself! A transfer from a wallet to itself isn\'t really a transfer at all, yeah? ')

        #Tokens is non-zero?
        if mp.almosteq(precise(TO_SAVE['tokens']),0):
            error = p(Message, self, 'ERROR!', 'Tokens must be non-zero!')

        #USD is non-zero for purchases and sales?
        if TO_SAVE['type'] in ['purchase', 'sale']:
            if mp.almosteq(precise(TO_SAVE['usd']),0):
                error = p(Message, self, 'ERROR!', 'USD must be non-zero!')
        
        #Price is non-zero for gifts and expenses?
        if TO_SAVE['type'] in ['gift','expense']:
            if mp.almosteq(precise(TO_SAVE['price']),0):
                error = p(Message, self, 'ERROR!', 'Price must be non-zero!')

        if error != None:
            error()
            return

        #TRANSACTION SAVING AND OVERWRITING
        #==============================
        #Creates the new transaction or overwrites the old one
        PERM['assets'][self.asset]['trans'][DATE] = TO_SAVE       
        #Deletes the old transaction, if we renamed it
        if self.transaction not in ['', DATE]:        PERM['assets'][self.asset]['trans'].pop(self.transaction)

        self.upper.undo_save()
        self.upper.metrics_ASSET(self.asset)
        self.upper.market_metrics_ASSET(self.asset)
        self.upper.render(self.asset, True)
        self.close()


class AddressManager(Dialogue): #For selecting addresses to edit
    '''Creates a small window for selecting addresses to edit, or creating new addresses'''
    def __init__(self, upper):
        super().__init__(upper, 'Manage Addresses')
        self.LIST_addresses = self.add_selection_list(0, 0, PERM['addresses'], False, False, width=24, truncate=True, button_command=self.edit_address)
        self.add_menu_button('Cancel', command=self.close)
        self.add_menu_button('+ Address', palette('purchase'), '#000000', command=p(AddressEditor, self))
        self.center_dialogue()
    
    def edit_address(self, item, selectionList): #Command executed when button is pressed in the manager
        AddressEditor(self, item)

    def refresh_addresses(self):
        self.LIST_addresses.update_items(PERM['addresses'])

class AddressEditor(Dialogue): #For editing Addresses
    '''Creates an address editing window, with master walletEditor \'walletEditor\', target wallet address list in PERM \'target\', and if editing an old address, address \'address\''''
    def __init__(self, addressManager, address=''):
        self.addressManager = addressManager
        self.address = address
        if address == '':   
            super().__init__(addressManager, 'Create Address')
            self.DROPDOWN_wallets = self.add_dropdown_list(0, 1, PERM['wallets'], '-SELECT WALLET-')
        else:               
            super().__init__(addressManager, 'Edit Address')
            self.DROPDOWN_wallets = self.add_dropdown_list(0, 1, PERM['wallets'], '-SELECT WALLET-', PERM['addresses'][address])
        self.ENTRY_address = self.add_entry(0, 0, address, width=52, charLimit=52)
        self.add_menu_button('Cancel', command=self.close)
        self.add_menu_button('Save', '#0088ff', command=self.save)
        if address != '': self.add_menu_button('Delete', "#ff0000", command=self.delete)
        self.center_dialogue()

    def delete(self):
        PERM['addresses'].pop(self.address)  #remove the old address
        self.addressManager.refresh_addresses()
        self.close()

    def save(self):
        ADDRESS = self.ENTRY_address.entry()
        WALLET = self.DROPDOWN_wallets.entry()
        # CHECKS
        #==============================
        #Name isn't an empty string?
        if ADDRESS == '':
            Message(self, 'ERROR!', 'Must enter something!')
            return
        #new address will be unique?
        if ADDRESS in PERM['addresses']:
            Message(self, 'ERROR!', 'This address already exists!')
            return
        #Selected a wallet?
        if WALLET == '-SELECT WALLET-':
            Message(self, 'ERROR!', 'Must select a wallet!')
            return

        #ADDRESS SAVING
        #==============================
        PERM['addresses'][ADDRESS] = WALLET
        #If we've renamed an address, delete the old one.
        if self.address != '' and self.address != ADDRESS:
            PERM['addresses'].pop(self.address)

        self.addressManager.refresh_addresses()
        self.close()
    

class WalletManager(Dialogue): #For selecting wallets to edit
    '''Creates a small window for selecting wallets to edit, or creating new wallets'''
    def __init__(self, upper):
        super().__init__(upper, 'Manage Wallets')
        self.walletlist = self.add_selection_list(0, 0, PERM['wallets'], False, False, width=24, button_command=self.edit_wallet)
        self.add_menu_button('Cancel', command=self.close)
        self.add_menu_button('+ Wallet', palette('purchase'), '#000000', command=p(WalletEditor, self))
        self.center_dialogue()
    
    def edit_wallet(self, item, selectionList): #Command executed when button is pressed in the manager
        WalletEditor(self, item)

    def refresh_wallets(self):
        self.walletlist.update_items(PERM['wallets'])
        
class WalletEditor(Dialogue): #For editing Wallets
    def __init__(self, walletManager, wallet=''):
        self.walletManager = walletManager
        self.wallet = wallet
        if wallet == '': #New wallet
            super().__init__(walletManager, 'Create Wallet')
            self.ENTRY_desc = self.add_entry(1,1,'',format='description',width=24)
        else:
            super().__init__(walletManager, 'Edit '+ wallet +' Wallet')
            self.ENTRY_desc = self.add_entry(1,1,PERM['wallets'][wallet],format='description',width=24)
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
        if self.wallet in TEMP['metrics'][' PORTFOLIO']['wallets']:   #is the wallet you're deleting used anywhere in the portfolio?
            Message(self, 'Error!', 'You cannot delete this wallet, as it is used by existing transactions.') # If so, you can't delete it. 
            return

        PERM['wallets'].pop(self.wallet)  #destroy the old wallet
        self.updateProfileWallets()
        self.updateAddresses() #If we delete a wallet w/ attached addresses, delete those addresses
        self.walletManager.refresh_wallets()
        self.close()

    def save(self):
        NAME = self.ENTRY_name.entry()
        DESC = self.ENTRY_desc.entry()
        # CHECKS
        #==============================
        #new ticker will be unique?
        for wallet in PERM['wallets']:
            if wallet.lower() == NAME.lower() and wallet.lower() != self.wallet.lower():
                Message(self, 'ERROR!', 'A wallet already exists with this name!')
                return
        #Name isn't an empty string?
        if NAME == '':
            Message(self, 'ERROR!', 'Must enter a name for this wallet')
            return

        #WALLET SAVING AND OVERWRITING
        #==============================
        PERM['wallets'][NAME] = DESC #Creates the new wallet, or overwrites the existing one's description

        if self.wallet != '' and self.wallet != NAME:   #WALLET RE-NAMED
            #destroy the old wallet
            PERM['wallets'].pop(self.wallet)   
            self.updateAddresses(NAME)  
            self.updateTransWallets(NAME)
            self.updateProfileWallets(NAME)
        
        self.upper.refresh_wallets()
        self.close()

    def updateAddresses(self, newWalletName=None):
        '''If a wallet name is modified, or a wallet is deleted, modifies or deletes addresses accordingly'''
        for address in list(PERM['addresses']):
            if PERM['addresses'][address] == self.wallet:
                if newWalletName == None:   PERM['addresses'].pop(address) #If this address's corresponding wallet has been deleted, delete it
                else:                       PERM['addresses'][address] = newWalletName

    def updateTransWallets(self, newWalletName=None):
        '''If a wallet name is modified, applies that to all relevant transactions.'''
        for a in PERM['assets']:
            #if self.wallet in TEMP['metrics'][a]['wallets']:   #skips assets that make no use of this wallet. Increases efficiency.
                for t in PERM['assets'][a]['trans']:
                    currTrans = PERM['assets'][a]['trans'][t]
                    if currTrans['wallet'] == self.wallet:
                        currTrans['wallet'] =  newWalletName            #sets wallet name to new name
                    if currTrans['type'] == 'TRANSFER' and currTrans['wallet2'] == self.wallet:
                        currTrans['wallet2'] =  newWalletName            #sets wallet2 name to new name

    def updateProfileWallets(self, newWalletName=None):
        '''If a wallet name is modified, or a wallet is deleted, applies that to all relevant profiles. '''
        for p in PERM['profiles']:
            wallets = PERM['profiles'][p]['wallets']
            if self.wallet in wallets:    #if this asset is in there, pop it
                wallets.remove(self.wallet)
                if newWalletName != None:
                    wallets.append(newWalletName)


class ProfileManager(Dialogue):
    def __init__(self, upper):
        super().__init__(upper, 'Manage Profiles')
        self.portfolio = upper

        #Used when closing, to check whether we should re-render the main portfolio
        self.hashold = hash(json.dumps(PERM['profiles'], sort_keys=True))

        self.LIST_profiles = self.add_selection_list(0,0,PERM['profiles'], True, False, 'Select a Profile', width=24, height=10, button_command=self.select_profile)
        self.LIST_profiles.add_menu_button('+ Profile', palette('purchase'), '#000000', command=p(ProfileEditor, self))
        self.editProfileButton = self.LIST_profiles.add_menu_button('Rename', palette('transfer'), '#000000', command=self.edit_profile)
        self.LIST_profiles.menu_buttons[1].configure(state='disabled')
        self.LIST_wallets = self.add_selection_list(1,0,PERM['wallets'], True, True, 'Filter by Wallet', width=24, height=10, button_command=self.select_wallet)
        self.LIST_assets = self.add_selection_list(2,0,self.assets_nice_print(PERM['assets']), True, True, 'Filter by Asset', width=24, height=10, button_command=self.select_asset)
        self.LIST_classes = self.add_selection_list(3,0,self.classes_nice_print(assetclasslib), True, True, 'Filter by Class', width=24, height=10, button_command=self.select_class)
        self.LIST_wallets.add_menu_button('Clear All', command=self.LIST_wallets.clear_selection)
        self.LIST_assets.add_menu_button('Clear All', command=self.LIST_assets.clear_selection)
        self.LIST_classes.add_menu_button('Clear All', command=self.LIST_classes.clear_selection)
        self.LIST_wallets.disable()
        self.LIST_assets.disable()
        self.LIST_classes.disable()
        
        self.add_menu_button('Close', command=self.close)

        self.center_dialogue()

    def edit_profile(self):
        ProfileEditor(self, self.LIST_profiles.selection[0])

    def select_profile(self, item, selectionList):
        if item in selectionList:
            self.LIST_wallets.set_selection(PERM['profiles'][item]['wallets'])
            self.LIST_assets.set_selection(self.assets_nice_print(PERM['profiles'][item]['assets']))
            self.LIST_classes.set_selection(self.classes_nice_print(PERM['profiles'][item]['classes']))
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
        if item in selectionList:   PERM['profiles'][self.LIST_profiles.selection[0]]['wallets'].append(item)
        else:                       PERM['profiles'][self.LIST_profiles.selection[0]]['wallets'].remove(item)
    def select_asset(self, item, selectionList):
        ID = item.split(' ')[0]+'z'+item.split(' ')[1][1]
        if item in selectionList:   PERM['profiles'][self.LIST_profiles.selection[0]]['assets'].append(ID)
        else:                       PERM['profiles'][self.LIST_profiles.selection[0]]['assets'].remove(ID)
    def select_class(self, item, selectionList):
        for c in assetclasslib:
            if assetclasslib[c]['name'] == item:    ID = c
        if item in selectionList:   PERM['profiles'][self.LIST_profiles.selection[0]]['classes'].append(ID)
        else:                       PERM['profiles'][self.LIST_profiles.selection[0]]['classes'].remove(ID)

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
        self.LIST_profiles.update_items(PERM['profiles'])
        self.select_profile(None, [])   #Effectively just clears and disables the whole interface

    def close(self):
        #resets the selected profile, if it was deleted/renamed
        if self.portfolio.profile not in PERM['profiles']:      self.portfolio.profile = ''
        
        #Re-renders the portfolio, if we've actually made changes
        hashnew = hash(json.dumps(PERM['profiles'], sort_keys=True))
        if self.hashold != hashnew:
            self.portfolio.create_PROFILE_MENU()    #Redoes the dropdown filtered list
            self.portfolio.metrics()
            self.portfolio.render(self.portfolio.asset, True)
            self.portfolio.undo_save()

        self.portfolio.grab_set()
        self.portfolio.focus_set()
        self.destroy()

class ProfileEditor(Dialogue):
    def __init__(self, profileManager, profile=''):
        self.profileManager = profileManager
        self.profile = profile

        if profile == '': #New profile
            super().__init__(profileManager, 'Create Profile')
        else:
            super().__init__(profileManager, 'Edit Profile')
        self.ENTRY_name = self.add_entry(1,0,profile, width=24, charLimit=24)
        self.add_menu_button('Cancel', command=self.close)
        self.add_menu_button('Save', '#0088ff', command=self.save)
        if profile != '':    self.add_menu_button('Delete', "#ff0000", command=self.delete)
        self.center_dialogue()

    def delete(self):
        PERM['profiles'].pop(self.profile)
        self.profileManager.refresh_profiles()
        self.close()

    def save(self):
        NAME = self.ENTRY_name.entry()

        #CHECKS
        #====================
        #Name is unique?
        if NAME in PERM['profiles'] and NAME != self.profile:
            Message(self, 'ERROR!', 'A profile already exists with this name!')
            return
        #Name isn't an empty string?
        if NAME == '':
            Message(self, 'ERROR!', 'Must enter a name for this profile')
            return
        
        #SAVING AND OVERWRITING
        if self.profile == '':    #New profile
            PERM['profiles'][NAME] = { 'wallets':[], 'classes':[], 'assets':[] }
        elif NAME != self.profile:  #Renamed profile
            PERM['profiles'][NAME] = PERM['profiles'][self.profile]
            PERM['profiles'].pop(self.profile)
        self.profileManager.refresh_profiles()
        self.close()




