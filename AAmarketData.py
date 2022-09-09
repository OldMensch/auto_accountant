


from AAmessageBox import MessageBox
from AAlib import *
from datetime import *
import json
from requests import Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import time
from threading import Thread
from functools import partial as p

import yahoofinancials as yf2


###Daemon which re-loads market data every 5 minutes:
###=================================================


global marketdatalib
marketdatalib = {}

def startMarketDataLoops(mainPortREF, sandbox=False):
    Thread(target=p(StockDataLoop, mainPortREF), daemon=True).start()
    Thread(target=p(CryptoDataLoop, mainPortREF), daemon=True).start()

###Yahoo Financials for STOCK DATA
###============================================

def StockDataLoop(mainPortREF):
    global marketdatalib
    while True:
        stockList = []   #creates a list of 'tickers' or 'symbols' or whatever you want to call them
        for asset in list(PERM['assets']):
            if asset.split('z')[1] == 's':
                stockList.append(asset.split('z')[0])

        if len(stockList) == 0:    #No reason to update nothing!
            time.sleep(120)        #Waits for 2 minutes, on an infinite waiting loop until the user adds this asset class to the portfolio
            continue

        ddate_today = datetime.date(datetime.now())     #today
        ddate_week = ddate_today - timedelta(days=7)     #7 days ago
        ddate_month = ddate_today - timedelta(days=30)   #30 days ago
        date_today = str(ddate_today)
        date_month = str(ddate_month)

        raw_data = yf2.YahooFinancials(stockList)  #0ms
        curr = raw_data.get_stock_price_data() #17000ms ....  takes a LONG time

        #Removal of invalid stocks (if user puts in a stock ticker that doesn't exist, or otherwise cannot be found on yahoo)
        INVALID = []
        for stock in list(curr):
            if curr[stock] == None:
                curr.pop(stock)
                INVALID.append(stock)
        stockList = list(curr)  #Updates the list of all valid stocks after removing the invalid ones
        if len(INVALID) > 0:
            invalidString = ''
            for badTicker in INVALID:
                invalidString += badTicker + ', '
            invalidString = invalidString[:-2]
            MessageBox(mainPortREF, 'Yahoo Finance API Error', 'The following stock tickers could not be identified: ' + invalidString + '.')

        raw_data = raw_data.get_historical_price_data(date_month, date_today, 'daily')    #300ms

        for stock in stockList:
            #creates the initial dictionary ready for filling. This removes all the unnecessary data from curr[stock], leaving just the info we want in a universal format
            export = {
                'marketcap' : curr[stock]['marketCap'],
                'price' :  curr[stock]['regularMarketPrice'],
                'volume24h' : curr[stock]['volume24Hr'],
            }
            #historical data from yesterday or before all comes form the historical data thing
            dataref = raw_data[stock]['prices']
            export['day%'] =   export['price'] / dataref[len(dataref) - 1]['close'] - 1   #Daily % change is always relative to the first ACTIVE trading day before today
            export['month%'] = export['price'] / dataref[0]['close'] - 1                  #Monthly % change is always relative to the first ACTIVE trading day after a month ago
            for i in range(len(dataref)):
                date_hist = dataref[i]['formatted_date']
                ddate_hist = datetime.date(datetime(int(date_hist[:4]), int(date_hist[5:7]), int(date_hist[8:])))
                if ddate_hist == ddate_week:
                    export['week%'] =  export['price'] / dataref[i]['close'] - 1
                elif ddate_hist > ddate_week:
                    export['week%'] =  export['price'] / dataref[i]['close'] - 1
                    break
            
            marketdatalib[stock + 'zs'] = export    #update the library which gets called to by the main portfolio

            mainPortREF.market_metrics_ASSET(stock + 'zs', False) #Updates summary info for all the relevant ledgers
        mainPortREF.market_metrics_PORTFOLIO()                     #Updates the overall portfolio summary info
        mainPortREF.render(mainPortREF.asset, True)

        #Updates the timestamp for last update of the marketdatalib
        marketdatalib['_timestamp'] = str(datetime.now())
        
        time.sleep(300) #Waits for five minutes after the load process has completed, before doing it all over again





###Coinmarketcap API for CRYPTO DATA
###============================================

def CryptoDataLoop(mainPortREF):
    global marketdatalib
    while True:
        cryptoString = ''   #creates a comma-separates list of 'tickers' or 'symbols' or whatever you want to call them
        for asset in list(PERM['assets']):
            if asset.split('z')[1] == 'c':
                cryptoString += asset.split('z')[0] + ','

        if cryptoString == '':    #No reason to update nothing!
            time.sleep(120)        #Waits for 2 minutes, on an infinite waiting loop until the user adds this asset class to the portfolio
            continue

        cryptoString = cryptoString[:-1]


        url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
        parameters = {
            'symbol': cryptoString
        }
        headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': settings('CMCAPIkey'),
        }

        session = Session()
        session.headers.update(headers)

        try:
            response = session.get(url, params=parameters)
            data = json.loads(response.text)
        except (ConnectionError, Timeout, TooManyRedirects) as e:
            MessageBox(mainPortREF, 'CoinMarketCap API Error', e)
        if data != None and data['status']['error_message'] != None:
            errmsg = data['status']['error_message']
            MessageBox(mainPortREF, 'CoinMarketCap API Error', errmsg)

            ###Removal of all the INVALID token tickers. All remaining valid tokens will still be updated
            INVALID = errmsg.split('\'')[3].split(',')  #creates a list of all the invalid tokens
            cryptoString += ','

            for inv in INVALID:
                cryptoString = cryptoString.replace(inv+',', '')

            if cryptoString == '':    #If all of the tokens are invalid, there is no reason to update nothing!
                time.sleep(120)      #Waits for 2 minutes
                continue

            cryptoString = cryptoString[:-1]

            parameters = {
                'symbol': cryptoString
            }

            response = session.get(url, params=parameters)  #reloads 
            data = json.loads(response.text)

        if data != None:
            for crypto in data['data']:
                marketdatalib[crypto + 'zc'] =  {
                    'marketcap' :   str(data['data'][crypto]['quote']['USD']['market_cap']),
                    'day%' :        str(data['data'][crypto]['quote']['USD']['percent_change_24h']/100),
                    'week%' :       str(data['data'][crypto]['quote']['USD']['percent_change_7d']/100),
                    'month%' :      str(data['data'][crypto]['quote']['USD']['percent_change_30d']/100),
                    'price' :       str(data['data'][crypto]['quote']['USD']['price']),
                    'volume24h' :   str(data['data'][crypto]['quote']['USD']['volume_24h']),
                }
                mainPortREF.market_metrics_ASSET(crypto + 'zc', False) #Updates summary info for all the relevant ledgers NOTE!!! This cannot be simplified to just 'metrics'! This set of assets is a subset of 
            mainPortREF.market_metrics_PORTFOLIO()                      #Updates the overall portfolio summary info
            mainPortREF.render(mainPortREF.asset, True)

        #Updates the timestamp for last update of the marketdatalib
        marketdatalib['_timestamp'] = str(datetime.now())
        
        time.sleep(300) #Waits for five minutes after the load process has completed, before doing it all over again

