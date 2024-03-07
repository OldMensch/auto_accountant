
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
    def __init__(self, portfolio, raw_data:dict):
        # 7.4042 ms for ~5300 transactions, for everything before recalculate 
        #Set to true for transfers that don't have a partner, and with missing data. Stops metrics() short, and tells the renderer to color this RED
        self.ERROR = False  
        self.ERR_MSG =  ''
        self.ERROR_TYPE = ''
        self.portfolio = portfolio
        
        self._data = dict(default_trans_data)
        self._data.update(raw_data) # 4.2939 ms
        self._metrics = dict(default_trans_metrics)
        self._formatted = {} # Contains pre-formatted copy of all metrics to improve performance
        self.recalculate()

    #Pre-calculates useful information to GREATLY increase performance
    def recalculate(self):          # 50.3061ms for ~5300 transactions
        """Recalculates all metrics and formatting based on current raw data"""
        self._metrics['hash'] = self.calc_hash(self._data) # 3.0735ms for ~5300 transactions
        self.calc_missing()         # 7.2830ms for ~5300 transactions
        self.calc_metrics()         # 24.3175ms for ~5300 transactions
        self.calc_inference()       # 2.0903ms for ~5300 transactions
        self.calc_formatting()      # 88.8317ms for ~5300 transactions # worst offender, mostly from format_general
        self.calc_bad_asset_tickers()
        #self.calc_quick_refs()      # 6.8355ms for ~5300 transactions 
    
    def calc_hash(self, raw_data:dict): #Hash Function - A transaction is unique insofar as its date, type, wallet, and three asset types are unique from any other transaction.
        """Returns hash for given raw data"""
        return hash((raw_data['date'],raw_data['type'],raw_data['wallet'],raw_data['loss_asset'],raw_data['fee_asset'],raw_data['gain_asset']))
    def calc_missing(self):
        """Detect and log missing data for this transaction"""
        missing = set()
        # Is it missing the type?
        if self._data['type'] == None: missing.add(data)
        else: # Can only calculate these if 'type' not missing
            # If there is a fee asset, is it missing the necessary quantity/price data?
            if self._data['fee_asset'] != None and self._data['fee_quantity'] == None:  missing.add('fee_quantity')
            if self._data['fee_asset'] != None and self._data['fee_price'] == None:     missing.add('fee_price')
            # Check all data
            for data in valid_transaction_data_lib[self._data['type']]:
                if data in ('fee_asset','fee_quantity','fee_price'):    continue    # Fees are special case (above)
                if self._data[data] == None:                            missing.add(data)

        self._metrics['missing'] = list(missing) # list of missing data
        self.ERROR = len(missing)>0
        self.ERROR_TYPE = 'data'
        self.ERR_MSG = f'Transaction is missing data: \'{'\', \''.join(metric_formatting_lib[m]['name'] for m in missing)}\''
        if self.ERROR: print(f'||WARNING|| Newly created t{self.ERR_MSG[1:]}')
    def calc_metrics(self):
        MISSING = self._metrics['missing']
        # DATATYPE CONVERSION - MASSIVE performance gains saved by converting raw strings to objects here
        # ==================
        # INTEGERS - Datatype preserved by JSON
        if 'date' not in MISSING: self._metrics['date'] = int(self._data['date'])
        # STRINGS - Datatype preserved by JSON
        for data in ('type','wallet','description','loss_asset','fee_asset','gain_asset'):
            if data not in MISSING: self._metrics[data] = self._data[data]
        # DECIMALS
        for data in ('loss_quantity','loss_price','fee_quantity','fee_price','gain_quantity','gain_price'):     #NOTE: Lag is ~11ms for ~4000 transactions
            if data not in MISSING: 
                d = self._data[data]
                if d:   self._metrics[data] = Decimal(d)

        if self.ERROR: return # DONT CALCULATE if there is any errors: this stuff can wait for now
        # NEW CALCULATED STUFF
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

        # PRICE QUANTITY VALUE - The price, quantity, and value, displayed on asset panes
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
        """Infers metrics where possible - really only for display purposes"""
        # Can only infer if type is known
        if 'type' in self._metrics['missing']: return 
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
            try:
                self._metrics['loss_price'] = (self._metrics['gain_quantity']-self._metrics['fee_quantity'])/self._metrics['loss_quantity']
            except: pass

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
            try:
                self._metrics['gain_price'] = (self._metrics['loss_value']+self._metrics['fee_value'])/self._metrics['gain_quantity']
            except: pass

        # QUANTITIES - always stored or irrelevant
    def calc_formatting(self):
        """Pre-calculates formatted versions of all metrics in _metrics"""
        for metric in default_trans_metrics.keys():
            formatted_metric = ''
            if metric in self._metrics['missing']: 
                self._formatted[metric] = MISSINGDATA
                continue
            if metric not in metric_formatting_lib: 
                self._formatted[metric] = '!NO_FORMAT'
                continue
            match metric:
                # asset-dependent variables
                case 'value' | 'quantity' | 'price' | 'balance': 
                    textFormat,colorFormat = metric_formatting_lib[metric]['format'],metric_formatting_lib[metric]['color']
                    self._formatted[metric] = {}
                    for a in self._metrics['all_assets']:
                        # if self._metrics[metric][a] doesn't exist, this causes a crash
                        try:    self._formatted[metric][a] = format_metric(self._metrics[metric][a], textFormat, colorFormat) 
                        except: self._formatted[metric][a] = MISSINGDATA
                    continue
                case other:    
                    textFormat,colorFormat = metric_formatting_lib[metric]['format'],metric_formatting_lib[metric]['color']
                    metric_value = self._metrics[metric]
                    if metric_value:    formatted_metric = format_metric(metric_value, textFormat, colorFormat)
            self._formatted[metric] = formatted_metric
    def calc_bad_asset_tickers(self):
        for a in ('loss_asset','fee_asset','gain_asset'):
            tc = self._data[a]
            if tc in forks_and_duplicate_tickers_lib:
                self._data[a] = forks_and_duplicate_tickers_lib[tc][0]
                break
        else: return # no assets replace
        self.recalculate()
        self.calc_formatting()
        

    def calc_quick_refs(self):
        """Sets WALLET, LOSS_ASSET, FEE_ASSET, and GAIN_ASSET to object references from the portfolio, in the _metrics dict"""
        for metric in ('loss_asset','fee_asset','gain_asset'):
            if self._data[metric] is not None:
                try:
                    self._metrics[metric] = self.portfolio.asset(self._data[metric])
                except: raise Exception(f'||ERROR|| Failed to find reference to asset \'{self._data[metric]}\' in portfolio')
        if self._data['wallet'] is not None:
            try:
                self._metrics['wallet'] = self.portfolio.wallet(self._data['wallet'])
                # Formatting can be done without the asset object
            except: raise Exception(f'||ERROR|| Failed to find reference to wallet \'{self._data['wallet']}\' in portfolio')

    #Comparison operator overrides
    def __eq__(self, __o: object) -> bool:
        if type(__o) != Transaction: return False
        return self.get_hash() == __o.get_hash()
    def __lt__(self, __o: object) -> bool:
        # Basically, we try to sort transactions by date, unless they're the same, then we sort by type, unless that's also the same, then by wallet... and so on.
        #date
        if 'date' in self._metrics['missing']: return True
        S,O = self.get_raw('date'),__o.get_raw('date')
        if S!=O:   return S<O
        #Type
        if 'type' in self._metrics['missing']: return True
        S,O = self.get_raw('type'),__o.get_raw('type')
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

    #JSON Functions
    def toJSON(self) -> dict: # Returns a dictionary of all data for this transaction. Missing/Nones are omitted
        return {data:self._data[data] for data in valid_transaction_data_lib[self._data['type']] if self._data[data] != None}
   


class Asset():  
    def __init__(self, tickerclass:str, name:str='', description:str=''):
        self.ERROR = False  
        self._tickerclass = tickerclass
        tc_tuple = self.calc_separate_tickerclass(tickerclass)
        self._ticker = tc_tuple[0]
        self._class = tc_tuple[1]
        self._name = name
        self._description = description
        self._hash = None

        self._metrics = {}

        self._ledger = {} #A dictionary of all the transactions for this asset. Mainly for making rendering more efficient.

        self._hash = self.calc_hash(self._ticker, self._class)

    def calc_hash(self, TICKER, CLASS, TICKERCLASS=None): # Gives this asset a unique identifier based on its ticker and class
        if TICKERCLASS: return hash(Asset.calc_separate_tickerclass(self, TICKERCLASS))
        return hash((TICKER, CLASS))
    
    def calc_separate_tickerclass(self, TICKERCLASS):
        return tuple(TICKERCLASS.split('z'))
    def calc_join_tickerclass(self, TICKER, CLASS):
        return TICKER+'z'+CLASS
    
    #Modification functions
    def add_transaction(self, transaction_obj:Transaction): self._ledger[transaction_obj.get_hash()] = transaction_obj
    def delete_transaction(self, transaction_obj:Transaction): self._ledger.pop(transaction_obj.get_hash())

    # Comparison functions
    def __eq__(self, __o: object) -> bool:
        if type(__o) != Asset: return False
        return self.get_hash() == __o.get_hash()
    def __lt__(self, __o: object) -> bool:
        return self.tickerclass() < __o.tickerclass()
    def __hash__(self) -> str: return self.get_hash()

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
        if info == 'class':         return assetclasslib[self._class]['name'] #Returns the long display name for this class

        #This is Market Data
        return format_metric(self.get_metric(info), metric_formatting_lib[info]['format'], metric_formatting_lib[info]['color'])
    
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
        # Automatically add assets
        for a in transaction_obj._metrics['all_assets']:
            if not self.hasAsset(a):
                asset_obj = Asset(a)
                self.add_asset(asset_obj)
            else:  asset_obj = self.asset(a)
            asset_obj.add_transaction(transaction_obj) #Adds this transaction to asset's ledger
        # Automatically add wallets
        WALLET = transaction_obj.get_raw('wallet')
        if WALLET and not self.hasWallet(WALLET):
            self.add_wallet(Wallet(WALLET))
        # Add transaction
        if self.hasTransaction(transaction_obj.get_hash()): print('||WARNING|| Overwrote transaction with same hash.', transaction_obj.get_hash())
        self._transactions[transaction_obj.get_hash()] = transaction_obj
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
        if self.hasWallet(wallet_obj.name()): print('||WARNING|| Overwrote wallet with same hash.', wallet_obj.get_hash())
        self._wallets[wallet_obj.get_hash()] = wallet_obj
    def add_filter(self, filter_obj:Filter):
        if self.hasFilter(filter_obj.get_hash()): print('||WARNING|| Overwrote filter with same hash.', filter_obj.get_hash())
        self._filters[filter_obj.get_hash()] = filter_obj

    def delete_asset(self, asset:Asset):              self._assets.pop(asset.get_hash())
    def delete_transaction(self, transaction_obj:Transaction):  
        # Automatically remove assets
        for a in transaction_obj.get_metric('all_assets'):
            a_obj = self.asset(a)
            if len(a_obj._ledger) == 0:
                self.delete_asset(a_obj)
        # Automatically add/remove assets
        transaction_obj = self._transactions.pop(transaction_obj.get_hash()) #Removes transaction from the portfolio itself
        #Removes transaction from relevant asset ledgers
        assets = set([transaction_obj.get_raw('loss_asset'),transaction_obj.get_raw('fee_asset'),transaction_obj.get_raw('gain_asset')])
        for a in assets: 
            if a != None: self.asset(a).delete_transaction(transaction_obj) #Adds this transaction to loss asset's ledger
    def delete_wallet(self, wallet:Wallet):            self._wallets.pop(wallet.get_hash())
    def delete_filter(self, filter:Filter):            self._filters.pop(filter.get_hash())


    #JSON functions
    def loadJSON(self, JSON:dict, merge=False, overwrite=False): #Loads JSON data, erases any existing data first
        
        #If loading...                      clear everything,  load the new data.
        #If merging and overwriting,                           load the new data.
        #If merging and NOT overwriting,                       load the new data, skipping duplicate transactions.

        if not merge:   self.clear()


        # TRANSACTIONS & ASSETS & WALLETS - NOTE: Lag is ~443.4364ms for ~5300 transactions
        if 'transactions' in JSON:
            parsed_transactions = None
            try: parsed_transactions = pd.read_csv(StringIO(JSON['transactions']), dtype='string').astype({'date':float})
            except: print('||ERROR|| Failed to read transactions from JSON.')
            if type(parsed_transactions) == pd.DataFrame:
                for t in parsed_transactions.iterrows():
                    raw_data = t[1].dropna().to_dict() # 185.2033 ms for ~5300 transactions
                    new_trans = Transaction(self, raw_data) # 153.2676 ms for ~5300 transactions
                    if merge and not overwrite and self.hasTransaction(new_trans.get_hash()): continue     #Don't overwrite identical transactions, when specified
                    self.add_transaction(new_trans) #8.5012ms for ~5300 transactions


        # ASSETS - 1.5335ms for ~40 assets
        # Assets already initialized in the previous step (implemented in add_transaction function)
        # Here we load names/descriptions
        if 'assets' in JSON:
            parsed_assets = None
            try: parsed_assets = pd.read_csv(StringIO(JSON['assets']), dtype='string').fillna('')
            except: print('||ERROR|| Failed to read asset names/descriptions from JSON.')
            if type(parsed_assets) == pd.DataFrame:
                for a in parsed_assets.iterrows(): # Look through all asset savedata
                    try:    new_asset_data = Asset.calc_join_tickerclass(None, a[1]['ticker'], a[1]['class']), a[1]['name'], a[1]['description'] # Parse row
                    except: 
                        print('||ERROR|| An asset\'s name/decription failed to load.')
                        continue
                    if self.hasAsset(new_asset_data[0]): # If asset already in portfolio, import name/description
                        if merge and not overwrite: continue #Don't overwrite identical assets, when specified
                        self.asset(new_asset_data[0])._name = new_asset_data[1] # Set existing asset name to saved name
                        self.asset(new_asset_data[0])._description = new_asset_data[2] # Set existing asset description to saved description
        
        # WALLETS - 0.9553ms for 9 wallets (probably not much more for a million) 
        # MOST Wallets already initialized in the first step (implemented in add_transaction function)
        # Here we load descriptions
        if 'wallets' in JSON:
            parsed_wallets = None
            try: parsed_wallets = pd.read_csv(StringIO(JSON['wallets']), dtype='string').fillna('')
            except: print('||ERROR|| Failed to read wallets from JSON.')
            if type(parsed_wallets) == pd.DataFrame:
                for w in parsed_wallets.iterrows():
                    try: NAME, DESC = w[1]['name'], w[1]['description']
                    except:  
                        print('||WARNING|| Wallet failed to load.')
                        continue
                    if self.hasWallet(NAME):    
                        if merge and not overwrite: continue #Don't overwrite identical wallets, when specified
                        self.wallet(NAME)._description = DESC
                    else:                       self.add_wallet(Wallet(NAME, DESC))
  

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
    def hasWallet(self, wallet:str) -> bool:                return Wallet(wallet).get_hash() in self._wallets
    def hasFilter(self, filter:str) -> bool:                return filter in self._filters
    
    #Access functions:
    def asset(self, asset:str) -> Asset:                    # Returns asset object, given its tickerclass
        """Returns asset object, given its tickerclass"""
        if type(asset)==str:        return self._assets[Asset.calc_hash(None, None, None, asset)]
        elif type(asset)==Asset:    return self._assets[asset]
        else: raise TypeError(f'||ERROR|| Invalid type {type(asset)}')
    def transaction(self, transaction:int) -> Transaction:  # Returns transaction object, given its hash
        """Returns transaction, given its hash"""
        return self._transactions[transaction]
    def wallet(self, wallet_name:str) -> Wallet:                 # Returns wallet object, given its hash
        """Returns wallet object, given its name"""
        return self._wallets[hash(wallet_name)]

    def assets(self) -> list:                               return self._assets.values()
    def transactions(self) -> list:                         return self._transactions.values()
    def wallets(self) -> list:                              return self._wallets.values()
    def filters(self) -> list:                              return self._filters.values()

    def all_wallet_names(self) -> list:                     return [w.name() for w in self._wallets.values()]
    def all_asset_tickerclasses(self) -> list:              return [a.tickerclass() for a in self._assets.values()]


    def get_metric(self, info:str):
        """Returns raw savedata string for this metric"""
        try:    return self._metrics[info]
        except: return MISSINGDATA

    def metric_to_str(self, info:str, charlimit=0, *args, **kwargs) -> str:
        """Returns formatted str for given metric"""
        return format_metric(self.get_metric(info), metric_formatting_lib[info]['format'], metric_formatting_lib[info]['color'], charlimit=charlimit)
    

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



class ViewState():
    """Stores current visual mode, and accessory relevant information"""
    def __init__(self):
        self.state = None
        self.asset = None
        self.PORTFOLIO = 'portfolio'
        self.GRAND_LEDGER = 'grand_ledger'
        self.ASSET = 'asset'
    
    def getState(self) -> str:
        return self.state
    def getDefHeader(self):
        try:        return default_headers[self.getState()]
        except:     raise KeyError(f'||ERROR|| getDefHeader not implemented for unknown ViewState {self.getState()}')
    def getHeaderID(self) -> list:
        return 'header_'+self.getState()
    def getHeaders(self) -> list:
        return setting('header_'+self.getState())
    def getAsset(self) -> str:
        return self.asset
    def getHeaderTooltip(self, header:str):
        if self.state == self.PORTFOLIO:    return metric_desc_lib['asset'][header]
        else:                               return metric_desc_lib['transaction'][header]


    def isPortfolio(self):
        return self.state == self.PORTFOLIO

    def setAsset(self, currentAsset):
        self.asset = currentAsset
    def isAsset(self):
        return self.state == self.ASSET
    
    def isGrandLedger(self):
        return self.state == self.GRAND_LEDGER

    
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
            QLabel("\n", styleSheet=style('GRID_header')),
            QLabel(alignment=Qt.AlignRight, styleSheet=style('GRID_header'))
        )
        self.highlights = [GRID_ROW(row, self.set_highlight, self._click, self._double_click) for row in range(self.pagelength)]
        
        self.fake_header = QWidget(styleSheet=style('GRID_header'))
        header,text = self.item_indices[0],self.item_indices[1]
        self.addWidget(header, 0, 0) # Upper-left corner of the GRID
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
            QLabel(alignment=Qt.AlignRight, styleSheet=style('GRID_data'))
        ))
        header,text = self.columns[new_index][0],self.columns[new_index][1]
        

        self.addWidget(header, 0, new_index+1)
        self.addWidget(text, 1, new_index+1, self.pagelength, 1)
        text.setAttribute(Qt.WA_TransparentForMouseEvents) # Our mouse cursor penetrates the text, goes right to the highlight layer
    def delete_column(self):    #NOTE: Lag is 7.52ms on avg
        old = self.columns.pop()    #Remove the tuple from the columns
        old[0].deleteLater()   #Destroy the header
        old[1].deleteLater()   #Destroy the label
    def set_columns(self, n:int):
        '''Automatically adds or removes header columns until there are \'n\' columns'''
        if n < 0: raise Exception('||ERROR|| Cannot set number of columns to less than 0')
        self.setColumnStretch(len(self.columns)+1, 0) # Unstretches previously stretchy column
        while len(self.columns) != n:
            if len(self.columns) > n:   self.delete_column()
            else:                       self.add_column()
        self.setColumnStretch(len(self.columns)+1, 1) #Stretches extremely distant column, so that all data columns clump as efficiently as possible
        self.addWidget(self.fake_header, 0, len(self.columns)+1) # Moves our fake header over to the final empty area
        
        # Readjusts highlight bars to be the correct width
        for r in range(self.pagelength):
            self.addWidget(self.highlights[r], r+1, 0, 1, len(self.columns)+2)
            self.highlights[r].lower()
        

    def update_page_length(self, n:int):
        if n < 25 or n > 100: return
        self.set_selection()    # De-selects everything
        self.set_highlight()    # De-highlights everything
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
            
        first = style('GRID_data').split('font-size:')
        second = first[1].split('px')
        second[0] = str(fontSize)
        styleSheetLib['GRID_data'] = first[0] + 'font-size:' + 'px'.join(second)
        first2 = style('GRID_header').split('font-size:')
        second2 = first2[1].split('px')
        second2[0] = str(fontSize)
        styleSheetLib['GRID_header'] = first2[0] + 'font-size:' + 'px'.join(second2)

        # Applies font size modification - only slow part of this whole thing
        self.item_indices[1].setStyleSheet(style('GRID_header'))
        for c in range(len(self.columns)):
            self.columns[c][1].setStyleSheet(style('GRID_data'))
        self.upper.set_page()

    # Loads all of the text and formatting for the GRID,
    # Depending on the view (assets or transactions), the columns we want to see, and the page we're on
    def grid_render(self, view:ViewState, sorted_items:list, page:int):
        self.set_columns(len(view.getHeaders()))  # NOTE: 10-20% of portfolio page lag, 50% of asset page lag

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
            header_ID = view.getHeaders()[c]
            self.columns[c][0].setText(metric_formatting_lib[header_ID]['headername']) # Sets text to proper header name
            self.columns[c][0].info = header_ID # Sets info quick-access variable, to current header's variable
            self.columns[c][0].setToolTip('\n'.join(textwrap.wrap(view.getHeaderTooltip(header_ID), 40))) # Sets header tooltip

            # Column rows' text
            toDisplay = '' # This will be the string of text for this column
            for r in rowrange:
                if r > stop: toDisplay += '<br>' #Inserts empty lines where there is nothing to display
                else:
                    item = sorted_items[r]
                    if item.ERROR:   self.highlights[r%self.pagelength].error(True) # if transaction/asset has an error, highlights it in red
                    # adds this row of text to the display
                    toDisplay += f'{item.metric_to_str(header_ID, view.getAsset())}<br>'
            self.columns[c][1].setText(toDisplay.removesuffix('<br>')) # Sets column text to toDisplay
            




