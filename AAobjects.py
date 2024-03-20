
from AAlib import *

import pandas as pd
from io import StringIO


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
    def deep_hash(self) -> int: return hash((self._name, self._description))
    def name(self) -> str:      return self._name
    def desc(self) -> str:      return self._description

    #JSON Function
    def toJSON(self) -> Dict[str,str]:   return {'name':self._name, 'description':self._description}

class Transaction():
    def __init__(self, raw_data:dict):
        self.ERROR = False  
        self.ERR_MSG =  ''
        self.ERROR_TYPE = ''
        
        # DATA DICTS - NOTE: 3 ms w/ 5600
        # Raw data to save to JSON
        self._data = {metric:None for metric in default_trans_data}
        self._metrics = {} # raw data converted to proper types, market data and post-instantiation calculated metrics
        self._formatted = {} # Metrics formatted and ready for display

        self._data.update(raw_data) # 5ms w/ 5600

        # Fixes bug where all balances are identical... odd this doesn't affect 
        self.precalculate() # NOTE: timing below

    # METRICS
    # On initialization
    def precalculate(self):                                 # NOTE: 211ms w/ 5600
        """Precalculates metrics and formatting, based only on raw data from THIS TRANSACTION"""
        self.calc_correct_bad_tickers()                     # NOTE: 7ms w/ 5600
        self._metrics['hash'] = self.calc_hash(self._data)  # NOTE: 1ms w/ 5600
        self.calc_missing()                                 # NOTE: 25ms w/ 5600
        self.calc_type_conversions()                        # NOTE: 70ms w/ 5600
        self.calc_inference()                               # NOTE: 4ms w/ 5600
        self.calc_new_metrics()                             # NOTE: 6ms w/ 5600
        self.calc_formatting()                              # NOTE: 120ms w/ 5600

    def calc_correct_bad_tickers(self):
        """Fixes tickers that have changed over time: Like how LUNA became LUNC"""
        changed_tickers = False
        for part in ('loss_','fee_','gain_'):
            TICKER,CLASS,DATE = self._data[part+'ticker'],self._data[part+'class'],self._data['date']
            if CLASS in forks_and_duplicate_tickers_lib and TICKER in forks_and_duplicate_tickers_lib[CLASS]:
                NEW_TICKER, FLIP_DATE  = forks_and_duplicate_tickers_lib[CLASS][TICKER]
                if DATE < FLIP_DATE:
                    self._data[part+'ticker'] = NEW_TICKER
                    changed_tickers = True
        if changed_tickers: # need to update _metrics if we changed tickers
            self._metrics.update(self._data)
    def calc_hash(self, raw_data:dict): #Hash Function - A transaction is unique insofar as its date, type, wallet, and three asset types are unique from any other transaction.
        """Transaction hash based on: DATE, TYPE, WALLET, LOSS TICKER/CLASS, FEE TICKER/CLASS, GAIN TICKER/CLASS"""
        return hash((raw_data['date'],
                     raw_data['type'],
                     raw_data['wallet'],
                     raw_data['loss_ticker'],
                     raw_data['fee_ticker'],
                     raw_data['gain_ticker'],
                     raw_data['loss_class'],
                     raw_data['fee_class'],
                     raw_data['gain_class'],
                     ))
    def calc_missing(self):
        """Detect and log missing data for this transaction"""
        missing = set()
        # Is it missing the type?
        if self._data['type'] == None: missing.add(data)
        else: # Can only calculate these if 'type' not missing
            # If there is a fee asset, is it missing the necessary quantity/price data?
            if self._data['fee_ticker'] != None and self._data['fee_class'] != None:
                if self._data['fee_quantity'] == None:  missing.add('fee_quantity')
                if self._data['fee_price'] == None:     missing.add('fee_price')
            # If there is a ticker w/o its corresponding class, or vice versa, error
            for a in ('loss_','fee_','gain_'):
                if self._data[a+'ticker'] is None and self._data[a+'class'] is not None:    missing.add(a+'ticker')
                elif self._data[a+'ticker'] is not None and self._data[a+'class'] is None:  missing.add(a+'class')
            # Check all data
            for data in trans_type_minimal_set[self._data['type']]:
                if data in ('description','fee_ticker','fee_class','fee_quantity','fee_price'):    continue    # Desc. and Fees are special case (above)
                if self._data[data] == None:                            missing.add(data)

        self._metrics['missing'] = list(missing) # list of missing data
        self.ERROR = len(missing)>0
        self.ERROR_TYPE = 'data'
        self.ERR_MSG = f'Transaction is missing data: \'{'\', \''.join(metric_formatting_lib[m]['name'] for m in missing)}\''
        if self.ERROR: print(f'||WARNING|| Newly created t{self.ERR_MSG[1:]}')
    def calc_type_conversions(self):
        """Pre-converts quantities/prices to Decimal objects, for much faster auto-accounting.
        \nAlso creates 'all_assets' metric, a list of ticker/class tuples for all assets related to this transaction"""
        # INTEGERS and STRINGS - Datatypes preserved by JSON (already copied on initialization)
        # DECIMALS - stored as strings in JSON, convert back to decimals here
        # NOTE: 10ms w/ 5600
        for metric,data in self._data.items():
            if data is None: 
                self._metrics[metric] = None
                continue
            match metric_formatting_lib[metric]['nativeType']:
                case 'decimal':     self._metrics[metric] = Decimal(data)
                case other:         self._metrics[metric] = data
        # ASSET SPECIFIC METRICS - NOTE: 30ms w/ 5600
        for asset_specific_metric in asset_specific_metrics:
            self._metrics[asset_specific_metric] = {class_code:{} for class_code in class_lib.keys()} # 4ms w/ 5600

        # ALL ASSETS - NOTE: 3ms w/ 5600
        self._metrics['all_assets'] = list(set((self._data[metric+'ticker'],self._data[metric+'class']) 
                                               for metric in ('loss_','fee_','gain_') 
                                               if self._data[metric+'ticker'] is not None and self._data[metric+'class'] is not None))
    def calc_inference(self):
        """Infers metrics where possible - reduces code complexity, increases performance"""
        TYPE = self._data['type']
        if not TYPE: return # Can only infer if type is known
        # STATIC INFERENCES - always the same, depending on transaction type
        self._metrics.update(trans_type_static_inference[TYPE])

        # DYNAMIC INFERENCES - depend on transaction data
        LQ,FQ,GQ = self._metrics['loss_quantity'],self._metrics['fee_quantity'],self._metrics['gain_quantity']
        LP,FP,GP = self._metrics['loss_price'],   self._metrics['fee_price'],   self._metrics['gain_price']
        if not LP: # loss price: omitted for sales
            try: self._metrics['loss_price'] = ((FQ*FP)+(GQ*GP))/LQ
            except: pass
        if not GP: # gain price: omitted for purchases/purchases w crypto fees/trades
            try:    self._metrics['gain_price'] = ((LQ*LP)+(FQ*FP))/GQ
            except: pass
    def calc_new_metrics(self):
        """Calculates per-transaction metrics:
        \n Loss/Fee/Gain Values - the quantity*price, aka total value in USD. We use these a lot! Good to pre-calculate.
        \n Per-Asset price/quantity/value: calculates the PQV to be displayed on asset ledgers for this transaction.
        """
        # LOSS/FEE/GAIN VALUES - Where value is quantity*price, AKA total value in USD. Saves performance to pre-calculate these!
        LQ,FQ,GQ = self._metrics['loss_quantity'],self._metrics['fee_quantity'],self._metrics['gain_quantity']
        LP,FP,GP = self._metrics['loss_price'], self._metrics['fee_price'], self._metrics['gain_price']
        if LQ and LP: LV = LQ*LP # Loss value
        else: LV = 0
        if FQ and FP: FV = FQ*FP # Fee value
        else: FV = 0
        if GQ and GP: GV = GQ*GP # Gain value
        else: GV = 0
        self._metrics['loss_value'],self._metrics['fee_value'],self._metrics['gain_value'] = LV,FV,GV

        if self.ERROR: return # Can't calculate these with errors!
        # PRICE QUANTITY VALUE - Price/quantity/value of transaction, per related asset
        LT,FT,GT = self._data['loss_ticker'],self._data['fee_ticker'],self._data['gain_ticker']
        LC,FC,GC = self._data['loss_class'],self._data['fee_class'],self._data['gain_class']
        for t,c in self._metrics['all_assets']:
            P,Q,V = 0,0,0
            if t==LT and c==LC:
                Q -= LQ
                V -= LV
            if t==FT and c==FC:
                Q -= FQ
                V -= FV
            if t==GT and c==GC:
                Q += GQ
                V += GV
            if Q!=0 and V!=0:  P = V/Q 
            V = abs(V)

            self._metrics['price'][c][t], self._metrics['quantity'][c][t], self._metrics['value'][c][t] = P,Q,V
    def calc_formatting(self):
        """Pre-calculates formatted versions of all metrics in _metrics"""
        for metric in trans_metrics_to_format:
            formatted_metric = ''
            if metric in self._metrics['missing']: 
                self._formatted[metric] = MISSINGDATA
                continue
            if metric not in metric_formatting_lib: 
                self._formatted[metric] = '!NO_FORMAT'
                continue

            # asset-dependent variables (price, value, quantity, etc)
            if metric_formatting_lib[metric]['asset_specific']: 
                textFormat,colorFormat = metric_formatting_lib[metric]['format'],metric_formatting_lib[metric]['color']
                self._formatted[metric] = {class_code:{} for class_code in class_lib.keys()}
                for t,c in self._metrics['all_assets']:
                    # If self._metrics[metric][a] doesn't exist, this causes a crash
                    try:    self._formatted[metric][c][t] = format_metric(self._metrics[metric][c][t], textFormat, colorFormat) 
                    except: self._formatted[metric][c][t] = MISSINGDATA
                continue
            else:    
                textFormat,colorFormat = metric_formatting_lib[metric]['format'],metric_formatting_lib[metric]['color']
                metric_value = self._metrics[metric]
                if metric_value:    formatted_metric = format_metric(metric_value, textFormat, colorFormat)
            self._formatted[metric] = formatted_metric
 
    # After initialization
    def recalc_iso_date(self) -> str:   
        self._formatted['date'] = format_metric(self._data['date'], metric_formatting_lib['date']['format'],metric_formatting_lib['date']['color'])

    # Access
    def get_raw(self, info:str) -> str:    
        """Returns raw savedata string for this metric"""
        return self._data[info]
    def get_metric(self, metric:str, ticker:str=None, class_code:str=None):
        """Returns this metric in its native datatype"""
        if metric in metric_formatting_lib and metric_formatting_lib[metric]['asset_specific']:    
            try:    return self._metrics[metric][class_code][ticker]
            except: return None
        try:    return self._metrics[metric]
        except: return None
    def get_formatted(self, metric:str, ticker:str=None, class_code:str=None) -> str:
        """Returns formatted str for given metric"""
        if metric_formatting_lib[metric]['asset_specific']:   
            try: return self._formatted[metric][class_code][ticker]
            except: pass
        else:       
            try: return self._formatted[metric]
            except: pass
        return MISSINGDATA


    # COMPARISON
    def __eq__(self, __o: object) -> bool:
        if type(__o) != Transaction: return False
        return self.get_hash() == __o.get_hash()
    def __lt__(self, __o: object) -> bool:
        # Sort by date, then by type based on type sorting priorities
        #date
        if 'date' in self._metrics['missing']: return True
        S,O = self._data['date'],__o._data['date']
        if S!=O:   return S<O
        #Type
        if 'type' in self._metrics['missing']: return True
        S,O = self._data['type'],__o._data['type']
        if S!=O:   return trans_type_formatting_lib[S]['priority']<trans_type_formatting_lib[O]['priority']
        # Break - assume always false
        return False
    def __hash__(self) -> str:          return self._metrics['hash']

    # QUICK ACCESS
    def get_hash(self) -> int:          return self._metrics['hash']
    def deep_hash(self) -> int:         return hash(tuple(self._data.values()))
    def unix_date(self) -> int:         return self._data['date']
    def iso_date(self) -> str:          return self._formatted['date']
    def type(self) -> str:              return self._data['type']
    def wallet(self) -> str:            return self._data['wallet']
    def desc(self) -> str:              return self._data['description']

    # JSON
    def toJSON(self) -> Dict[str,int|str]: # Returns a dictionary of all data for this transaction. Missing/Nones are omitted
        return {metric:self._data[metric] for metric in trans_type_minimal_set[self._data['type']] if self._data[metric] is not None}
   
class Asset():  
    def __init__(self, ticker:str, class_code:str, name:str='', description:str=''):
        self.ERROR = False  

        # Raw data to save to JSON
        self._data = self._metrics = {'ticker':ticker,'class':class_code,'name':name,'description':description}
        # raw data converted to proper types, market data and post-instantiation calculated metrics
        self._metrics = {'ticker':ticker,'class':class_code,'name':name,'description':description}
        # Metrics formatted and ready for display
        self._formatted = {}

        self._ledger = {} #A dictionary of all the transactions under this asset. Makes rendering more efficient.

        self.precalculate()

    # METRICS
    # On initialization
    def precalculate(self):
        """Precalculates metrics and formatting, based only on raw data from THIS ASSET"""
        self._metrics['hash'] = self.calc_hash(self._data['ticker'], self._data['class'])
        self.calc_formatting_static()

    def calc_hash(self, TICKER, CLASS) -> int:
        return hash((TICKER, CLASS))
    def calc_formatting_static(self):
        """Pre-calculates formatted strings for static metrics"""
        for metric in self._data:
            self._formatted[metric] = format_metric(self._data[metric], metric_formatting_lib[metric]['format'], metric_formatting_lib[metric]['color'])
    
    # After initialization
    def calc_formatting_dynamic(self):
        """Calculates formatted strings for dynamic metrics"""
        for metric in self._metrics:
            if metric not in self._data and metric in metric_desc_lib['asset']: # Don't reformat static metrics
                self._formatted[metric] = format_metric(self._metrics[metric], metric_formatting_lib[metric]['format'], metric_formatting_lib[metric]['color'])
    
    # Access
    def get_metric(self, info:str, *args, **kwargs) -> Decimal:
        """Returns this metric in its native datatype"""
        try:    return self._metrics[info]
        except: return None
    def get_formatted(self, metric:str, *args, **kwargs) -> str:
        """Returns formatted str for given metric"""
        try:    return self._formatted[metric]
        except: return MISSINGDATA
    

    # MODIFICATION
    def add_transaction(self, transaction_obj:Transaction): self._ledger[transaction_obj.get_hash()] = transaction_obj
    def delete_transaction(self, transaction_obj:Transaction): self._ledger.pop(transaction_obj.get_hash())
    def calculate_metric(self, metric, operation, A=None, B=None):
        """Calculates and sets metric for asset, based on given data"""
        if not A or not B: 
            raise Exception(f'||ERROR|| When calculating asset operation, \'A\' and \'B\' must be specified')
        result = 0
        match operation:
            case 'sum': # add across all transactions on this asset's ledger
                for t in self._ledger:    
                    try: result += t.get_metric(metric) # Add to sum if it exists
                    except: pass  
            case 'A+B': # add two portfolio metrics
                try: result = self.get_metric(A) + self.get_metric(B)
                except: pass
            case 'A-B': # add two portfolio metrics
                try: result = self.get_metric(A) - self.get_metric(B)
                except: pass
            case 'A*B': # multiply two portfolio metrics
                try: result = self.get_metric(A) * self.get_metric(B)
                except: pass
            case 'A/B': # divide one portfolio metric by another
                try: result = self.get_metric(A) / self.get_metric(B)
                except: pass
            case '(AB)/(1+B)':
                try: result = (self.get_metric(A) * self.get_metric(B)) / (1 + self.get_metric(B))
                except: pass
            case '(A/B)-1':
                try: result = (self.get_metric(A) / self.get_metric(B)) - 1
                except: pass
            case other:
                raise Exception(f'||ERROR|| Unknown operation for calculating asset metric, \'{operation}\'')
        self._metrics[metric] = result

    # COMPARISON
    def __eq__(self, __o: object) -> bool:
        if type(__o) != Asset: return False
        return self.get_hash() == __o.get_hash()
    def __lt__(self, __o: object) -> bool:
        S,O = self.ticker(), __o.ticker()
        if S<O: return S<O
        S,O = self.class_code(), __o.class_code()
        if S<O: return S<O
        return False
    def __hash__(self) -> str: return self._metrics['hash']

    # QUICK ACCESS
    def get_hash(self) -> int:      return self._metrics['hash']
    def deep_hash(self) -> int:     return hash(tuple(self._data.values()))
    def ticker(self) -> str:        return self._data['ticker']
    def class_code(self) -> str:    return self._data['class']
    def name(self) -> str:          return self._data['name']
    def desc(self) -> str:          return self._data['description']
    
    # JSON
    def toJSON(self) -> Dict[str,str]:
        return {key:value for key,value in self._data.items() if value is not None}

class Portfolio():
    def __init__(self):
        '''Initializes a Portfolio object, which contains dictionaries and lists of all the below:'''
        # For all of these, the key is the object's hash, and the value is the object itself 
        self._assets = {}
        self._transactions = {}
        self._wallets = {}
        self._filters = {} # in-memory only: not saved to JSON

        # Raw data to save to JSON
        #       (the only "raw data" is in the above dictionaries)
        # post-instantiation calculated metrics
        self._metrics = {}
        # Metrics formatted and ready for display
        self._formatted = {}
    
    # METRICS
    # After Initialization
    def calc_formatting_dynamic(self):
        for metric in self._metrics:
            try: self._formatted[metric] = format_metric(self.get_metric(metric), metric_formatting_lib[metric]['format'], metric_formatting_lib[metric]['color'])
            except: pass

    def calculate_metric(self, metric, operation, A=None, B=None, C=None):
        """Calculates new metric \'metric\', given operation and input of other metrics"""
        if operation != 'sum' and (not A or not B): 
            raise Exception(f'||ERROR|| When calculating portfolio operation, \'A\' and \'B\' must be specified')
        result = 0
        match operation:
            case 'sum': # add across assets
                for a in self.assets():    
                    try: result += a.get_metric(metric) # Add to sum if it exists
                    except: pass  
            case 'A+B': # add two portfolio metrics
                try: result = self.get_metric(A) + self.get_metric(B)
                except: pass
            case 'A-B': # add two portfolio metrics
                try: result = self.get_metric(A) - self.get_metric(B)
                except: pass
            case 'A*B': # multiply two portfolio metrics
                try: result = self.get_metric(A) * self.get_metric(B)
                except: pass
            case 'A/B': # divide one portfolio metric by another
                try: result = self.get_metric(A) / self.get_metric(B)
                except: pass
            case 'A/(B-C)':
                try: result = self.get_metric(A) / (self.get_metric(B) - self.get_metric(C))
                except: pass
            case '(A/B)-1':
                try: result = (self.get_metric(A) / self.get_metric(B)) - 1
                except: pass
            case other:
                raise Exception(f'||ERROR|| Unknown operation for calculating portfolio metric, \'{operation}\'')
        self._metrics[metric] = result

    # Access
    def get_metric(self, metric:str, *args, **kwargs):
        """Returns raw savedata string for this metric"""
        try:    return self._metrics[metric]
        except: return None
    def get_formatted(self, metric:str, charLimit:int=0, *args, **kwargs) -> str:
        """Returns formatted str for given metric"""
        if charLimit>0: 
            try: return format_metric(self.get_metric(metric), metric_formatting_lib[metric]['format'], metric_formatting_lib[metric]['color'], charLimit=charLimit)
            except: return MISSINGDATA
        try:    return self._formatted[metric]
        except: return MISSINGDATA
    
    # comparison
    def __hash__(self):
        # Gathers all item DEEP hashes, sorts them, returns 
        all_hashed = [a.deep_hash() for a in self.assets()]+[t.deep_hash() for t in self.transactions()]+[w.deep_hash() for w in self.wallets()]
        all_hashed.sort()
        return hash(tuple(all_hashed))

    # MODIFICATION
    def clear(self):
        """Deletes all assets, transactions, wallets, and filters"""
        self._assets.clear()
        self._transactions.clear()
        self._wallets.clear()
        self._filters.clear()

    def add_asset(self, asset_obj:Asset):
        if self.hasAsset(asset_obj.ticker(), asset_obj.class_code()): print('||WARNING|| Overwrote asset with same hash.', asset_obj.get_hash())
        self._assets[asset_obj.get_hash()] = asset_obj
    def add_transaction(self, transaction_obj:Transaction):
        # Automatically add assets
        for t,c in transaction_obj._metrics['all_assets']:
            if not self.hasAsset(t,c):
                asset_obj = Asset(t, c, t)
                self.add_asset(asset_obj)
            else:  asset_obj = self.asset(t, c)
            asset_obj.add_transaction(transaction_obj) #Adds this transaction to asset's ledger
        # Automatically add wallets
        WALLET = transaction_obj.get_metric('wallet')
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
            other_trans.precalculate()
    def add_wallet(self, wallet_obj:Wallet):
        if self.hasWallet(wallet_obj.name()): print('||WARNING|| Overwrote wallet with same hash.', wallet_obj.get_hash())
        self._wallets[wallet_obj.get_hash()] = wallet_obj
    def add_filter(self, filter_obj:Filter):
        if self.hasFilter(filter_obj.get_hash()): print('||WARNING|| Overwrote filter with same hash.', filter_obj.get_hash())
        self._filters[filter_obj.get_hash()] = filter_obj

    def delete_asset(self, asset:Asset):               self._assets.pop(asset.get_hash())
    def delete_transaction(self, transaction_obj:Transaction):  
        # Remove transaction from portfolio
        transaction_obj = self._transactions.pop(transaction_obj.get_hash()) #Removes transaction from the portfolio itself
        # Remove transaction from asset ledgers
        for t,c in transaction_obj.get_metric('all_assets'): 
            if t and c: self.asset(t,c).delete_transaction(transaction_obj) #Adds this transaction to loss asset's ledger
        # Automatically remove assets
        for t,c in transaction_obj.get_metric('all_assets'):
            a_obj = self.asset(t,c)
            if len(a_obj._ledger) == 0:
                self.delete_asset(a_obj)
    def delete_wallet(self, wallet:Wallet):            self._wallets.pop(wallet.get_hash())
    def delete_filter(self, filter:Filter):            self._filters.pop(filter.get_hash())

    def rename_wallet(self, current_name:str, new_name:str) -> Tuple[Wallet,Wallet]:
        """Annoying operation. Have to delete ALL transactions under this wallet and re-instantiate them.
        \nThe problem: transactions' hash is dependent on their wallet. Changing wallet name changes hash, 
        \nthus we have to re-instantiate all these transactions and re-insert them into the portfolio
        \nReturns the old and new wallet objects
        """
        old_wallet = self.wallet(current_name)
        new_wallet = Wallet(new_name, old_wallet.desc())
        self.delete_wallet(self.wallet(current_name)) 
        self.add_wallet(new_wallet) # add wallet here, so it keeps its description
        for t in list(self.transactions()):   #sets wallet name to the new name for all relevant transactions
            if t.wallet() == old_wallet.name():      
                t_raw = t.toJSON()
                t_raw['wallet'] = new_name
                self.delete_transaction(t) #Changing the wallet name changes the transactions HASH: its key in the portfolio dict will change 
                self.add_transaction(Transaction(t_raw))
        return old_wallet, new_wallet


    # JSON
    def loadJSON(self, JSON:dict, merge=False, overwrite=False): #Loads JSON data, erases any existing data first
        
        #If loading...                      clear everything,  load the new data.
        #If merging and overwriting,                           load the new data.
        #If merging and NOT overwriting,                       load the new data, skipping duplicate transactions.

        if not merge:   self.clear()

        # TRANSACTIONS & ASSETS & WALLETS - NOTE: Lag is ~443.4364ms for ~5300 transactions
        if 'transactions' in JSON:
            parsed_transactions = None
            # NOTE: ~12ms w/ 5600
            try: parsed_transactions = pd.read_csv(StringIO(JSON['transactions']), dtype='string').astype({'date':float})
            except: print('||ERROR|| Failed to read transactions from JSON.')
            if parsed_transactions is not None:
                # NOTE: ~35ms w/ 5600 for list_of_dicts_without_nulls
                list_of_dicts_without_nulls = parsed_transactions.apply(lambda row: {k: v for k, v in row.items() if pd.notna(v)}, axis=1).tolist()
                for raw_data in list_of_dicts_without_nulls:
                    new_trans = Transaction(raw_data) # 323ms for ~5600 transactions: all [FORMAT_METRIC]
                    if merge and not overwrite and self.hasTransaction(new_trans.get_hash()): continue     #Don't overwrite identical transactions, when specified
                    self.add_transaction(new_trans) #8.5012ms for ~5600 transactions

        # If merging & NOT overwriting, skip everything else:
        if merge and not overwrite: return

        # ASSETS - 1.5335ms for ~40 assets
        # Assets already initialized in the previous step (implemented in add_transaction function)
        # Here we load names/descriptions
        if 'assets' in JSON:
            parsed_assets = None
            try: parsed_assets = pd.read_csv(StringIO(JSON['assets']), dtype='string').fillna('')
            except: print('||ERROR|| Failed to read asset names/descriptions from JSON.')
            if type(parsed_assets) == pd.DataFrame:
                for a in parsed_assets.iterrows(): # Look through all asset savedata
                    try:    TICKER, CLASS, NAME, DESC = a[1]['ticker'], a[1]['class'], a[1]['name'], a[1]['description'] # Parse row
                    except: 
                        print('||ERROR|| An asset\'s name/decription failed to load.')
                        continue
                    if self.hasAsset(TICKER, CLASS): # If asset already in portfolio, import name/description
                        existing_asset = self.asset(TICKER, CLASS)
                        existing_asset._data['name'] = NAME
                        existing_asset._data['description'] = DESC # Set existing asset description to saved description
                        existing_asset.precalculate()
        
        # WALLETS - 0.9553ms for 9 wallets (probably not much more for a million) 
        # Wallets already initialized in the first step (implemented in add_transaction function)
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
                        self.wallet(NAME)._description = DESC
    def toJSON(self) -> Dict[str,pd.DataFrame]:
        # Up to this point we store information as dictionaries
        # Now, we convert each list of assets/transactions/wallets and their respective properties into a dataframe, 
        # then into a CSV to save a TON of disk space. The CSV is stored as a string.
        return {
            'assets':       pd.DataFrame.from_dict([a.toJSON() for a in self.assets()]).to_csv(index=False),
            'transactions': pd.DataFrame.from_dict([t.toJSON() for t in self.transactions()]).to_csv(index=False),
            'wallets':      pd.DataFrame.from_dict([w.toJSON() for w in self.wallets()]).to_csv(index=False),
        }
    
    # STATUS
    def isEmpty(self) -> bool:  return {} == self._assets == self._transactions == self._wallets

    def hasAsset(self, ticker, class_code:str) -> bool:     return Asset.calc_hash(None, ticker, class_code) in self._assets.keys()
    def hasTransaction(self, transaction_hash:int) -> bool: return transaction_hash in self._transactions.keys()
    def hasWallet(self, wallet_name:str) -> bool:           return Wallet(wallet_name).get_hash() in self._wallets
    def hasFilter(self, filter:str) -> bool:                return filter in self._filters
    
    # QUICK ACCESS
    def asset(self, ticker:str, class_code=None) -> Asset:  return self._assets[Asset.calc_hash(None, ticker, class_code)]
    def transaction(self, transaction_hash:int) -> Transaction:  return self._transactions[transaction_hash]
    def wallet(self, wallet_name:str) -> Wallet:            return self._wallets[hash(wallet_name)]

    def assets(self) -> List[Asset]:                        return self._assets.values()
    def transactions(self) -> List[Transaction]:            return self._transactions.values()
    def wallets(self) -> List[Wallet]:                      return self._wallets.values()
    def filters(self) -> List[Filter]:                      return self._filters.values()



class ViewState():
    """Stores current visual mode, and accessory relevant information"""
    def __init__(self):
        self.state = ''
        self.asset = (None, None)
        self.PORTFOLIO = 'portfolio'
        self.GRAND_LEDGER = 'grand_ledger'
        self.ASSET = 'asset'
    
    def getState(self) -> str:
        return self.state
    def getDefHeader(self):
        try:        return default_headers[self.getState()]
        except:     raise KeyError(f'||ERROR|| getDefHeader not implemented for unknown ViewState {self.getState()}')
    def getHeaderID(self) -> str:
        return 'header_'+self.getState()
    def getHeaders(self) -> List[str]:
        return setting('header_'+self.getState())
    def getAsset(self) -> str:
        return self.asset
    def getHeaderTooltip(self, header:str):
        if self.state == self.PORTFOLIO:    return metric_desc_lib['asset'][header]
        else:                               return metric_desc_lib['transaction'][header]

    def setAsset(self, ticker, class_code):
        self.asset = (ticker, class_code)

    def isPortfolio(self):
        return self.state == self.PORTFOLIO
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
    

    def mouseReleaseEvent(self, e: QMouseEvent): # We basically just run our own filter, then run the base QPushButton command
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
    
    def mouseMoveEvent(self, e: QMouseEvent):
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
    
    def leaveEvent(self, e: QMouseEvent):
        self.isDragging = False
        return super().leaveEvent(e)
    
    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasFormat("AAheader"):
            e.acceptProposedAction()
        return super().dragEnterEvent(e)
    def dropEvent(self, e: QDropEvent):
        this_header, header_being_dropped = self.info, e.mimeData().headerID
        if this_header != header_being_dropped: 
            self.upper.upper.move_header(header_being_dropped, this_header)
        return super().dropEvent(e)
        
class GRID_ROW(QFrame): # One of the rows in the GRID, which can be selected, colored, etc.
    def __init__(self, row, set_highlight, click, double_click):
        super().__init__() #Contructs the tk.Frame object
        self.setMouseTracking(True)
        self.mouseMoveEvent = p(set_highlight, row+1)           # Hovering over rows highlights them
        self.leaveEvent = p(set_highlight, None)                # Causes highlight to disappear when mouse leaves GRID area
        self.mousePressEvent = p(click, row)                    # Single-clicking only selects items
        self.mouseDoubleClickEvent = p(double_click, row)       # Double clicking opens next level of hierarchy
        self.row_index = row
        if self.row_index % 2 == 0:     self.setStyleSheet(style('GRID_row_even'))
        else:                           self.setStyleSheet(style('GRID_row_odd'))
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
            if self.hover_state:            self.setStyleSheet(style('GRID_hover'))
            elif self.select_state:         self.setStyleSheet(style('GRID_selection'))
            elif self.row_index % 2 == 0:   self.setStyleSheet(style('GRID_row_even'))
            else:                           self.setStyleSheet(style('GRID_row_odd'))

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
        self.font_size_style = '' # used to store dynamic font size

        # Adds the first column in the grid, with the row indices
        self.item_indices = (
            QLabel("\n", styleSheet=style('GRID_header')),
            QLabel(alignment=Qt.AlignRight, styleSheet=style('GRID_header'), margin=-2) # margin weirdly big by default, -2 sets to 0 effectively
        )
        self.highlights = [GRID_ROW(row, self.set_highlight, self._click, self._double_click) for row in range(self.pagelength)]
        
        self.fake_header = QWidget(styleSheet=style('GRID_header')) # "header" right of last actual header
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
            QLabel(alignment=Qt.AlignRight, styleSheet=style('GRID_data')+self.font_size_style, margin=-2) # margin weirdly big by default, -2 sets to 0 effectively
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
        QScrollArea_margin_and_border_height = 2 # currently border is 1 px thick, top and bottom
        QScrollArea_scrollbar_height = scrollArea.horizontalScrollBar().height() #Always assume horizontal scrollbar is present, even if not. Solves issue with flickering
        header_height = icon('size').height()
        desired_font_px_height = (QScrollArea_height-QScrollArea_margin_and_border_height-header_height-QScrollArea_scrollbar_height)//self.pagelength
        
        fontSize = 0
        f = QFont(font)
        while True:
            f.setPixelSize( fontSize+1 )
            if QFontMetrics(f).height() <= desired_font_px_height: 
                fontSize += 1
            else:   break
        
        self.font_size_style = f'font-size: {fontSize}px;' #CSS font-size code

        # Applies font size modification - only slow part of this whole thing
        self.item_indices[1].setStyleSheet(style('GRID_header')+self.font_size_style)
        for c in range(len(self.columns)):
            self.columns[c][1].setStyleSheet(style('GRID_data')+self.font_size_style)
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
            header_metric = view.getHeaders()[c]
            header_obj = self.columns[c][0]
            header_obj.setText(metric_formatting_lib[header_metric]['headername']) # Sets text to proper header name
            header_obj.info = header_metric # Sets info quick-access variable, to current header's variable
            header_obj.setToolTip('\n'.join(textwrap.wrap(view.getHeaderTooltip(header_metric), 40))) # Sets header tooltip
            sort_setting = setting('sort_'+view.state)
            if sort_setting[0] == header_metric: # up/down arrow indicating sorting method
                if sort_setting[1]: header_obj.setIcon(icon('arrow_up'))
                else:               header_obj.setIcon(icon('arrow_down'))
            else:                   header_obj.setIcon(QIcon())

            # Column rows' text
            toDisplay = '' # This will be the string of text for this column
            for r in rowrange:
                if r > stop: toDisplay += '<br>' #Inserts empty lines where there is nothing to display
                else:
                    item = sorted_items[r]
                    if item.ERROR:   self.highlights[r%self.pagelength].error(True) # if transaction/asset has an error, highlights it in red
                    # adds this row of text to the display
                    toDisplay += f'{item.get_formatted(metric=header_metric, ticker=view.getAsset()[0], class_code=view.getAsset()[1])}<br>'
            self.columns[c][1].setText(toDisplay.removesuffix('<br>')) # Sets column text to toDisplay
            




