from json.tool import main
from numpy import NAN, NaN, nan
import pandas as pd
from io import StringIO
from datetime import datetime, tzinfo
from mpmath import mpf as precise
from mpmath import mp
from AAlib import PERM

from AAmessageBox import MessageBox

def address_list(): #Creates and returns a list of all wallet addresses, and their associated wallet
    addresses = {}
    for wallet in PERM['wallets']:
        for address in PERM['wallets'][wallet]['addresses']:
            addresses[address] = wallet
    return addresses

def finalize_import(mainAppREF, toMerge):
    mainAppREF.init_PERM(toMerge, True)
    mainAppREF.metrics()
    mainAppREF.render(None, True)
    mainAppREF.create_PROFILE_MENU()
    mainAppREF.undo_save()

def import_gemini(mainAppREF, fileDir, geminiWallet='Gemini', geminiEarnWallet='Gemini Earn'):
    data = pd.read_excel(fileDir, dtype='string', keep_default_na=False)
    #Checks whether this is a Gemini Earn or Gemini XLSX file
    if 'APY' in data.columns:   gemini_earn(mainAppREF, data, geminiWallet=geminiWallet, geminiEarnWallet=geminiEarnWallet)
    else:                       gemini(mainAppREF, data, geminiWallet=geminiWallet, geminiEarnWallet=geminiEarnWallet)

def import_coinbase(mainAppREF, fileDir, coinbaseWallet='Coinbase', coinbaseProWallet='Coinbase Pro'):
    #Checks whether this is a Coinbase Pro or Coinbase CSV file
    if open(fileDir, 'r').readlines()[0][0:9] == 'portfolio':   coinbase_pro(mainAppREF, fileDir, coinbaseProWallet)
    else:                                                       coinbase(mainAppREF, fileDir, coinbaseWallet)

def import_etherscan(mainAppREF, fileDir, etherscanWallet='Metamask'):
    #Etherscan's CSV file is fucky and has an extra column for every transaction, but not an extra row. We have to fix that by adding in another column.
    raw = open(fileDir, 'r').readlines()
    data = ''
    if raw[0].count(',') < raw[1].count(','):   #We can tell how many columns of data there are by the number of delimiters. If too few columns, add more empty columns
        raw[0] = raw[0].replace('\n', '') + ',\"\"\n'
    for line in raw: data += line
    open('C:/Users/evans/Desktop/Auto-Accountant/transaction histories/#boop.CSV', 'w').write(data)
    data = pd.read_csv(StringIO(data), dtype='string') #We read the data all as strings to preserve accuracy
    if 'TokenSymbol' in data:   etherscan_ERC20(mainAppREF, data, etherscanWallet)
    else:                       etherscan_ETH(mainAppREF, data, etherscanWallet)


def etherscan_findWallet(data, etherscanWallet):    #Figures out the wallet address of a given etherscan wallet from its transaction history
    #First, we have to figure out which wallet is this particular wallet of interest
    walletAddress = None
    wallet1, wallet2 = data['From'][0], data['To'][0]
    for t in data.iterrows():
        #The wallet address for this etherscan history is found in every transaction. 
        if wallet1 not in [t[1][4], t[1][5]]:   
            walletAddress = wallet2
            break
        if wallet2 not in [t[1][4], t[1][5]]:   
            walletAddress = wallet1
            break
    #If we can't find this address, then either add it under the specified wallet, or create a new wallet with this specified address
    if walletAddress not in address_list():
        if etherscanWallet == None:     
            PERM['wallets']['Unknown Etherum Wallet'] = {'addresses':[walletAddress], 'desc':''}
            return ('Unknown Etherum Wallet', walletAddress)
        else:                           
            PERM['wallets'][etherscanWallet]['addresses'].append(walletAddress)
            return (etherscanWallet, walletAddress)
    else:
        return (address_list()[walletAddress], walletAddress)

def etherscan_ETH(mainAppREF, data, etherscanWallet=None):      #Imports the Etherscan transaction history for ETH only
    walletdata = etherscan_findWallet(data, etherscanWallet)
    etherscanWallet, walletAddress = walletdata[0], walletdata[1]

    toMerge = { 'assets' : { 'ETHzc': {'desc':'', 'name':'ETH', 'trans':{}} }, 'wallets':{}, 'profiles' : {} }

    for t in data.iterrows():
        date = str(datetime.utcfromtimestamp(int(t[1][2]))).replace('-','/')   #Uses the UNIX timestamp, not the 'datetime' column
        wallet = t[1][4]
        wallet2 = t[1][5]
        valueIN = t[1][7]
        valueOUT = t[1][8]
        fee = t[1][10]
        price = t[1][12]
        error = t[1][14]  
        transType = t[1][15]

        if 'ETHzc' in PERM['assets'] and date in PERM['assets']['ETHzc']:   #If this transaction is already in our data, don't add it again, it may be the transfer from Gemini/Coinbase into Metamask.
            print('Transaction ' + date + ' was already found in the ETH ledger.')
            continue

        trans = {'desc':transType,}

        if not pd.isna(error) or transType in ['Approve', 'Deposit', 'Request Release', 'Transfer By Partition']:  #If there was an error, we only record the fee as an expense
            trans['type'] = 'expense'
            trans['tokens'] = fee
            trans['price'] = price
        elif transType == 'Swap Exact ETH For Tokens':  #If it was a successful swap, we lump the fee and amount sold together as one.
            trans['type'] = 'sale'
            trans['tokens'] = str(precise(valueOUT) + precise(fee))
            trans['usd'] = str(precise(trans['tokens']) * precise(price))
        elif transType == 'Transfer':
            trans['type'] = 'transfer'
            if t[1][4] == walletAddress:  #If we are transferring OUT of this ethereum wallet:
                MessageBox(mainAppREF, 'Import ERROR', 'Couldn\'t import Etherscan ETH history, since I have not implemented the transfer of assets out of the Metamask wallet. This is since there is an associated fee with transfers, which occurs at the exact same time. ')
                return
            else:   trans['tokens'] = valueIN   #If we are transferring INTO this ethereum wallet:
        else:
            MessageBox(mainAppREF, 'Import ERROR', 'Couldn\'t import Etherscan ETH history due to unknown transaction type' + transType + '.')
            return
        
        addresses = address_list()
        if wallet in addresses:     trans['wallet'] = addresses[wallet]
        else:                       trans['wallet'] = ' MISSINGWALLET'
        if trans['type'] == 'transfer':
            if wallet2 in addresses:    trans['wallet2'] = addresses[wallet2]
            else:                       trans['wallet2'] = ' MISSINGWALLET'

        toMerge['assets']['ETHzc']['trans'][date] = trans
        
    finalize_import(mainAppREF, toMerge)

def etherscan_ERC20(mainAppREF, data, etherscanWallet='Unknown Ethereum Wallet'):      #Imports the Etherscan transaction history for all other ERC-20 tokens
    walletdata = etherscan_findWallet(data, etherscanWallet)
    etherscanWallet, walletAddress = walletdata[0], walletdata[1]

    toMerge = { 'assets' : {}, 'wallets':{}, 'profiles' : {} }

    for t in data.iterrows():
        date = str(datetime.utcfromtimestamp(int(t[1][1]))).replace('-','/')   #Uses the UNIX timestamp, not the 'datetime' column
        asset = t[1][8] + 'zc'
        wallet = t[1][3]
        wallet2 = t[1][4]
        tokens = t[1][5].replace(',','')
        if asset not in toMerge['assets']:
            toMerge['assets'][asset] = {'desc':'', 'name':asset[:-2], 'trans':{}}
        
        if 'ETHzc' not in PERM['assets'] or date not in PERM['assets']['ETHzc']['trans']:
            MessageBox(mainAppREF, 'Import ERROR', 'Couldn\'t import Etherscan ERC20 transaction history, because Etherscan ETH transaction history was not imported first (or was tampered with).')
            return

        trans = {'desc':'', 'tokens':tokens}

        if date in PERM['assets']['ETHzc']['trans'] and PERM['assets']['ETHzc']['trans'][date]['type'] == 'sale':    #If the corresponding ETH transaction was a sale, then this was a swap!
            trans['desc'] = 'Swap from ETH to ' + asset[:-2]
            trans['type'] = 'purchase'
            trans['usd'] = PERM['assets']['ETHzc']['trans'][date]['usd']   #The USD for this purchase is the sale value of the ETH, including its fee
        else:
            trans['type'] = 'transfer'

        addresses = address_list()
        if wallet in addresses:     trans['wallet'] = addresses[wallet]
        else:                       trans['wallet'] = ' MISSINGWALLET'
        if trans['type'] == 'transfer':
            if wallet2 in addresses:    trans['wallet2'] = addresses[wallet2]
            else:                       trans['wallet2'] = ' MISSINGWALLET'

        toMerge['assets'][asset]['trans'][date] = trans

    finalize_import(mainAppREF, toMerge)


def coinbase_pro(mainAppREF, fileDir, coinbaseProWallet='Coinbase Pro'):    #Imports Coinbase Pro transaction history
    '''Reads the CSV file you downloaded from Coinbase Pro, spits out a dictionary in the same format as PERM, to be merged and overwrite the old PERM'''
    toMerge = { 'assets' : {}, 'wallets' : {coinbaseProWallet:{'addresses':[],'desc':''}}, 'profiles' : {} }
    data = pd.read_csv(fileDir, dtype='string')

    transactions = {}
    assets = set()

    #Coinbase PRO transaction data comes in triplets for buys/sells:
    #One is the USD gained/lost, one is the USD gained/lost from fees, and one is the ASSET gained/lost
    #Withdrawals and deposits are only a single line

    for t in data.iterrows():
        type = t[1][1]
        date = t[1][2].replace('-','/').replace('T',' ')[0:19]

        if type == 'deposit' and t[1][5] != 'USD': #Coinbase Pro's CSV doesn't give us enough info to infer where we may have withdrawn our assets to. So, we ignore this. 
            MessageBox(mainAppREF, 'Import ERROR', 'Couldn\'t import Coinbase PRO history, since non-USD deposits haven\'t been implemented yet.')
            return
        elif (type == 'deposit' and t[1][5] == 'USD') or (type == 'withdrawal' and t[1][5] == 'USD'): #We don't care about USD going in/out!
            continue

        elif type == 'withdrawal':
            #We automatically generate these transfer transactions, but the user has to manually fix what the destination wallet is
            #Coinbase Pro transaction history provides absolutely no information on the withdrawal destination.
            transactions[date] = {
                    'desc': '',
                    'tokens': str(-precise(t[1][3])),
                    'type': 'transfer',
                    'wallet': 'Coinbase Pro',
                    'wallet2': ' MISSINGWALLET',
                    'TEMP_TICKER': t[1][5] + 'zc'
                }
            assets.add(t[1][5] + 'zc')
        elif type == 'match' or type == 'fee':  #A match is a purchase or sale, the fee is... the fee
            if date not in transactions:
                transactions[date] = {
                'desc': '',
                'wallet': coinbaseProWallet,
                'tokens':'0',
                'usd':'0',
                'TEMP_TICKER': ''
                }
            #Set the USD and tokens, depending on if its a sale or purchase
            if t[1][5] == 'USD':
                if precise(t[1][3]) > 0:
                    MessageBox(mainAppREF, 'Import ERROR', 'Couldn\'t import Coinbase PRO history, since I don\'t know how CB PRO records sales in its history yet.')
                    return
                transactions[date]['usd'] = str( precise(transactions[date]['usd']) - precise(t[1][3]) )
            else:
                transactions[date]['TEMP_TICKER'] = t[1][5] + 'zc'
                assets.add(t[1][5] + 'zc')
                transactions[date]['tokens'] = str( precise(transactions[date]['tokens']) + precise(t[1][3]) )
            #Set the type
            if precise(transactions[date]['tokens']) > 0:    transactions[date]['type'] = 'purchase'
            else:                                   transactions[date]['type'] = 'sale'
        else:
            MessageBox(mainAppREF, 'Import ERROR', 'Couldn\'t import Coinbase PRO history due to unimplemented transaction type, \'' + type + '\'')
            return
        


    #Adds in all the assets to the toMerge dictionary
    for asset in assets:
        if asset not in toMerge['assets']:
            toMerge['assets'][asset] = {'desc':'', 'name':asset[:-2], 'trans':{}}
    #Adds in all the new transactions to those assets
    for trans in transactions.keys():
        asset = transactions[trans].pop('TEMP_TICKER') #Remove the temporary asset ticker ID
        toMerge['assets'][asset]['trans'][trans] = transactions[trans]  #Add it to the toMerge dictionary
    
    finalize_import(mainAppREF, toMerge)

def coinbase(mainAppREF, fileDir, coinbaseWallet='Coinbase'):    #Imports Coinbase transaction history
    '''Reads the CSV file you downloaded from Coinbase (not PRO), spits out a dictionary in the same format as PERM, to be merged and overwrite the old PERM'''    
    toMerge = { 'assets' : {}, 'wallets' : {coinbaseWallet:{'addresses':[],'desc':''}}, 'profiles' : {} }

    #I have to do this malarkey, since Coinbase's CSV file is missing delimiters, which messes up Pandas.
    #It cuts out the first 6 rows/lines from the CSV file, since they're just useless
    #But I don't want to modify the original file, so we use StringIO to pretend the string we create is a file and 'trick' pandas into parsing it.
    raw = open(fileDir, 'r').readlines()[7:]
    data = ''
    for line in raw: data += line + '\n'
    data = pd.read_csv(StringIO(data), dtype='string') #We read the data all as strings to preserve accuracy

    for t in data.iterrows():
        asset = t[1][2] + 'zc'
        if asset not in toMerge['assets']:
            toMerge['assets'][asset] = {'desc':'', 'name':asset[:-2], 'trans':{}}

        date = t[1][0].replace('-','/').replace('T',' ')[0:19]
        type = t[1][1]
        tokens = t[1][3]
        price = t[1][5]
        usd = t[1][7] #NOTE: This is the total, INCLUDING fees

        trans = {
            'desc': '',
            'wallet': coinbaseWallet,
            'tokens':tokens
        }

        if type in ('Buy', 'Sell', 'Coinbase Earn', 'Rewards Income'):
            if type in ['Coinbase Earn', 'Rewards Income']:
                trans['type'] = 'gift'
                trans['price'] = price
            elif type == 'Buy':
                trans['type'] = 'purchase'
                trans['usd'] = usd
            elif type == 'Sell':
                trans['type'] = 'sale'
                trans['usd'] = usd

            toMerge['assets'][asset]['trans'][date] = trans
        else:
            MessageBox(mainAppREF, 'Import ERROR', 'Couldn\'t import Coinbase history due to unimplemented transaction type, \'' + type + '\'')
            return

    finalize_import(mainAppREF, toMerge)
                

def gemini_earn(mainAppREF, data, geminiWallet='Gemini', geminiEarnWallet='Gemini Earn'):   #Imports Gemini Earn transaction history
    '''Reads the XLSX file you downloaded from Gemini or Gemini Earn, spits out a dictionary in the same format as PERM, to be merged and overwrite the old PERM'''
    toMerge = { 'assets' : {}, 'wallets' : {geminiWallet:{'addresses':[],'desc':''}, geminiEarnWallet:{'addresses':[],'desc':''}}, 'profiles' : {} }

    priceUSDcolumnIDs = {}
    lastcol = ''
    for column in data.items():
        if 'Price USD' in column[0]:   priceUSDcolumnIDs[lastcol.replace('Amount ', '') + 'zc'] = column[0]
        lastcol = column[0]

    for t in data.iterrows():
        #We ignore missing data (the last row), and the Monthly Interest Summaries
        if t[1][3] == '' or t[1][2] == 'Monthly Interest Summary':
            continue
        
        #Need to know the date/time to give our transaction a unique ID!
        date = str(t[1][0]).replace('-','/')[0:19]

        #Retrieves the transaction type, and the asset that we're working with
        trans_type = t[1][2]
        asset = t[1][3] + 'zc'
        #If this asset is not in toMerge already, add it!
        if asset not in toMerge['assets']:
            toMerge['assets'][asset] = {'desc':'', 'name':asset[:-2], 'trans':{}}

        #Handles the three different transaction types within Gemini Earn Reports: Deposit, Redeem, Interest Credit
        if trans_type == 'Deposit': #Crypto funds moved into Gemini Earn from Gemini Wallet
            toMerge['assets'][asset]['trans'][date] = {
            'desc' : '',
            'type' : 'transfer',
            'wallet' : geminiWallet,
            'wallet2' : geminiEarnWallet,
            'tokens' : data['Amount ' + asset[:-2]][t[0]],
            }
        elif trans_type == 'Redeem': #Crypto funds moved out of Gemini Earn back to Gemini
            toMerge['assets'][asset]['trans'][date] = {
            'desc' : '',
            'type' : 'transfer',
            'wallet' : geminiEarnWallet,
            'wallet2' : geminiWallet,
            'tokens' : data['Amount ' + asset[:-2]][t[0]].replace('-',''), #we have to remove the negative sign since we always store tokens as positive
            }
        elif trans_type == 'Interest Credit': #This is only possible within Gemini Earn
            toMerge['assets'][asset]['trans'][date] = {
                'desc': '',
                'tokens': data['Amount ' + asset[:-2]][t[0]],
                'type': 'gift',
                'wallet': geminiEarnWallet,
                'tokens' : data['Amount ' + asset[:-2]][t[0]],
                'price': data[ priceUSDcolumnIDs[asset] ][t[0]],
            }



        else:
            MessageBox(mainAppREF, 'Import ERROR', 'Couldn\'t import Gemini (Earn) history due to unimplemented transaction type, \'' + trans_type + '\'')
            return

    finalize_import(mainAppREF, toMerge)

def gemini(mainAppREF, data, geminiWallet='Gemini', geminiEarnWallet='Gemini Earn'):   #Imports Gemini transaction history
    '''Reads the XLSX file you downloaded from Gemini or Gemini Earn, spits out a dictionary in the same format as PERM, to be merged and overwrite the old PERM'''
    toMerge = { 'assets' : {}, 'wallets' : {geminiWallet:{'addresses':[],'desc':''}, geminiEarnWallet:{'addresses':[],'desc':''}}, 'profiles' : {} }

    for t in data.iterrows():
        #We ignore anything that's just USD, and we ignore an empty cell as a way of ignoring the final row in the dataset, which are just totals
        if t[1][3] in ('USD', ''):
            continue

        #Need to know the date/time to give our transaction a unique ID!
        date = str(t[1][0]).replace('-','/')[0:19]

        #Retrieves the transaction type, and the asset that we're working with
        type = t[1][2]
        asset = t[1][3]
        if type in ['Buy','Sell']:
            if asset[-3:] != 'USD': #If the last three characters are 'USD'
                MessageBox(mainAppREF, 'Import ERROR', 'Couldn\'t import Gemini history due to pure crypto market pairs being unimplemented. Market pair ' + type + ' is unsupported.')
                return
            else: asset = asset[:-3] + 'zc'     #Removes the 'USD' from the market pair
        else: asset += 'zc'     #If its 'credit' or 'debit', there is no pair, no need to remove the 'USD'
        #If this asset is not in toMerge already, add it!
        if asset not in toMerge['assets']:
            toMerge['assets'][asset] = {'desc':'', 'name':asset[:-2], 'trans':{}}

        #Handles the five different transaction types within Gemini
        if type == 'Credit': #Crypto funds moved into Gemini
            toMerge['assets'][asset]['trans'][date] = {
            'desc' : t[1][4],
            'type' : 'transfer',
            'wallet' : ' MISSINGWALLET',
            'wallet2' : geminiWallet,
            'tokens' : data[asset[:-2] + ' Amount ' + asset[:-2]][t[0]],
            }
            if t[1][4] == 'Earn Redemption':
                toMerge['assets'][asset]['trans'][date]['wallet'] = geminiEarnWallet
        elif type == 'Debit': #Crypto funds moved out of Gemini
            toMerge['assets'][asset]['trans'][date] = {
            'desc' : t[1][4],
            'type' : 'transfer',
            'wallet' : geminiWallet,
            'wallet2' : ' MISSINGWALLET',
            'tokens' : (data[asset[:-2] + ' Amount ' + asset[:-2]][t[0]]).replace('-',''),
            }
            #If this transaction is deignated as a earn transfer, its obviously going to Gemini Earn.
            if t[1][4] == 'Earn Transfer':
                toMerge['assets'][asset]['trans'][date]['wallet2'] = geminiEarnWallet
            #If we recognize the address of the withdrawal destination, we know what wallet it was.
            elif data['Withdrawal Destination'][t[0]] in address_list():
                toMerge['assets'][asset]['trans'][date]['wallet2'] = address_list()[data['Withdrawal Destination'][t[0]]]
        elif type == 'Buy':
            toMerge['assets'][asset]['trans'][date] = {
            'desc' : t[1][4],
            'type' : 'purchase',
            'wallet' : geminiWallet,
            'tokens' : data[asset[:-2] + ' Amount ' + asset[:-2]][t[0]],
            'usd' : str(-precise(data['USD Amount USD'][t[0]]) - precise(data['Fee (USD) USD'][t[0]])),
            }
        elif type == 'Sell':
            toMerge['assets'][asset]['trans'][date] = {
            'desc' : t[1][4],
            'type' : 'sale',
            'wallet' : geminiWallet,
            'tokens' : (data[asset[:-2] + ' Amount ' + asset[:-2]][t[0]]).replace('-',''),
            'usd' : str(precise(data['USD Amount USD'][t[0]]) + precise(data['Fee (USD) USD'][t[0]])),
            }
        else:
            MessageBox(mainAppREF, 'Import ERROR', 'Couldn\'t import Gemini (Normal Gemini) history due to unimplemented transaction type, \'' + type + '\'')
            return

    finalize_import(mainAppREF, toMerge)

