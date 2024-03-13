from AAobjects import *
import heapq

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



class metrics:
    # We initialize the metrics object with a reference to our Portfolio, and TEMP data
    def __init__(self, portfolio:Portfolio, temp, main_app):
        self.PORTFOLIO = portfolio
        self.TEMPDATA = temp
        self.MAIN_APP_REF = main_app
        

    def recalculate_all(self, tax_report:str=None): # Recalculates ALL metrics
        self.recalculate_market_independent(tax_report) # Recalculates all metrics that only need historical transaction data to calculate
        self.recalculate_market_dependent() # Recalculates all metrics that depend on current market information

    # Functions to calculate only what's needed
    def recalculate_market_independent(self, tax_report:str=None): # Recalculates all market-independent asset metrics: also triggers portfolio recalculation
        '''ALL market independent, for ASSETS and PORTFOLIO'''
        if tax_report:
            self.TEMPDATA['taxes'] = { 
                '8949':     pd.DataFrame(columns=['Description of property','Date acquired','Date sold or disposed of','Proceeds','Cost or other basis','Gain or (loss)']) ,
                '1099-MISC':pd.DataFrame(columns=['Date acquired', 'Value of assets']),
                }
        # Automatic accounting is the most complex, market-independent group of calculations we do here.
        # ERROR CLEARING - clear transaction errors, unless they are due to bad data
        for t in self.PORTFOLIO.transactions():
            if t.ERROR and t.ERROR_TYPE != 'data':
                t.ERROR,t.ERROR_TYPE = False,''
        for a in self.PORTFOLIO.assets():   a.ERROR = False # Assume false, only true due to bad transactions
        for w in self.PORTFOLIO.wallets():  w.ERROR = False # Assume false, only true due to bad transactions

        # ACCOUNTING
        # Link transfer_out's with transfer_in's where possible (sets dest_wallet hidden metric)
        self.automatically_link_transfers() 
        # Beating heart: processes all transaction data
        self.perform_automatic_accounting(tax_report) # TODO: Laggiest part of the program! (~116ms for ~12000 transactions)

        # ERROR SETTING - set asset/wallet error to true if they contain bad transactions
        for t in self.PORTFOLIO.transactions():
            if t.ERROR:
                for TICKER, CLASS in t.get_metric('all_assets'):
                    self.PORTFOLIO.asset(TICKER, CLASS).ERROR = True
                self.PORTFOLIO.wallet(t.wallet()).ERROR = True

        # MORE METRIC CALCULATION
        for asset in self.PORTFOLIO.assets():
            self.calculate_for_asset(asset, 'average_buy_price', 'A/B', 'cost_basis', 'balance')
        self.recalculate_portfolio_market_independent()

    def recalculate_portfolio_market_independent(self): #Recalculates all market-independent portfolio metrics
        '''ALL market independent, for PORTFOLIO'''
        self.PORTFOLIO._metrics['number_of_transactions'] = len(self.PORTFOLIO.transactions())
        self.PORTFOLIO._metrics['number_of_assets'] = len(self.PORTFOLIO.assets())
        self.calculate_for_portfolio('cash_flow', 'sum')
        self.calculate_for_portfolio('cost_basis', 'sum')

    def recalculate_market_dependent(self):   # Recalculates all market-dependent asset metrics: also triggers portfolio recalculation
        '''ALL market dependent, for ASSETS and PORTFOLIO'''
        for asset in self.PORTFOLIO.assets(): 
            # Update asset's market metrics with from market_data
            CLASS, TICKER = asset.class_code(), asset.ticker()
            recent_market_data = self.MAIN_APP_REF.market_data
            if TICKER in recent_market_data[CLASS].keys():
                asset._metrics.update(recent_market_data[CLASS][TICKER])

            self.calculate_for_asset(asset, 'value', 'A*B', 'balance', 'price')
            self.calculate_for_asset(asset, 'unrealized_profit_and_loss', 'A-B', 'value', 'cost_basis')
            self.calculate_for_asset(asset, 'unrealized_profit_and_loss%', '(A/B)-1', 'value', 'cost_basis')
            self.calculate_for_asset(asset, 'day_change', '(AB)/(1+B)', 'value', 'day%')
            self.calculate_for_asset(asset, 'week_change', '(AB)/(1+B)', 'value', 'week%')
            self.calculate_for_asset(asset, 'month_change', '(AB)/(1+B)', 'value', 'month%')
            self.calculate_for_asset(asset, 'projected_cash_flow', 'A+B', 'cash_flow', 'value')
        self.recalculate_portfolio_market_dependent()

    def recalculate_portfolio_market_dependent(self): #Recalculates all market-dependent portfolio metrics
        '''ALL market dependent, for PORTFOLIO'''
        self.calculate_for_portfolio('value', 'sum')
        for asset in self.PORTFOLIO.assets():
            self.calculate_percentage_of_portfolio(asset)
        self.calculate_for_portfolio('projected_cash_flow', 'A+B', 'cash_flow', 'value')
        self.calculate_for_portfolio('day_change', 'sum')
        self.calculate_for_portfolio('week_change', 'sum')
        self.calculate_for_portfolio('month_change', 'sum')
        self.calculate_for_portfolio('day%', 'A/(B-C)', 'day_change', 'value', 'day_change')
        self.calculate_for_portfolio('week%', 'A/(B-C)', 'week_change', 'value', 'week_change')
        self.calculate_for_portfolio('month%', 'A/(B-C)', 'month_change', 'value', 'month_change')
        self.calculate_for_portfolio('unrealized_profit_and_loss', 'A-B', 'value', 'cost_basis')
        self.calculate_for_portfolio('unrealized_profit_and_loss%', '(A/B)-1', 'value', 'cost_basis')
        self.calculate_portfolio_value_by_wallet()

    ############################
    # ACCOUNTING
    ############################
    # Link TRANSFER_OUTs with TRANSFER_INs
    def automatically_link_transfers(self):
        """Market-independent. Links TRANSFER_OUTs with TRANSFER_INs via dest_wallet variable, to allow for cross-platform, cross-wallet accounting.
        \nLinks transactions if: 
        \n    - Same asset ticker
        \n    - Same asset class
        \n    - Timestamps within 5 minutes of eachother
        \n    - Quantities within 0.1% of eachother
        \nNOTE: The 'dest_wallet' variable is given only to TRANSFER_OUTs"""

        # Retrieve all non-erroneous TRANSFER_INs and TRANSFER_OUTs
        transfer_IN =  {t.get_hash():t for t in self.PORTFOLIO.transactions() if t.type() == 'transfer_in'  and not t.ERROR}    #List of all transfer_INs, chronologically ordered
        transfer_OUT = {t.get_hash():t for t in self.PORTFOLIO.transactions() if t.type() == 'transfer_out' and not t.ERROR}    #List of all transfer_OUTs, chronologically ordered
        
        # Link transfers based on similarity
        for hash_out,t_out in dict(transfer_OUT).items():
            for hash_in,t_in in dict(transfer_IN).items(): #We have to look at all the t_in's
                # Already paired: skip this!
                if (hash_in not in transfer_IN) or (hash_out not in transfer_OUT):    continue
                # Pair them up based on three checks:
                in_GT, in_GC, out_LT, out_LC = t_in.get_raw('gain_ticker'), t_in.get_raw('gain_class'), t_out.get_raw('loss_ticker'), t_out.get_raw('loss_class')
                if in_GT==out_LT and in_GC==out_LC: # Asset ticker/class the same
                    if acceptableTimeDiff(t_in.unix_date(),t_out.unix_date(),300): # Occurred within 5 minutes of eachother
                        if acceptableDifference(t_in.get_metric('gain_quantity'), t_out.get_metric('loss_quantity'), 0.1): # Quantities are within 0.1% of eachother
                            
                            #SUCCESS - We've paired this t_out with a t_in!
                            t_out._metrics['dest_wallet'] = t_in.wallet() #We found a partner for this t_out, so set its _dest_wallet variable to the t_in's wallet

                            # Two transfers have been paired. Remove them from their respective lists
                            transfer_IN.pop(hash_in)
                            transfer_OUT.pop(hash_out)
        
        # If unlinked, ERROR!!!
        transfer_IN.update(transfer_OUT) # merge dictionaries
        for t in transfer_IN:
            t.ERROR,t.ERROR_TYPE = True,'transfer'
            if t.type() == 'transfer_in':
                t.ERR_MSG = f'Failed to automatically find a \'Transfer Out\' transaction under {t.get_raw('gain_ticker')} that pairs with this \'Transfer In\'.'
            else:
                t.ERR_MSG = f'Failed to automatically find a \'Transfer In\' transaction under {t.get_raw('loss_ticker')} that pairs with this \'Transfer Out\'.'
                        
    # "Holy Grail" Function of the program
    # Calculates all metrics which are directly dependent on the order of transactions (thus, the accounting method)
    def perform_automatic_accounting(self, tax_report:str=''):   #Dependent on the Accounting Method, calculates the Holdings per Wallet, Total Holdings, Average Buy Price, Real P&L (Capital Gains)
        """Market-independent. Calculates all metrics dependent on the particular order of transactions"""
        #Creates a list of all transactions, sorted chronologically #NOTE: Lag is ~18ms for ~12000 transactions
        transactions = list(self.PORTFOLIO.transactions()) #0ms
        transactions.sort()

        # METRICS - Per-asset metrics
        # STRUCTURE:    metrics[class][ticker] = dictionary of metrics with default values
        metrics = { class_code:{} for class_code in class_lib.keys()}
        for asset in self.PORTFOLIO.assets():
            metrics[asset.class_code()][asset.ticker()] = {
                'cash_flow':0, 
                'realized_profit_and_loss': 0, 
                'tax_capital_gains': 0,
                'tax_income': 0,
                'balance':0,
                }

        # LEDGER - The data structure which tracks asset's original price across sales #NOTE: Lag is 0ms for ~12000 transactions
        # STRUCTURE:    ledger[class][ticker][wallet] = gain_heap
        # We use a min/max heap to decide which transactions are "sold" when assets are sold, to determine what the capital gains actually is
        accounting_method = setting('accounting_method')
        ledger = { class_code:{} for class_code in class_lib.keys()}
        for asset in self.PORTFOLIO.assets():
            ledger[asset.class_code()][asset.ticker()] = {wallet:gain_heap(accounting_method) for wallet in self.PORTFOLIO.all_wallet_names()}

        # DISBURSE QUANTITY - removes a 'gain', from the LEDGER data structure.
        def disburse_quantity(t:Transaction, quantity:Decimal, ticker:str, class_code:str, wallet:str, wallet2:str=None):  #NOTE: Lag is ~50ms for ~231 disbursals with ~2741 gains moved on average, or ~5 disbursals/ms, or ~54 disbursed gains/ms
            '''Removes, quantity of asset from specified wallet, then returns cost basis of removed quantity.\n
                If wallet2 \'w2\' specified, instead moves quantity into w2.'''
            quantity_left,gains_removed = ledger[class_code][ticker][wallet].disburse(quantity)     #NOTE - Lag is ~40ms for ~12000 transactions
            if not zeroish_prec(quantity_left):  #NOTE: Lag is ~0ms
                t.ERROR,t.ERROR_TYPE = True,'over_disbursed'
                t.ERR_MSG = f'User disbursed {quantity_left} more {ticker} than their {wallet} wallet contained.'
                

            #NOTE - Lag is ~27ms including store_quantity, 11ms excluding
            cost_basis = 0
            for gain in gains_removed: #Result[1] is a list of gain objects that were just disbursed
                cost_basis += gain._price*gain._quantity
                if tax_report == '8949': tax_8949(t, gain, quantity)
                if wallet2: ledger[class_code][ticker][wallet2].store_direct(gain)   #Moves transfers into the other wallet, using the gains objects we already just created
            return cost_basis
        
        def tax_8949(t:Transaction, gain:gain_obj, total_disburse:Decimal):
            ################################################################################################
            # This might still be broken. ALSO: Have to separate the transactions into short- and long-term
            ################################################################################################
            if zeroish_prec(gain._quantity):     return
            if t.type() == 'transfer_out':  return 
            store_date = self.PORTFOLIO.transaction(gain._hash).iso_date()  # Date of aquisition - note: we do this so we don't have to convert the gain's date from UNIX to ISO
            disburse_date = t.iso_date()                                    # Date of disposition
            cost_basis = gain._price*gain._quantity
            #The 'post-fee-value' is the sales profit, after fees, weighted to the actual quantity sold 
            post_fee_value = (t.get_metric('gain_value')-t.get_metric('fee_value'))*(gain._quantity/total_disburse)
            if post_fee_value < 0:  post_fee_value = 0     #If we gained nothing and there was a fee, it will be negative. We can't have negative proceeds.
            form8949 = {
                'Description of property':      str(gain._quantity) + ' ' + self.PORTFOLIO.transaction(gain._hash).get_raw('gain_ticker').split('z')[0],  # 0.0328453 ETH
                'Date acquired':                store_date[5:7]+'/'+store_date[8:10]+'/'+store_date[:4],            # 11/12/2021    month, day, year
                'Date sold or disposed of':     disburse_date[5:7]+'/'+disburse_date[8:10]+'/'+disburse_date[:4],   # 6/23/2022     month, day, year
                'Proceeds':                     str(post_fee_value),    # to value gained from this sale/trade/expense/gift_out. could be negative if its a gift_out with a fee.
                'Cost or other basis':          str(cost_basis),        # the cost basis of these tokens
                'Gain or (loss)':               str(post_fee_value - cost_basis)  # the Capital Gains from this. The P&L. 
                }
            self.TEMPDATA['taxes']['8949'] = self.TEMPDATA['taxes']['8949'].append(form8949, ignore_index=True)

        # AUTO-ACCOUNTING: This is the heart of hearts, true core of the program right here.
        for t in transactions:  # 24.5693ms for 5300 transactions
            # Ignore: missing data, transfer failures,
            # Other errors are OK: over-disbursal, 
            if t.ERROR and t.ERROR_TYPE in ('data','transfer'): continue    

            #NOTE: 6.9029ms for ~5300 transactions
            HASH,TYPE,WALLET = t.get_metric('hash'),    t.get_raw('type'),              t.get_raw('wallet') # 2.3034 ms
            WALLET2 = t.get_metric('dest_wallet') # only exists for TRANSFER_OUTs
            LT,FT,GT = t.get_raw('loss_ticker'),        t.get_raw('fee_ticker'),        t.get_raw('gain_ticker')
            LC,FC,GC = t.get_raw('loss_class'),         t.get_raw('fee_class'),         t.get_raw('gain_class')
            LQ,FQ,GQ = t.get_metric('loss_quantity'),   t.get_metric('fee_quantity'),   t.get_metric('gain_quantity')
            LV,FV,GV = t.get_metric('loss_value'),      t.get_metric('fee_value'),      t.get_metric('gain_value')
            GP = t.get_metric('gain_price')
            COST_BASIS_OF_LOSS,COST_BASIS_OF_FEE = 0,0
            
            # BALANCE CALCULATION
            # Balance is for AFTER the transaction, here
            if LT: 
                metrics[LC][LT]['balance'] -= LQ # Update total balance for this asset
                t._metrics['balance'][LC][LT] = metrics[LC][LT]['balance'] # Set balance for this transaction
            if FT: 
                metrics[FC][FT]['balance'] -= FQ # Update total balance for this asset
                t._metrics['balance'][FC][FT] = metrics[FC][FT]['balance'] # Set balance for this transaction
            if GT: 
                metrics[GC][GT]['balance'] += GQ # Update total balance for this asset
                t._metrics['balance'][GC][GT] = metrics[GC][GT]['balance'] # Set balance for this transaction
            # Pre-calculates formatted version of "balance" for all of this transaction's assets
            for class_code in t._metrics['balance']:
                for ticker,quantity in t._metrics['balance'][class_code].items():
                    formatting = metric_formatting_lib['balance']
                    t._formatted['balance'][class_code][ticker] = format_metric(quantity, formatting['format'], colorFormat=formatting['color']) 

            # COST BASIS CALCULATION    #NOTE: Lag ~7.0662ms for ~5300 transactions. 
            # Gain, then fee, then loss: If I swapped ETH for ETH using ETH, remove loss/fee from gain_heap BEFORE adding new gain
            # FEE LOSS - We lose assets because of a fee     #NOTE: Lag ~xxx, on average
            if FT:          COST_BASIS_OF_FEE =  disburse_quantity(t, FQ, FT, FC, WALLET)
            # LOSS - We lose assets one way or another.
            if LT:          COST_BASIS_OF_LOSS = disburse_quantity(t, LQ, LT, LC, WALLET, WALLET2)
            # GAINS - We gain assets one way or another     #NOTE: Lag ~xxx, on average
            if GT and GP:   ledger[GC][GT][WALLET].store(HASH, GP, GQ, t.unix_date())

            # METRIC CALCULATION    #NOTE: Lag is ~3.0454ms for ~5300 transactions (all metrics below)
            
            # CASH FLOW - Only purchases, sales, and swaps(trades)
            match TYPE:
                case 'purchase' | 'purchase_crypto_fee':    metrics[GC][GT]['cash_flow'] += -GV - FV
                case 'sale':                                metrics[LC][LT]['cash_flow'] += LV - FV
                case 'trade': # Trades: treated as cash_flow event. fee lumped ONLY into gained asset, not both
                    metrics[GC][GT]['cash_flow'] += -GV - FV
                    metrics[LC][LT]['cash_flow'] += LV
            
            # REAL P&L - Sales and trades sometimes profit, whereas gift_outs, expenses, as well as any fees always incur a loss
            # Value - Cost Basis = P&L 
            # Realized loss from FEE
            if GT and TYPE in ('purchase','sale'):  metrics[GC][GT]['realized_profit_and_loss'] += -FV                  # Fee is USD: we only lose the value of the fee
            elif FT:                                metrics[FC][FT]['realized_profit_and_loss'] += -COST_BASIS_OF_FEE   # We lost original asset here (cost basis)
            # Realized loss from LOSS
            if TYPE in ('expense','gift_out'):      metrics[LC][LT]['realized_profit_and_loss'] += -COST_BASIS_OF_LOSS  # Base loss cost is realized
            elif TYPE in ('sale','trade'):          metrics[LC][LT]['realized_profit_and_loss'] += LV - COST_BASIS_OF_LOSS # Base loss cost is realized, but sale yields the loss value

            # CAPITAL GAINS TAX
            #Fees not lumped into cost basis are taxed as a 'sale'
            if FT and TYPE in ('gift_out','transfer_out','transfer_in'): metrics[FC][FT]['tax_capital_gains'] += FV - COST_BASIS_OF_FEE
            #Expenses taxed as a 'sale', trade treated as an immediate sale and purchase
            elif TYPE in ('sale','trade'):                               metrics[LC][LT]['tax_capital_gains'] += (LV - FV) - COST_BASIS_OF_LOSS 
            elif TYPE == 'expense':                                      metrics[LC][LT]['tax_capital_gains'] += (LV + FV) - COST_BASIS_OF_LOSS 

            # INCOME TAX
            if TYPE in ('card_reward','income'):    #This accounts for all transactions taxable as INCOME: card rewards, and staking rewards
                metrics[GC][GT]['tax_income'] += GV
                if tax_report=='1099-MISC':  
                    self.TEMPDATA['taxes']['1099-MISC'] = self.TEMPDATA['taxes']['1099-MISC'].append( {'Date acquired':t.iso_date(), 'Value of assets':str(GV)}, ignore_index=True)

            #*** *** *** DONE FOR THIS TRANSACTION *** *** ***#
        
        # COST BASIS AND WALLET BALANCES
        for asset in self.PORTFOLIO.assets(): #TODO: Lag is like 30ms for ~4000 transactions
            CLASS, TICKER = asset.class_code(), asset.ticker()
            asset._metrics.update(metrics[CLASS][TICKER]) # Update asset metrics

            total_cost_basis = 0    #The overall cost basis of what you currently own
            wallet_balance = {}    #A dictionary indicating the balance by wallet
            for WALLET in ledger[CLASS][TICKER]:
                wallet_balance[WALLET] = 0 # Initializes wallet balance at 0$
                for gain in ledger[CLASS][TICKER][WALLET]._heap:
                    total_cost_basis        += gain._price*gain._quantity   #cost basis of this gain
                    wallet_balance[WALLET]      += gain._quantity               #Number of tokens within each wallet
            asset._metrics['cost_basis'] =  total_cost_basis # original value of current asset balance
            asset._metrics['wallets'] =     wallet_balance
            
    ############################
    # Generalized metric calculation functions
    ############################
    # ASSETS
    # Generic functions
    def calculate_for_asset(self, asset:Asset, metric, operation, A=None, B=None):
        if not A or not B: 
            raise Exception(f'||ERROR|| When calculating asset operation, \'A\' and \'B\' must be specified')
        result = 0
        match operation:
            case 'sum': # add across all transactions on this asset's ledger
                for t in asset._ledger:    
                    try: result += t.get_metric(metric) # Add to sum if it exists
                    except: pass  
            case 'A+B': # add two portfolio metrics
                try: result = asset.get_metric(A) + asset.get_metric(B)
                except: pass
            case 'A-B': # add two portfolio metrics
                try: result = asset.get_metric(A) - asset.get_metric(B)
                except: pass
            case 'A*B': # multiply two portfolio metrics
                try: result = asset.get_metric(A) * asset.get_metric(B)
                except: pass
            case 'A/B': # divide one portfolio metric by another
                try: result = asset.get_metric(A) / asset.get_metric(B)
                except: pass
            case '(AB)/(1+B)':
                try: result = (asset.get_metric(A) * asset.get_metric(B)) / (1 + asset.get_metric(B))
                except: pass
            case '(A/B)-1':
                try: result = (asset.get_metric(A) / asset.get_metric(B)) - 1
                except: pass
            case other:
                raise Exception(f'||ERROR|| Unknown operation for calculating asset metric, \'{operation}\'')
        asset._metrics[metric] = result
    # Special Cases
    def calculate_percentage_of_portfolio(self, asset:str): #Calculates how much of the value of your portfolio is this asset - NOTE: must be done after total portfolio value calculated
        try:    asset._metrics['portfolio%'] = asset.get_metric('value')  / self.PORTFOLIO.get_metric('value')
        except: pass

    # PORTFOLIO
    # Generic functions
    def calculate_for_portfolio(self, metric, operation, A=None, B=None, C=None):
        if operation != 'sum' and (not A or not B): 
            raise Exception(f'||ERROR|| When calculating portfolio operation, \'A\' and \'B\' must be specified')
        result = 0
        match operation:
            case 'sum': # add across assets
                for a in self.PORTFOLIO.assets():    
                    try: result += a.get_metric(metric) # Add to sum if it exists
                    except: pass  
            case 'A+B': # add two portfolio metrics
                try: result = self.PORTFOLIO.get_metric(A) + self.PORTFOLIO.get_metric(B)
                except: pass
            case 'A-B': # add two portfolio metrics
                try: result = self.PORTFOLIO.get_metric(A) - self.PORTFOLIO.get_metric(B)
                except: pass
            case 'A*B': # multiply two portfolio metrics
                try: result = self.PORTFOLIO.get_metric(A) * self.PORTFOLIO.get_metric(B)
                except: pass
            case 'A/B': # divide one portfolio metric by another
                try: result = self.PORTFOLIO.get_metric(A) / self.PORTFOLIO.get_metric(B)
                except: pass
            case 'A/(B-C)':
                try: result = self.PORTFOLIO.get_metric(A) / (self.PORTFOLIO.get_metric(B) - self.PORTFOLIO.get_metric(C))
                except: pass
            case '(A/B)-1':
                try: result = (self.PORTFOLIO.get_metric(A) / self.PORTFOLIO.get_metric(B)) - 1
                except: pass
            case other:
                raise Exception(f'||ERROR|| Unknown operation for calculating portfolio metric, \'{operation}\'')
        self.PORTFOLIO._metrics[metric] = result
    # Special Cases
    def calculate_portfolio_value_by_wallet(self):    #Calculates the current market value held within each wallet, across all assets
        wallets = {wallet:0 for wallet in self.PORTFOLIO.all_wallet_names()}  #Creates a dictionary of wallets, defaulting to 0$ within each
        for asset in self.PORTFOLIO.assets():       #Then, for every asset, we look at its 'wallets' dictionary, and sum up the value of each wallet's tokens by wallet
            for wallet in asset.get_metric('wallets'):
                # Asset wallet list is total units by wallet, multiply by asset price to get value
                try:    wallets[wallet] += asset.get_metric('wallets')[wallet] * asset.get_metric('price')
                except: pass
        self.PORTFOLIO._metrics['wallets'] = wallets
