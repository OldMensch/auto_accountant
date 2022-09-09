


from AAdialogues import Message
from AAlib import *
from AAobjects import MAIN_PORTFOLIO

import time
import json
from requests import Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import time

from threading import Thread

import yahoofinancials as yf2


###Daemon which re-loads market data every 5 minutes:
###=================================================

def startMarketDataLoops(mainPortREF, online_event):
    Thread(target=StockDataLoop, daemon=True, args=(mainPortREF, online_event)).start()
    Thread(target=CryptoDataLoop, daemon=True, args=(mainPortREF, online_event)).start()

###Yahoo Financials for STOCK DATA and finding missing data
###============================================

def StockDataLoop(mainPortREF, online_event):
    last_load_time = 0
    
    while True:
        online_event.wait() #waits eternally until we're online
        #Ok, we're online. Process immediately, then wait for 5 minutes and do it all again.

        stockList = []   #creates a list of 'tickers' or 'symbols' or whatever you want to call them
        for asset in MAIN_PORTFOLIO.assets():
            if asset.assetClass() == 's':
                stockList.append(asset.ticker())

        if len(stockList) == 0:    #No reason to update nothing! Restarts the wait timer.
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
            Message(mainPortREF, 'Yahoo Finance API Error', 'The following stock tickers could not be identified: ' + invalidString + '.')

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

        mainPortREF.market_metrics()                     #Updates the overall portfolio summary info
        mainPortREF.render(sort=True)

        #Updates the timestamp for last update of the marketdatalib
        marketdatalib['_timestamp'] = str(datetime.now())
            

        #Ok, we've got the market data. Wait 5 minutes
        time.sleep(300)
        
def getMissingPrice(date, tickerclass):
    '''Uses the date's OPEN price to fill in missing price data, when data is imported with missing information.\n
        While it works, it's kinda slow. And innacurate, though so is Etherscan's price data.'''   
    TICKER = tickerclass.split('z')[0]
    CLASS = tickerclass.split('z')[1]
    if   CLASS == 'c':  TO_FIND = TICKER+'-USD' #This is a crypto
    elif CLASS == 's':  TO_FIND = TICKER        #This is a stock
    elif CLASS == 'f':  TO_FIND = TICKER+'/USD' #This is a fiat

    date = str(datetime.date(datetime( int(date[:4]), int(date[5:7]), int(date[8:10]) )))
    raw_data = yf2.YahooFinancials([TO_FIND])  #0ms
    
    #We HAVE to do this extra function, because get_historical_price_data never stops running if it gets an unsupported market pair input
    if TO_FIND not in raw_data.get_summary_data():
        print('||ERROR|| Yahoo Finance API Error: ' + TO_FIND + ' is not a supported market pair on Yahoo Finance.')
        return None
        #Message(mainPortREF, 'Yahoo Finance API Error', 'The following stock tickers could not be identified: ' + invalidString + '.')

    raw_data = raw_data.get_historical_price_data(date, date, 'daily')    #300ms 

    return str(raw_data[TO_FIND]['prices'][0]['close'])    # We assume the close is "good enough" an approximation for missing data
        


###Coinmarketcap API for CRYPTO DATA
###============================================

def CryptoDataLoop(mainPortREF, online_event):
    while True:
        online_event.wait() #waits eternally until we're online
        #Ok, we're online. Process immediately, then wait for 5 minutes. Then we do this check again, and so on.

        cryptoString = ''   #creates a comma-separates list of 'tickers' or 'symbols' or whatever you want to call them
        for asset in MAIN_PORTFOLIO.assets():
            if asset.assetClass() == 'c':
                cryptoString += asset.ticker() + ','

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
        'X-CMC_PRO_API_KEY': setting('CMCAPIkey'),
        }

        session = Session()
        session.headers.update(headers)

        try:
            response = session.get(url, params=parameters)
            data = json.loads(response.text)
        except (ConnectionError, Timeout, TooManyRedirects) as e:
            Message(mainPortREF, 'CoinMarketCap API Error', e)
        if data != None and data['status']['error_message'] != None:
            errmsg = data['status']['error_message']
            Message(mainPortREF, 'CoinMarketCap API Error', errmsg)

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
                try:
                    marketdatalib[crypto + 'zc'] =  {
                        'marketcap' :   str(data['data'][crypto]['quote']['USD']['market_cap']),
                        'day%' :        str(data['data'][crypto]['quote']['USD']['percent_change_24h']/100),
                        'week%' :       str(data['data'][crypto]['quote']['USD']['percent_change_7d']/100),
                        'month%' :      str(data['data'][crypto]['quote']['USD']['percent_change_30d']/100),
                        'price' :       str(data['data'][crypto]['quote']['USD']['price']),
                        'volume24h' :   str(data['data'][crypto]['quote']['USD']['volume_24h']),
                    }
                except:
                    marketdatalib[crypto + 'zc'] =  {   #Basically this is just for LUNA which is no longer tracked on CoinMarketCap
                        'marketcap' :   '0',
                        'day%' :        '0',
                        'week%' :       '0',
                        'month%' :      '0',
                        'price' :       '0',
                        'volume24h' :   '0',
                    }
                
            mainPortREF.market_metrics()                      #Updates the overall portfolio summary info
            mainPortREF.render(sort=True)

        #Updates the timestamp for last update of the marketdatalib
        marketdatalib['_timestamp'] = str(datetime.now())
        
        #Ok, we've got the market data. Wait 5 minutes, then start the loop again.
        time.sleep(300)

