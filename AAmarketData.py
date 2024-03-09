import time
import json
from requests import Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import time

from threading import Thread

import yahoofinancials as yf2
import threading

from AAdialogs import Message
from AAlib import *

class market_data_thread:
    def __init__(self, main_app, portfolio, online_flag:threading.Event):
        self.MAIN_APP = main_app
        self.PORTFOLIO = portfolio
        self.online_event = online_flag

    ###Two independent threads which re-load market data every 5 minutes:
    ###=================================================
    def start_threads(self):
        """Starts two independent threads which """
        Thread(target=self.StockDataLoop, daemon=True).start()
        Thread(target=self.CryptoDataLoop, daemon=True).start()

    def finalize_market_import(self, toImport):
        self.MAIN_APP.market_data.update(toImport) # replaces all data for each class
        #Updates the timestamp for last update of the self.MAIN_APP.market_data
        self.MAIN_APP.market_data['_timestamp'] = str(datetime.now()) 
        self.MAIN_APP.GUI['timestamp_indicator'].setText('Data from ' + self.MAIN_APP.market_data['_timestamp'][0:16])

        self.MAIN_APP.market_metrics() # Recalculates all market-based metrics
        self.MAIN_APP.render(sort=True) # Re-renders portfolio



    ###Yahoo Financials for STOCK DATA and finding missing data
    ###============================================
    def StockDataLoop(self): # Only works when all stocks actually exist
        
        while True:
            self.online_event.wait() #waits eternally until we're online
            self.MAIN_APP.GUI['timestamp_indicator'].setText('Data being downloaded...')
            #Ok, we're online. Process immediately, then wait for 5 minutes and do it all again.

            # creates a list of 'tickers' or 'symbols' or whatever you want to call them
            stockList = [asset.ticker() for asset in self.PORTFOLIO.assets() if asset.class_code() == 's']

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

            # Removal of invalid stocks (if user puts in a stock ticker that cannot be found on yahooFinance)
            INVALID = [stock for stock in list(curr) if curr[stock]==None]      # Create list of stocks that could not be found
            stockList = [stock for stock in list(curr) if curr[stock]!=None]    # Replace stock list with list of stocks that DO exist
            if len(INVALID) > 0:                                                # Spawn an error message to notify the user which stocks could not be found
                InvokeMethod(p(Message, self.MAIN_APP, 'Yahoo Finance API Error', 'The following stock tickers could not be identified: ' + ', '.join(INVALID) + '.'))

            raw_data = raw_data.get_historical_price_data(date_month, date_today, 'daily')    #300ms

            toExport = {'s':{}}
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
                
                toExport['s'][stock] = export    #update the library which gets called to by the main portfolio

            toExport = {key:Decimal(value) for key,value in toExport.items()} # convert all data to Decimal object
            InvokeMethod(p(self.finalize_market_import, toExport))

            #Ok, we've got the market data. Wait 5 minutes
            time.sleep(300)
            

    ###Coinmarketcap API for CRYPTO DATA
    ###============================================
    def CryptoDataLoop(self):
        while True:
            self.online_event.wait() #waits eternally until we're online
            self.MAIN_APP.GUI['timestamp_indicator'].setText('Data being downloaded...')
            #Ok, we're online. Process immediately, then wait for 5 minutes. Then we do this check again, and so on.

            #creates a comma-separated list of crypto tickers to be fed into CoinMarketCap
            cryptoString = ','.join(asset.ticker() for asset in self.PORTFOLIO.assets() if asset.class_code() == 'c')

            if cryptoString == '':    #No reason to update nothing!
                time.sleep(120)        #Waits for 2 minutes, on an infinite waiting loop until the user adds this asset class to the portfolio
                continue


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
                if type(e) == ConnectionError: msg = 'Connection error: Could not connect to CoinMarketCap API'
                elif type(e) == Timeout: msg = 'Timeout error: Timed out while trying to connect to CoinMarketCap API'
                elif type(e) == TooManyRedirects: msg = 'TooManyRedirects error: Could not connect to CoinMarketCap API'
                else: msg = str(e)
                InvokeMethod(p(Message, self.MAIN_APP, 'CoinMarketCap API Error', msg))
                time.sleep(60)      #Waits for 1 minute
                continue
            if data and data['status']['error_message']:
                errmsg = data['status']['error_message']
                InvokeMethod(p(Message, self.MAIN_APP, 'CoinMarketCap API Error', errmsg))

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
            
            if data:
                toExport = {'c':{crypto:{
                            'marketcap' :   Decimal(data['data'][crypto]['quote']['USD']['market_cap']),
                            'day%' :        Decimal(data['data'][crypto]['quote']['USD']['percent_change_24h']/100),
                            'week%' :       Decimal(data['data'][crypto]['quote']['USD']['percent_change_7d']/100),
                            'month%' :      Decimal(data['data'][crypto]['quote']['USD']['percent_change_30d']/100),
                            'price' :       Decimal(data['data'][crypto]['quote']['USD']['price']),
                            'volume24h' :   Decimal(data['data'][crypto]['quote']['USD']['volume_24h']),
                            } for crypto in data['data']}}

                InvokeMethod(p(self.finalize_market_import, toExport))
            
            #Ok, we've got the market data. Wait 5 minutes, then start the loop again.
            time.sleep(300)


def getMissingPrice(date, TICKER, CLASS):
    '''Uses the date's OPEN price to fill in missing price data, when data is imported with missing information.\n
        While it works, it's kinda slow. And innacurate, though so is Etherscan's price data.'''   
    match CLASS:
        case 'c':  TO_FIND = TICKER+'-USD' #This is a crypto
        case 's':  TO_FIND = TICKER        #This is a stock
        case 'f':  TO_FIND = TICKER+'USD' #This is a fiat
        case other: raise Exception(f'||Error|| Unknown asset class code \'{CLASS}\'')

    date = str(datetime.date(datetime( int(date[:4]), int(date[5:7]), int(date[8:10]) )))
    raw_data = yf2.YahooFinancials([TO_FIND])  #0ms
    
    #We HAVE to do this extra function, because get_historical_price_data never stops running if it gets an unsupported market pair input
    if TO_FIND not in raw_data.get_summary_data():
        print('||ERROR|| Yahoo Finance API Error: ' + TO_FIND + ' is not a supported market pair on Yahoo Finance.')
        return None

    raw_data = raw_data.get_historical_price_data(date, date, 'daily')    #300ms 

    return str(raw_data[TO_FIND]['prices'][0]['close'])    # We assume the close is "good enough" an approximation for missing data
        