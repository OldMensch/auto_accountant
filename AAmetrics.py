
from AAobjects import *

class metrics:
    # We initialize the metrics object with a reference to our Portfolio, and TEMP data
    def __init__(self, portfolio, temp, main_app):
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
                if t_in.get_raw('gain_asset') == t_out.get_raw('loss_asset') and acceptableTimeDiff(t_in.unix_date(),t_out.unix_date(),300) and acceptableDifference(t_in.get_metric('gain_quantity'), t_out.get_metric('loss_quantity'), 0.1):
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
                t.ERR_MSG = 'Failed to automatically find a \'Transfer Out\' transaction under '+t.get_raw('gain_asset')[:-2]+' that pairs with this \'Transfer In\'.'
            else:
                t.ERR_MSG = 'Failed to automatically find a \'Transfer In\' transaction under '+t.get_raw('loss_asset')[:-2]+' that pairs with this \'Transfer Out\'.'
                        

        ###################################
        # AUTO-ACCOUNTING
        ###################################
        #Transfers linked. It's showtime. Time to perform the Auto-Accounting!
        # INFO VARIABLES - data we collect as we account for every transaction #NOTE: Lag is 0ms for ~12000 transactions
        metrics = { asset:{'cash_flow':0, 'realized_profit_and_loss': 0, 'tax_capital_gains': 0,'tax_income': 0,} for asset in self.PORTFOLIO.all_asset_tickerclasses() }
        
        # LEDGER - The data structure which tracks asset's original price across sales #NOTE: Lag is 0ms for ~12000 transactions
        # Ledger is a dict of all assets, under which is a dict of all wallets, and each wallet is a priority heap (depending on HIFO/LIFO/FIFO) which stores our transactions
        # We use a min/max heap to decide which transactions are "sold" when assets are sold, to determine what the capital gains actually is
        accounting_method = setting('accounting_method')
        ledger = {asset:{wallet:gain_heap(accounting_method) for wallet in self.PORTFOLIO.all_wallet_names()} for asset in self.PORTFOLIO.all_asset_tickerclasses()}

        # DISBURSE QUANTITY - removes a 'gain', from the LEDGER data structure.
        def disburse_quantity(t:Transaction, quantity:Decimal, a:str, w:str, w2:str=None):  #NOTE: Lag is ~50ms for ~231 disbursals with ~2741 gains moved on average, or ~5 disbursals/ms, or ~54 disbursed gains/ms
            '''Removes, quantity of asset from specified wallet, then returns cost basis of removed quantity.\n
                If wallet2 \'w2\' specified, instead moves quantity into w2.'''
            result = ledger[a][w].disburse(quantity)     #NOTE - Lag is ~40ms for ~12000 transactions
            if not zeroish_prec(result[0]):  #NOTE: Lag is ~0ms
                t.ERROR,t.ERROR_TYPE = True,'over_disbursed'
                t.ERR_MSG = 'User disbursed more ' + a.split('z')[0] + ' than they owned from the '+w+' wallet, with ' + str(result[0]) + ' remaining to disburse.'
                

            #NOTE - Lag is ~27ms including store_quantity, 11ms excluding
            cost_basis = 0
            for gain in result[1]: #Result[1] is a list of gain objects that were just disbursed
                cost_basis += gain._price*gain._quantity
                if tax_report == '8949': tax_8949(t, gain, quantity)
                if w2: ledger[a][w2].store_direct(gain)   #Moves transfers into the other wallet, using the gains objects we already just created
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
                'Description of property':      str(gain._quantity) + ' ' + self.PORTFOLIO.transaction(gain._hash).get_raw('gain_asset').split('z')[0],  # 0.0328453 ETH
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
            HASH,TYPE,WALLET = t.get_metric('hash'),     t.get_raw('type'),              t.get_raw('wallet') # 2.3034 ms
            WALLET2 = t.get_metric('dest_wallet') # only exists for TRANSFER_OUTs
            LA,FA,GA = t.get_raw('loss_asset'),         t.get_raw('fee_asset'),         t.get_raw('gain_asset') # These are the asset tickers combined with their class (like BTCzc)
            LQ,FQ,GQ = t.get_metric('loss_quantity'),   t.get_metric('fee_quantity'),   t.get_metric('gain_quantity')
            LV,FV,GV = t.get_metric('loss_value'),      t.get_metric('fee_value'),      t.get_metric('gain_value')
            LOSS_COST_BASIS,FEE_COST_BASIS = 0,0
            COST_BASIS_PRICE = t.get_metric('basis_price')
            
            # BALANCE CALCULATION - 10.0648 ms for 5300 transactions - to improve efficiency, make it so parent assets saved to transaction's _metrics dict for direct access
            # Sets account balance for these assets at time of transaction
            if LA: 
                LAA = self.PORTFOLIO.asset(LA)
                LAA._metrics['balance'] -= LQ
                t._metrics['balance'][LA] = LAA._metrics['balance']
            if FA: 
                FAA = self.PORTFOLIO.asset(FA)
                FAA._metrics['balance'] -= FQ
                t._metrics['balance'][FA] = FAA._metrics['balance']
            if GA: 
                GAA = self.PORTFOLIO.asset(GA)
                GAA._metrics['balance'] += GQ
                t._metrics['balance'][GA] = GAA._metrics['balance']
            for asset,quantity in t._metrics['balance'].items():
                formatting = metric_formatting_lib['balance']
                t._formatted['balance'][asset] = format_metric(quantity, formatting['format'], colorFormat=formatting['color']) 

            # COST BASIS CALCULATION    #NOTE: Lag ~7.0662ms for ~5300 transactions. 
            # NOTE: We have to do the gain, then the fee, then the loss, because some Binance trades incur a fee in the crypto you just bought
            # GAINS - We gain assets one way or another     #NOTE: Lag ~xxx, on average
            if COST_BASIS_PRICE:    ledger[GA][WALLET].store(HASH, COST_BASIS_PRICE, GQ, t.unix_date())
            # FEE LOSS - We lose assets because of a fee     #NOTE: Lag ~xxx, on average
            if FA:                  FEE_COST_BASIS =  disburse_quantity(t, FQ, FA, WALLET)
            # LOSS - We lose assets one way or another.
            if LA:                  LOSS_COST_BASIS = disburse_quantity(t, LQ, LA, WALLET, WALLET2)

            # METRIC CALCULATION    #NOTE: Lag is ~3.0454ms for ~5300 transactions (all metrics below)
            
            # CASH FLOW - Only transactions involving USD can affect cash flow.
            # HOWEVER... when you "swap" one crypto for another, then the gain asset technically has "0 cash flow", which from an investing perspective, makes no sense
            # Since swaps/trades essentially use the loss asset instrumentally to acquire the gain asset, 
            # I essentially just "move the cash flow" from the Loss Asset to the Gain Asset, and pretend that I bought the gain asset directly with USD
            # Since LV - FV = GV, this shouldn't affect the cash flow for the overall portfolio, since the +/- change on each asset cancels out overall
            match TYPE:
                case 'purchase' | 'purchase_crypto_fee':    metrics[GA]['cash_flow'] -= GV + FV
                case 'sale':                                metrics[LA]['cash_flow'] += LV - FV
                case 'trade': # Here, we include the trades
                    metrics[LA]['cash_flow'] += LV - FV
                    metrics[GA]['cash_flow'] -= GV

            
            # REALIZED PROFIT AND LOSS - Sales and trades sometimes profit, whereas gift_outs, expenses, as well as any fees always incur a loss
            # Fees are always a realized loss, if there is one
            if FA:                              metrics[FA]['realized_profit_and_loss'] -= FEE_COST_BASIS   # Base fee cost is realized
            elif TYPE == 'purchase':            metrics[GA]['realized_profit_and_loss'] -= FV        # Base fee cost is realized to asset bought
            elif TYPE == 'sale':                metrics[LA]['realized_profit_and_loss'] -= FV        # Base fee cost is realized to asset sold
            #Expenses and gift_outs are a complete realized loss. Sales and trades we already lost the fee, but hopefully gain more from sale yield
            if TYPE in ('expense','gift_out'):  metrics[LA]['realized_profit_and_loss'] -= LOSS_COST_BASIS  # Base loss cost is realized
            elif TYPE in ('sale','trade'):      metrics[LA]['realized_profit_and_loss'] += LV - LOSS_COST_BASIS # Base loss cost is realized, but sale yields the loss value

            # CAPITAL GAINS TAX
            #Independent transfer fees are taxed as a 'sale'
            if FA and TYPE in ('gift_out','transfer_out','transfer_in'): metrics[FA]['tax_capital_gains'] += FV - FEE_COST_BASIS
            #Expenses taxed as a 'sale', trade treated as an immediate sale and purchase
            elif TYPE in ('sale','trade'):                               metrics[LA]['tax_capital_gains'] += (LV - FV) - LOSS_COST_BASIS 
            elif TYPE == 'expense':                                      metrics[LA]['tax_capital_gains'] += (LV + FV) - LOSS_COST_BASIS 

            # INCOME TAX
            if TYPE in ('card_reward','income'):    #This accounts for all transactions taxable as INCOME: card rewards, and staking rewards
                metrics[GA]['tax_income'] += GV
                if tax_report=='1099-MISC':  
                    self.TEMPDATA['taxes']['1099-MISC'] = self.TEMPDATA['taxes']['1099-MISC'].append( {'Date acquired':t.iso_date(), 'Value of assets':str(GV)}, ignore_index=True)

            #*** *** *** DONE FOR THIS TRANSACTION *** *** ***#
        

        #ERRORS - applies error state to any asset with an erroneous transaction on its ledger.
        # Initially assume all assets are error free (asset errors can only result from )
        for a in self.PORTFOLIO.assets():   a.ERROR = False
        # Then we check all transactions for an ERROR state, and apply that to its parent asset(s)
        for t in transactions:
            if t.ERROR:
                if t.get_raw('loss_asset'):     self.PORTFOLIO.asset(t.get_raw('loss_asset')).ERROR = True
                if t.get_raw('fee_asset'):      self.PORTFOLIO.asset(t.get_raw('fee_asset')).ERROR =  True
                if t.get_raw('gain_asset'):     self.PORTFOLIO.asset(t.get_raw('gain_asset')).ERROR = True

        for asset in self.PORTFOLIO.assets(): #TODO: Lag is like 30ms for ~4000 transactions
            #Update this asset's metrics dictionary with our newly calculated information
            a = asset.tickerclass()
            asset._metrics.update(metrics[a])

            total_cost_basis = 0    #The overall cost basis of what you currently own
            wallet_balance = {}    #A dictionary indicating the balance by wallet
            for w in ledger[a]:
                wallet_balance[w] = 0 # Initializes wallet balance at 0$
                for gain in ledger[a][w]._heap:
                    total_cost_basis        += gain._price*gain._quantity   #cost basis of this gain
                    wallet_balance[w]      += gain._quantity               #Number of tokens within each wallet
            asset._metrics['cost_basis'] =  total_cost_basis
            asset._metrics['wallets'] =     wallet_balance
            
    # METRICS FOR INDIVIDUAL ASSETS
    # Market-independent
    def calculate_average_buy_price(self, asset:Asset):
        try:    asset._metrics['average_buy_price'] = asset.get_metric('cost_basis') / asset.get_metric('balance')
        except: asset._metrics['average_buy_price'] = 0
    # Market-dependent
    def calculate_value(self, asset:Asset):   #Calculates the overall value of this asset
        #Must be a try statement because it relies on market data
        try:    asset._metrics['value'] = asset.get_metric('balance') * asset.get_metric('price')
        except: asset._metrics['value'] = None
    def calculate_unrealized_profit_and_loss(self, asset:Asset):
        #You need current market data for these bad boys
        average_buy_price = asset.get_metric('average_buy_price')
        try:        
            asset._metrics['unrealized_profit_and_loss'] =      asset.get_metric('value') - ( average_buy_price * asset.get_metric('balance') )
            asset._metrics['unrealized_profit_and_loss%'] =   ( asset.get_metric('price') /  average_buy_price )-1
        except:     asset._metrics['unrealized_profit_and_loss%'] = asset._metrics['unrealized_profit_and_loss'] = 0
    def calculate_changes(self, asset:Asset): #Calculates the unrealized USD lost or gained in the last 24 hours, week, and month for this asset
        #Must be a try statement because it relies on market data
        value = asset.get_metric('value')
        try:    asset._metrics['day_change'] =   value-(value / (1 + asset.get_metric('day%')))
        except: asset._metrics['day_change'] =   0
        try:    asset._metrics['week_change'] =  value-(value / (1 + asset.get_metric('week%')))
        except: asset._metrics['week_change'] =  0
        try:    asset._metrics['month_change'] = value-(value / (1 + asset.get_metric('month%')))
        except: asset._metrics['month_change'] = 0
    def calculate_projected_cash_flow(self, asset:Asset): #Calculates what the cash flow would become if you sold everything right now
        #Must be a try statement because it relies on market data
        try:    asset._metrics['projected_cash_flow'] = asset.get_metric('cash_flow') + asset.get_metric('value') 
        except: asset._metrics['projected_cash_flow'] = 0
    def calculate_percentage_of_portfolio(self, asset:str): #Calculates how much of the value of your portfolio is this asset - NOTE: must be done after total portfolio value calculated
        try:    asset._metrics['portfolio%'] = asset.get_raw('value')  / self.PORTFOLIO.get_metric('value')
        except: asset._metrics['portfolio%'] = 0

    # METRICS FOR THE OVERALL PORTFOLIO
    # Market-independent
    def calculate_portfolio_cash_flow(self): # Calculates to total USD that has gone into and out of the portfolio
        cash_flow = 0
        for a in self.PORTFOLIO.assets():    #Compiles complete list of all assets in the portfolio
            try: cash_flow += a.get_raw('cash_flow') #Adds the cash flow for this asset to the overall portfolio cash flow.
            except: continue # If the cash flow was unable to be calculated, ignore this asset
        self.PORTFOLIO._metrics['cash_flow'] = cash_flow
    # Market-Dependent
    def calculate_portfolio_value(self): # Calculates the overall current market value of the portfolio
        value = 0
        for a in self.PORTFOLIO.assets():    #Compiles complete list of all wallets used in the portfolio
            try: value += a.get_raw('value') #Adds the total value of this asset to the overall portfolio value. If no price data can be found we assume this asset it worthless.
            except: continue
        self.PORTFOLIO._metrics['value'] = value
    def calculate_portfolio_projected_cash_flow(self): #Calculates what the cash flow would become if you sold everything right now
        #Must be a try statement because it relies on market data
        try:    self.PORTFOLIO._metrics['projected_cash_flow'] = self.PORTFOLIO._metrics['cash_flow'] + self.PORTFOLIO._metrics['value']
        except: self.PORTFOLIO._metrics['projected_cash_flow'] = 0
    def calculate_portfolio_changes(self): # Calculates absolute change over the past day, week, and month
        self.PORTFOLIO._metrics.update({'day_change':0,'week_change':0,'month_change':0})
        for a in self.PORTFOLIO.assets():
            try:
                self.PORTFOLIO._metrics['day_change'] += a.get_raw('day_change')
                self.PORTFOLIO._metrics['week_change'] += a.get_raw('week_change')
                self.PORTFOLIO._metrics['month_change'] += a.get_raw('month_change')
            except: pass
    def calculate_portfolio_percents(self): # Calculates relative change over the past day, week, and month
        try:    self.PORTFOLIO._metrics['day%'] =   self.PORTFOLIO.get_metric('day_change') /   (self.PORTFOLIO.get_metric('value') - self.PORTFOLIO.get_metric('day_change'))
        except: self.PORTFOLIO._metrics['day%'] = 0
        try:    self.PORTFOLIO._metrics['week%'] =  self.PORTFOLIO.get_metric('week_change') /  (self.PORTFOLIO.get_metric('value') - self.PORTFOLIO.get_metric('week_change'))
        except: self.PORTFOLIO._metrics['week%'] = 0
        try:    self.PORTFOLIO._metrics['month%'] = self.PORTFOLIO.get_metric('month_change') / (self.PORTFOLIO.get_metric('value') - self.PORTFOLIO.get_metric('month_change'))
        except: self.PORTFOLIO._metrics['month%'] = 0
    def calculate_portfolio_value_by_wallet(self):    #Calculates the current market value held within each wallet, across all assets
        wallets = {wallet:0 for wallet in self.PORTFOLIO.all_wallet_names()}  #Creates a dictionary of wallets, defaulting to 0$ within each
        for asset in self.PORTFOLIO.assets():       #Then, for every asset, we look at its 'wallets' dictionary, and sum up the value of each wallet's tokens by wallet
            for wallet in asset.get_raw('wallets'):
                # Asset wallet list is total units by wallet, multiply by asset price to get value
                try:    wallets[wallet] += asset.get_raw('wallets')[wallet] * asset.get_metric('price')
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
