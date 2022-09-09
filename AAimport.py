
import pandas as pd
from io import StringIO
from datetime import datetime, tzinfo
from mpmath import mpf as precise
from AAobjects import *

from AAdialogues import Message



def finalize_import(mainAppREF, TO_MERGE):
    MAIN_PORTFOLIO.loadJSON(TO_MERGE.toJSON(), True, False)   # Imports new transactions, doesn't overwrite duplicates (to preserve custom descriptions, type changes, etc.)
    mainAppREF.metrics()
    mainAppREF.render(mainAppREF.asset, True)
    mainAppREF.undo_save()


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
    #I have to do this malarkey, since Coinbase's CSV file is missing delimiters, which messes up Pandas.
    #It cuts out the first 6 rows/lines from the CSV file, since they're just useless
    #But I don't want to modify the original file, so we use StringIO to pretend the string we create is a file and 'trick' pandas into parsing it.
    raw = open(fileDir, 'r').readlines()[7:]
    data = ''
    for line in raw: data += line + '\n'
    return pd.read_csv(StringIO(data), dtype='string') #We read the data all as strings to preserve accuracy

def loadEtherscanFile(fileDir):
    #Etherscan's CSV file is fucky and has an extra column for every transaction, but not an extra row. We have to fix that by adding in another column.
    raw = open(fileDir, 'r').readlines()
    data = ''
    if raw[0].count(',') < raw[1].count(','):   #We can tell how many columns of data there are by the number of delimiters. If too few columns, add more empty columns
        raw[0] = raw[0].replace('\n', '') + ',\"\"\n'
    for line in raw: data += line
    return pd.read_csv(StringIO(data), dtype='string') #We read the data all as strings to preserve accuracy



def import_etherscan(mainAppREF, ethFileDir, erc20FileDir, etherscanWallet=None):      #Imports the Etherscan transaction history for ETH only
    eth_data = loadEtherscanFile(ethFileDir)
    erc20_data = loadEtherscanFile(erc20FileDir)
    if isEtherscanERC20(eth_data):
        Message(mainAppREF, 'IMPORT ERROR!','The first CSV you chose is Etherscan ERC-20 history, not Etherscan ETH history.')
        return 
    if not isEtherscanERC20(erc20_data):
        Message(mainAppREF, 'IMPORT ERROR!','The second CSV you chose it Etherscan ETH history, not Etherscan ERC-20 history.')
        return 
    TO_MERGE = Portfolio()

    #1) parse ERC20s, if their txhash not in ETH, then they are a transfer_in of ERC20 tokens. 
    #2) parse ETH. If error, expense. If TO is this wallet, then transfer_in of ETH. If Swap, trade.
    #3) parse ETH, if their txhash not in ERC20s, then they are an independent expense
    #4) parse ERC20s, if FROM this wallet, then a transfer out with fee. If TO this wallet, then create both a transfer_in, and a transfer_out w/ fee & MISSINGWALLET

    eth_trans = {}
    erc20_trans = {}
    this_wallet_address = None
    
    TO_MERGE.add_asset(Asset('ETHzc','ETH'))

    for t in eth_data.iterrows():
        date = str(datetime.utcfromtimestamp(int(t[1][2]))).replace('-','/')   #Uses the UNIX timestamp, not the 'datetime' column
        # Indexed by txhash - Date, from, to, value_in, value_out, fee, price, error_code, method
        eth_trans[t[1][0]] = (date, t[1][4], t[1][5], t[1][7], t[1][8], t[1][10], t[1][12], t[1][14], t[1][15])
    for t in erc20_data.iterrows():
        date = str(datetime.utcfromtimestamp(int(t[1][1]))).replace('-','/')   #Uses the UNIX timestamp, not the 'datetime' column
        # Indexed by txhash - Date, from, to, value, ticker
        #NOTE: The 'value' has commas in it, like for '75,688.999011', gotta remove those
        erc20_trans[t[1][0]] = (date, t[1][3], t[1][4], t[1][5].replace(',',''), t[1][8]+'zc')
        if not TO_MERGE.hasAsset(t[1][8]+'zc'): TO_MERGE.add_asset(Asset(t[1][8]+'zc',t[1][8]))
    
    for t in list(erc20_trans): #Transfer_in of ERC-20 tokens, from an external wallet
        if t not in eth_trans:
            trans = erc20_trans.pop(t)
            this_wallet_address = trans[2]
            TO_MERGE.add_transaction(Transaction(trans[0], 'transfer_in', etherscanWallet, gain=[trans[4],trans[3],None]))
    for t in list(eth_trans):
        trans = eth_trans[t]
        if not pd.isna(trans[7]):      #There is an error - just an expense of the fee, then.
            eth_trans.pop(t)
            TO_MERGE.add_transaction(Transaction(trans[0], 'expense', etherscanWallet, loss=['ETHzc',trans[5],trans[6]]))
        elif trans[2] == this_wallet_address:  #If its TO this wallet, then it's a transfer_in of ETH. Possibly a gift_in, but that's up to the user to correct. No fees.
            eth_trans.pop(t)
            TO_MERGE.add_transaction(Transaction(trans[0], 'transfer_in', etherscanWallet, gain=['ETHzc',trans[3],None]))
        elif trans[8]=='Swap Exact ETH For Tokens': #A swap! A Trade! This is only for swapping ETH to something, not anything to anything.
            erc20 = erc20_trans.pop(t)
            eth_trans.pop(t)
            TO_MERGE.add_transaction(Transaction(trans[0], 'trade', etherscanWallet, '', ['ETHzc',trans[4],trans[6]],['ETHzc',trans[5],trans[6]],[erc20[4],erc20[3],None]))
    for t in list(eth_trans):       #Independent expenses, probably related to staking
        if t not in erc20_trans:
            trans = eth_trans.pop(t)
            TO_MERGE.add_transaction(Transaction(trans[0], 'expense', etherscanWallet, loss=['ETHzc',trans[5],trans[6]]))
    for t in list(erc20_trans):     #Transfers of ERC-20 tokens, probably for staking
        eth = eth_trans.pop(t)
        trans = erc20_trans.pop(t)
        if trans[1] == this_wallet_address:
            TO_MERGE.add_transaction(Transaction(trans[0], 'transfer_out', etherscanWallet, '', [trans[4],trans[3],None],['ETHzc',eth[5],eth[6]]))
            TO_MERGE.add_transaction(Transaction(trans[0], 'transfer_in', None, gain=[trans[4],trans[3],None]))
        else:
            TO_MERGE.add_transaction(Transaction(trans[0], 'transfer_in', etherscanWallet, gain=[trans[4],trans[3],None]))
            #Expense is just the fee for transfer_out, but the fee is applied to the ETH wallet, not the wallet we're transferring out of
            TO_MERGE.add_transaction(Transaction(trans[0], 'expense', etherscanWallet, loss=['ETHzc',eth[5],eth[6]]))
            TO_MERGE.add_transaction(Transaction(trans[0], 'transfer_out', None, loss=[trans[4],trans[3],None]))
    
    if len(eth_trans) > 0: print('||IMPORT ERROR|| '+str(len(eth_trans)+len(erc20_trans)) + ' ETH transactions failed to parse.')
    if len(erc20_trans) > 0: print('||IMPORT ERROR|| '+str(len(eth_trans)+len(erc20_trans)) + ' ERC-20 transactions failed to parse.')
        
    finalize_import(mainAppREF, TO_MERGE)
 

def import_coinbase_pro(mainAppREF, fileDir, coinbaseProWallet='Coinbase Pro'):    #Imports Coinbase Pro transaction history
    '''Reads the CSV file you downloaded from Coinbase Pro, spits out a dictionary in the same format as PERM, to be merged and overwrite the old PERM'''
    TO_MERGE = Portfolio()
    if not isCoinbasePro(fileDir):
        Message(mainAppREF, 'IMPORT ERROR!','This is Coinbase history, not Coinbase Pro history.')
        return
    data = pd.read_csv(fileDir, dtype='string')

    losses = {} #Coinbase Pro thinks like I do - you lose something, gain something, and have some fee. They report in triplets. Very nice.
    fees = {}
    gains = {}

    # BASIC TRANSACTIONS - Scans all the transactions, adds some of the basic ones like deposits/withdrawals
    for t in data.iterrows():
        ID = t[1][2] #The date but more specific
        date = t[1][2].replace('-','/').replace('T',' ')[0:19]
        type = t[1][1]
        asset = t[1][5]+'zc'
        quantity = t[1][3].removeprefix('-')
        isLoss = t[1][3][0]=='-' #True if the first character of the 

        if asset != 'USDzc' and not TO_MERGE.hasAsset(asset): TO_MERGE.add_asset(Asset(asset, asset[:-2]))

        # First, simple transactions are completed
        if asset == 'USDzc' and type in ['deposit','withdrawal']: continue
        elif type == 'deposit':    TO_MERGE.add_transaction(Transaction(date, 'transfer_in', coinbaseProWallet, gain=[asset,quantity,None]))
        elif type == 'withdrawal': TO_MERGE.add_transaction(Transaction(date, 'transfer_out', coinbaseProWallet, loss=[asset,quantity,None]))

        #Not simple. Ok, add it to the list of losses/fees/gains
        elif type == 'fee':     fees[ID] = [asset, quantity, None]
        elif type == 'match': 
            if isLoss:          losses[ID] = [asset, quantity, None]
            else:               gains[ID] = [asset, quantity, None]
        else:
            Message(mainAppREF, 'Import ERROR', 'Couldn\'t import Coinbase PRO history due to unknown transaction type \"'+type+'\".')
            return

    # COMPLEX TRANSACTIONS - Adds in the rest of the transactions that come in triplets
    for t in losses:
        date = t.replace('-','/').replace('T',' ')[0:19]
        L,F,G = losses[t],fees[t],gains[t]
        for a in [L,F,G]: 
            if a[0]=='USDzc': a[0]=None #Get rid of USD's
        
        if L[0] == None:    TO_MERGE.add_transaction(Transaction(date, 'purchase', coinbaseProWallet, '', L, F, G))
        else:               TO_MERGE.add_transaction(Transaction(date, 'sale', coinbaseProWallet, '', L, F, G))
        
    finalize_import(mainAppREF, TO_MERGE)

def import_coinbase(mainAppREF, fileDir, coinbaseWallet='Coinbase'):    #Imports Coinbase transaction history
    '''Reads the CSV file you downloaded from Coinbase (not PRO), spits out a dictionary in the same format as PERM, to be merged and overwrite the old PERM'''   
    if isCoinbasePro(fileDir):
        Message(mainAppREF, 'IMPORT ERROR!','This is Coinbase Pro history, not Coinbase history.')
        return 
    TO_MERGE = Portfolio()
    data = loadCoinbaseFile(fileDir)

    for t in data.iterrows():
        #INFORMATION GATHERING
        date = t[1][0].replace('-','/').replace('T',' ')[0:19] #The 'Z' on the end indicates that this it UTC, like Gemini
        trans_type = t[1][1]
        asset = t[1][2] + 'zc'
        if not TO_MERGE.hasAsset(asset): TO_MERGE.add_asset(Asset(asset, asset[:-2]))
        quantity = t[1][3]
        spot_price = t[1][5]
        subtotal = t[1][6]  #The profit before the fee
        fee = t[1][8]  #The fee (USD)
        desc = t[1][9]
        loss_asset, fee_asset, gain_asset = None, None, None
        if trans_type in ['Advanced Trade Buy','Advanced Trade Sell']: #Getting the second asset of the market pair for trades
            market_pair = desc.split(' ').pop().split('-')
            fee_asset = market_pair[1]+'zc' #Fee asset, like in Gemini, is always the second asset in the market pair
            if fee_asset != 'USDzc' and not TO_MERGE.hasAsset(fee_asset): TO_MERGE.add_asset(Asset(fee_asset, fee_asset[:-2]))
            if trans_type == 'Advanced Trade Buy':
                gain_asset = t[1][2]
                if market_pair[0] == gain_asset:    loss_asset = market_pair[1]
                else:                               loss_asset = market_pair[0]
            else:
                loss_asset = t[1][2]
                if market_pair[0] == loss_asset:    gain_asset = market_pair[1]
                else:                               gain_asset = market_pair[0]
            loss_asset += 'zc'
            gain_asset += 'zc'

        if trans_type == 'Buy' or loss_asset == 'USDzc': # Buy and "advanced trade buy" with a -USD market pair
            trans = Transaction(date, 'purchase', coinbaseWallet, desc, [None,subtotal,None],[None,fee,None],[asset,quantity,None])
        elif trans_type == 'Sell' or gain_asset == 'USDzc': # Sell and "advanced trade sell" with a -USD market pair
            trans = Transaction(date, 'sale', coinbaseWallet, desc, [asset,quantity,None],[None,fee,None],[None,subtotal,None])
        elif trans_type == 'Receive' and desc[-13:] == 'Coinbase Card':     #Card reward is card reward
            trans = Transaction(date, 'card_reward', coinbaseWallet, desc, gain=[asset,quantity,spot_price])
        elif trans_type == 'Receive':
            trans = Transaction(date, 'transfer_in', coinbaseWallet, desc, gain=[asset,quantity,None])
        elif trans_type in ['Coinbase Earn', 'Rewards Income'] or trans_type == 'Receive':   #Coinbase Learn & Earn treated as income by the IRS, according to Coinbase
            trans = Transaction(date, 'income', coinbaseWallet, desc, gain=[asset,quantity,spot_price])
        elif trans_type == 'Advanced Trade Buy': #Trades.... even worse than Gemini! Missing quantity recieved data.
            trans = Transaction(date, 'trade', coinbaseWallet, desc, [loss_asset,None,None],[fee_asset,None,None],[gain_asset,quantity,None])
        elif trans_type == 'Advanced Trade Sell':
            trans = Transaction(date, 'trade', coinbaseWallet, desc, [loss_asset,quantity,spot_price],[fee_asset,None,None],[gain_asset,None,None])

        else:
            Message(mainAppREF, 'Import ERROR', 'Couldn\'t import Coinbase history due to unimplemented transaction type, \'' + trans_type + '\'')
            return

        TO_MERGE.add_transaction(trans)

    finalize_import(mainAppREF, TO_MERGE)
                

def import_gemini_earn(mainAppREF, fileDir, geminiEarnWallet='Gemini Earn'):   #Imports Gemini Earn transaction history
    '''Reads the XLSX file you downloaded from Gemini or Gemini Earn, spits out a dictionary in the same format as PERM, to be merged and overwrite the old PERM'''
    data = pd.read_excel(fileDir, dtype='string', keep_default_na=False)
    if not isGeminiEarn(data):
        Message(mainAppREF, 'IMPORT ERROR!','This is Gemini history, not Gemini Earn history.')
        return
    TO_MERGE = Portfolio()

    priceUSDcolumnIDs = {}      # Every column for token prices are just called "price USD", this helps us get a ticker-based reference to them
    previous_column = ''
    for column in data.items():     
        #Knowing that the previous column has this one's asset ticker in its name, we make a reference for that ticker to this column
        if 'Price USD' in column[0]:   priceUSDcolumnIDs[previous_column[7:] + 'zc'] = column[0]
        previous_column = column[0]

    for t in data.iterrows():
        #We ignore missing data (the last row), and the Monthly Interest Summaries
        if t[1][3] == '' or t[1][2] == 'Monthly Interest Summary':      continue
        
        # INFORMATION GATHERING
        date = str(t[1][0]).replace('-','/')[0:19]
        trans_type = t[1][2]
        asset = t[1][3] + 'zc'
        asset_ticker = t[1][3]
        quantity = data['Amount ' + asset_ticker][t[0]].removeprefix('-') #Removes negative from redemptions
        price = data[ priceUSDcolumnIDs[asset] ][t[0]]

        #If this asset is not in TO_MERGE already, add it!
        if not TO_MERGE.hasAsset(asset):     TO_MERGE.add_asset(Asset(asset, asset_ticker))

        # TRANSACTION HANDLING - Handles the three different transaction types within Gemini Earn Reports: Deposit, Redeem, Interest Credit
        if trans_type == 'Deposit':             TO_MERGE.add_transaction(Transaction(date, 'transfer_in', geminiEarnWallet, '', gain=[asset, quantity, None]))
        elif trans_type == 'Redeem':            TO_MERGE.add_transaction(Transaction(date, 'transfer_out', geminiEarnWallet, '', loss=[asset, quantity, None]))
        elif trans_type == 'Interest Credit':   TO_MERGE.add_transaction(Transaction(date, 'income', geminiEarnWallet, '', gain=[asset, quantity, price]))
        
        else:
            Message(mainAppREF, 'Import ERROR', 'Couldn\'t import Gemini (Earn) history due to unimplemented transaction type, \'' + trans_type + '\'')
            return

    finalize_import(mainAppREF, TO_MERGE)

def import_gemini(mainAppREF, fileDir, geminiWallet='Gemini'):   #Imports Gemini transaction history
    '''Reads the XLSX file you downloaded from Gemini or Gemini Earn, spits out a dictionary in the same format as PERM, to be merged and overwrite the old PERM'''
    data = pd.read_excel(fileDir, dtype='string', keep_default_na=False)
    if isGeminiEarn(data):
        Message(mainAppREF, 'IMPORT ERROR!','This is Gemini Earn history, not Gemini history.')
        return
    TO_MERGE = Portfolio()

    for t in data.iterrows():
        #We ignore anything that's just USD, and we ignore an empty cell as a way of ignoring the final row in the dataset, which are just totals
        if t[1][3] in ('USD', ''):  continue

        #INFORMATION GATHERING
        date = str(t[1][0]).replace('-','/')[0:19]
        trans_type = t[1][2]
        spec = t[1][4] #The 'specification' of the transaction. 'Earn Redemption', 'Gemini Pay', etc.
        desc = trans_type+' - '+spec
        LA = t[1][3]    #Loss asset
        FA = ''         #Fee asset
        GA = ''         #Gain asset
        for i in range(3,len(LA)-2): #t[1][3] is the asset debted/credited, or for sales/buys, its the market pair, like USDGUSD. Here, we split that between asset_1 and asset_2
            try:
                a1,a2 = LA[:i],LA[i:]
                FA = a2 #Second of the two is always the fee asset
                FQ = data['Fee (' + a2 + ') ' + a2][t[0]].removeprefix('-') #Fee quantity. [1:] removes the - sign
                if data[a1 + ' Amount ' + a1][t[0]][0] == '-':      LA,GA = a1,a2    #If the first character is -, then a1 is the loss asset, otherwise its the other way around
                elif data[a2 + ' Amount ' + a2][t[0]][0] == '-':    LA,GA = a2,a1
                GQ = data[GA + ' Amount ' + GA][t[0]]  # Gain quantity
                break
            except: continue
        LQ = data[LA + ' Amount ' + LA][t[0]].removeprefix('-') # Loss quantity, or the only quantity. negative sign removed
        LA += 'zc'
        if FA != '': FA += 'zc'
        if GA != '': GA += 'zc'
        
        # Adds assets 1 and 2 if they don't exist in the portfolio
        if LA != 'USDzc'           and not TO_MERGE.hasAsset(LA): TO_MERGE.add_asset(Asset(LA,LA[:-2]))
        if GA not in ['USDzc', ''] and not TO_MERGE.hasAsset(GA): TO_MERGE.add_asset(Asset(GA,GA[:-2]))

        # TRANSACTION HANDLING
        if spec == 'Gemini Pay':        trans = Transaction(date, 'expense', geminiWallet, desc, loss=[LA,LQ,None]) #Gemini Pay Expense... MISSING PRICE DATA
        elif trans_type == 'Credit':    trans = Transaction(date, 'transfer_in', geminiWallet, desc, gain=[LA,LQ,None])
        elif trans_type == 'Debit':     trans = Transaction(date, 'transfer_out', geminiWallet, desc, loss=[LA,LQ,None])
        elif LA == 'USDzc':             trans = Transaction(date, 'purchase', geminiWallet, desc, [None,LQ,None],[None,FQ,None],[GA,GQ,None])
        elif GA == 'USDzc':             trans = Transaction(date, 'sale', geminiWallet, desc, [LA,LQ,None],[None,FQ,None],[None,GQ,None])
        elif trans_type in ['Buy','Sell']:   #Trades.... we have NO price information! :( BIG sad. Nothing but the crypto-crypto conversion rate.
            trans = Transaction(date, 'trade', geminiWallet, desc, [LA,LQ,None],[FA,FQ,None],[GA,GQ,None])
            trans.ERROR = True #
        else:
            Message(mainAppREF, 'Import ERROR', 'Couldn\'t import Gemini (Normal Gemini) history due to unimplemented transaction type, \'' + trans_type + '\'')
            return

        TO_MERGE.add_transaction(trans)
            

    finalize_import(mainAppREF, TO_MERGE)

