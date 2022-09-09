from AAlib import *

from mpmath import mpf as precise
from mpmath import mp
from datetime import datetime

import copy


class Portfolio():
    def __init__(self):
        '''Initializes a Portfolio object, which contains dictionaries and lists of all the below:'''
        self._addresses = {}
        self._assets = {}
        self._transactions = {}
        self._wallets = {}
    
    #Modification Functions
    def clear(self):
        self._addresses.clear()
        self._assets.clear()
        self._transactions.clear()
        self._wallets.clear()

    def add_address(self, address_obj):
        self._addresses[address_obj.address()] = address_obj
    def add_asset(self, asset_obj):
        self._assets[asset_obj.tickerclass()] = asset_obj
    def add_transaction(self, transaction_obj):
        if self.hasTransaction(transaction_obj.get_hash()): print('||WARNING|| Overwrote transaction with same hash.')
        self._transactions[transaction_obj.get_hash()] = transaction_obj
        a = (transaction_obj.get('loss_asset'),transaction_obj.get('fee_asset'),transaction_obj.get('gain_asset'))
        if a[0] != None:    self.asset(a[0]).add_transaction(transaction_obj) #Adds this transaction to loss asset's ledger
        if a[1] != None:    self.asset(a[1]).add_transaction(transaction_obj) #Adds this transaction to fee asset's ledger
        if a[2] != None:    self.asset(a[2]).add_transaction(transaction_obj) #Adds this transaction to gain asset's ledger
    def add_wallet(self, wallet_obj):
        self._wallets[wallet_obj.name()] = wallet_obj

    def delete_address(self, address):          self._addresses.pop(address)
    def delete_asset(self, asset):              self._assets.pop(asset)
    def delete_transaction(self, transaction_hash):  
        transaction_obj = self._transactions.pop(transaction_hash) #Removes transaction from the portfolio itself
        #Removes transaction from relevant asset ledgers
        assets = set([transaction_obj.get('loss_asset'),transaction_obj.get('fee_asset'),transaction_obj.get('gain_asset')])
        for a in assets: 
            if a != None: self.asset(a).delete_transaction(transaction_hash) #Adds this transaction to loss asset's ledger
    def delete_wallet(self, wallet):            self._wallets.pop(wallet)
    


    #JSON functions
    def loadJSON(self, JSON, merge=False, overwrite=False): #Loads JSON data, erases any existing data first
        
        #If loading...                      clear everything,  load the new data.
        #If merging and overwriting,                           load the new data.
        #If merging and NOT overwriting,                       load the new data, skipping duplicates.

        if not merge:   self.clear()

        # ADDRESSES
        try:
            for address in JSON['addresses']:
                if (merge and not overwrite) and self.hasAddress(address):    continue
                a = JSON['addresses'][address]
                self.add_address(Address(address, a['wallet']))
        except: print('||WARNING|| Failed to load addresses from JSON.')
        # ASSETS
        try:
            for asset in JSON['assets']:
                if (merge and not overwrite) and self.hasAsset(asset):    continue
                a = JSON['assets'][asset]
                self.add_asset(Asset(asset, a['name'], a['description']))
        except: print('||WARNING|| Failed to load assets from JSON.')
        # TRANSACTIONS
        try:
            for t in JSON['transactions']:
                try:
                    #Creates a rudimentary transaction, then fills in the data from the JSON. Bad data is cleared upon saving, not loading.
                    trans = Transaction(t['date'], t['type'])
                    for data in t:    trans._data[data] = t[data]   #Overwrites all the optional data
                    trans.calc_values() #We gotta do this here, since we're loading arbitrary data AFTER initializing the transaction, when it normally does this
                    if (merge and not overwrite) and self.hasTransaction(trans.get_hash()):    continue     #Don't overwrite identical transactions
                    self.add_transaction(trans)
                except: 
                    print('||WARNING|| Transaction ' + t['date'] + ' failed to load.')
        except: print('||WARNING|| Failed to load transactions from JSON.')
        # WALLETS
        try:
            for wallet in JSON['wallets']:
                if (merge and not overwrite) and self.hasWallet(wallet):    continue
                w = JSON['wallets'][wallet]
                self.add_wallet(Wallet(wallet, w['description']))
        except: print('||WARNING|| Failed to load wallets from JSON.')

    def toJSON(self):
        toReturn = {
            'addresses':{},
            'assets':{},
            'transactions':[],
            'wallets':{},
        }
        for address in self.addresses():        toReturn['addresses']    [address.address()]   = address.toJSON()
        for asset in self.assets():             toReturn['assets']       [asset.tickerclass()] = asset.toJSON()
        for transaction in self.transactions(): toReturn['transactions'].append(transaction.toJSON())
        for wallet in self.wallets():           toReturn['wallets']      [wallet.name()]       = wallet.toJSON()

        return copy.deepcopy(toReturn) #TODO TODO TODO: Not sure if deepcopy is necessary here. Should test this. Might be needlessly inefficient.
    
    #Informational functions
    def isEmpty(self):  return {} == self._addresses == self._assets == self._transactions == self._wallets

    def hasAsset(self, asset):              return asset in self._assets
    def hasTransaction(self, transaction):  return transaction in self._transactions
    def hasAddress(self, address):          return address in self._addresses
    def hasWallet(self, wallet):            return wallet in self._wallets
    
    #Access functions:
    def address(self, address):     return self._addresses[address]
    def addresses(self):            return self._addresses.values()
    def addresskeys(self):          return self._addresses

    def asset(self, asset):         return self._assets[asset]
    def assets(self):               return self._assets.values()
    def assetkeys(self):            return self._assets

    def transaction(self, transaction):  return self._transactions[transaction]
    def transactions(self):              return self._transactions.values()

    def wallet(self, wallet):       return self._wallets[wallet]
    def wallets(self):              return self._wallets.values()
    def walletkeys(self):           return self._wallets

MAIN_PORTFOLIO = Portfolio()
    

class Asset():  
    def __init__(self, tickerclass, name, description=''):
        self.ERROR =        False  
        self._tickerclass = tickerclass
        self._ticker = tickerclass.split('z')[0]
        self._class = tickerclass.split('z')[1]
        self._name = name
        self._description = description

        self._ledger = {} #A dictionary of all the transactions for this asset. Mainly only for making rendering more efficient.

    #Modification functions
    def add_transaction(self, transaction_obj): self._ledger[transaction_obj.get_hash()] = transaction_obj
    def delete_transaction(self, transaction_hash): self._ledger.pop(transaction_hash)

    #Access functions
    def tickerclass(self):          return self._tickerclass
    def ticker(self):               return self._ticker
    def assetClass(self):           return self._class
    def name(self):                 return self._name
    def desc(self):                 return self._description

    def get(self, info):
        #This info is basic
        if info == 'ticker':        return self._ticker
        if info == 'name':          return self._name
        if info == 'class':         return self._class

        #This is Market Datas
        try:    return precise(marketdatalib[self._tickerclass][info])
        except: pass

        #None of the basic data worked. Try TEMP data:
        try:    return precise(TEMP['metrics'][self._tickerclass][info])
        except: pass
        
        return MISSINGDATA

    def prettyPrint(self, info):
        #This info is basic
        if info == 'ticker':        return self._ticker
        if info == 'name':          return self._name
        if info == 'class':         return assetclasslib[self._class]['name'] #Returns the long-form name for this class

        #This is Market Data
        return format_general(self.get(info), assetinfolib[info]['format'])

    #JSON functions
    def toJSON(self):
        toReturn = {
            'name':self._name, 
            'description':self._description,
            }
        return toReturn
    
class Transaction():
    def __init__(self, date, type, wallet=None, description='', loss=[None,None,None], fee=[None,None,None], gain=[None,None,None]):

        #Set to true for transfers that don't have a partner, and transfers with missing data. Stops metrics() short, and tells the renderer to color this RED
        self.ERROR =    False  
        self.ERR_MSG =  ''

        #Fully-encompassing data dictionary
        self._data = {
            'date' :            date,
            'type' :            type,
            'wallet' :          wallet,
            'description' :     description,

            'loss_asset' :      loss[0],
            'loss_quantity' :   loss[1],
            'loss_price' :      loss[2],
            'fee_asset' :       fee[0],
            'fee_quantity' :    fee[1],
            'fee_price' :       fee[2],
            'gain_asset' :      gain[0],
            'gain_quantity' :   gain[1],
            'gain_price' :      gain[2],

            'loss_value':       '0',
            'fee_value':        '0',
            'gain_value':       '0',
        }
        self.calc_values()

    #Pre-calculates useful information
    def calc_values(self):
        
        if self._data['type'] in ['purchase','sale']: 
            #Loss and gain value identical for purchases and sales, fee value is its own quantity either way.
            if self._data['type'] == 'sale':         self._data['loss_value'] = self._data['gain_value'] = self._data['gain_quantity']
            if self._data['type'] == 'purchase':     self._data['loss_value'] = self._data['gain_value'] = self._data['loss_quantity']
            self._data['fee_value'] = self._data['fee_quantity']
        elif self._data['type'] == 'trade':
            try: self._data['loss_value'] = str(precise(self._data['loss_quantity'])*precise(self._data['loss_price']))
            except: pass
            try: self._data['fee_value'] = str(precise(self._data['fee_quantity'])*precise(self._data['fee_price']))
            except: pass
            self._data['gain_value'] = self._data['loss_value'] #What's lost is worth as much as what's gained, ignoring fees
        else:
            #Loss value
            try:    self._data['loss_value'] = str(precise(self._data['loss_quantity'])*precise(self._data['loss_price']))
            except: pass

            #Fee value
            try:    self._data['fee_value'] = str(precise(self._data['fee_quantity'])*precise(self._data['fee_price']))
            except: pass

            #Gain value
            try:    self._data['gain_value'] = str(precise(self._data['gain_quantity'])*precise(self._data['gain_price']))
            except: pass

    #Informative functions
    def hasMinInfo(self):
        if self._data['type'] == None: return (False,'Transaction has unknown type.') # No type is an obvious issue
        if self._data['fee_asset'] != None and self._data['fee_quantity'] == None: #Fee asset exists, but missing quantity or price
            return (False,'\'Fee Asset\' is specified, but is missing required data: \'Fee Quantity\'.')
        if self._data['fee_asset'] != None and self._data['fee_price'] == None: #Fee asset exists, but missing quantity or price
            return (False,'\'Fee Asset\' is specified, but is missing required data: \'Fee Price\'.')
        for data in valid_transaction_data_lib[self._data['type']]:
            if data[0:4] == 'fee_': continue    #Ignore fees since they're optional
            if self._data[data] == None: return (False,'Missing required data: \'' + transinfolib[data]['name'] + '\'.')
        return (True,'')

    #Access functions for basic information
    def date(self):         return self._data['date']
    def type(self):         return self._data['type']
    def wallet(self):       return self._data['wallet']
    def desc(self):         return self._data['description']
    def value(self, asset):
        net_value = precise(0)
        try: 
            if asset == self._data['loss_asset']:   net_value -= precise(self._data['loss_value'])
        except: pass
        try: 
            if asset ==  self._data['fee_asset']:   net_value -= precise(self._data['fee_value'])
        except: pass
        try: 
            if asset == self._data['gain_asset']:   net_value += precise(self._data['gain_value'])
        except: pass
        return abs(net_value)
    def quantity(self, asset):
        net_quantity = precise(0)
        try: 
            if asset == self._data['loss_asset']:   net_quantity -= precise(self._data['loss_quantity'])
        except: pass
        try: 
            if asset ==  self._data['fee_asset']:   net_quantity -= precise(self._data['fee_quantity'])
        except: pass
        try: 
            if asset == self._data['gain_asset']:   net_quantity += precise(self._data['gain_quantity'])
        except: pass
        return net_quantity
    def price(self, asset):
        v = self.value(asset)
        q = self.quantity(asset)
        if mp.almosteq(q, 0):   return precise(0)
        return abs(v/q)

    def get(self, info, asset=None):    
        if info == 'value':         return self.value(asset)
        elif info == 'quantity':    return self.quantity(asset)
        elif info == 'price':       return self.price(asset)
        try:                        return self._data[info]
        except:                     return None #If we try to access non-existant data, its basically just "None"

    def prettyPrint(self, info, asset=None):  #pretty printing for anything
        if info == 'type':      return pretty_trans[self._data['type']]
        else:                           
            data = self.get(info, asset)
            if data == None:    return MISSINGDATA
            else:               return format_general(data, transinfolib[info]['format'])

    #JSON Functions
    def toJSON(self):
        toReturn = {}
        #Add any valid data that isn't 'None' to the dictionary. Print a warning if we're missing data.
        for data in valid_transaction_data_lib[self._data['type']]:
            if self._data[data] != None:  toReturn[data] = self._data[data]
        return toReturn #This is what we save to JSON for transactions.
    
    #Hash Function - A transaction is unique insofar as its date, type, wallet, and three asset types are unique from any other transaction.
    def get_hash(self):
        # NOTE: The integer returned from this is different every time you run the program, but unique while it runs
        #NOTE: Can't use just prices instead of quantities for hashing... mutliple fills can be the same price sometimes. These might be worth lumping together though.
        return hash((self._data['date'],self._data['type'],self._data['wallet'],self._data['loss_asset'],self._data['fee_asset'],self._data['gain_asset'],self._data['loss_quantity'],self._data['fee_quantity'],self._data['gain_quantity']))

class Wallet():
    def __init__(self, name, description=''):
        self._name = name
        self._description = description

    #access functions
    def name(self): return self._name
    def desc(self): return self._description

    #JSON Function
    def toJSON(self):   return {'description':self._description}

class Address():
    def __init__(self, address, wallet):
        self._address = str(address)
        self._wallet = str(wallet)
        
    #access functions
    def address(self):  return self._address
    def wallet(self):   return self._wallet

    #JSON Function
    def toJSON(self):   return {'wallet':self._wallet}


