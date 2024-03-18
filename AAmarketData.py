import time
import json
from requests import Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import time

import threading
from threading import Thread
from concurrent.futures import ThreadPoolExecutor

import yahoofinancials as yf2
from yahooquery import Ticker

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
        """Starts stock/crypto market data gathering threads"""
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

            while len(stockList) == 0:    #No reason to update nothing! Restarts the wait timer.
                time.sleep(30)        #Waits for 2 minutes, on an infinite waiting loop until the user adds this asset class to the portfolio
                continue            
            
            # Retrieve raw YahooFinance data
            raw_data = {}
            def retrieve_data(ticker):
                raw_data[ticker] = Ticker(ticker).price[ticker]
            with ThreadPoolExecutor() as executor:
                executor.map(retrieve_data, stockList)
            
            # Cull data down to just what we want
            TO_EXPORT = { 's':{ticker:{
                'price':        Decimal(raw_data[ticker]['regularMarketPrice']),
                'marketcap':    Decimal(raw_data[ticker]['marketCap']),
                'volume24h':    Decimal(raw_data[ticker]['regularMarketVolume']),
                'day%':         Decimal(raw_data[ticker]['regularMarketChangePercent']),
                } for ticker in raw_data}
            }
            # Have to calculate week% and month% independently, not included in summary info above
            date_week_ago = str((datetime.now() - timedelta(days=7)).date())
            date_month_ago = str((datetime.now() - timedelta(days=30)).date())
            for ticker in raw_data:
                try: TO_EXPORT['s'][ticker]['week%'] = (TO_EXPORT['s'][ticker]['price'] / Decimal(getMissingPrice(date_week_ago, ticker, 's'))) - 1
                except:pass
                try: TO_EXPORT['s'][ticker]['month%'] = (TO_EXPORT['s'][ticker]['price'] / Decimal(getMissingPrice(date_month_ago, ticker, 's'))) - 1
                except:pass
            
            InvokeMethod(p(self.finalize_market_import, TO_EXPORT))

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
                TO_EXPORT = {'c':{crypto:{
                            'marketcap' :   Decimal(data['data'][crypto]['quote']['USD']['market_cap']),
                            'day%' :        Decimal(data['data'][crypto]['quote']['USD']['percent_change_24h']/100),
                            'week%' :       Decimal(data['data'][crypto]['quote']['USD']['percent_change_7d']/100),
                            'month%' :      Decimal(data['data'][crypto]['quote']['USD']['percent_change_30d']/100),
                            'price' :       Decimal(data['data'][crypto]['quote']['USD']['price']),
                            'volume24h' :   Decimal(data['data'][crypto]['quote']['USD']['volume_24h']),
                            } for crypto in data['data']}}

                InvokeMethod(p(self.finalize_market_import, TO_EXPORT))
            
            #Ok, we've got the market data. Wait 5 minutes, then start the loop again.
            time.sleep(300)



def getMissingPrice(date:str, TICKER:str, CLASS:str) -> str|None:
    '''Returns asset's close-price for defined date.'''   
    match CLASS:
        case 'c':  TO_FIND = TICKER+'-USD'  # Cryptos
        case 's':  TO_FIND = TICKER         # Stocks
        case 'f':  TO_FIND = TICKER+'USD=X' # Fiats
        case other: raise Exception(f'||Error|| Unknown asset class code \'{CLASS}\'')
    
    url = yf2.YahooFinancials(TO_FIND).get_stock_summary_url()

    #We HAVE to do this extra function, because get_historical_price_data never stops running if it gets an unsupported market pair input
    if isValidURL(url): 
        date_datetime = datetime.fromisoformat(date)
        OHLCV = Ticker(TO_FIND).history(start=date_datetime-timedelta(days=1), end=date_datetime)
        return OHLCV['close'].iloc[0]
    else:
        print(f'||ERROR|| Invalid YahooFinance URL for {class_lib[CLASS]['name']} \'{TICKER}\': {url}')
        return None


