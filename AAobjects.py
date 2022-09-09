
from AAdialogue import TextBox
from AAlib import *

import copy
import heapq
from functools import partial as p


class Wallet():
    def __init__(self, name:str, description:str=''):
        self._name = name
        self._description = description

    #access functions
    def name(self) -> str: return self._name
    def desc(self) -> str: return self._description

    #JSON Function
    def toJSON(self) -> dict:   return {'description':self._description}

class Transaction():
    def __init__(self, unix_time:int=None, type:str=None, wallet:str=None, description:str='', loss:tuple=(None,None,None), fee:tuple=(None,None,None), gain:tuple=(None,None,None)):

        #Set to true for transfers that don't have a partner, and transfers with missing data. Stops metrics() short, and tells the renderer to color this RED
        self.ERROR =    False  
        self.ERR_MSG =  ''

        #Fully-encompassing data dictionary
        self._data = {
            'date' :            unix_time,
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

            'hash':             None,
            'missing':          (False,[]),
            'dest_wallet':      None,
        }
        self._metrics = {
            'date':             None,
            'loss_quantity' :   None,
            'fee_quantity' :    None,
            'gain_quantity' :   None,
            'loss_price' :      None,
            'fee_price' :       None,
            'gain_price' :      None,
            'loss_value':       0,
            'fee_value':        0,
            'gain_value':       0,

            'basis_price':      0,      #The cost basis price 

            'price':    {},     #Price, value, quantity by asset, for displaying
            'value':    {},
            'quantity': {}
            }
        if type: self.recalculate()

    #Pre-calculates useful information
    def recalculate(self):
        self.calc_hash()    #NOTE: Lag is ~4ms for ~4000 transactions
        #We try to calculate this, because otherwise, if a transaction is missing some data, it won't display its ISO date
        try:    self.calc_iso_date()    #NOTE: Lag is ~30ms for ~4000 transactions
        except: pass
        self.calc_has_required_data()
        # Don't continue performing calculations if we're missing data!
        if self._data['missing'][0]:    return   #NOTE: Lag is ~2ms for ~4000 transactions
        self.calc_metrics()

    def calc_hash(self): #Hash Function - A transaction is unique insofar as its date, type, wallet, and three asset types are unique from any other transaction.
        self._data['hash'] = hash((self._data['date'],self._data['type'],self._data['wallet'],self._data['loss_asset'],self._data['fee_asset'],self._data['gain_asset']))
    def calc_has_required_data(self):
        missing = []
        #We assume that the transaction has a type
        if self._data['fee_asset'] != None and self._data['fee_quantity'] == None:  missing.append('fee_quantity')
        if self._data['fee_asset'] != None and self._data['fee_price'] == None:     missing.append('fee_price')
        for data in valid_transaction_data_lib[self._data['type']]:
            if data in ('fee_asset','fee_quantity','fee_price'):    continue    #Ignore fees, we already check them
            if self._data[data] == None:                            missing.append(data)
        self._data['missing'] = (len(missing)!=0,missing)
    def calc_iso_date(self):
        # DATE - convert the transaction's unix timestamp to ISO format, in your specified local timezone
        self._metrics['date'] = unix_to_local_timezone(self._data['date'])
    def calc_metrics(self):
        # PRECISE METRICS - we pre-convert the data strings to MPFs to significantly increase performance
        for data in ('loss_quantity','loss_price','fee_quantity','fee_price','gain_quantity','gain_price'):     #NOTE: Lag is ~11ms for ~4000 transactions
            d = self._data[data]
            if d:   self._metrics[data] = mpf(d)
        
        # VALUES - the USD value of the quantity of the loss, fee, and gain at time of transaction
        TYPE = self._data['type']
        LQ,FQ,GQ = self._metrics['loss_quantity'],self._metrics['fee_quantity'],self._metrics['gain_quantity']
        LP,FP,GP = self._metrics['loss_price'], self._metrics['fee_price'], self._metrics['gain_price']
        LV,FV,GV = 0,0,0
        #Loss value
        if   TYPE in ('purchase','purchase_crypto_fee'):    LV = LQ
        elif TYPE == 'sale':                                LV = GQ
        elif LQ and LP:                                     LV = LQ*LP
        #Fee value
        if   TYPE in ['purchase','sale']:                   FV = FQ
        elif GQ and FP:                                     FV = FQ*FP
        #Gain value
        if   TYPE in ('purchase','purchase_crypto_fee'):    GV = LQ
        elif TYPE == 'sale':                                GV = GQ
        elif TYPE == 'trade':                               GV = LV
        elif GQ and GP:                                     GV = GQ*GP
        
        self._metrics['loss_value'],self._metrics['fee_value'],self._metrics['gain_value'] = LV,FV,GV

        # PRICE QUANTITY VALUE - The price, quantity, and value
        LA,FA,GA = self._data['loss_asset'],self._data['fee_asset'],self._data['gain_asset']
        for a in set((LA,FA,GA)):
            if a == None:   continue
            P,Q,V = 0,0,0
            if a == LA:
                Q -= LQ
                V -= LV
            if a == FA:
                Q -= FQ
                V -= FV
            if a == GA:
                Q += GQ
                V += GV
            if Q!=0 and V!=0:  P = V/Q 
            V = abs(V)

            self._metrics['price'][a], self._metrics['quantity'][a], self._metrics['value'][a] = P,Q,V

        # BASIS PRICE - The price of the cost basis of this transaction, if it is a gain
        if   TYPE in ('purchase','purchase_crypto_fee'):    self._metrics['basis_price'] = (LV+FV)/GQ     # Purchase cost basis includes fee
        elif TYPE == 'trade':                               self._metrics['basis_price'] = LV/GQ          # Trade price doesn't include fee
        elif GP:                                            self._metrics['basis_price'] = GP             # Gain price is defined already

    #Comparison operator overrides
    def __eq__(self, __o: object) -> bool:
        if type(__o) != Transaction: return True
        return self.get_hash() == __o.get_hash()
    def __lt__(self, __o: object) -> bool:
        # Basically, we try to sort transactions by date, unless they're the same, then we sort by type, unless that's also the same, then by wallet... and so on.
        S,O = self.unix_date(),__o.unix_date()
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

    #Access functions for basic information
    def unix_date(self) -> int:         return self._data['date']
    def date(self) -> str:              return self._metrics['date']
    def type(self) -> str:              return self._data['type']
    def wallet(self) -> str:            return self._data['wallet']
    def desc(self) -> str:              return self._data['description']
    def get_hash(self) -> int:          return self._data['hash']
    def price(self, asset:str) -> str:      return self._metrics['price'][asset]
    def quantity(self, asset:str) -> str:   return self._metrics['quantity'][asset]
    def value(self, asset:str) -> str:      return self._metrics['value'][asset]

    def get(self, info:str, asset:str=None) -> str:    
        if info in ['value','quantity','price']:    
            try:    return self._metrics[info][asset]
            except: return MISSINGDATA
        try:                        return self._data[info]
        except:                     return None #If we try to access non-existant data, its basically just "None"
    def precise(self, info:str) -> mpf:
        try:    return self._metrics[info]
        except: return None

    def prettyPrint(self, info:str, asset:str=None) -> str:  #pretty printing for anything
        if info == 'date':      return self.date()
        elif info == 'type':    return pretty_trans[self._data['type']]
        elif info == 'missing':
            toReturn = 'Transaction is missing data: '
            for m in self._data[info][1]:   toReturn += '\'' + info_format_lib[m]['name'] + '\', '
            return toReturn[:-2]
        else:                           
            data = self.get(info, asset)
            if data == None:    return MISSINGDATA
            else:               return format_general(data, info_format_lib[info]['format'])

    def color(self, info:str, asset:str=None) -> tuple: #returns a tuple of foreground, background color
        if self.ERROR:  return (palette('errortext'),palette('error'))
        color_format = info_format_lib[info]['color']
        if color_format == 'type':                  return (None, palette(self._data['type']))
        elif color_format == 'accounting':
            if self.get(info, asset) < 0:  return (palette('loss'), None)
        return (None, None)

    def pretty(self, info:str, asset:str=None) -> tuple: #Returns a tuple of pretty info, foreground color, and background color
        color = self.color(info, asset)
        return (self.prettyPrint(info, asset), color[0], color[1])

    #JSON Functions
    def toJSON(self) -> dict:
        toReturn = {}
        #Add any valid data that isn't 'None' to the dictionary. Print a warning if we're missing data.
        for data in valid_transaction_data_lib[self._data['type']]:
            if self._data[data] != None:  toReturn[data] = self._data[data]
        return toReturn #This is what we save to JSON for transactions.
   
def trans_from_dict(dict:dict): #Allows for the creation of a transaction directly from a dictionary
    new_trans = Transaction()
    new_trans._data.update(dict)
    new_trans.recalculate()
    return new_trans

class Asset():  
    def __init__(self, tickerclass:str, name:str, description:str=''):
        self.ERROR =        False  
        self._tickerclass = tickerclass
        self._ticker = tickerclass.split('z')[0]
        self._class = tickerclass.split('z')[1]
        self._name = name
        self._description = description

        self._metrics = {}

        self._ledger = {} #A dictionary of all the transactions for this asset. Mainly only for making rendering more efficient.

    #Modification functions
    def add_transaction(self, transaction_obj:Transaction): self._ledger[transaction_obj.get_hash()] = transaction_obj
    def delete_transaction(self, transaction_hash:int):     self._ledger.pop(transaction_hash)

    #Access functions
    def tickerclass(self) -> str:   return self._tickerclass
    def ticker(self) -> str:        return self._ticker
    def assetClass(self) -> str:    return self._class
    def name(self) -> str:          return self._name
    def desc(self) -> str:          return self._description

    def get(self, info:str) -> str:
        #This info is basic
        if info == 'ticker':        return self._ticker
        if info == 'name':          return self._name
        if info == 'class':         return self._class

        #This is metric data
        try:    return self._metrics[info]
        except: pass

        #This is Market Data (separate from metric data, so we don't delete it upon deleting this asset)
        try:    return marketdatalib[self._tickerclass][info]
        except: pass
        
        return MISSINGDATA
    
    def precise(self, info:str) -> mpf:
        #This is metric data
        try:    return self._metrics[info]
        except: pass
        #This is Market Data (separate from metric data, so we don't delete it upon deleting this asset)
        try:    return mpf(marketdatalib[self._tickerclass][info])
        except: pass

    def prettyPrint(self, info:str) -> str:
        #This info is basic
        if info == 'ticker':        return self._ticker
        if info == 'name':          return self._name
        if info == 'class':         return assetclasslib[self._class]['name'] #Returns the long-form name for this class

        #This is Market Data
        return format_general(self.precise(info), info_format_lib[info]['format'])
    
    def color(self, info:str, ignoreError:bool=False) -> tuple: #returns a tuple of foreground, background color
        if self.ERROR and not ignoreError:  return (palette('errortext'),palette('error'))
        color_format = info_format_lib[info]['color']
        if color_format == 'profitloss':    
            try:    
                data = self.precise(info)
                if   data > 0: return (palette('profit'), None)
                elif data < 0: return (palette('loss'), None)
                else:                   return (palette('neutral'), None)
            except: return (None, None)
        return (None, None)

    def pretty(self, info:str, uselessInfo=None, ignoreError:bool=False) -> tuple: #Returns a tuple of pretty info, foreground color, and background color
        color = self.color(info, ignoreError)
        return (self.prettyPrint(info), color[0], color[1])

    #JSON functions
    def toJSON(self) -> dict:
        toReturn = {
            'name':self._name, 
            'description':self._description,
            }
        return toReturn

class Portfolio():
    def __init__(self):
        '''Initializes a Portfolio object, which contains dictionaries and lists of all the below:'''
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
        self._assets.clear()
        self._transactions.clear()
        self._wallets.clear()

    def add_asset(self, asset_obj:Asset):
        self._assets[asset_obj.tickerclass()] = asset_obj
    def add_transaction(self, transaction_obj:Transaction):
        if self.hasTransaction(transaction_obj.get_hash()): print('||WARNING|| Overwrote transaction with same hash.', transaction_obj.get_hash())
        self._transactions[transaction_obj.get_hash()] = transaction_obj
        for a in set((transaction_obj.get('loss_asset'),transaction_obj.get('fee_asset'),transaction_obj.get('gain_asset'))):
            if a != None: self.asset(a).add_transaction(transaction_obj) #Adds this transaction to loss asset's ledger
    def import_transaction(self, transaction_obj:Transaction): #Merges simultaneous fills from the same order
        transaction_obj._fills = 1
        if not self.hasTransaction(transaction_obj.get_hash()): self.add_transaction(transaction_obj)
        else:
            other_trans = self.transaction(transaction_obj.get_hash())
            other_trans._fills += 1
            print('||INFO|| ' + other_trans.wallet() + ' transaction at time ' + other_trans.date() + ' had '+str(other_trans._fills)+' simultaneous fills. They were merged.')
            for part in ['loss','fee','gain']:
                NQ,OQ = transaction_obj.precise(part+'_quantity'), other_trans.precise(part+'_quantity')
                NP,OP = transaction_obj.precise(part+'_price'), other_trans.precise(part+'_price')
                if NQ and OQ:
                    merged_quantity = OQ + NQ
                    other_trans._data[part+'_quantity'] =   str(merged_quantity)
                if NP and OP and not appxEqPrec(OP, NP):
                    other_trans._data[part+'_price'] = str((OQ/merged_quantity*OP)+(NQ/merged_quantity*NP)) #Weighted average of prices
            other_trans.recalculate()
    def add_wallet(self, wallet_obj:Wallet):
        self._wallets[wallet_obj.name()] = wallet_obj


    def delete_asset(self, asset:str):              self._assets.pop(asset)
    def delete_transaction(self, transaction_hash:int):  
        transaction_obj = self._transactions.pop(transaction_hash) #Removes transaction from the portfolio itself
        #Removes transaction from relevant asset ledgers
        assets = set([transaction_obj.get('loss_asset'),transaction_obj.get('fee_asset'),transaction_obj.get('gain_asset')])
        for a in assets: 
            if a != None: self.asset(a).delete_transaction(transaction_hash) #Adds this transaction to loss asset's ledger
    def delete_wallet(self, wallet:str):            self._wallets.pop(wallet)


    #JSON functions
    def loadJSON(self, JSON:dict, merge=False, overwrite=False): #Loads JSON data, erases any existing data first
        
        #If loading...                      clear everything,  load the new data.
        #If merging and overwriting,                           load the new data.
        #If merging and NOT overwriting,                       load the new data, skipping duplicates.

        if not merge:   self.clear()

        # ASSETS
        if 'assets' in JSON:
            for asset in JSON['assets']:
                if merge and not overwrite and self.hasAsset(asset):    continue
                a = JSON['assets'][asset]
                self.add_asset(Asset(asset, a['name'], a['description']))
        else: print('||WARNING|| Failed to find any assets in JSON.')
        # TRANSACTIONS - NOTE: Lag is ~80ms for ~4000 transactions
        if 'transactions' in JSON:
            for t in JSON['transactions']:
                try:
                    #Creates a rudimentary transaction, then fills in the data from the JSON. Bad data is cleared upon saving, not loading.
                    trans = trans_from_dict(t)
                    if merge and not overwrite and self.hasTransaction(trans.get_hash()): continue     #Don't overwrite identical transactions
                    self.add_transaction(trans) #45ms for ~4000 transactions
                except:  print('||WARNING|| Transaction ' + t['date'] + ' failed to load.')
        else: print('||WARNING|| Failed to find any transactions in JSON.')
        #WALLETS
        if 'wallets' in JSON:
            for wallet in JSON['wallets']:
                if merge and not overwrite and self.hasWallet(wallet):    continue
                w = JSON['wallets'][wallet]
                self.add_wallet(Wallet(wallet, w['description']))
        else: print('||WARNING|| Failed to find any wallets in JSON.')

        self.fixBadAssetTickers()
    
    def fixBadAssetTickers(self): #Fixes tickers that have changed over time, like LUNA to LUNC, or ones that have multiple names like CELO also being CGLD
        for asset in forks_and_duplicate_tickers_lib:
            if asset in list(self._assets):
                new_ticker = forks_and_duplicate_tickers_lib[asset][0]
                if not self.hasAsset(new_ticker):    self.add_asset(Asset(new_ticker, new_ticker.split('z')[0]))  #Add the werd asset name if it hasn't been added already
                for transaction in list(self.asset(asset)._ledger.values()):
                    if transaction.date() < forks_and_duplicate_tickers_lib[asset][1]:  #Change relevant transaction tickers, IF they occur before a certain "fork" or "renaming" date
                        newTrans = transaction.toJSON()
                        self.delete_transaction(transaction.get_hash()) #Delete the old erroneous transaction
                        for data in ['loss_asset','fee_asset','gain_asset']:    #Update all relevant tickers to the new ticker name
                            if data in newTrans and newTrans[data] == asset:    newTrans[data] = new_ticker
                        self.add_transaction(trans_from_dict(newTrans)) #add the fixed transaction back in
                if len(self.asset(asset)._ledger) == 0:  self.delete_asset(asset)

    def toJSON(self) -> dict:
        toReturn = {
            'assets':{},
            'transactions':[],
            'wallets':{},
        }
        for asset in self.assets():             toReturn['assets']       [asset.tickerclass()] = asset.toJSON()
        for transaction in self.transactions(): toReturn['transactions'].append(transaction.toJSON())
        for wallet in self.wallets():           toReturn['wallets']      [wallet.name()]       = wallet.toJSON()

        return copy.deepcopy(toReturn) #TODO TODO TODO: Not sure if deepcopy is necessary here. Should test this. Might be needlessly inefficient.
    
    #Status functions
    def isEmpty(self) -> bool:  return {} == self._assets == self._transactions == self._wallets

    def hasAsset(self, asset:str) -> bool:                  return asset in self._assets
    def hasTransaction(self, transaction:int) -> bool:      return transaction in self._transactions
    def hasWallet(self, wallet:str) -> bool:                return wallet in self._wallets
    
    #Access functions:
    def asset(self, asset:str) -> Asset:                    return self._assets[asset]
    def transaction(self, transaction:int) -> Transaction:  return self._transactions[transaction]
    def wallet(self, wallet:str) -> Wallet:                 return self._wallets[wallet]

    def assets(self) -> list:                               return self._assets.values()
    def transactions(self) -> list:                         return self._transactions.values()
    def wallets(self) -> list:                              return self._wallets.values()

    def assetkeys(self) -> list:                            return self._assets
    def walletkeys(self) -> list:                           return self._wallets


    def get(self, info:str):
        try:    return self._metrics[info]
        except: return MISSINGDATA

    def prettyPrint(self, info:str) -> str:  #pretty printing for anything   
        try:    return format_general(self.get(info), info_format_lib[info]['format'])
        except: return MISSINGDATA
    
    def color(self, info:str) -> tuple: #returns a tuple of foreground, background color
        color_format = info_format_lib[info]['color']
        if color_format == 'profitloss':    
            try:    
                data = self.get(info)
                if   data > 0: return (palette('profit'), None)
                elif data < 0: return (palette('loss'), None)
                else:                   return (palette('neutral'), None)
            except: return (None, None)
        return (None, None)

    def pretty(self, info:str, uselessInfo=None) -> tuple: #Returns a tuple of pretty info, foreground color, and background color
        color = self.color(info)
        return (self.prettyPrint(info), color[0], color[1])

MAIN_PORTFOLIO = Portfolio()
 


class gain_obj(): #A unit of assets aquired. Could be a purchase, gift_in, income, card_reward, anything with an asset gained.
    def __init__(self, hash:int, price:mpf, quantity:mpf, date:str, accounting_method:str):
        self._hash =        hash
        self._price =       price
        self._quantity =    quantity
        self._date =        date
        self._accounting_method = accounting_method

    def __lt__(self, __o: object) -> bool:
        if self._accounting_method == 'hifo':   return self._price > __o._price #"Smallest" element in the minheap is the highest (greatest) price  #NOTE: Insertion is 60ms avg
        if self._accounting_method == 'fifo':   return self._date < __o._date   #"Smallest" element in the minheap is the oldest (least) date       #NOTE: Insertion is 20ms avg
        if self._accounting_method == 'lifo':   return self._date > __o._date   #"Smallest" element in the minheap is the newest (greatest) date    #NOTE: Insertion is 30ms avg

class gain_heap(): #Sorts the gains depending on the accounting method chosen. HIFO, FIFO, LIFO. Uses a heap for maximum efficiency
    def __init__(self, accounting_method:str):
        self._heap = [] #Stores all gains with minimum at the top
        self._dict = {} #Stores all gains, indexed by their respective transaction's hash. This allows for efficient merging of re-united gains
        self._accounting_method = accounting_method
    
    def store(self, hash:int, price:mpf, quantity:mpf, date:str):   #NOTE: Lag is ~34ms on average
        if hash not in self._dict:  #Re-unite same-source gains, if possible, to be a little more efficient, and for less discombobulated tax reports
            new_gain = gain_obj(hash, price, quantity, date, self._accounting_method)    #15-20ms for ~14000 stores
            heapq.heappush(self._heap, new_gain)                #25ms for ~14000 stores
            self._dict[hash] = new_gain                         #4ms for ~14000 stores
        else:
            self._dict[hash]._quantity += quantity          #~1ms for ~14000 stores (few will fit this category)

    def store_direct(self, new_gain:gain_obj):
        hash = new_gain._hash
        if hash not in self._dict:  #Re-unite same-source gains, if possible, to be a little more efficient, and for less discombobulated tax reports
            heapq.heappush(self._heap, new_gain)                #25ms for ~14000 stores
            self._dict[hash] = new_gain                         #4ms for ~14000 stores
        else:
            self._dict[hash]._quantity += new_gain._quantity          #~1ms for ~14000 stores (few will fit this category)

    def disburse(self, quantity:mpf): #Removes quantity, returns list of the gains which were sold #NOTE: 30ms on avg for 231 disbursals
        
        gains_removed = []
        while len(self._dict) > 0 and quantity > 0:
            next_gain = self._heap[0]
            next_gain_quantity = next_gain._quantity
            #We completely disburse a gain
            gain_is_equivalent = appxEqPrec(quantity, next_gain_quantity)
            if quantity > next_gain_quantity or gain_is_equivalent:
                if gain_is_equivalent:  quantity = 0
                else:                   quantity -= next_gain_quantity
                gains_removed.append(next_gain) #Add this gain to what's been disbursed     #2ms for ~12000 transactions
                heapq.heappop(self._heap)       #Remove this gain from the heap array       #30ms for ~12000 transactions
                self._dict.pop(next_gain._hash) #Remove this gain from the dictionary       #4ms for ~12000 transactions
            #We partially disburse a gain - this will always be the last one we disburse from
            else:
                #Adds this gain to what's been disbursed, with its quantity modified to what's been disbursed
                gains_removed.append(gain_obj(next_gain._hash, next_gain._price, quantity, next_gain._date, self._accounting_method))
                next_gain._quantity -= quantity   #Remove the quantity disbursed
                quantity = 0
                
        #return what's remaining to disburse (to check if its not close enough to zero), and what gains have been removed (to calculate cost basis, taxes, etc.)
        return (quantity, gains_removed)



class GRID(tk.Frame): # Displays all the rows of info for assets/transactions/whatever
    def __init__(self, upper:tk.Widget, header_left_click, header_right_click, left_click, right_click, bg:str=palette('grid_bg')):
        super().__init__(upper, bg=bg) #Contructs the tk.Frame object
        self.columns = []                           # Dictionary of the columns of the GRID
        self.pagelength = setting('itemsPerPage')   # Number of items to render per page
        self.selection = [None, None]
        self.highlighted = None
        self.header_left_click,self.header_right_click = header_left_click,header_right_click        # Command that triggers when you click on a header
        self.left_click,self.right_click = left_click,right_click
        self.rowconfigure(0, weight=1)  # Makes the headers stretch

        # Adds the first column in the grid, the column with the '#' and the numbers
        self.item_indices = (
            tk.Label(self, text='#', font=setting('font', 0.75), fg=palette('grid_text'), bg=palette('grid_header'), relief='groove', bd=1),
            TextBox(self, state='readonly', fg=palette('grid_text'), bg=palette('grid_highlight'), height=self.pagelength,width=2,font=setting('font'), wrap='none',spacing3=3)
        )
        header,textbox = self.item_indices[0],self.item_indices[1]
        header.grid(row=0, column=0, sticky='NSEW')
        textbox.grid(row=1, column=0, sticky='EW')

    def _mouse_hover(self, textbox:TextBox, event):
        mouse_text_pos = textbox.index(f"@{event.x},{event.y}").split('.')[0]
        self.highlighted = int(mouse_text_pos)-1    
        self.set_highlight(mouse_text_pos)   
    def set_highlight(self, index:str=None, event=None):
        for c in range(len(self.columns)):  
            self.columns[c][1].tag_remove('highlight','1.0','end')              # Remove all previous highlighting
            if index != None: 
                self.columns[c][1].tag_add('highlight', index+'.0', str(int(index)+1)+'.0')   # Apply highlighting to this entire row
    
    def _left_click(self, event):
        index = self.highlighted
        if self.selection == [index, index]:    self.left_click(index)      # Do fancy stuff in the main portfolio
        else:                                   self.set_selection(index)   # Left click once, set selection to just this item
    def _shift_left_click(self, event): #Allows for easy selection of multiple items
        index = self.highlighted
        if self.selection[0] != None and self.selection[0] == self.selection[1]:    
            if self.selection[0] < index:   self.set_selection(self.selection[0], index)
            else:                           self.set_selection(index, self.selection[0])
        else:                               self.set_selection(index)
    def _right_click(self, event):   self.right_click(self.highlighted,self.selection[0],self.selection[1])
    def set_selection(self, start:int=None, end:int=None):
        if start==None:     self.selection = [None, None]   # Clear selection
        elif end == None:   self.selection = [start, start] # Set selection to one item
        else:               self.selection = [start, end]   # Set selection to range
        for c in range(len(self.columns)):  
            self.columns[c][1].tag_remove('selection','1.0','end')                  # Remove all previous highlighting
            if self.selection[0] != None:
                self.columns[c][1].tag_add('selection', str(self.selection[0]+1)+'.0', str(self.selection[1]+2)+'.0') # Apply highlighting to this entire row
    def get_selection(self):
        '''Returns list of indices of selected items within the GRID'''
        if self.selection[0] == None:   return None
        else:                           return range(self.selection[0],self.selection[1]+1)

    def add_column(self):
        new_index = len(self.columns)
        self.columns.append(
            (
            tk.Button(self, command=p(self.header_left_click, new_index), font=setting('font', 0.75), fg=palette('grid_header_text'), bg=palette('grid_header'), relief='groove', bd=1),
            TextBox(self, state='readonly', fg=palette('grid_text'), bg=palette('grid_bg'), height=self.pagelength, width=1, font=setting('font3',.9), wrap='none',spacing3=1)
        ))
        header,textbox = self.columns[new_index][0],self.columns[new_index][1]
        header.grid(row=0, column=new_index+1, sticky='NSEW')
        header.bind('<Button-3>', p(self.header_right_click, new_index))
        textbox.grid(row=1, column=new_index+1, sticky='EW')
        textbox.bind('<Motion>', p(self._mouse_hover, textbox))
        textbox.bind('<Button-1>', self._left_click)
        textbox.bind('<Button-3>', self._right_click)
        textbox.bind('<Shift-Button-1>', self._shift_left_click)
        textbox.bind('<Leave>', p(self.set_highlight, None))
    def delete_column(self):    #NOTE: Lag is 7.52ms on avg
        old = self.columns.pop()    #Remove the tuple from the columns
        old[0].destroy()            #Destroy the header
        old[1].destroy()            #Destroy the label
    def set_columns(self, n:int):
        '''Automatically adds or removes header columns until there are \n\ columns'''
        if n < 0: raise Exception('||ERROR|| Cannot set number of columns to less than 1')
        while len(self.columns) != n:
            if len(self.columns) > n:   self.delete_column()
            else:                       self.add_column()
        
    def force_formatting(self, fg:str=None, bg:str=None, font:tuple=None, justify:str=None):
        for c in range(len(self.columns)):
            textbox = self.columns[c][1]
            textbox.clear_formatting()
            textbox.force_formatting(fg, bg, font, justify)

    def update_page_length(self, n:int):
        set_setting('itemsPerPage', n)
        self.pagelength = n
        self.item_indices[1].configure(height=n)
        for c in range(len(self.columns)):
            self.columns[c][1].configure(height=n)


    def grid_render(self, headers:list, sorted_items:list, page:int, specialinfo=None):
        self.set_columns(len(headers))  # NOTE: 10-20% of portfolio page lag, 50% of asset page lag

        first_item = self.pagelength*page
        last_item = self.pagelength*(page+1)
        rowrange = range(first_item,last_item)
        
        #Sets the item indices
        item_indices = self.item_indices[1]
        item_indices.configure(width=len(str(last_item))) #Appropriately sets the width of the indices column
        item_indices.clear()
        for r in rowrange:
            item_indices.insert_text(str(r+1)+'\n')
        
        stop = len(sorted_items)-1 #last viable index with an item in self.sorted
        for c in range(len(self.columns)):
            #The header
            header = headers[c]
            self.columns[c][0].configure(text=info_format_lib[header]['headername'])

            #The data
            longest_text_length = 0
            textbox = self.columns[c][1]
            textbox.clear()
            textbox.tag_config('highlight', background=palette('grid_highlight'))   # Item we're hovering over looks like this
            textbox.tag_config('selection', background=palette('grid_highlight'))   # Selected items are formatted like this
            for r in rowrange:
                if r > stop: textbox.newline() #Inserts empty lines where there is nothing to display
                else:
                    formatting = sorted_items[r].pretty(header, specialinfo) #NOTE: Lag is ~3.84ms
                    if len(formatting[0]) > longest_text_length: longest_text_length = len(formatting[0])
                    textbox.insert_text(formatting[0]+'\n', fg=formatting[1], bg=formatting[2], justify='center')   #NOTE: Lag is ~6.31ms
            
            textbox.configure(width=longest_text_length+1) #Appropriately sets the width of the indices column


