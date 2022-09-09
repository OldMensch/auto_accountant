from numpy import NAN, NaN, nan
import pandas as pd
from io import StringIO
from datetime import datetime

from AAmessageBox import MessageBox
    
def import_coinbase_pro(mainAppREF, fileDir, walletName="Coinbase Pro"):
    """Reads the CSV file you downloaded from Coinbase Pro, spits out a dictionary in the same format as PERM, to be merged and overwrite the old PERM"""
    toMerge = { "assets" : {}, "wallets" : {walletName:""}, "profiles" : {} }
    ######################################
    #This is a COINBASE PRO CSV file!
    ######################################
    data = pd.read_csv(fileDir)

    transactions = {}
    assets = set()

    #Coinbase PRO transaction data comes in triplets for buys/sells:
    #One is the USD gained/lost, one is the USD gained/lost from fees, and one is the ASSET gained/lost
    #Withdrawals and deposits are only a single line

    for t in data.iterrows():
        type = t[1][1]
        date = t[1][2].replace("-","/").replace("T"," ")[0:19]

        if type == "deposit": #Coinbase Pro's CSV doesn't give us enough info to infer where we may have withdrawn our assets to. So, we ignore this. 
            if t[1][5] != "USD":
                MessageBox(mainAppREF, "Import ERROR", "Couldn't import Coinbase PRO history, since non-USD deposits haven't been implemented yet.")
                return
            continue
        elif type == "withdrawal":
            #We atomatically generate these transfer transactions, but the user has to manually fix what the destination wallet is, since we have no way of knowing where the tokens went
            transactions[date] = {
                    "desc": "",
                    "tokens": -t[1][3],
                    "type": "transfer",
                    "wallet": "Coinbase Pro",
                    "wallet2": " MISSINGWALLET",
                    "TEMP_TICKER": t[1][5] + "zc"
                }
            assets.add(t[1][5] + "zc")
            print(t[1][5] + "zc")
        elif type == "match" or type == "fee":  #A match is a purchase or sale, the fee is... the fee
            if date not in transactions:
                transactions[date] = {
                "desc": "",
                "wallet": walletName,
                "tokens":0,
                "usd":0,
                "TEMP_TICKER": ""
                }
            #Set the USD and tokens, depending on if its a sale or purchase
            if t[1][5] == "USD":
                if t[1][3] > 0:
                    MessageBox(mainAppREF, "Import ERROR", "Couldn't import Coinbase PRO history, since I don't know how CB PRO records sales in its history yet.")
                    return
                transactions[date]["usd"] -= t[1][3]
            else:
                transactions[date]["TEMP_TICKER"] = t[1][5] + "zc"
                assets.add(t[1][5] + "zc")
                transactions[date]["tokens"] += t[1][3]
            #Set the type
            if transactions[date]["tokens"] > 0:
                transactions[date]["type"] = "purchase"
            else:
                transactions[date]["type"] = "sale"
        else:
            MessageBox(mainAppREF, "Import ERROR", "Couldn't import Coinbase PRO history due to unimplemented transaction type, \'" + type + "\'")
            return
        


    #Adds in all the assets to the toMerge dictionary
    for asset in assets:
        if asset not in toMerge["assets"]:
            toMerge["assets"][asset] = {"desc":"", "name":asset[:-2], "trans":{}}
    #Adds in all the new transactions to those assets
    for trans in transactions.keys():
        asset = transactions[trans].pop("TEMP_TICKER") #Remove the temporary asset ticker ID
        if asset == "USDzc":
            print(transactions[trans], asset, trans)
        toMerge["assets"][asset]["trans"][trans] = transactions[trans]  #Add it to the toMerge dictionary
    mainAppREF.init_PERM(toMerge, True)
    mainAppREF.create_PORTFOLIO_WIDGETS()
    mainAppREF.create_metrics()
    mainAppREF.create_PROFILE_MENU()
    mainAppREF.undo_save()

def import_coinbase(mainAppREF, fileDir, walletName="Coinbase"):
    """Reads the CSV file you downloaded from Coinbase (not PRO), spits out a dictionary in the same format as PERM, to be merged and overwrite the old PERM"""    
    toMerge = { "assets" : {}, "wallets" : {walletName:""}, "profiles" : {} }
    ######################################
    #This is a NORMAL COINBASE CSV file!
    ######################################

    #I have to do this malarkey, since Coinbase's CSV file is missing delimiters, which messes up Pandas.
    #It cuts out the first 6 rows/lines from the CSV file, since they're just useless
    #But I don't want to modify the original file, so we use StringIO to pretend the string we create is a file and "trick" pandas into parsing it.
    raw = open(fileDir, "r").readlines()[7:]
    data = ""
    for line in raw:
        data += line + "\n"
    data = pd.read_csv(StringIO(data))

    for t in data.iterrows():
        asset = t[1][2] + "zc"
        if asset not in toMerge["assets"]:
            toMerge["assets"][asset] = {"desc":"", "name":asset[:-2], "trans":{}}

        type = t[1][1]
        date = t[1][0].replace("-","/").replace("T"," ")[0:19]
        tokens = t[1][3]
        usd = t[1][7] #NOTE: This is the total, INCLUDING fees

        trans = {
            "desc": "",
            "wallet": walletName,
            "tokens":tokens
        }

        if type == "Rewards Income":
            if walletName not in toMerge["assets"][asset]["trans"]: #If this is the first "staking income", create a new staking transaction 
                trans["type"] = "stake"
                toMerge["assets"][asset]["trans"][walletName] = trans
            else:
                toMerge["assets"][asset]["trans"][walletName]["tokens"] += tokens   #If its not the first, merge it with the other staking transaction
        
        elif type in ("Buy", "Sell", "Coinbase Earn"):
            if type == "Coinbase Earn":
                trans["type"] = "gift"
                trans["price"] = usd / tokens
            elif type == "Buy":
                trans["type"] = "purchase"
                trans["usd"] = usd
            elif type == "Sell":
                trans["type"] = "sale"
                trans["usd"] = usd

            toMerge["assets"][asset]["trans"][date] = trans
        else:
            MessageBox(mainAppREF, "Import ERROR", "Couldn't import Coinbase history due to unimplemented transaction type, \'" + type + "\'")
            return

    mainAppREF.init_PERM(toMerge, True)
    mainAppREF.create_PORTFOLIO_WIDGETS()
    mainAppREF.create_metrics()
    mainAppREF.create_PROFILE_MENU()
    mainAppREF.undo_save()
                
def import_gemini(mainAppREF, fileDir, geminiWalletName="Gemini", geminiEarnWalletName="Gemini Earn"):
    data = pd.read_excel(fileDir)
    #Checks whether this is a Gemini Earn or Gemini XLSX file
    if "APY" in data.columns:
        import_gemini_earn(mainAppREF, data, geminiWalletName="Gemini", geminiEarnWalletName="Gemini Earn")
    else:
        import_gemini_normal(mainAppREF, data, geminiWalletName="Gemini", geminiEarnWalletName="Gemini Earn")

def import_gemini_earn(mainAppREF, data, geminiWalletName="Gemini", geminiEarnWalletName="Gemini Earn"):
    """Reads the XLSX file you downloaded from Gemini or Gemini Earn, spits out a dictionary in the same format as PERM, to be merged and overwrite the old PERM"""
    toMerge = { "assets" : {}, "wallets" : {geminiWalletName:"", geminiEarnWalletName:""}, "profiles" : {} }

    for t in data.iterrows():
        #We ignore anything that's just USD, and we ignore an empty cell as a way of ignoring the final row in the dataset, which are just totals
        if t[1][3] in ("USD", NAN):
            continue
        #We also ignore the "Monthly interest summaries"
        if t[1][2] == "Monthly Interest Summary":
            continue

        #Need to know the date/time to give our transaction a unique ID!
        date = str(t[1][0]).replace("-","/")[0:19]

        #Retrieves the transaction type, and the asset that we're working with
        type = t[1][2]
        asset = t[1][3] + "zc"
        #If this asset is not in toMerge already, add it!
        if asset not in toMerge["assets"]:
            toMerge["assets"][asset] = {"desc":"", "name":asset[:-2], "trans":{}}

        #Handles the three different transaction types within Gemini Earn Reports: Deposit, Interest Credit, Redeem
        if type == "Deposit": #Crypto funds moved into Gemini Earn from Gemini Wallet
            toMerge["assets"][asset]["trans"][date] = {
            "desc" : t[1][4],
            "type" : "transfer",
            "wallet" : geminiWalletName,
            "wallet2" : geminiEarnWalletName,
            "tokens" : data["Amount " + asset[:-2]][t[0]],
            }
            if t[1][4] in ("Earn Redemption", "Earn Transfer"):
                toMerge["assets"][asset]["trans"][date]["wallet"] = geminiEarnWalletName
        elif type == "Redeem": #Crypto funds moved out of Gemini Earn back to Gemini
            toMerge["assets"][asset]["trans"][date] = {
            "desc" : t[1][4],
            "type" : "transfer",
            "wallet" : geminiEarnWalletName,
            "wallet2" : geminiWalletName,
            "tokens" : -data["Amount " + asset[:-2]][t[0]],
            }
            if t[1][4] in ("Earn Redemption", "Earn Transfer"):
                toMerge["assets"][asset]["trans"][date]["wallet2"] = geminiEarnWalletName
        elif type == "Interest Credit": #This is only possible within Gemini Earn
            #If this wallet does not yet have a staking transaction set up, create it:
            if geminiWalletName not in toMerge["assets"][asset]["trans"]:
                toMerge["assets"][asset]["trans"][geminiWalletName] = {
                    "desc": t[1][4],
                    "tokens": data["Amount " + asset[:-2]][t[0]],
                    "type": "stake",
                    "wallet": geminiWalletName
                }
            #Otherwise, just merge the staking rewards into one lump:
            else:
                toMerge["assets"][asset]["trans"][geminiWalletName]["tokens"] += data["Amount " + asset[:-2]][t[0]]
        else:
            MessageBox(mainAppREF, "Import ERROR", "Couldn't import Gemini history due to unimplemented transaction type, \'" + type + "\'")
            return

    mainAppREF.init_PERM(toMerge, True)
    mainAppREF.create_PORTFOLIO_WIDGETS()
    mainAppREF.create_metrics()
    mainAppREF.create_PROFILE_MENU()
    mainAppREF.undo_save()

def import_gemini_normal(mainAppREF, data, geminiWalletName="Gemini", geminiEarnWalletName="Gemini Earn"):
    """Reads the XLSX file you downloaded from Gemini or Gemini Earn, spits out a dictionary in the same format as PERM, to be merged and overwrite the old PERM"""
    toMerge = { "assets" : {}, "wallets" : {geminiWalletName:"", geminiEarnWalletName:""}, "profiles" : {} }

    for t in data.iterrows():
        #We ignore anything that's just USD, and we ignore an empty cell as a way of ignoring the final row in the dataset, which are just totals
        if t[1][3] in ("USD", NAN):
            continue

        #Need to know the date/time to give our transaction a unique ID!
        date = str(t[1][0]).replace("-","/")[0:19]

        #Retrieves the transaction type, and the asset that we're working with
        type = t[1][2]
        asset = t[1][3]
        if type in ("Buy","Sell"):
            if asset[-3:] != "USD": #If the last three characters are 'USD'
                MessageBox(mainAppREF, "Import ERROR", "Couldn't import Gemini history due to pure crypto market pairs being unimplemented. Market pair " + type + " is unsupported.")
                return
            else: asset = asset[:-3] + "zc"     #Removes the "USD" from the market pair
        else: asset += "zc"     #If its "credit" or "debit", there is no pair, no need to remove the "USD"
        #If this asset is not in toMerge already, add it!
        if asset not in toMerge["assets"]:
            toMerge["assets"][asset] = {"desc":"", "name":asset[:-2], "trans":{}}

        #Handles the five different transaction types within Gemini
        if type == "Credit": #Crypto funds moved into Gemini or Gemini Earn
            toMerge["assets"][asset]["trans"][date] = {
            "desc" : t[1][4],
            "type" : "transfer",
            "wallet" : " MISSINGWALLET",
            "wallet2" : geminiWalletName,
            "tokens" : data[asset[:-2] + " Amount " + asset[:-2]][t[0]],
            }
            if t[1][4] in ("Earn Redemption", "Earn Transfer"):
                toMerge["assets"][asset]["trans"][date]["wallet"] = geminiEarnWalletName
        elif type == "Debit": #Crypto funds moved out of Gemini or Gemini Earn
            toMerge["assets"][asset]["trans"][date] = {
            "desc" : t[1][4],
            "type" : "transfer",
            "wallet" : geminiWalletName,
            "wallet2" : " MISSINGWALLET",
            "tokens" : -data[asset[:-2] + " Amount " + asset[:-2]][t[0]],
            }
            if t[1][4] in ("Earn Redemption", "Earn Transfer"):
                toMerge["assets"][asset]["trans"][date]["wallet2"] = geminiEarnWalletName
        elif type == "Buy":
            toMerge["assets"][asset]["trans"][date] = {
            "desc" : t[1][4],
            "type" : "purchase",
            "wallet" : geminiWalletName,
            "tokens" : data[asset[:-2] + " Amount " + asset[:-2]][t[0]],
            "usd" : -data["USD Amount USD"][t[0]] + data["Fee (USD) USD"][t[0]],
            }
        elif type == "Sell":
            toMerge["assets"][asset]["trans"][date] = {
            "desc" : t[1][4],
            "type" : "sale",
            "wallet" : geminiWalletName,
            "tokens" : -data[asset[:-2] + " Amount " + asset[:-2]][t[0]],
            "usd" : data["USD Amount USD"][t[0]] + data["Fee (USD) USD"][t[0]],
            }
        else:
            MessageBox(mainAppREF, "Import ERROR", "Couldn't import Gemini history due to unimplemented transaction type, \'" + type + "\'")
            return

    mainAppREF.init_PERM(toMerge, True)
    mainAppREF.create_PORTFOLIO_WIDGETS()
    mainAppREF.create_metrics()
    mainAppREF.create_PROFILE_MENU()
    mainAppREF.undo_save()