
from AAlib import *

import pandas as pd
from io import StringIO
import copy
import heapq
from functools import partial as p



class Filter():
    def __init__(self, metric:str, relation:str, state:str):
        self._metric = metric
        self._relation = relation
        self._state = state
        self._hash = None

        self.calc_hash()

    def calc_hash(self): self._hash = hash((self._metric, self._relation, self._state))

    #access functions
    def get_hash(self) -> int:  return self._hash
    def metric(self) -> str:  return self._metric
    def relation(self) -> str:  return self._relation
    def state(self):  return self._state # may return str/int depending on metric

    # Returns true, when format of metric/state is alpha (non-numeric)
    def is_alpha(self) -> bool: return metric_formatting_lib[self._metric]['format'] == 'alpha' 

    # Prints rule-name for this filter like "Value > 5"
    def get_rule_name(self) -> str:
        """Returns proper title for filter, like \"Value > 5\""""
        if self.metric() == 'date':
            return metric_formatting_lib[self.metric()]['name']+' '+self.relation()+' '+unix_to_local_timezone(self.state())
        else:
            return metric_formatting_lib[self.metric()]['name']+' '+self.relation()+' '+str(self.state())


class Wallet():
    def __init__(self, name:str, description:str=''):
        self._name = name
        self._description = description
        self._hash = None

        self.calc_hash()

    def calc_hash(self): self._hash = hash(self._name)

    #access functions
    def get_hash(self) -> int:  return self._hash
    def name(self) -> str:      return self._name
    def desc(self) -> str:      return self._description

    #JSON Function
    def toJSON(self) -> dict:   return {'name':self._name, 'description':self._description}

class Transaction():
    def __init__(self, date_unix:int=None, type:str=None, wallet:str=None, description:str='', loss:tuple=(None,None,None), fee:tuple=(None,None,None), gain:tuple=(None,None,None)):

        #Set to true for transfers that don't have a partner, and with missing data. Stops metrics() short, and tells the renderer to color this RED
        self.ERROR = False  
        self.ERR_MSG =  ''

        
        self._data = { # RAW STRING DATA
            'date' :            date_unix,
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
        }
        self._metrics = { # DATA IN PROPER TYPES
            'date':             None, # Stored here as ISO date, not UNIX
            'type':             None,
            'wallet':           None,
            'description':      None,
            'loss_quantity' :   None,
            'fee_quantity' :    None,
            'gain_quantity' :   None,
            'loss_price' :      None,
            'fee_price' :       None,
            'gain_price' :      None,
            
            'loss_value':       0,
            'fee_value':        0,
            'gain_value':       0,
            'loss_balance':       0,
            'fee_balance':        0,
            'gain_balance':       0,

            'basis_price':      0,      #The cost basis price

            'price':    {},     #Price, value, quantity by asset, for displaying
            'value':    {},
            'quantity': {},
            'balance': {},
            'all_assets':[],

            'hash':             None,
            'missing':          [],
            'dest_wallet':      None, # Re-calculated for transfers on metric calculation
            }
        self._formatted = {} # Contains pre-formatted copy of all metrics to improve performance
        if type: self.recalculate()

    #Pre-calculates useful information to GREATLY increase performance
    def recalculate(self):          # 0.0211ms for ~5300 transactions
        """Recalculates all metrics and formatting based on current raw data"""
        self.calc_hash()            # 0.0011ms for ~5300 transactions
        self.calc_missing()         # 0.0014ms for ~5300 transactions
        #We try to calculate this, because otherwise, if a transaction is missing some data, it won't display its ISO date
        self.calc_iso_date()        # 0.0031ms for ~5300 transactions
        # Don't continue performing calculations if we're missing data!
        if self.ERROR: return
        self.calc_metrics()         # 0.0045ms for ~5300 transactions
        self.calc_inference()       # 0.0005ms for ~5300 transactions
        self.calc_formatting()      # 0.0142ms for ~5300 transactions # worst offender
    
    def calc_hash(self): #Hash Function - A transaction is unique insofar as its date, type, wallet, and three asset types are unique from any other transaction.
        self._metrics['hash'] = hash((self._data['date'],self._data['type'],self._data['wallet'],self._data['loss_asset'],self._data['fee_asset'],self._data['gain_asset']))
    def calc_missing(self):
        """Detect and log missing data for this transaction"""
        missing = set()
        # Is it missing the type?
        if self._data['type'] == None: missing.add(data)
        # If there is a fee asset, is it missing the necessary quantity/price data?
        if self._data['fee_asset'] != None and self._data['fee_quantity'] == None:  missing.add('fee_quantity')
        if self._data['fee_asset'] != None and self._data['fee_price'] == None:     missing.add('fee_price')
        # Is it missing date/wallet, or asset/quantity/price data (that it ought to have?)
        for data in valid_transaction_data_lib[self._data['type']]:
            if data in ('fee_asset','fee_quantity','fee_price'):    continue    #Ignore fees, they are a special case, and aren't always necessary
            if self._data[data] == None:                            missing.add(data)
        self._metrics['missing'] = list(missing) # list of missing data
        self.ERROR = len(missing)>0
        
        missingMessage = 'Transaction is missing data: '
        for m in missing:   missingMessage += '\'' + metric_formatting_lib[m]['name'] + '\', '
        self.ERR_MSG = missingMessage[:-2]
    def calc_metrics(self):
        # COPIED FROM RAW DATA
        # ==================
        # INTEGERS - Datatype preserved by JSON
        self._metrics['date'] = int(self._data['date'])
        # STRINGS - Datatype preserved by JSON
        for data in ('type','wallet','description','loss_asset','fee_asset','gain_asset'):
            self._metrics[data] = self._data[data]
        # DECIMALS
        for data in ('loss_quantity','loss_price','fee_quantity','fee_price','gain_quantity','gain_price'):     #NOTE: Lag is ~11ms for ~4000 transactions
            d = self._data[data]
            if d:   self._metrics[data] = Decimal(d)
        
        # FANCY STUFF
        # ==================
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
        self._metrics['all_assets'] = list(set(self._data[data] for data in ('loss_asset','fee_asset','gain_asset') if self._data[data] is not None))
        for a in self._metrics['all_assets']:
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
    def calc_inference(self):
        """Infers metrics where possible"""
        TYPE = self._data['type']
        # Date - always stored
        # Type - always stored
        # Desc - always stored
        # Wallet - always stored

        # loss_asset
        #       purchase: USDzf
        #       purchase w/ crypto fee: USDzf
        if TYPE in ('purchase','purchase_crypto_fee'):
            self._metrics['loss_asset'] = 'USDzf'

        # loss_price - as above
        #       purchase: 1
        #       purchase w/ crypto fee: 1
        #       sale: inferrable from USD fee and gained USD
        if TYPE in ('purchase','purchase_crypto_fee'):
            self._metrics['loss_price'] = 1.0
        elif TYPE == 'sale':
            self._metrics['loss_price'] = (self._metrics['gain_quantity']-self._metrics['fee_quantity'])/self._metrics['loss_quantity']

        # fee_asset
        #       purchase: USDzf
        #       sale: USDzf
        if TYPE in ('purchase','sale'):
            self._metrics['fee_asset'] = 'USDzf'

        # fee_price
        if TYPE in ('purchase','sale'):
            self._metrics['fee_price'] = 1.0

        # gain_asset
        if TYPE == 'sale':
            self._metrics['gain_asset'] = 'USDzf'

        # gain_price
        if TYPE == 'sale':
            self._metrics['gain_price'] = 1.0
        elif TYPE in ('purchase','purchase_crypto_fee','trade'):
            self._metrics['gain_price'] = (self._metrics['loss_value']+self._metrics['fee_value'])/self._metrics['gain_quantity']

        # QUANTITIES - always stored or irrelevant
    def calc_iso_date(self):
        """Converts the transaction's unix timestamp to ISO format, in your specified timezone
        \nThis is separate from calc_metrics to reduce performance cost when changing timezone setting"""
        if self._data['date'] is None:  self._formatted['date'] = MISSINGDATA
        else:                           self._formatted['date'] = unix_to_local_timezone(self._data['date'])
    def calc_formatting(self):
        """Pre-calculates formatted metric strings to greatly increase performance"""
        for metric in self._metrics.keys():
            # If the metric is missing, its a PROBLEM!!! We mark this as '???'
            # Otherwise, if the data is not missing, leave the space blank
            if metric in self._metrics['missing']:  formatted_metric = MISSINGDATA
            else:                                   formatted_metric = ''
            # Now, let's see if the data is actually there
            match metric:
                case 'basis_price' | 'hash' | 'all_assets' | 'missing' | 'date': 
                    continue # Unnecessary, or already calculated elsewhere
                case 'type':    formatted_metric = pretty_trans[self._data['type']]
                case 'value' | 'quantity' | 'price' | 'balance': 
                    self._formatted[metric] = {}
                    for a in self._metrics['all_assets']:
                        try:    self._formatted[metric][a] = format_general(self._metrics[metric][a], metric_formatting_lib[metric]['format']) 
                        except: self._formatted[metric][a] = MISSINGDATA
                    continue
                case other:         
                    data = self._metrics[metric]
                    if data != None:    formatted_metric = format_general(data, metric_formatting_lib[metric]['format'])
            self._formatted[metric] = formatted_metric

    #Comparison operator overrides
    def __eq__(self, __o: object) -> bool:
        if type(__o) != Transaction: return True
        return self.get_hash() == __o.get_hash()
    def __lt__(self, __o: object) -> bool:
        # If self.ERROR, do not sort this item: self < __o always in this case
        if self.ERROR: return False
        if __o.ERROR: return True
        # Basically, we try to sort transactions by date, unless they're the same, then we sort by type, unless that's also the same, then by wallet... and so on.
        S,O = self.unix_date(),__o.unix_date()
        if S!=O:   return S<O
        S,O = self.type(),__o.type()
        if S!=O:   return trans_priority[S]<trans_priority[O]
        # S,O = self.wallet(),__o.wallet()                      #Hopefully I don't need to add the rest in. With them all, sorting goes from ~17ms to ~120ms for ~12000 transactions
        # if S!=O:   return S<O
        # S,O = self.get_raw('loss_asset'),__o.get_raw('loss_asset')
        # if S and O and S!=O: return S<O
        # S,O = self.get_raw('fee_asset'),__o.get_raw('fee_asset')
        # if S and O and S!=O: return S<O
        # S,O = self.get_raw('gain_asset'),__o.get_raw('gain_asset')
        # if S and O and S!=O: return S<O
        return False
    def __hash__(self) -> str: return self.get_hash()

    #Access functions for basic information
    def unix_date(self) -> int:         return self._data['date']
    def iso_date(self) -> str:          return self._formatted['date']
    def type(self) -> str:              return self._data['type']
    def wallet(self) -> str:            return self._data['wallet']
    def desc(self) -> str:              return self._data['description']
    def get_hash(self) -> int:          return self._metrics['hash']
    def price(self, asset:str) -> str:      return self._metrics['price'][asset]
    def quantity(self, asset:str) -> str:   return self._metrics['quantity'][asset]
    def value(self, asset:str) -> str:      return self._metrics['value'][asset]

    def get_raw(self, info:str) -> str:    
        """Returns raw savedata string for this metric"""
        return self._data[info]
    def get_metric(self, info:str, asset:str=None):
        """Returns this metric in its native datatype"""
        if info in ['value','quantity','price','balance']:    
            try:    return self._metrics[info][asset]
            except: return None
        try:    return self._metrics[info]
        except: return None

    def metric_to_str(self, info:str, asset:str=None) -> str:
        """Returns formatted str for given metric"""
        try:
            if info in ('value','quantity','price','balance'):   
                return self._formatted[info][asset]
            else:       return self._formatted[info]
        except: 
            return MISSINGDATA

    def get_metric_style(self, info:str, asset:str=None) -> tuple:
        """Returns StyleSheet HTML formatting for color, font, whatever."""
        if self.ERROR: return ''
        color_format = metric_formatting_lib[info]['color']
        if color_format == 'type':                                          return style(self._data['type'])
        elif color_format == 'accounting' and self.get_metric(info, asset) and self.get_metric(info, asset) < 0:    return style('loss')
        return ''

    #JSON Functions
    def toJSON(self) -> dict: # Returns a dictionary of all data for this transaction. Missing/Nones are omitted
        return {data:self._data[data] for data in valid_transaction_data_lib[self._data['type']] if self._data[data] != None}
   
def trans_from_dict(dict:dict): #Allows for the creation of a transaction directly from a dictionary
    new_trans = Transaction()
    new_trans._data.update(dict)
    new_trans.recalculate()
    return new_trans


class Asset():  
    def __init__(self, tickerclass:str, name:str='', description:str=''):
        self.ERROR = False  
        self._tickerclass = tickerclass
        self._ticker = tickerclass.split('z')[0].upper()
        self._class = tickerclass.split('z')[1].lower()
        self._name = name
        self._description = description
        self._hash = None

        self._metrics = {}

        self._ledger = {} #A dictionary of all the transactions for this asset. Mainly for making rendering more efficient.

        self.calc_hash()

    def calc_hash(self): # Gives this asset a unique identifier based on its ticker and class
        self._hash = hash((self._ticker,self._class))
    
    #Modification functions
    def add_transaction(self, transaction_obj:Transaction): self._ledger[transaction_obj.get_hash()] = transaction_obj
    def delete_transaction(self, transaction_hash:int):     self._ledger.pop(transaction_hash)

    #Access functions
    def get_hash(self) -> int:      return self._hash
    def tickerclass(self) -> str:   return self._tickerclass
    def ticker(self) -> str:        return self._ticker
    def assetClass(self) -> str:    return self._class
    def name(self) -> str:          return self._name
    def desc(self) -> str:          return self._description

    def get_raw(self, info:str) -> str:
        """Returns raw savedata string for this metric"""
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
    
    def get_metric(self, info:str) -> Decimal:
        """Returns this metric in its native datatype"""
        #This is metric data
        try:    return self._metrics[info]
        except: pass
        #This is Market Data (separate from metric data, so we don't delete it upon deleting this asset)
        try:    return Decimal(marketdatalib[self._tickerclass][info])
        except: pass

    def metric_to_str(self, info:str, *args, **kwargs) -> str:
        """Returns formatted str for given metric"""
        if info == 'ticker':        return self._ticker
        if info == 'name':          return self._name
        if info == 'class':         return assetclasslib[self._class]['name'] #Returns the long-form name for this class

        #This is Market Data
        return format_general(self.get_metric(info), metric_formatting_lib[info]['format'])
    
    def get_metric_style(self, info:str, *args, **kwargs) -> str: # Returns styleSheet with proper formatting
        color_format = metric_formatting_lib[info]['color']
        if color_format == 'profitloss':    
            try:    
                data = self.get_metric(info)
                if   data > 0:  return style('profit')
                elif data < 0:  return style('loss')
                else:           return style('neutral')
            except: return ''
        return ''

    def pretty(self, info:str, *args, **kwargs) -> tuple: #Returns a tuple of pretty info, foreground color, and background color
        return (self.metric_to_str(info), self.get_metric_style(info))

    #JSON functions
    def toJSON(self) -> dict:
        toReturn = {
            'ticker':self._ticker, 
            'class':self._class, 
            'name':self._name, 
            'description':self._description,
            }
        return toReturn

class Portfolio():
    def __init__(self):
        '''Initializes a Portfolio object, which contains dictionaries and lists of all the below:'''
        # For all of these, the key is the object's hash, and the value is the object itself 
        self._assets = {}
        self._transactions = {}
        self._wallets = {}
        self._filters = {} # in-memory only

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
        if self.hasAsset(asset_obj.get_hash()): print('||WARNING|| Overwrote asset with same hash.', asset_obj.get_hash())
        self._assets[asset_obj.get_hash()] = asset_obj
    def add_transaction(self, transaction_obj:Transaction):
        if self.hasTransaction(transaction_obj.get_hash()): print('||WARNING|| Overwrote transaction with same hash.', transaction_obj.get_hash())
        self._transactions[transaction_obj.get_hash()] = transaction_obj
        for a in set((transaction_obj.get_raw('loss_asset'),transaction_obj.get_raw('fee_asset'),transaction_obj.get_raw('gain_asset'))):
            if a != None: self.asset(a).add_transaction(transaction_obj) #Adds this transaction to asset's ledger
    def import_transaction(self, transaction_obj:Transaction): #Merges simultaneous fills from the same order
        transaction_obj._fills = 1
        if not self.hasTransaction(transaction_obj.get_hash()): self.add_transaction(transaction_obj)
        else:
            other_trans = self.transaction(transaction_obj.get_hash())
            other_trans._fills += 1
            print('||INFO|| ' + other_trans.wallet() + ' transaction at time ' + other_trans.iso_date() + ' had '+str(other_trans._fills)+' simultaneous fills. They were merged.')
            for part in ['loss','fee','gain']:
                NQ,OQ = transaction_obj.get_metric(part+'_quantity'), other_trans.get_metric(part+'_quantity')
                NP,OP = transaction_obj.get_metric(part+'_price'), other_trans.get_metric(part+'_price')
                if NQ and OQ:
                    merged_quantity = OQ + NQ
                    other_trans._data[part+'_quantity'] =   str(merged_quantity)
                if NP and OP and not appxEqPrec(OP, NP):
                    other_trans._data[part+'_price'] = str((OQ/merged_quantity*OP)+(NQ/merged_quantity*NP)) #Weighted average of prices
            other_trans.recalculate()
    def add_wallet(self, wallet_obj:Wallet):
        if self.hasWallet(wallet_obj.get_hash()): print('||WARNING|| Overwrote wallet with same hash.', wallet_obj.get_hash())
        self._wallets[wallet_obj.get_hash()] = wallet_obj
    def add_filter(self, filter_obj:Filter):
        if self.hasFilter(filter_obj.get_hash()): print('||WARNING|| Overwrote filter with same hash.', filter_obj.get_hash())
        self._filters[filter_obj.get_hash()] = filter_obj

    def delete_asset(self, asset:Asset):              self._assets.pop(asset.get_hash())
    def delete_transaction(self, transaction_hash:int):  
        transaction_obj = self._transactions.pop(transaction_hash) #Removes transaction from the portfolio itself
        #Removes transaction from relevant asset ledgers
        assets = set([transaction_obj.get_raw('loss_asset'),transaction_obj.get_raw('fee_asset'),transaction_obj.get_raw('gain_asset')])
        for a in assets: 
            if a != None: self.asset(a).delete_transaction(transaction_hash) #Adds this transaction to loss asset's ledger
    def delete_wallet(self, wallet:Wallet):            self._wallets.pop(wallet.get_hash())
    def delete_filter(self, filter:Filter):            self._filters.pop(filter.get_hash())


    #JSON functions
    def loadJSON(self, JSON:dict, merge=False, overwrite=False): #Loads JSON data, erases any existing data first
        
        #If loading...                      clear everything,  load the new data.
        #If merging and overwriting,                           load the new data.
        #If merging and NOT overwriting,                       load the new data, skipping duplicates.

        if not merge:   self.clear()


        # TRANSACTIONS & ASSETS - NOTE: Lag is ~80ms for ~4000 transactions
        unique_assets_by_tickerclass = set()
        if 'transactions' in JSON:
           # try:
                for t in pd.read_csv(StringIO(JSON['transactions']), dtype='string').astype({'date':float}).iterrows():
                   # try:
                        #Creates a rudimentary transaction, then fills in the data from the JSON. Bad data is cleared upon saving, not loading.
                        new_trans = trans_from_dict(t[1].dropna().to_dict())
                        for a in ('loss_asset','fee_asset','gain_asset'): # compiles list of assets based on transaction history
                            tc = new_trans.get_raw(a)
                            if tc is not None and tc not in unique_assets_by_tickerclass:
                                self.add_asset(Asset(tc)) 
                                unique_assets_by_tickerclass.add(new_trans.get_raw(a))
                        if merge and not overwrite and self.hasTransaction(new_trans.get_hash()): continue     #Don't overwrite identical transactions
                        self.add_transaction(new_trans) #45ms for ~4000 transactions
               #     except:  print('||WARNING|| Transaction failed to load.')
            #except: print('||ERROR|| Failed to read transactions from JSON.')


        #ASSETS
        # Second, we look at our saved asset data to find names/descriptions
        if 'assets' in JSON:
            try:
                for a in pd.read_csv(StringIO(JSON['assets']), dtype='string').fillna('').iterrows(): # Look through all asset savedata
                    try:    new_asset_data = a[1]['ticker']+'z'+a[1]['class'], a[1]['name'], a[1]['description'] # Parse row
                    except: 
                        print('||ERROR|| An asset\'s name/decription failed to load.')
                        continue
                    if self.hasAsset(new_asset_data[0]): # If asset already in portfolio, import name/description
                        self.asset(new_asset_data[0])._name = new_asset_data[1] # Set existing asset name to saved name
                        self.asset(new_asset_data[0])._description = new_asset_data[2] # Set existing asset description to saved description
            except: print('||ERROR|| Failed to read asset names/decriptions from JSON.')
        
        
        #WALLETS
        if 'wallets' in JSON:
            try:
                for w in pd.read_csv(StringIO(JSON['wallets']), dtype='string').fillna('').iterrows():
                    try:
                        new_wallet = Wallet(w[1]['name'], w[1]['description'])
                        if merge and not overwrite and self.hasWallet(new_wallet.get_hash()):    continue
                        self.add_wallet(new_wallet)
                    except:  print('||WARNING|| Wallet failed to load.')
            except: print('||ERROR|| Failed to read wallets from JSON.')

        self.fixBadAssetTickers()
    
    def fixBadAssetTickers(self): 
        #Fixes tickers that have changed over time, like LUNA to LUNC, or ones that have multiple names like CELO also being CGLD
        # Also deletes assets that have no transactions under them
        for asset in forks_and_duplicate_tickers_lib:
            if asset in list(self._assets):
                new_ticker = forks_and_duplicate_tickers_lib[asset][0]
                if not self.hasAsset(new_ticker):    self.add_asset(Asset(new_ticker, new_ticker.split('z')[0]))  #Add the werd asset name if it hasn't been added already
                for transaction in list(self.asset(asset)._ledger.values()):
                    if transaction.iso_date() < forks_and_duplicate_tickers_lib[asset][1]:  #Change relevant transaction tickers, IF they occur before a certain "fork" or "renaming" date
                        newTrans = transaction.toJSON()
                        self.delete_transaction(transaction.get_hash()) #Delete the old erroneous transaction
                        for data in ['loss_asset','fee_asset','gain_asset']:    #Update all relevant tickers to the new ticker name
                            if data in newTrans and newTrans[data] == asset:    newTrans[data] = new_ticker
                        self.add_transaction(trans_from_dict(newTrans)) #add the fixed transaction back in
                if len(asset._ledger) == 0:  self.delete_asset(asset)

    def toJSON(self) -> dict:
        # Up to this point we store information as dictionaries
        # Now, we convert each list of assets/transactions/wallets and their respective properties into a dataframe, 
        # then into a CSV to save a TON of disk space. The CSV is stored as a string.
        return {
            'assets':       pd.DataFrame.from_dict([asset.toJSON() for asset in self.assets()]).to_csv(index=False),
            'transactions': pd.DataFrame.from_dict([transaction.toJSON() for transaction in self.transactions()]).to_csv(index=False),
            'wallets':      pd.DataFrame.from_dict([wallet.toJSON() for wallet in self.wallets()]).to_csv(index=False),
        }
    
    #Status functions
    def isEmpty(self) -> bool:  return {} == self._assets == self._transactions == self._wallets

    def hasAsset(self, asset) -> bool: 
        """Takes Asset obj or tickerclass"""                 
        if type(asset)==str:  # "asset" is a tickerclass string
            return Asset(asset).get_hash() in self._assets.keys() # True if hashed tickerclass is in our portfolio, false other
        else: # "asset" is an Asset object
            return asset in self.assets()
    def hasTransaction(self, transaction:int) -> bool:      return transaction in self._transactions
    def hasWallet(self, wallet:str) -> bool:                return wallet in self._wallets
    def hasFilter(self, filter:str) -> bool:                return filter in self._filters
    
    #Access functions:
    def asset(self, asset:str) -> Asset:                    # Returns asset object, given its tickerclass
        """Returns asset object, given its ticker and class"""
        if type(asset)==str:    return self._assets[hash((asset.split('z')[0],asset.split('z')[1]))]
        return self._assets[asset]
    def transaction(self, transaction:int) -> Transaction:  # Returns transaction object, given its hash
        """Returns transaction, given its hash"""
        return self._transactions[transaction]
    def wallet(self, wallet:str) -> Wallet:                 # Returns wallet object, given its name
        """Returns wallet object, given its name"""
        return self._wallets[hash(wallet)]

    def assets(self) -> list:                               return self._assets.values()
    def transactions(self) -> list:                         return self._transactions.values()
    def wallets(self) -> list:                              return self._wallets.values()
    def filters(self) -> list:                              return self._filters.values()

    def all_wallet_names(self) -> list:                     return [w.name() for w in self._wallets.values()]
    def all_asset_tickerclasses(self) -> list:                      return [a.tickerclass() for a in self._assets.values()]


    def get_metric(self, info:str):
        """Returns raw savedata string for this metric"""
        try:    return self._metrics[info]
        except: return MISSINGDATA

    def metric_to_str(self, info:str, *args, **kwargs) -> str:
        """Returns formatted str for given metric"""
        try:    return format_general(self.get_metric(info), metric_formatting_lib[info]['format'])
        except: return MISSINGDATA
    
    def get_metric_style(self, info:str, *args, **kwargs) -> tuple: #returns a tuple of foreground, background color
        color_format = metric_formatting_lib[info]['color']
        if color_format == 'profitloss':    
            try:    
                data = self.get_metric(info)
                if   data > 0: return style('profit')
                elif data < 0: return style('loss')
                else:          return style('neutral')
            except: return ''
        return ''

    def pretty(self, info:str, *args, **kwargs) -> tuple: #Returns a tuple of pretty info, foreground color, and background color
        return (self.metric_to_str(info), self.get_metric_style(info))

MAIN_PORTFOLIO = Portfolio()
 



class gain_obj(): #A unit of assets aquired. Could be a purchase, gift_in, income, card_reward, anything with an asset gained.
    def __init__(self, hash:int, price:Decimal, quantity:Decimal, date:str, accounting_method:str):
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
    
    def store(self, hash:int, price:Decimal, quantity:Decimal, date:str):   #NOTE: Lag is ~34ms on average
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

    def disburse(self, quantity:Decimal): #Removes quantity, returns list of the gains which were sold #NOTE: 30ms on avg for 231 disbursals
        
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


    
class GRID_HEADER(QPushButton):
    def __init__(self, upper, lClick, rClick, *args, **kwargs):
        super().__init__(acceptDrops=True, *args, **kwargs) #Contructs the button
        self.lClick = lClick
        self.rClick = rClick
        self.isPressed = False
        self.isDragging = False
        self.upper = upper
        self.info = ''
    

    def mouseReleaseEvent(self, e: QMouseEvent) -> None: # We basically just run our own filter, then run the base QPushButton command
        #If mouse release is not over the button, release button without running command
        if e.pos().x() < 0 or e.pos().x() > self.width() or e.pos().y() < 0 or e.pos().y() > self.height(): 
            return super().mouseReleaseEvent(e)

        if e.button() == Qt.MouseButton.LeftButton:
            self.setProperty('focus', False)
            self.setProperty('pressed', False)
            self.lClick()
        elif e.button() == Qt.MouseButton.RightButton:
            self.rClick(e)
        
        return super().mouseReleaseEvent(e)
    
    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if not self.isDragging:
            if e.pos().x() < 0 or e.pos().x() > self.width() or e.pos().y() < 0 or e.pos().y() > self.height(): 
                self.isDragging = True
                mime = QMimeData()
                mime.setData('AAheader', 'emptydata'.encode('utf-8')) # It needs data to work, but its retarted and needs to be a stupid encoded byte array...
                mime.headerID = self.info                       # So I made my own variable instead: the GRID sets self.info to what it should be
                header_image = self.grab()
                qdrag = QDrag(self, mimeData=mime, pixmap=header_image) # QDrag object actually creates the dragging action, and the pixmap is an image of our header button
                qdrag.setMimeData(mime)
                qdrag.setHotSpot(QPoint(header_image.width()/2, header_image.height()/2)) # This centers our pixmap under the cursor
                qdrag.exec_()

        return super().mouseMoveEvent(e)
    
    def leaveEvent(self, e: QMouseEvent) -> None:
        self.isDragging = False
        return super().leaveEvent(e)
    
    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        if e.mimeData().hasFormat("AAheader"):
            e.acceptProposedAction()
        return super().dragEnterEvent(e)
    def dropEvent(self, e: QDropEvent) -> None:
        this_header, header_being_dropped = self.info, e.mimeData().headerID
        if this_header != header_being_dropped: 
            self.upper.upper.move_header(header_being_dropped, this_header)
        return super().dropEvent(e)
        
class GRID_ROW(QFrame): # One of the rows in the GRID, which can be selected, colored, etc.
    def __init__(self, row, set_highlight, click, double_click):
        super().__init__(styleSheet=style('GRID_none')) #Contructs the tk.Frame object
        self.setMouseTracking(True)
        self.mouseMoveEvent = p(set_highlight, row+1)           # Hovering over rows highlights them
        self.leaveEvent = p(set_highlight, None)                # Causes highlight to disappear when mouse leaves GRID area
        self.mousePressEvent = p(click, row)                    # Single-clicking only selects items
        self.mouseDoubleClickEvent = p(double_click, row)       # Double clicking opens next level of hierarchy
        self.hover_state = False
        self.select_state = False
        self.error_state = False
    
    def hover(self, state):    # Toggles hover state
        recolor = self.hover_state != state
        self.hover_state = state
        if recolor: self.color()
    def select(self, state):   # Toggles selection state
        recolor = self.select_state != state
        self.select_state = state
        if recolor: self.color()
    def error(self, state):    # Toggles error state
        recolor = self.error_state != state
        self.error_state = state
        if recolor: self.color()
    
    def color(self):
        if self.error_state:
            if self.hover_state:    self.setStyleSheet(style('GRID_error_hover'))
            elif self.select_state: self.setStyleSheet(style('GRID_error_selection'))
            else:                   self.setStyleSheet(style('GRID_error_none'))
        else:
            if self.hover_state:    self.setStyleSheet(style('GRID_hover'))
            elif self.select_state: self.setStyleSheet(style('GRID_selection'))
            else:                   self.setStyleSheet(style('GRID_none'))

class GRID(QGridLayout): # Displays all the rows of info for assets/transactions/whatever
    def __init__(self, upper, header_left_click, header_right_click, left_click, right_click):
        super().__init__(verticalSpacing=0, horizontalSpacing=1) #Contructs the tk.Frame object
        super().setContentsMargins(0,0,0,0)
        self.columns = []                           # Dictionary of the columns of the GRID
        self.pagelength = setting('itemsPerPage')   # Number of items to render per page
        self.trueHeight = None
        self.selection = [None, None]
        self.highlighted = None
        self.header_left_click,self.header_right_click = header_left_click,header_right_click        # Command that triggers when you click on a header
        self.left_click,self.right_click = left_click,right_click
        self.upper = upper
        self.setRowStretch(self.pagelength+1, 1)        # Headers stretch to accomodate bits of extra space

        # Adds the first column in the grid, with the row indices
        self.item_indices = (
            QWidget(styleSheet=style('GRID_label')),
            QLabel(alignment=Qt.AlignRight, styleSheet=style('GRID_label'))
        )
        self.highlights = [GRID_ROW(row, self.set_highlight, self._click, self._double_click) for row in range(self.pagelength)]
        
        self.fake_header = QWidget(styleSheet=style('GRID_label'))
        header,text = self.item_indices[0],self.item_indices[1]
        self.addWidget(header, 0, 0)
        self.addWidget(text, 1, 0, self.pagelength, 1)
        text.setAttribute(Qt.WA_TransparentForMouseEvents) # Our mouse cursor penetrates the text, goes right to the highlight layer


    def _click(self, row, event): # Single-click event
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_selection(row)
        elif event.button() == Qt.MouseButton.RightButton:
            self.right_click(row,self.selection[0],self.selection[1], event)
    def _double_click(self, row, event): #Double-click event
        if event.button() == Qt.MouseButton.LeftButton:
            self.left_click(row)

    def set_highlight(self, index:str=None, event=None):
        if index != None and index > len(self.highlights): return

        #remove previous highlighting
        if self.highlighted and self.highlighted == index: return
        if self.highlighted:    self.highlights[self.highlighted-1].hover(False)
        self.highlighted = index
        if self.highlighted:    self.highlights[self.highlighted-1].hover(True)
    def set_selection(self, start:int=None, end:int=None):
        if self.selection[0] != None:
            for row in range(self.selection[0], self.selection[1]+1):
                self.highlights[row].select(False)

        if QApplication.instance().keyboardModifiers() == Qt.ShiftModifier:
            if self.selection[0] != None and self.selection[0] == self.selection[1]:    
                    self.selection = [self.selection[0], start]
                    self.selection.sort()
            else:   self.selection = [start, start]
        else:
            if end != None:                                 self.selection = [start, end]
            elif start==None or start==self.selection[0]:   self.selection = [None, None]   # Clear selection
            else:                                           self.selection = [start, start] # Set selection to one item
        
        if self.selection[0] != None:
            for row in range(self.selection[0], self.selection[1]+1):
                self.highlights[row].select(True)
            

    def add_column(self):
        new_index = len(self.columns)
        self.columns.append(
            (
            GRID_HEADER(self, p(self.header_left_click, new_index), p(self.header_right_click, new_index), fixedHeight=(icon('size').height())),
            QLabel(alignment=Qt.AlignCenter, styleSheet=style('GRID_column'))
        ))
        header,text = self.columns[new_index][0],self.columns[new_index][1]
        

        self.addWidget(header, 0, new_index+1)
        self.addWidget(text, 1, new_index+1, self.pagelength, 1)
        self.addWidget(self.fake_header, 0, new_index+2) # Moves our fake label over to the final empty area
        text.setAttribute(Qt.WA_TransparentForMouseEvents) # Our mouse cursor penetrates the text, goes right to the highlight layer
    def delete_column(self):    #NOTE: Lag is 7.52ms on avg
        old = self.columns.pop()    #Remove the tuple from the columns
        old[0].deleteLater()   #Destroy the header
        old[1].deleteLater()   #Destroy the label
    def set_columns(self, n:int):
        '''Automatically adds or removes header columns until there are \n columns'''
        if n < 0: raise Exception('||ERROR|| Cannot set number of columns to less than 0')
        self.setColumnStretch(len(self.columns)+1, 0) # Unstretches previously stretchy column
        while len(self.columns) != n:
            if len(self.columns) > n:   self.delete_column()
            else:                       self.add_column()
        self.setColumnStretch(len(self.columns)+1, 1) #Stretches extremely distant column, so that all data columns clump as efficiently as possible
        
        # Readjusts highlight bars to be the correct width
        for r in range(self.pagelength):
            self.addWidget(self.highlights[r], r+1, 0, 1, len(self.columns)+2)
            self.highlights[r].lower()
        

    def update_page_length(self, n:int):
        if n < 1 or n > 100: return
        self.set_selection()    # De-selects everything
        self.set_highlight()        # De-highlights everything
        # Adjusts number of highlight rows, resets highlighting

        if n > self.pagelength:
            for i in range(n-self.pagelength):
                new_highlight = GRID_ROW(self.pagelength+i, self.set_highlight, self._click, self._double_click)
                self.highlights.append(new_highlight)
                self.addWidget(new_highlight, self.pagelength+i+1, 0, 1, len(self.columns)+2)
        else:
            for i in range(self.pagelength-n):
                self.highlights.pop().deleteLater()
        self.addWidget(self.item_indices[1], 1, 0, n, 1) # Re-inserts indices text with correct # of rows to stretch across
        for c in range(len(self.columns)):
            self.addWidget(self.columns[c][1], 1, c+1, n, 1) # Re-inserts column text with correct # of rows to stretch across
            
        set_setting('itemsPerPage', n)
        self.setRowStretch(self.pagelength+1, 0)        # Headers stretch to accomodate bits of extra space
        self.setRowStretch(n+1, 1)        # Headers stretch to accomodate bits of extra space
        self.pagelength = n
        self.doResizification()

    def doResizification(self):
        font = self.item_indices[1].font()
        scrollArea = self.upper.GUI['gridScrollArea']
        QScrollArea_height = scrollArea.height()
        QScrollArea_margin_and_border_height = 4 # currently border is 1 px thick, top and bottom, and margin is 2px on the bottom (2px intersect with scrollbar but whatever)
        QScrollArea_scrollbar_height = scrollArea.horizontalScrollBar().height() #Always assume horizontal scrollbar is present, even if not. Solves issue with flickering
        header_height = icon('size').height()
        desired_height = (QScrollArea_height-QScrollArea_margin_and_border_height-header_height-QScrollArea_scrollbar_height)//self.pagelength
        
        fontSize = 0
        f = QFont(font)
        while True:
            f.setPixelSize( fontSize+1 )
            if QFontMetrics(f).height() <= desired_height: 
                fontSize += 1
            else:   break
            
        first = style('GRID_column').split('font-size:')
        second = first[1].split('px')
        second[0] = str(fontSize)
        styleSheetLib['GRID_column'] = first[0] + 'font-size:' + 'px'.join(second)
        first2 = style('GRID_label').split('font-size:')
        second2 = first2[1].split('px')
        second2[0] = str(fontSize)
        styleSheetLib['GRID_label'] = first2[0] + 'font-size:' + 'px'.join(second2)

        # Applies font size modification - only slow part of this whole thing
        self.item_indices[1].setStyleSheet(style('GRID_label'))
        for c in range(len(self.columns)):
            self.columns[c][1].setStyleSheet(style('GRID_column'))
        self.upper.set_page()

    # Loads all of the text and formatting for the GRID,
    # Depending on the view (assets or transactions), the columns we want to see, and the page we're on
    def grid_render(self, headers:list, sorted_items:list, page:int, specialinfo=None):
        self.set_columns(len(headers))  # NOTE: 10-20% of portfolio page lag, 50% of asset page lag

        first_item = self.pagelength*page
        last_item = self.pagelength*(page+1)
        rowrange = range(first_item,last_item)
        
        # Clears error states
        for r in range(self.pagelength):
            self.highlights[r%self.pagelength].error(False)

        #Sets the item indices
        toDisplay = ''
        for r in rowrange:
            toDisplay += str(r+1)+'<br>'
        self.item_indices[1].setText(toDisplay.removesuffix('<br>'))
        
        stop = len(sorted_items)-1 #last index in self.sorted
        for c in range(len(self.columns)):
            # Column header
            header_title = headers[c]
            self.columns[c][0].setText(metric_formatting_lib[header_title]['headername']) # Sets text to proper header name
            self.columns[c][0].info = header_title # Sets info quick-access variable, to current header's variable
            if self.upper.rendered.isPortfolio(): # Sets header tooltip
                self.columns[c][0].setToolTip('\n'.join(textwrap.wrap(metric_desc_lib['asset'][header_title], 40)))
            elif self.upper.rendered.isAsset() or self.upper.rendered.isGrandLedger():
                self.columns[c][0].setToolTip('\n'.join(textwrap.wrap(metric_desc_lib['transaction'][header_title], 40)))


            # Column rows' text
            longest_text_length = 0 # Records longest word/number: we use this to set the width of the column
            toDisplay = '' # This will be the string of text for this column
            for r in rowrange:
                if r > stop: toDisplay += '<br>' #Inserts empty lines where there is nothing to display
                else:
                    item = sorted_items[r]
                    formatted_text = item.metric_to_str(header_title, specialinfo) # Retrieves formatted version of text itself
                    HTML_formatting = item.get_metric_style(header_title, specialinfo) # Retrieves HTML formatting for text
                    if item.ERROR:   self.highlights[r%self.pagelength].error(True) # if transaction/asset has an error, highlights it in red
                    if len(formatted_text) > longest_text_length: longest_text_length = len(formatted_text) # Records longest text, to set column width
                    toDisplay += HTMLify(formatted_text, HTML_formatting)+'<br>' # adds this row of text to toDisplay
            self.columns[c][1].setText(toDisplay.removesuffix('<br>')) # Sets column text to toDisplay
            

class RenderState():
    def __init__(self, func_portfolio, func_asset, func_grand_ledger, currentState, currentAsset=None):
        self.func_asset = func_asset
        self.func_portfolio = func_portfolio
        self.func_grand_ledger = func_grand_ledger

        self.state = currentState
        self.asset = currentAsset
    
    def getState(self) -> str:
        return self.state
    def getAsset(self) -> str:
        return self.asset
    
    def setPortfolio(self):
        self.state = 'portfolio'
        self.asset = None
        self.func_portfolio()
    def isPortfolio(self):
        return self.state == 'portfolio'

    def setAsset(self, currentAsset):
        self.state = 'asset'
        self.asset = currentAsset
        self.func_asset()
    def isAsset(self):
        return self.state == 'asset'
    
    def setGrandLedger(self):
        self.state = 'grand_ledger'
        self.asset = None
        self.func_grand_ledger()
    def isGrandLedger(self):
        return self.state == 'grand_ledger'




