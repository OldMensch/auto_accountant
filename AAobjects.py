
from AAdialogue import TextBox
from AAlib import *

import copy
import heapq
from functools import partial as p


class Portfolio():
    def __init__(self):
        '''Initializes a Portfolio object, which contains dictionaries and lists of all the below:'''
        self._addresses = {}
        self._assets = {}
        self._transactions = {}
        self._wallets = {}

        self._metrics = {
            'number_of_transactions':   0,
            'number_of_assets':         0,
            'value':                    0,
            'day_change':               0,
            'day%':                     0,
            'week%':                    0,
            'month%':                   0,
            'wallets':                  {},
        }
    
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
    def import_transaction(self, transaction_obj): #Merges simultaneous fills from the same order
        if not self.hasTransaction(transaction_obj.get_hash()): self.add_transaction(transaction_obj)
        else:
            other_trans = self.transaction(transaction_obj.get_hash())
            for part in ['loss','fee','gain']:
                if transaction_obj.get(part+'_quantity') != None and other_trans.get(part+'_quantity') != None:
                    old_quantity = precise(other_trans.get(part+'_quantity'))
                    new_quantity = precise(transaction_obj.get(part+'_quantity'))
                    merged_quantity = old_quantity + new_quantity
                    merged_price = other_trans.get(part+'_price')
                    other_trans._data[part+'_quantity'] =   str(merged_quantity)
                    other_trans._data[part+'_price'] =      str(merged_price)
                if transaction_obj.get(part+'_price') != None and other_trans.get(part+'_price') != None:
                    old_price = precise(other_trans.get(part+'_price'))
                    new_price = precise(transaction_obj.get(part+'_price'))
                    if not appxEq(old_price, new_price):    merged_price = (old_quantity/merged_quantity*old_price)+(new_quantity/merged_quantity*new_price)
                    other_trans._data[part+'_price'] =      str(merged_price)
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
                    trans = TransactionFromDict(t['date'], t['type'], t)
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

        self.fixBadAssetTickers()
    
    def fixBadAssetTickers(self): #Fixes tickers that have changed over time, like LUNA to LUNC, or ones that have multiple names like CELO also being CGLD
        for asset in list(self._assets):
            if asset in forks_and_duplicate_tickers_lib:
                new_ticker = forks_and_duplicate_tickers_lib[asset][0]
                if not self.hasAsset(new_ticker):    self.add_asset(Asset(new_ticker, new_ticker.split('z')[0]))  #Add the werd asset name if it hasn't been added already
                for transaction in list(self.asset(asset)._ledger.values()):
                    if transaction.date() < forks_and_duplicate_tickers_lib[asset][1]:  #Change relevant transaction tickers, IF they occur before a certain "fork" or "renaming" date
                        newTrans = transaction.toJSON()
                        self.delete_transaction(transaction.get_hash()) #Delete the old erroneous transaction
                        for data in ['loss_asset','fee_asset','gain_asset']:    #Update all relevant tickers to the new ticker name
                            if data in newTrans and newTrans[data] == asset:    newTrans[data] = new_ticker
                        self.add_transaction(TransactionFromDict(newTrans['date'],newTrans['type'],newTrans)) #add the fixed transaction back in
                if len(self.asset(asset)._ledger) == 0:  self.delete_asset(asset)

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
    
    #Status functions
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

    def get(self, metric):
        try:    return self._metrics[metric]
        except: return MISSINGDATA

    def prettyPrint(self, info):  #pretty printing for anything   
        try:    return format_general(self.get(info), portfolioinfolib[info]['format'])
        except: return MISSINGDATA
    
    def color(self, info): #returns a tuple of foreground, background color
        color_format = portfolioinfolib[info]['color']
        if color_format == 'profitloss':    
            try:    
                data = self.get(info)
                if   precise(data) > 0: return (palette('profit'), None)
                elif precise(data) < 0: return (palette('loss'), None)
                else:                   return (palette('neutral'), None)
            except: return (None, None)
        return (None, None)

MAIN_PORTFOLIO = Portfolio()
    
class Asset():  
    def __init__(self, tickerclass, name, description=''):
        self.ERROR =        False  
        self._tickerclass = tickerclass
        self._ticker = tickerclass.split('z')[0]
        self._class = tickerclass.split('z')[1]
        self._name = name
        self._description = description

        self._metrics = {}

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

        #This is Market Data (separate from metric data, so we don't delete it upon deleting this asset)
        try:    return precise(marketdatalib[self._tickerclass][info])
        except: pass
        #This is Market Data (separate from metric data, so we don't delete it upon deleting this asset)
        try:    return marketdatalib[self._tickerclass][info]
        except: pass

        #This is metric data
        try:    return precise(self._metrics[info])
        except: pass
        #This is metric data
        try:    return self._metrics[info]
        except: pass
        
        return MISSINGDATA

    def prettyPrint(self, info):
        #This info is basic
        if info == 'ticker':        return self._ticker
        if info == 'name':          return self._name
        if info == 'class':         return assetclasslib[self._class]['name'] #Returns the long-form name for this class

        #This is Market Data
        return format_general(self.get(info), assetinfolib[info]['format'])
    
    def color(self, info): #returns a tuple of foreground, background color
        color_format = assetinfolib[info]['color']
        if color_format == 'profitloss':    
            try:    
                data = self.get(info)
                if   precise(data) > 0: return (palette('profit'), None)
                elif precise(data) < 0: return (palette('loss'), None)
                else:                   return (palette('neutral'), None)
            except: return (None, None)
        return (None, None)

    #JSON functions
    def toJSON(self):
        toReturn = {
            'name':self._name, 
            'description':self._description,
            }
        return toReturn

def TransactionFromDict(date, type, dict): #Handy little function that allows us to create a new transaction based on a data dictionary
    trans = Transaction(date, type)
    trans.set_from_dict(dict)
    return trans

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

            'loss_value':       0,
            'fee_value':        0,
            'gain_value':       0,
            'price':            {},     #Price, value, quantity by asset, for displaying
            'value':            {},
            'quantity':         {},
            'hash':             None,
            'missing':          (False,[])
        }
        self.recalculate()

    #Pre-calculates useful information
    def recalculate(self):
        self.calc_values()
        self.calc_pqv()
        self.calc_hash()
        self.calc_has_required_data()

    def calc_values(self):
        TYPE = self._data['type']
        try:    #Loss value
            if TYPE in ['purchase','purchase_crypto_fee']:  self._data['loss_value'] = precise(self._data['loss_quantity'])
            elif TYPE == 'sale':                            self._data['loss_value'] = precise(self._data['gain_quantity'])
            else:                                           self._data['loss_value'] = precise(self._data['loss_quantity'])*precise(self._data['loss_price'])
        except: pass
        try:    #Fee value
            if TYPE in ['purchase','sale']: self._data['fee_value'] = precise(self._data['fee_quantity'])
            else:                           self._data['fee_value'] = precise(self._data['fee_quantity'])*precise(self._data['fee_price'])
        except: pass
        try:    #Gain value
            if TYPE == 'purchase':  self._data['gain_value'] = precise(self._data['loss_quantity'])
            elif TYPE == 'sale':    self._data['gain_value'] = precise(self._data['gain_quantity'])
            elif TYPE == 'trade':   self._data['gain_value'] = self._data['loss_value']
            else:                   self._data['gain_value'] = precise(self._data['gain_quantity'])*precise(self._data['gain_price'])
        except: pass
    def calc_pqv(self):
        for a in set((self._data['loss_asset'],self._data['fee_asset'],self._data['gain_asset'])):
            if a == None:   continue
            self._data['quantity'][a] = precise(0)
            self._data['value'][a] = precise(0)
            self._data['price'][a] = precise(0)
            try: 
                if a == self._data['loss_asset']:   
                    self._data['quantity'][a] -= precise(self._data['loss_quantity'])
                    self._data['value'][a] -= precise(self._data['loss_value'])
            except: pass
            try: 
                if a ==  self._data['fee_asset']:   
                    self._data['quantity'][a] -= precise(self._data['fee_quantity'])
                    self._data['value'][a] -= precise(self._data['fee_value'])
            except: pass
            try: 
                if a == self._data['gain_asset']:   
                    self._data['quantity'][a] += precise(self._data['gain_quantity'])
                    self._data['value'][a] += precise(self._data['gain_value'])
            except: pass
            self._data['value'][a] = abs(self._data['value'][a])
            if not zeroish(self._data['quantity'][a]):  self._data['price'][a] = abs(self._data['value'][a]/self._data['quantity'][a])
    def calc_hash(self): #Hash Function - A transaction is unique insofar as its date, type, wallet, and three asset types are unique from any other transaction.
        # NOTE: The integer returned from this is different every time you run the program, but unique while it runs
        self._data['hash'] = hash((self._data['date'],self._data['type'],self._data['wallet'],self._data['loss_asset'],self._data['fee_asset'],self._data['gain_asset']))
    def calc_has_required_data(self):
        missing = []
        #We assume that the transaction has a type
        if self._data['fee_asset'] != None and self._data['fee_quantity'] == None:  missing.append('fee_quantity')
        if self._data['fee_asset'] != None and self._data['fee_price'] == None:     missing.append('fee_price')
        for data in valid_transaction_data_lib[self._data['type']]:
            if data[0:4] == 'fee_': continue    #Ignore fees, we already checked them if the exist
            if self._data[data] == None:                                            missing.append(data)
        self._data['missing'] = (len(missing)>0,missing)

    #Comparison operator overrides
    def __eq__(self, __o: object) -> bool:
        if type(__o) != Transaction: return False
        return self.get_hash() == __o.get_hash()
    def __lt__(self, __o: object) -> bool:
        # Basically, we try to sort transactions by date, unless they're the same, then we sort by type, unless that's also the same, then by wallet... and so on.
        S,O = self.date(),__o.date()
        if S!=O:   return S<O
        S,O = self.type(),__o.type()
        if S!=O:   return trans_priority[S]<trans_priority[O]
        # S,O = self.wallet(),__o.wallet()                      #Hopefully I don't need to add the rest in. With them all, sorting goes from ~17ms to ~120ms for ~12000 transactions
        # if S!=O:   return S<O
        # S,O = self.get('loss_asset'),__o.get('loss_asset')
        # if S and O and S!=O: return S<O
        # S,O = self.get('fee_asset'),__o.get('fee_asset')
        # if S and O and S!=O: return S<O
        # S,O = self.get('gain_asset'),__o.get('gain_asset')
        # if S and O and S!=O: return S<O
        return False

    #Modification functions
    def set_from_dict(self, dict): #Modify the values of this transaction based on a dictionary input
        for data in valid_transaction_data_lib[self._data['type']]:     
            if data in dict:    self._data[data] = dict[data]
        self.recalculate()

    #Access functions for basic information
    def date(self):             return self._data['date']
    def type(self):             return self._data['type']
    def wallet(self):           return self._data['wallet']
    def desc(self):             return self._data['description']
    def get_hash(self):         return self._data['hash']
    def price(self, asset):     return self._data['price'][asset]
    def quantity(self, asset):  return self._data['quantity'][asset]
    def value(self, asset):     return self._data['value'][asset]

    def get(self, info, asset=None):    
        if info == 'value':         return self._data['value'][asset]
        elif info == 'quantity':    return self._data['quantity'][asset]
        elif info == 'price':       return self._data['price'][asset]
        try:                        return self._data[info]
        except:                     return None #If we try to access non-existant data, its basically just "None"

    def prettyPrint(self, info, asset=None):  #pretty printing for anything
        if info == 'type':      return pretty_trans[self._data['type']]
        elif info == 'missing':
            toReturn = 'Transaction is missing data: '
            for m in self._data[info][1]:   toReturn += '\'' + transinfolib[m]['name'] + '\', '
            return toReturn[:-2]
        else:                           
            data = self.get(info, asset)
            if data == None:    return MISSINGDATA
            else:               return format_general(data, transinfolib[info]['format'])

    def color(self, info, asset=None): #returns a tuple of foreground, background color
        color_format = transinfolib[info]['color']
        if color_format == 'type':                  return (None, palette(self._data['type']))
        elif color_format == 'accounting':
            if precise(self.get(info, asset)) < 0:  return (palette('loss'), None)
        return (None, None)

    #JSON Functions
    def toJSON(self):
        toReturn = {}
        #Add any valid data that isn't 'None' to the dictionary. Print a warning if we're missing data.
        for data in valid_transaction_data_lib[self._data['type']]:
            if self._data[data] != None:  toReturn[data] = self._data[data]
        return toReturn #This is what we save to JSON for transactions.
    
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



class gain(): #A unit of assets aquired. Could be a purchase, gift_in, income, card_reward, anything with an asset gained.
    def __init__(self, hash, price, quantity, date):
        self._hash =        hash
        self._price =       price
        self._quantity =    quantity
        self._date =        date
        self._accounting_method = setting('accounting_method')
    def __lt__(self, __o: object) -> bool:
        if self._accounting_method == 'hifo':   return self._price > __o._price #"Smallest" element in the minheap is the highest (greatest) price
        if self._accounting_method == 'fifo':   return self._date < __o._date   #"Smallest" element in the minheap is the oldest (least) date
        if self._accounting_method == 'lifo':   return self._date > __o._date   #"Smallest" element in the minheap is the newest (greatest) date

    def disburse(self, quantity):               self._quantity -= quantity

class gain_heap(): #Sorts the gains depending on the accounting method chosen. HIFO, FIFO, LIFO. Uses a heap for maximum efficiency
    def __init__(self):
        self._heap = [] #Stores all gains with minimum at the top
        self._dict = {} #Stores all gains, indexed by their respective transaction's hash. This allows for efficient merging of re-united gains

    def store(self, hash, price, quantity, date):
        if hash in self._dict:  #Re-unite same-source gains, if possible, to be a little more efficient
            self._dict[hash]._quantity += quantity
        else:
            new_gain = gain(hash, price, quantity, date)    #14ms for ~12000 transactions
            heapq.heappush(self._heap, new_gain)            #62ms for ~12000 transactions
            self._dict[hash] = new_gain                     #6ms for ~12000 transactions

    def disburse(self, quantity): #Removes quantity, returns list of the gains which were sold
        gains_removed = []
        remaining_to_disburse = quantity
        while len(self._dict) > 0 and remaining_to_disburse > 0:
            next_gain = self._heap[0]
            almost_equal = appxEq(remaining_to_disburse, next_gain._quantity)
            #We completely disburse a gain
            if remaining_to_disburse > next_gain._quantity or almost_equal:
                if almost_equal:    remaining_to_disburse = 0
                else:               remaining_to_disburse -= next_gain._quantity
                gains_removed.append(next_gain) #Add this gain to what's been disbursed     #2ms for ~12000 transactions
                heapq.heappop(self._heap)       #Remove this gain from the heap array       #30ms for ~12000 transactions
                self._dict.pop(next_gain._hash) #Remove this gain from the dictionary       #4ms for ~12000 transactions
            #We partially disburse a gain - this will always be the last one we disburse from
            else:
                #Adds this gain to what's been disbursed, with its quantity modified to what's been disbursed
                gains_removed.append(gain(next_gain._hash, next_gain._price, remaining_to_disburse, next_gain._date))
                next_gain.disburse(remaining_to_disburse)   #Remove the quantity disbursed
                remaining_to_disburse = 0
                
        #return what's remaining to disburse (to check if its not close enough to zero), and what gains have been removed (to calculate cost basis, taxes, etc.)
        return (remaining_to_disburse, gains_removed)


class GRID(tk.Frame):
    def __init__(self, upper, setSortCommand, bg=palette('grid_bg')):
        super().__init__(self, upper, bg=bg) #Contructs the tk.Frame object
        self.columns = []                           # Dictionary of the columns of the GRID
        self.pagelength = setting('itemsPerPage')   # Number of items to render per page
        self.setSortCommand = setSortCommand    # Command which retrieves a sorted list of assets/transactions/whatever to display

        # Adds the first column in the grid, the column with the '#' and the numbers
        self.item_indices = (
            tk.Label(self.GUI['GRIDframe'], text='#', font=setting('font', 0.75), fg=palette('grid_text'), bg=palette('grid_header'), relief='groove', bd=1),
            TextBox(self, state='readonly', fg=palette('grid_text'), bg=palette('grid_highlight'), height=30,width=1,font=setting('font'))
        )
        self.item_indices[0].grid(row=0, column=0, sticky='NSEW')
        self.item_indices[1].grid(row=0, column=0, sticky='NSEW')
    

    def add_column(self):
        new_index = len(self.columns)
        self.columns.append(
            (
            tk.Button(self, command=p(self.setSortCommand, new_index), font=setting('font', 0.75), fg=palette('grid_text'), bg=palette('grid_header'), relief='groove', bd=1),
            TextBox(self, state='readonly', fg=palette('grid_text'), bg=palette('grid_highlight'), height=30,width=1,font=setting('font'))
        ))
        self.columns[new_index][0].grid(row=0, column=new_index+1, sticky='NSEW')
        self.columns[new_index][1].grid(row=1, column=new_index+1, sticky='NSEW')
    def delete_column(self):
        old = self.columns.pop()    #Remove the tuple from the columns
        old[0].destroy()            #Destroy the header
        old[1].destroy()            #Destroy the label
        
    def set_columns(self, n):
        '''Automatically adds or removes header columns until there are \n\ columns'''
        if n < 0: raise Exception('||ERROR|| Cannot set number of columns to less than 1')
        while len(self.columns) != n:
            if len(self.columns) > n:   self.delete_column()
            else:                       self.add_column()
        
    def grid_render(self, prettyHeaders, sorted, page):
        self.set_columns(len(prettyHeaders))
        
        #Sets the page number
        item_indices = self.item_indices[1]
        item_indices.clear()
        for i in range(self.pagelength*page+1,self.pagelength*(page+1)+1):
            item_indices.insert_text(i)


        for i in range(len(prettyHeaders)):
            #The header
            self.columns[i][0].configure(text=prettyHeaders[i])
            #The data
            textbox = self.columns[i][1]
            textbox.clear()
            textbox

