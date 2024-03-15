
import pandas as pd
from io import StringIO

from AAobjects import *
from AAdialogs import Message
from AAmarketData import getMissingPrice

def trans_from_raw(date_unix=None,type=None,wallet=None,description='',loss=(None,None,None),fee=(None,None,None),gain=(None,None,None)):
    raw_data = { # RAW STRING DATA
        'date' :            date_unix,
        'type' :            type,
        'wallet' :          wallet,
        'description' :     description,

        'loss_ticker' :     loss[0],
        'fee_ticker' :      fee[0],
        'gain_ticker' :     gain[0],
        'loss_class' :      'c',
        'fee_class' :       'c',
        'gain_class' :      'c',
        'loss_quantity' :   loss[1],
        'fee_quantity' :    fee[1],
        'gain_quantity' :   gain[1],
        'loss_price' :      loss[2],
        'fee_price' :       fee[2],
        'gain_price' :      gain[2],
    }
    # Replace NA pandas data with None
    for metric,data in raw_data.items():
        if pd.isna(data): raw_data[metric] = None
    if raw_data['description'] == None: raw_data['description']=''
    # Clear class data if ticker is None: otherwise this causes errors
    for part in ('loss_','fee_','gain_'):
        if raw_data[f'{part}ticker'] is None:
            raw_data[f'{part}class'] = None
    # Clean data (just in case! should be unneccessary)
    if type:    raw_data = {metric:raw_data[metric] for metric in trans_type_minimal_set[type]}
    return Transaction(raw_data)

def finalize_import(mainAppREF, PORTFOLIO_TO_MERGE):
    mainAppREF.PORTFOLIO.loadJSON(PORTFOLIO_TO_MERGE.toJSON(), merge=True, overwrite=False)   # Imports new transactions, doesn't overwrite duplicates (to preserve custom descriptions, type changes, etc.)
    mainAppREF.metrics()
    mainAppREF.render(sort=True)
    mainAppREF.undo_save()
    mainAppREF.hide_progress()


def isCoinbasePro(fileDir): #Returns true if this is a Coinbase Pro file
    try:    return open(fileDir, 'r').readlines()[0][0:9] == 'portfolio'
    except: return False
def isGeminiEarn(data): #Returns true if this is a Gemini Earn file (uses data to do this)
    if 'APY' in data.columns:   return True
    else:                       return False
def isEtherscanERC20(data): # Returns true if this is a Etherscan ERC-20 tokens transaction file
    if 'TokenSymbol' in data:   return True
    else:                       return False

def loadCoinbaseFile(fileDir):
    """Removes whitespace rows at the top of Coinbase CSV. Returns user's username and DataFrame"""
    #CUTS OUT the FIRST THREE ROWS from the CSV file, since they're just useless
    raw = open(fileDir, 'r').readlines()
    for i in range(len(raw)):
        if raw[i][0:5] == 'User,':
            username = raw[i].split(',')[1]
        if raw[i][0:10] == 'Timestamp,':
            firstindex = i
            break
    data = ''.join([line for line in raw[firstindex:]])
    return username, pd.read_csv(StringIO(data), dtype='string') #We read the data all as strings to preserve accuracy
def loadEtherscanFile(fileDir) -> pd.DataFrame:
    """Fixes Etherscan CSV missing delimiters issue"""
    #Etherscan's CSV file is fucky, and sometimes has more delimiters in the headers than the rows
    raw = open(fileDir, 'r').readlines()
    data = ''
    if raw[0].count(',') < raw[1].count(','):   #We can tell how many columns of data there are by the number of delimiters. If too few columns, add more empty columns
        raw[0] = raw[0].replace('\n', '') + ',\"\"\n'
    for line in raw: data += line
    return pd.read_csv(StringIO(data), dtype='string') #We read the data all as strings to preserve accuracy



# IMPORT FUNCTIONS

# NOTE: needs to check this works still
def binance(mainAppREF, fileDir, wallet):   #Imports Binance transaction history
    '''Reads the CSV file you downloaded from Binance tax transaction history, imports it into your portfolio'''
    data = pd.read_csv(fileDir, dtype='string')
    PORTFOLIO_TO_MERGE = Portfolio()

    print('||WARNING|| I don\'t know whether Binance transaction times are reported in UTC or your local time zone... the dates/times may be wrong')
    print('||WARNING|| Also I may have messed up how the dates were saved in my copy of the Binance CSV file.... so it might be very broken...')

    for t in data.iterrows():
        # 0-5   User_Id, Time, Category, Operation, Order_Id, Transaction_Id,
        # 6-8   Primary_Asset, Realized_Amount_For_Primary_Asset, Realized_Amount_For_Primary_Asset_In_USD_Value,
        # 9-11  Base_Asset, Realized_Amount_For_Base_Asset, Realized_Amount_For_Base_Asset_In_USD_Value,
        # 12-14 Quote_Asset, Realized_Amount_For_Quote_Asset, Realized_Amount_For_Quote_Asset_In_USD_Value,
        # 15-17 Fee_Asset, Realized_Amount_For_Fee_Asset, Realized_Amount_For_Fee_Asset_In_USD_Value,
        # 18-20 Payment_Method, Withdrawal_Method, Additional_Note

        #This is still here in case I actually broke the date when I re-saved the CSV file
        #date =      t[1]['Time'].replace('-','/')
        date = t[1]['Time'].replace('/',' ').replace(':',' ').split(' ')
        date = date[2]+' '+date[0]+' '+date[1]+' '+date[3]+' '+date[4]+' '+date[5] #TODO TODO TODO: This date might be wrong! I probably messed up my copy of the binance CSV file.
        date = timezone_to_unix(date, 'UTC')
        category =  t[1]['Category']
        operation = t[1]['Operation']
        PA, PQ, PV = t[1]['Primary_Asset'], t[1]['Realized_Amount_For_Primary_Asset'], t[1]['Realized_Amount_For_Primary_Asset_In_USD_Value']  #Primary Asset
        try:    PP = str(Decimal(PV.replace('$',''))/Decimal(PQ))
        except: pass
        BA, BQ, BV = t[1]['Base_Asset'], t[1]['Realized_Amount_For_Base_Asset'], t[1]['Realized_Amount_For_Base_Asset_In_USD_Value'] #Base Asset
        try:    BP = str(Decimal(BV.replace('$',''))/Decimal(BQ))
        except: pass
        QA, QQ, QV = t[1]['Quote_Asset'], t[1]['Realized_Amount_For_Quote_Asset'], t[1]['Realized_Amount_For_Quote_Asset_In_USD_Value'] #Quote Asset
        try:    QP = str(Decimal(QV.replace('$',''))/Decimal(QQ))
        except: pass
        FA, FQ, FV = t[1]['Fee_Asset'], t[1]['Realized_Amount_For_Fee_Asset'], t[1]['Realized_Amount_For_Fee_Asset_In_USD_Value'] #Fee Asset
        try:    FP = str(Decimal(FV.replace('$',''))/Decimal(FQ))
        except: pass

        if operation == 'USD Deposit':  continue
        elif operation == 'Staking Rewards':
            trans = trans_from_raw(date, 'income', wallet, operation, gain=[PA, PQ, PP])
        elif category == 'Quick Buy': #For quick buys, the base_asset is the USD loss, the quote_asset is the crypto gain, fee is USD fee
            trans = trans_from_raw(date, 'purchase', wallet, operation, [None, BQ, None], [None, FQ, None], [QA, QQ, QP])
        elif category == 'Spot Trading' and operation == 'Buy' and QA == 'USD': #For spot buys, base_asset is the gain, quote_asset is the loss, fee is crypto fee
            trans = trans_from_raw(date, 'purchase_crypto_fee', wallet, operation, [None, QQ, None], [FA, FQ, FP], [BA, BQ, None])

        else:
            Message(mainAppREF, 'IMPORT ERROR!', 'Failed to import unknown Binance wallet transaction type: ' + category + ' - ' + operation + '.')
            return

        PORTFOLIO_TO_MERGE.import_transaction(trans)
    
    finalize_import(mainAppREF, PORTFOLIO_TO_MERGE)

def coinbase_pro(mainAppREF, fileDir, wallet):    #Imports Coinbase Pro transaction history
    '''Reads the CSV file you downloaded from Coinbase Pro, imports it into your portfolio'''
    PORTFOLIO_TO_MERGE = Portfolio()
    if not isCoinbasePro(fileDir):
        Message(mainAppREF, 'IMPORT ERROR!','This is Coinbase history, not Coinbase Pro history.')
        return
    data = pd.read_csv(fileDir, dtype='string')

    losses = {} #Coinbase Pro thinks like I do - you lose something, gain something, and have some fee. They report in triplets. Very nice.
    fees = {}
    gains = {}

    # BASIC TRANSACTIONS - Scans all the transactions, adds some of the basic ones like deposits/withdrawals
    for t in data.iterrows():
        # portfolio,type,time,amount,balance,amount/balance unit,transfer id,trade id,order id
        ID = t[1]['time']
        date = timezone_to_unix(t[1]['time'], 'UTC') #Coinbase Pro time is UTC by default
        type = t[1]['type']
        asset = t[1]['amount/balance unit']
        quantity = t[1]['amount'].removeprefix('-')
        isLoss = t[1]['amount'][0]=='-' # True if amount is negative

        # First, simple transactions are completed
        if asset == 'USD' and type in ('deposit','withdrawal'): continue
        elif type == 'deposit':    PORTFOLIO_TO_MERGE.import_transaction(trans_from_raw(date, 'transfer_in', wallet, gain=[asset,quantity,None]))
        elif type == 'withdrawal': PORTFOLIO_TO_MERGE.import_transaction(trans_from_raw(date, 'transfer_out', wallet, loss=[asset,quantity,None]))

        #Not simple. Ok, add it to the list of losses/fees/gains
        elif type == 'fee':     fees[ID] = [asset, quantity, None]
        elif type == 'match': 
            if isLoss:          losses[ID] = [asset, quantity, None]
            else:               gains[ID] = [asset, quantity, None]
        else:
            Message(mainAppREF, 'IMPORT ERROR!', 'Couldn\'t import Coinbase PRO history due to unknown transaction type \"'+type+'\".')
            return

    # COMPLEX TRANSACTIONS - Adds in the rest of the transactions that come in triplets
    for t in losses:
        date = timezone_to_unix(t, 'UTC')
        L,F,G = losses[t],fees[t],gains[t]
        for a in (L,F,G): 
            if a[0]=='USD': a[0]=None #Get rid of USD's
        
        if L[0] == None:    PORTFOLIO_TO_MERGE.import_transaction(trans_from_raw(date, 'purchase', wallet, '', L, F, G))
        else:               PORTFOLIO_TO_MERGE.import_transaction(trans_from_raw(date, 'sale', wallet, '', L, F, G))
        
    finalize_import(mainAppREF, PORTFOLIO_TO_MERGE)

def coinbase(mainAppREF, fileDir, wallet):    #Imports Coinbase transaction history
    '''Reads the CSV file you downloaded from Coinbase (not PRO), imports it into your portfolio'''   
    if isCoinbasePro(fileDir):
        Message(mainAppREF, 'IMPORT ERROR!','This is Coinbase Pro history, not Coinbase history.')
        return 
    PORTFOLIO_TO_MERGE = Portfolio()
    username, data = loadCoinbaseFile(fileDir)

    mainAppREF.show_progress()
    mainAppREF.set_progress_range(0,len(data.count(axis=0)))
    i = 0
    for t in data.iterrows():
        # Timestamp,Transaction Type,Asset,Quantity Transacted,Spot Price Currency,Spot Price at Transaction,Subtotal,Total (inclusive of fees),Fees,Notes
        i+=1
        mainAppREF.set_progress(i)
        #INFORMATION GATHERING
        date = timezone_to_unix(t[1]['Timestamp'].replace('T',' ').replace('Z',''), 'UTC')
        TYPE = t[1]['Transaction Type']
        asset = t[1]['Asset']
        quantity = t[1]['Quantity Transacted']
        fee = t[1]['Fees and/or Spread']  #The fee (USD)
        spot_price = t[1]['Spot Price at Transaction']
        ############################
        # Patch to fix issue of innaccurate spot prices, fees, ans subtotals
        # if Decimal(spot_price) < 0.10:
        #     print('||WARNING|| Transaction found for which Coinbase has inaccurate price data!')
        #     spot_price = getMissingPrice(t[1]['Timestamp'], asset, 'c')
        #     subtotal = str((Decimal(quantity) * Decimal(spot_price)) + Decimal(fee))
        # else:
        #     subtotal = t[1]['Subtotal']  #The profit before the fee
        if Decimal(spot_price) < 0.10:
            print('||WARNING|| Transaction found for which Coinbase has inaccurate price data! AUTOMATIC PRICE CORRECTION DISABLED!')
        subtotal = t[1]['Subtotal']  #The profit before the fee
        ############################
        desc = t[1]['Notes']
        loss_ticker, gain_ticker = None,None
        if TYPE in ('Advance Trade Buy', 'Advance Trade Sell'):
            if TYPE == 'Advance Trade Buy':
                gain_ticker =   desc.split(' on ')[1].split('-')[0] # Bought this,
                loss_ticker =   desc.split(' on ')[1].split('-')[1] # With this
            else:
                loss_ticker =   desc.split(' on ')[1].split('-')[0] # Sold this,
                gain_ticker =   desc.split(' on ')[1].split('-')[1] # and got this
            
            fee_ticker = desc.split('-')[1]

        # Advance Trade Buy
        # Advance Trade Sell

        if asset=='USD': continue # Ignore USD withdrawals/deposits
        elif   TYPE == 'Buy' or loss_ticker == 'USD': # Buy and "advanced trade buy" with a -USD market pair
            trans = trans_from_raw(date, 'purchase', wallet, desc, [None,subtotal,None],[None,fee,None],[asset,quantity,None])
        elif TYPE == 'Sell' or gain_ticker == 'USD': # Sell and "advanced trade sell" with a -USD market pair
            trans = trans_from_raw(date, 'sale', wallet, desc, [asset,quantity,None],[None,fee,None],[None,subtotal,None])
        elif TYPE == 'Receive' and desc.split(' from ')[1]:
            match desc.split(' from ')[1]:
                # Recieved is a transfer_in
                case 'GDAX'|'an external account':
                    trans = trans_from_raw(date, 'transfer_in', wallet, desc, gain=[asset,quantity,None])
                # Recieved is an income event
                case ''|'Coinbase'|'Coinbase Earn'|'Coinbase Card'|'Coinbase Rewards':
                    trans = trans_from_raw(date, 'income', wallet, desc, gain=[asset,quantity,spot_price])
                # Username ones are duplicates....
                case str(username): continue 
                case other:
                    Message(mainAppREF, 'IMPORT ERROR!', f'Failed to import due to unknown \'Recieve\' type, {other}')
                    return
        elif TYPE == 'Receive':
            trans = trans_from_raw(date, 'income', wallet, desc, gain=[asset,quantity,spot_price])
        elif TYPE == 'Send':
            if desc.split(' to ')[1] == username: continue # Username ones are duplicates....
            trans = trans_from_raw(date, 'transfer_out', wallet, desc, loss=[asset,quantity,None])
        elif TYPE in ('Learning Reward', 'Staking Income', 'Inflation Reward'):   #Coinbase Learn & Earn treated as income by the IRS, according to Coinbase
            trans = trans_from_raw(date, 'income', wallet, desc, gain=[asset,quantity,spot_price])
        elif TYPE in 'Advance Trade Buy': #Trades.... even worse than Gemini! Missing quantity/price data...
            trans = trans_from_raw(date, 'trade', wallet, desc, [loss_ticker,None,None],[fee_ticker,None,None],[gain_ticker,quantity,None])
        elif TYPE == 'Advance Trade Sell':
            trans = trans_from_raw(date, 'trade', wallet, desc, [loss_ticker,quantity,spot_price],[fee_ticker,None,None],[gain_ticker,None,None])
        else:
            Message(mainAppREF, 'IMPORT ERROR!', 'Couldn\'t import Coinbase history due to unimplemented transaction type, \'' + TYPE + '\'')
            return

        PORTFOLIO_TO_MERGE.import_transaction(trans)
        mainAppREF.set_progress(len(PORTFOLIO_TO_MERGE._transactions))

    finalize_import(mainAppREF, PORTFOLIO_TO_MERGE)
                

def etherscan(mainAppREF, ethFileDir, erc20FileDir, wallet):      #Imports the Etherscan transaction history, requires both ETH and ERC-20 history
    '''Reads the pair of CSV files you downloaded from Etherscan on ETH and ERC-20 transactions, imports them into your portfolio'''
    eth_data = loadEtherscanFile(ethFileDir)
    erc20_data = loadEtherscanFile(erc20FileDir)
    if isEtherscanERC20(eth_data):
        Message(mainAppREF, 'IMPORT ERROR!','The first CSV you chose is Etherscan ERC-20 history, not Etherscan ETH history.')
        return 
    if not isEtherscanERC20(erc20_data):
        Message(mainAppREF, 'IMPORT ERROR!','The second CSV you chose it Etherscan ETH history, not Etherscan ERC-20 history.')
        return 
    PORTFOLIO_TO_MERGE = Portfolio()

    #1) parse ERC20s, if their txhash not in ETH, then they are a transfer_in of ERC20 tokens. 
    #2) parse ETH. If error, expense. If TO is this wallet, then transfer_in of ETH. If Swap, trade.
    #3) parse ETH, if their txhash not in ERC20s, then they are an independent expense
    #4) parse ERC20s, if FROM this wallet, then a transfer out with fee. If TO this wallet, then create both a transfer_in, and a transfer_out w/ fee & MISSINGWALLET

    this_wallet_address = None

    # REFORMATTING OUR TRANSACTIONS:
    # Fixes NA issues
    eth_data.fillna('', inplace=True)
    erc20_data.fillna('', inplace=True)

    # ETH Transactions
    # Indexed by txhash:    Unixtime, from, to, value_in, value_out, fee, price, error_code, method
    eth_trans = {t[1]['Txhash']:{
        'unix':int(t[1]['UnixTimestamp']),
        'from':t[1]['From'],
        'to':t[1]['To'],
        'eth_in':t[1]['Value_IN(ETH)'],
        'eth_out':t[1]['Value_OUT(ETH)'],
        'eth_fee':t[1]['TxnFee(ETH)'],
        'eth_price':t[1]['Historical $Price/Eth'],
        'err':t[1]['ErrCode'], # error, if there is one
        'method':t[1]['Method'] # "transaction type" more or less, on their end
        } for t in eth_data.iterrows()}

    # ERC-20 Transactions
    # Indexed by txhash:    Unixtime, from, to, value, ticker
    erc20_trans = {t[1]['Txhash']:{
        'unix':int(t[1]['UnixTimestamp']),
        'from':t[1]['From'],
        'to':t[1]['To'],
        'quantity':t[1]['TokenValue'].replace(',',''), #value #NOTE: Can have commas in it, gotta remove those
        'ticker':t[1]['TokenSymbol']
        } for t in erc20_data.iterrows()}
        
    # 1) FIND WALLET ADDRESS
    # This wallet's address will be present in EVERY transaction
    # Intersection of four sets of from/to/from/to data will return this wallet's address
    if len(eth_trans) + len(erc20_trans) < 2:
        Message(mainAppREF, 'Import Error', 'Could not import data from etherscan: with less than 2 transactions, the wallet\'s address cannot be determined.')
    eth_from =      {  eth_trans[txhash]['from'] for txhash in eth_trans}
    eth_to =        {  eth_trans[txhash]['to']   for txhash in eth_trans}
    erc20_from =    {erc20_trans[txhash]['from'] for txhash in erc20_trans}
    erc20_to =      {erc20_trans[txhash]['to']   for txhash in erc20_trans}
    this_wallet_address = eth_from.intersection(eth_to).intersection(erc20_from).intersection(erc20_to).pop()
    
    # 2) TRANSACTIONS IN BOTH RECORDS
    # Records:
    #   - Trades (swaps)
    #   - Transfer_in of ERC-20 tokens WITH FEE
    #   - Transfer_out of ERC-20 tokens WITH FEE
    for txhash in set(eth_trans.keys()).intersection(set(erc20_trans.keys())):
        eth,erc20 = eth_trans[txhash],erc20_trans[txhash]
        if eth['method'] == 'Swap Exact ETH For Tokens':
            PORTFOLIO_TO_MERGE.import_transaction(trans_from_raw(eth['unix'], 'trade', wallet,
                                                                 loss=['ETH',eth['eth_out'],eth['eth_price']],
                                                                 fee=['ETH',eth['eth_fee'],eth['eth_price']],
                                                                 gain=[erc20['ticker'],erc20['quantity'],None]))
        elif erc20['from'] == this_wallet_address: # transfer of non-ETH, OUT of this wallet
            PORTFOLIO_TO_MERGE.import_transaction(trans_from_raw(eth['unix'], 'transfer_out', wallet,
                                                                 loss=[erc20['ticker'],erc20['quantity'],None], # loss
                                                                 fee=['ETH',eth['eth_fee'],eth['eth_price']]))
        elif erc20['to'] == this_wallet_address: # transfer of non-ETH, IN to this wallet
            PORTFOLIO_TO_MERGE.import_transaction(trans_from_raw(eth['unix'], 'transfer_in', wallet,
                                                                 gain=[erc20['ticker'],erc20['quantity'],None], # gain
                                                                 fee=['ETH',eth['eth_fee'],eth['eth_price']]))

        eth_trans.pop(txhash)
        erc20_trans.pop(txhash)

    # 3) REMAINING ERC-20 TRANSACTIONS
    # Records:
    #   - Transfer_in of ERC-20 tokens NO FEE
    #   - Transfer_out of ERC-20 tokens NO FEE
    for txhash in list(erc20_trans):
        erc20 = erc20_trans[txhash]
        if erc20['from'] == this_wallet_address: # transfer of non-ETH, OUT of this wallet
            PORTFOLIO_TO_MERGE.import_transaction(trans_from_raw(erc20['unix'], 'transfer_out', wallet, loss=[erc20['ticker'],erc20['quantity'],None])) # loss
        elif erc20['to'] == this_wallet_address: # transfer of non-ETH, IN to this wallet
            PORTFOLIO_TO_MERGE.import_transaction(trans_from_raw(erc20['unix'], 'transfer_in',  wallet, gain=[erc20['ticker'],erc20['quantity'],None])) # gain

        erc20_trans.pop(txhash)


    # 4) REMAINING ETH TRANSACTIONS
    # Records:
    #   - Expenses, due to failed transactions
    #   - Transfer_in of ETH tokens NO FEE (fee paid by sender)
    #   - Transfer_out of ETH tokens WITH FEE
    #   - Expenses, due to approvals and other such things
    for txhash in list(eth_trans):
        eth = eth_trans[txhash]

        # Expenses, due to failed transactions
        if eth['err']!='':
            PORTFOLIO_TO_MERGE.import_transaction(trans_from_raw(eth['unix'], 'expense', wallet, f'ETH fee due to error, \'{eth['err']}\'', 
                                                                 loss=['ETH',eth['eth_fee'],eth['eth_price']]))
        # Transfer_in of ETH tokens NO FEE (fee paid by sender)
        elif Decimal(eth['eth_in'])>0 and Decimal(eth['eth_out'])==0:
            PORTFOLIO_TO_MERGE.import_transaction(trans_from_raw(eth['unix'], 'transfer_in',  wallet, gain=['ETH',eth['eth_in'],None])) # gain
        # Transfer_out of ETH tokens WITH FEE
        elif Decimal(eth['eth_in'])==0 and Decimal(eth['eth_out'])>0:
            PORTFOLIO_TO_MERGE.import_transaction(trans_from_raw(eth['unix'], 'transfer_out', wallet, loss=['ETH',eth['eth_out'],None], fee=['ETH',eth['eth_fee'],eth['eth_price']])) # loss
        # Expenses, due to approvals and other such things
        else: # eth_in == eth_out == 0: only fee, and fee not associated with anything on erc20 ledger
            PORTFOLIO_TO_MERGE.import_transaction(trans_from_raw(eth['unix'], 'expense', wallet, f'ETH fee due to \'{eth['method']}\'', 
                                                                 loss=['ETH',eth['eth_fee'],eth['eth_price']]))

        eth_trans.pop(txhash)
        
    finalize_import(mainAppREF, PORTFOLIO_TO_MERGE)


def gemini_earn(mainAppREF, fileDir, wallet):   #Imports Gemini Earn transaction history
    '''Reads the XLSX file you downloaded from Gemini or Gemini Earn, imports it into your portfolio'''
    data = pd.read_excel(fileDir, dtype='string', keep_default_na=False)
    if not isGeminiEarn(data):
        Message(mainAppREF, 'IMPORT ERROR!','This is Gemini history, not Gemini Earn history.')
        return
    PORTFOLIO_TO_MERGE = Portfolio()

    # For whatever reason the 'Price USD' and 'Amount USD' column names have NO reference to what crypto they are for, 
    # so I add the crypto ticker to the column name for easier processing
    prev_col = ''
    new_columns = list(data.columns)
    for i in range(len(new_columns)):
        col = new_columns[i]
        ticker = prev_col.split(' ')[-1] # Takes the last word from the previous column. This should always be the ticker
        if 'Price USD' in col:        new_columns[i] = 'Price USD ' + ticker
        elif 'Amount USD' in col:     new_columns[i] = 'Amount USD ' + ticker
        prev_col = new_columns[i]
    data.columns = new_columns

    for t in data.iterrows():
        #We ignore missing data (the last row), and the Monthly Interest Summaries
        if t[1].iloc[3] == '' or t[1].iloc[2] == 'Monthly Interest Summary':      continue
        
        # INFORMATION GATHERING
        date = timezone_to_unix(t[1].iloc[0], 'UTC')
        trans_type = t[1].iloc[2]
        asset_ticker = t[1].iloc[3]
        asset = asset_ticker
        quantity = data['Amount ' + asset_ticker][t[0]].removeprefix('-') #Removes negative from redemptions
        price = data[ 'Price USD '+  asset_ticker][t[0]]

        # TRANSACTION HANDLING - Handles the three different transaction types within Gemini Earn Reports: Deposit, Redeem, Interest Credit
        if trans_type == 'Deposit':             trans = trans_from_raw(date, 'transfer_in', wallet, gain=[asset, quantity, None])
        elif trans_type == 'Redeem':            trans = trans_from_raw(date, 'transfer_out', wallet, loss=[asset, quantity, None])
        elif trans_type == 'Interest Credit':   trans = trans_from_raw(date, 'income', wallet, gain=[asset, quantity, price])
        elif trans_type == 'Administrative Debit': # MUST RE-IMPLEMENT once assets are transferred back to Gemini proper
            print("||WARNING|| Gemini Earn transaction \'Administrative Debit\' currently not supported until Genesis bankruptcy case is over")
            continue
        
        else:
            Message(mainAppREF, 'IMPORT ERROR!', 'Couldn\'t import Gemini (Earn) history due to unimplemented transaction type, \'' + trans_type + '\'')
            return
        
        PORTFOLIO_TO_MERGE.import_transaction(trans)

    finalize_import(mainAppREF, PORTFOLIO_TO_MERGE)

def gemini(mainAppREF, fileDir, wallet):   #Imports Gemini transaction history
    '''Reads the XLSX file you downloaded from Gemini or Gemini Earn, imports it into your portfolio'''
    data = pd.read_excel(fileDir, dtype='string', keep_default_na=False)
    if isGeminiEarn(data):
        Message(mainAppREF, 'IMPORT ERROR!','This is Gemini Earn history, not Gemini history.')
        return
    PORTFOLIO_TO_MERGE = Portfolio()

    for t in data.iterrows():
        #We ignore anything that's just USD, and we ignore an empty cell as a way of ignoring the final row in the dataset, which are just totals
        if t[1].iloc[3] in ('USD', ''):  continue

        #INFORMATION GATHERING
        DATE = timezone_to_unix(t[1]['Date'], 'UTC')
        TYPE = t[1]['Type']
        SYMBOL = t[1]['Symbol'] # ticker or market pair
        spec = t[1]['Specification'] #The 'specification' of the transaction. 'Earn Redemption', 'Gemini Pay', etc.
        LA = t[1]['Symbol'] #Loss asset - initialized as market pair or ticker (can be either)
        FA = ''             #Fee asset
        GA = ''             #Gain asset
        for i in range(3,len(LA)-2): #t[1].iloc[3] is the asset debted/credited, or for sales/buys, its the market pair, like USDGUSD. Here, we split that between asset_1 and asset_2
            try:
                a1,a2 = LA[:i],LA[i:]
                FA = a2 #Second of the two is always the fee asset
                FQ = t[1][f'Fee ({a2}) {a2}'].removeprefix('-') #Fee quantity. [1:] removes the - sign
                if t[1][f'{a1} Amount {a1}'][0] == '-':      LA,GA = a1,a2    #If the first character is -, then a1 is the loss asset, otherwise its the other way around
                else:                                        LA,GA = a2,a1
                GQ = t[1][f'{GA} Amount {GA}']  # Gain quantity
                break
            except: continue
        LQ = t[1][f'{LA} Amount {LA}'].removeprefix('-') # Loss quantity, or the only quantity. negative sign removed``

        # TRANSACTION HANDLING
        if SYMBOL == 'USD':                     continue # Ignore USD deposits/withdrawals
        elif spec == 'Gemini Pay':              trans = trans_from_raw(DATE, 'expense', wallet, loss=[LA,LQ,None]) #Gemini Pay Expense... MISSING PRICE DATA
        elif TYPE == 'Credit':                  trans = trans_from_raw(DATE, 'transfer_in', wallet, gain=[LA,LQ,None])
        elif TYPE == 'Debit':                   trans = trans_from_raw(DATE, 'transfer_out', wallet, loss=[LA,LQ,None])
        # Buys/sales using USD
        elif TYPE == 'Buy' and LA == 'USD':     trans = trans_from_raw(DATE, 'purchase', wallet, '', [None,LQ,None],[None,FQ,None],[GA,GQ,None])
        elif TYPE == 'Sell' and GA == 'USD':    trans = trans_from_raw(DATE, 'sale', wallet, '', [LA,LQ,None],[None,FQ,None],[None,GQ,None])
        # Buys/sales using crypto
        elif TYPE in ('Buy','Sell'):   #Trades.... we have NO price information! :( BIG sad. Nothing but the crypto-crypto conversion rate.
            trans = trans_from_raw(DATE, 'trade', wallet, '', [LA,LQ,None],[FA,FQ,None],[GA,GQ,None])
        else:
            Message(mainAppREF, 'IMPORT ERROR!', f'Couldn\'t import Gemini (Normal Gemini) history due to unimplemented transaction type, \'{TYPE}\'')
            return

        PORTFOLIO_TO_MERGE.import_transaction(trans)
            

    finalize_import(mainAppREF, PORTFOLIO_TO_MERGE)

# NOTE: needs to check this works still
def yoroi(mainAppREF, fileDir, wallet): #Imports Yoroi Wallet transaction history
    '''Reads the CSV file you downloaded from your Yoroi wallet, imports it into your portfolio'''
    data = pd.read_csv(fileDir, dtype='string')
    PORTFOLIO_TO_MERGE = Portfolio()

    for t in data.iterrows():
        # Crap, the date is downloaded in your ''local timezone'', so I have to add 4 hours to make it UTC/GMT time. 
        # Except my local timezone is actually GMT-5, not GMT-4, so, idk.
        date = timezone_to_unix(t[1].iloc[10], 'EST')

        #1111/11/11 20:11:11
        trans_type = t[1].iloc[0]
        gain_quantity = t[1].iloc[1]
        gain_ticker =    t[1].iloc[2]
        loss_quantity = t[1].iloc[3]
        loss_ticker =    t[1].iloc[4]
        fee_quantity =  t[1].iloc[5]
        fee_ticker =     t[1].iloc[6]
        comment =       t[1].iloc[9]

        # Only three type of transactions that I know of at this point: transfer_in, expense, and income
        # Unfortunately their report gives us NO price information at all! At least I can automatically get this from YahooFinance...

        if trans_type == 'Deposit' and not pd.isna(comment) and 'Staking Reward' in comment: #Staking reward
            trans = trans_from_raw(date, 'income', wallet, gain=[gain_ticker, gain_quantity, None])    #Missing price date
        elif trans_type == 'Deposit':   #Transfer of crypto into the wallet
            trans = trans_from_raw(date, 'transfer_in', wallet, gain=[gain_ticker, gain_quantity, None])
        elif trans_type == 'Withdrawal' and loss_quantity == '0.0':
            trans = trans_from_raw(date, 'expense', wallet, loss=[fee_ticker, fee_quantity, None])    #Missing price date
        
        else:
            Message(mainAppREF, 'IMPORT ERROR!', 'Failed to import unknown Yoroi wallet transaction type: ' + trans_type + '.')
            return
        
        PORTFOLIO_TO_MERGE.import_transaction(trans)
    
    finalize_import(mainAppREF, PORTFOLIO_TO_MERGE)