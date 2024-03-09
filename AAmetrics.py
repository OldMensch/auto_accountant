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
        

    def calculate_all(self, tax_report:str=''): # Recalculates ALL metrics
        '''Calculates and renders all static metrics for all assets, and the overall portfolio'''
        if tax_report:
            self.TEMPDATA['taxes'] = { 
                '8949':     pd.DataFrame(columns=['Description of property','Date acquired','Date sold or disposed of','Proceeds','Cost or other basis','Gain or (loss)']) ,
                '1099-MISC':pd.DataFrame(columns=['Date acquired', 'Value of assets']),
                }
        # Automatic accounting is the most complex, market-independent group of calculations we do here.
        self.perform_automatic_accounting(tax_report) # TODO: Laggiest part of the program! (~116ms for ~12000 transactions)

        self.recalculate_market_independent() # Recalculates all metrics that only need historical transaction data to calculate
        self.recalculate_market_dependent() # Recalculates all metrics that depend on current market information

    # We separate all metrics into different categories, because depending on user action, we increase performance by only calculating only what is absolutely needed.

    def recalculate_market_independent(self): # Recalculates all market-independent asset metrics: also triggers portfolio recalculation
        for asset in self.PORTFOLIO.assets():
            self.calculate_average_buy_price(asset)
        self.recalculate_portfolio_market_independent()

    def recalculate_portfolio_market_independent(self): #Recalculates all market-independent portfolio metrics
        '''Calculates all metrics for the overall portfolio'''
        self.PORTFOLIO._metrics['number_of_transactions'] = len(self.PORTFOLIO.transactions())
        self.PORTFOLIO._metrics['number_of_assets'] = len(self.PORTFOLIO.assets())
        self.calculate_portfolio_cash_flow()

    def recalculate_market_dependent(self):   # Recalculates all market-dependent asset metrics: also triggers portfolio recalculation
        for asset in self.PORTFOLIO.assets():    
            self.calculate_value(asset)
            self.calculate_unrealized_profit_and_loss(asset)
            self.calculate_changes(asset)
            self.calculate_projected_cash_flow(asset)
        self.recalculate_portfolio_market_dependent()

    # PORTFOLIO
    def recalculate_portfolio_market_dependent(self): #Recalculates all market-dependent portfolio metrics

        self.calculate_portfolio_value()
        for asset in self.PORTFOLIO.assets():
            self.calculate_percentage_of_portfolio(asset)
        self.calculate_portfolio_projected_cash_flow()
        self.calculate_portfolio_changes()
        self.calculate_portfolio_percents()
        self.calculate_portfolio_value_by_wallet()
        self.calculate_portfolio_unrealized_profit_and_loss()

    # The single most important method in the entire program is this.
    # Calculates all metrics which are directly dependent on the order of transactions (thus, the accounting method)
    def perform_automatic_accounting(self, tax_report:str=''):   #Dependent on the Accounting Method, calculates the Holdings per Wallet, Total Holdings, Average Buy Price, Real P&L (Capital Gains)
        
        #Creates a list of all transactions, sorted chronologically #NOTE: Lag is ~18ms for ~12000 transactions
        transactions = list(self.PORTFOLIO.transactions()) #0ms
        transactions.sort()

        # ERROR CLEARING - clear ERROR if it's unrelated to data
        for t in transactions:
            if t.ERROR and t.ERROR_TYPE != 'data':
                t.ERROR,t.ERROR_TYPE = False,''

        ###################################
        # TRANSFER LINKING - #NOTE: Lag is ~16ms for 159 transfer pairs under ~12000 transactions
        ###################################
        #Before we can iterate through all of our transactions, we need to pair up transfer_IN and transfer_OUTs, otherwise we lose track of cost basis which is BAD
        transfer_IN = [t for t in transactions if t.type() == 'transfer_in' and not t.ERROR]    #A list of all transfer_INs, chronologically ordered
        transfer_OUT = [t for t in transactions if t.type() == 'transfer_out' and not t.ERROR]  #A list of all transfer_OUTs, chronologically ordered

        #Then, iterating through all the transactions, we pair them up. 
        for t_out in list(transfer_OUT):
            for t_in in list(transfer_IN): #We have to look at all the t_in's
                # We pair them up if they have the same asset, occur within 5 minutes of eachother, and if their quantities are within 0.1% of eachother
                in_GT, in_GC, out_LT, out_LC = t_in.get_raw('gain_ticker'), t_in.get_raw('gain_class'), t_out.get_raw('loss_ticker'), t_out.get_raw('loss_class')
                if in_GT==out_LT and in_GC==out_LC and acceptableTimeDiff(t_in.unix_date(),t_out.unix_date(),300) and acceptableDifference(t_in.get_metric('gain_quantity'), t_out.get_metric('loss_quantity'), 0.1):
                        # we've already paired this t_in or t_out. Skip this!
                        if (t_in not in transfer_IN) or (t_out not in transfer_OUT):    continue
                        
                        #SUCCESS - We've paired this t_out with a t_in!
                        t_out._metrics['dest_wallet'] = t_in.wallet() #We found a partner for this t_out, so set its _dest_wallet variable to the t_in's wallet

                        # Two transfers have been paired. Remove them from their respective lists
                        transfer_IN.remove(t_in)
                        transfer_OUT.remove(t_out)
        
        # We have tried to find a partner for all transfers: any remaining transfers are erroneous
        for t in transfer_IN + transfer_OUT:
            t.ERROR,t.ERROR_TYPE = True,'transfer'
            if t.type() == 'transfer_in':
                t.ERR_MSG = f'Failed to automatically find a \'Transfer Out\' transaction under {t.get_raw('gain_ticker')} that pairs with this \'Transfer In\'.'
            else:
                t.ERR_MSG = f'Failed to automatically find a \'Transfer In\' transaction under {t.get_raw('loss_ticker')} that pairs with this \'Transfer Out\'.'
                        

        ###################################
        # AUTO-ACCOUNTING
        ###################################
        #Transfers linked. It's showtime. Time to perform the Auto-Accounting!
        # INFO VARIABLES - data we collect as we account for every transaction #NOTE: Lag is 0ms for ~12000 transactions
        metrics = { class_code:{} for class_code in class_lib.keys()}
        for asset in self.PORTFOLIO.assets():
            metrics[asset.class_code()][asset.ticker()] = {'cash_flow':0, 'realized_profit_and_loss': 0, 'tax_capital_gains': 0,'tax_income': 0}
        
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
            quantity,gains_removed = ledger[class_code][ticker][wallet].disburse(quantity)     #NOTE - Lag is ~40ms for ~12000 transactions
            if not zeroish_prec(quantity):  #NOTE: Lag is ~0ms
                t.ERROR,t.ERROR_TYPE = True,'over_disbursed'
                t.ERR_MSG = f'User disbursed {quantity} more {ticker} than their {wallet} wallet contained.'
                

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

        for asset in self.PORTFOLIO.assets(): #TODO: Lag unknown
            asset._metrics['cost_basis'] =  Decimal(0)
            asset._metrics['balance'] =    Decimal(0)
            asset._metrics['wallets'] =     {}

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
            LOSS_COST_BASIS,FEE_COST_BASIS = 0,0
            COST_BASIS_PRICE = t.get_metric('basis_price')
            
            # BALANCE CALCULATION - 10.0648 ms for 5300 transactions - to improve efficiency, make it so parent assets saved to transaction's _metrics dict for direct access
            # Sets account balance for these assets at time of transaction
            if LT: 
                LAA = self.PORTFOLIO.asset(LT,LC)
                LAA._metrics['balance'] -= LQ
                t._metrics['balance'][LC][LT] = LAA._metrics['balance']
            if FT: 
                FAA = self.PORTFOLIO.asset(FT,FC)
                FAA._metrics['balance'] -= FQ
                t._metrics['balance'][FC][FT] = FAA._metrics['balance']
            if GT: 
                GAA = self.PORTFOLIO.asset(GT,GC)
                GAA._metrics['balance'] += GQ
                t._metrics['balance'][GC][GT] = GAA._metrics['balance']
            for class_code in t._metrics['balance']:
                for ticker,quantity in t._metrics['balance'][class_code].items():
                    formatting = metric_formatting_lib['balance']
                    t._formatted['balance'][class_code][ticker] = format_metric(quantity, formatting['format'], colorFormat=formatting['color']) 

            # COST BASIS CALCULATION    #NOTE: Lag ~7.0662ms for ~5300 transactions. 
            # NOTE: We have to do the gain, then the fee, then the loss, because some Binance trades incur a fee in the crypto you just bought
            # GAINS - We gain assets one way or another     #NOTE: Lag ~xxx, on average
            if COST_BASIS_PRICE:    ledger[GC][GT][WALLET].store(HASH, COST_BASIS_PRICE, GQ, t.unix_date())
            # FEE LOSS - We lose assets because of a fee     #NOTE: Lag ~xxx, on average
            if FT:                  FEE_COST_BASIS =  disburse_quantity(t, FQ, FT, FC, WALLET)
            # LOSS - We lose assets one way or another.
            if LT:                  LOSS_COST_BASIS = disburse_quantity(t, LQ, LT, LC, WALLET, WALLET2)

            # METRIC CALCULATION    #NOTE: Lag is ~3.0454ms for ~5300 transactions (all metrics below)
            
            # CASH FLOW - Only transactions involving USD can affect cash flow.
            # HOWEVER... when you "swap" one crypto for another, then the gain asset technically has "0 cash flow", which from an investing perspective, makes no sense
            # Since swaps/trades essentially use the loss asset instrumentally to acquire the gain asset, 
            # I essentially just "move the cash flow" from the Loss Asset to the Gain Asset, and pretend that I bought the gain asset directly with USD
            # Since LV - FV = GV, this shouldn't affect the cash flow for the overall portfolio, since the +/- change on each asset cancels out overall
            match TYPE:
                case 'purchase' | 'purchase_crypto_fee':    metrics[GC][GT]['cash_flow'] -= GV + FV
                case 'sale':                                metrics[LC][LT]['cash_flow'] += LV - FV
                case 'trade': # Here, we include the trades
                    metrics[LC][LT]['cash_flow'] += LV - FV
                    metrics[GC][GT]['cash_flow'] -= GV

            
            # REALIZED PROFIT AND LOSS - Sales and trades sometimes profit, whereas gift_outs, expenses, as well as any fees always incur a loss
            # Fees are always a realized loss, if there is one
            if FT:                              metrics[FC][FT]['realized_profit_and_loss'] -= FEE_COST_BASIS   # Base fee cost is realized
            elif TYPE == 'purchase':            metrics[GC][GT]['realized_profit_and_loss'] -= FV        # Base fee cost is realized to asset bought
            elif TYPE == 'sale':                metrics[LC][LT]['realized_profit_and_loss'] -= FV        # Base fee cost is realized to asset sold
            #Expenses and gift_outs are a complete realized loss. Sales and trades we already lost the fee, but hopefully gain more from sale yield
            if TYPE in ('expense','gift_out'):  metrics[LC][LT]['realized_profit_and_loss'] -= LOSS_COST_BASIS  # Base loss cost is realized
            elif TYPE in ('sale','trade'):      metrics[LC][LT]['realized_profit_and_loss'] += LV - LOSS_COST_BASIS # Base loss cost is realized, but sale yields the loss value

            # CAPITAL GAINS TAX
            #Independent transfer fees are taxed as a 'sale'
            if FT and TYPE in ('gift_out','transfer_out','transfer_in'): metrics[FC][FT]['tax_capital_gains'] += FV - FEE_COST_BASIS
            #Expenses taxed as a 'sale', trade treated as an immediate sale and purchase
            elif TYPE in ('sale','trade'):                               metrics[LC][LT]['tax_capital_gains'] += (LV - FV) - LOSS_COST_BASIS 
            elif TYPE == 'expense':                                      metrics[LC][LT]['tax_capital_gains'] += (LV + FV) - LOSS_COST_BASIS 

            # INCOME TAX
            if TYPE in ('card_reward','income'):    #This accounts for all transactions taxable as INCOME: card rewards, and staking rewards
                metrics[GC][GT]['tax_income'] += GV
                if tax_report=='1099-MISC':  
                    self.TEMPDATA['taxes']['1099-MISC'] = self.TEMPDATA['taxes']['1099-MISC'].append( {'Date acquired':t.iso_date(), 'Value of assets':str(GV)}, ignore_index=True)

            #*** *** *** DONE FOR THIS TRANSACTION *** *** ***#
        

        #ERRORS - applies error state to any asset with an erroneous transaction on its ledger.
        # Initially assume all assets are error free (asset errors can only result from )
        for a in self.PORTFOLIO.assets():   a.ERROR = False
        # Then we check all transactions for an ERROR state, and apply that to its parent asset(s)
        for t in transactions:
            if t.ERROR:
                for part in ('loss_','fee_','gain_'):
                    if t.get_raw(part+'ticker') and t.get_raw(part+'class'):     
                        self.PORTFOLIO.asset(t.get_raw(part+'ticker'), t.get_raw(part+'class')).ERROR = True

        for asset in self.PORTFOLIO.assets(): #TODO: Lag is like 30ms for ~4000 transactions
            #Update this asset's metrics dictionary with our newly calculated information
            asset._metrics.update(metrics[asset.class_code()][asset.ticker()])
            CLASS, TICKER = asset.class_code(), asset.ticker()

            total_cost_basis = 0    #The overall cost basis of what you currently own
            wallet_balance = {}    #A dictionary indicating the balance by wallet
            for WALLET in ledger[CLASS][TICKER]:
                wallet_balance[WALLET] = 0 # Initializes wallet balance at 0$
                for gain in ledger[CLASS][TICKER][WALLET]._heap:
                    total_cost_basis        += gain._price*gain._quantity   #cost basis of this gain
                    wallet_balance[WALLET]      += gain._quantity               #Number of tokens within each wallet
            asset._metrics['cost_basis'] =  total_cost_basis
            asset._metrics['wallets'] =     wallet_balance
            
    # METRICS FOR INDIVIDUAL ASSETS
    # Market-independent
    def calculate_average_buy_price(self, asset:Asset):
        try:    asset._metrics['average_buy_price'] = asset.get_metric('cost_basis') / asset.get_metric('balance')
        except: pass
    # Market-dependent
    def calculate_value(self, asset:Asset):   #Calculates the overall value of this asset
        #Must be a try statement because it relies on market data
        try: asset._metrics['value'] = asset.get_metric('balance') * asset.get_metric('price')
        except: pass
    def calculate_unrealized_profit_and_loss(self, asset:Asset):
        #You need current market data for these bad boys
        average_buy_price = asset.get_metric('average_buy_price')
        try:        
            asset._metrics['unrealized_profit_and_loss'] =      asset.get_metric('value') - ( average_buy_price * asset.get_metric('balance') )
            asset._metrics['unrealized_profit_and_loss%'] =   ( asset.get_metric('price') /  average_buy_price )-1
        except: pass
    def calculate_changes(self, asset:Asset): #Calculates the unrealized USD lost or gained in the last 24 hours, week, and month for this asset
        #Must be a try statement because it relies on market data
        value = asset.get_metric('value')
        try:    asset._metrics['day_change'] =   value-(value / (1 + asset.get_metric('day%')))
        except: pass
        try:    asset._metrics['week_change'] =  value-(value / (1 + asset.get_metric('week%')))
        except: pass
        try:    asset._metrics['month_change'] = value-(value / (1 + asset.get_metric('month%')))
        except: pass
    def calculate_projected_cash_flow(self, asset:Asset): #Calculates what the cash flow would become if you sold everything right now
        #Must be a try statement because it relies on market data
        try:    asset._metrics['projected_cash_flow'] = asset.get_metric('cash_flow') + asset.get_metric('value') 
        except: pass
    def calculate_percentage_of_portfolio(self, asset:str): #Calculates how much of the value of your portfolio is this asset - NOTE: must be done after total portfolio value calculated
        try:    asset._metrics['portfolio%'] = asset.get_metric('value')  / self.PORTFOLIO.get_metric('value')
        except: pass

    # METRICS FOR THE OVERALL PORTFOLIO
    # Market-independent
    def calculate_portfolio_cash_flow(self): # Calculates to total USD that has gone into and out of the portfolio
        cash_flow = 0
        for a in self.PORTFOLIO.assets():    #Compiles complete list of all assets in the portfolio
            try: cash_flow += a.get_metric('cash_flow') #Adds the cash flow for this asset to the overall portfolio cash flow.
            except: continue # If the cash flow was unable to be calculated, ignore this asset
        self.PORTFOLIO._metrics['cash_flow'] = cash_flow
    # Market-Dependent
    def calculate_portfolio_value(self): # Calculates the overall current market value of the portfolio
        value = 0
        for a in self.PORTFOLIO.assets():    #Compiles complete list of all wallets used in the portfolio
            try: value += a.get_metric('value') #Adds the total value of this asset to the overall portfolio value. If no price data can be found we assume this asset it worthless.
            except: continue
        self.PORTFOLIO._metrics['value'] = value
    def calculate_portfolio_projected_cash_flow(self): #Calculates what the cash flow would become if you sold everything right now
        #Must be a try statement because it relies on market data
        try:    self.PORTFOLIO._metrics['projected_cash_flow'] = self.PORTFOLIO._metrics['cash_flow'] + self.PORTFOLIO._metrics['value']
        except: pass
    def calculate_portfolio_changes(self): # Calculates absolute change over the past day, week, and month
        self.PORTFOLIO._metrics.update({'day_change':0,'week_change':0,'month_change':0})
        for a in self.PORTFOLIO.assets():
            try:
                self.PORTFOLIO._metrics['day_change'] += a.get_metric('day_change')
                self.PORTFOLIO._metrics['week_change'] += a.get_metric('week_change')
                self.PORTFOLIO._metrics['month_change'] += a.get_metric('month_change')
            except: pass
    def calculate_portfolio_percents(self): # Calculates relative change over the past day, week, and month
        try:    self.PORTFOLIO._metrics['day%'] =   self.PORTFOLIO.get_metric('day_change') /   (self.PORTFOLIO.get_metric('value') - self.PORTFOLIO.get_metric('day_change'))
        except: pass
        try:    self.PORTFOLIO._metrics['week%'] =  self.PORTFOLIO.get_metric('week_change') /  (self.PORTFOLIO.get_metric('value') - self.PORTFOLIO.get_metric('week_change'))
        except: pass
        try:    self.PORTFOLIO._metrics['month%'] = self.PORTFOLIO.get_metric('month_change') / (self.PORTFOLIO.get_metric('value') - self.PORTFOLIO.get_metric('month_change'))
        except: pass
    def calculate_portfolio_value_by_wallet(self):    #Calculates the current market value held within each wallet, across all assets
        wallets = {wallet:0 for wallet in self.PORTFOLIO.all_wallet_names()}  #Creates a dictionary of wallets, defaulting to 0$ within each
        for asset in self.PORTFOLIO.assets():       #Then, for every asset, we look at its 'wallets' dictionary, and sum up the value of each wallet's tokens by wallet
            for wallet in asset.get_metric('wallets'):
                # Asset wallet list is total units by wallet, multiply by asset price to get value
                try:    wallets[wallet] += asset.get_metric('wallets')[wallet] * asset.get_metric('price')
                except: pass
        self.PORTFOLIO._metrics['wallets'] = wallets
    def calculate_portfolio_unrealized_profit_and_loss(self):
        total_unrealized_profit = 0
        for asset in self.PORTFOLIO.assets():
            try:    total_unrealized_profit += asset.get_metric('unrealized_profit_and_loss')
            except: continue    #Just ignore assets missing price data
        try:        
            self.PORTFOLIO._metrics['unrealized_profit_and_loss'] = total_unrealized_profit
            self.PORTFOLIO._metrics['unrealized_profit_and_loss%'] = total_unrealized_profit / (self.PORTFOLIO.get_metric('value') - total_unrealized_profit)
        except:
            self.PORTFOLIO._metrics['unrealized_profit_and_loss'] = self.PORTFOLIO._metrics['unrealized_profit_and_loss%'] = 0
