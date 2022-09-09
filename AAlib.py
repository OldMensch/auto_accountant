
import json
import time
from datetime import datetime, timedelta
from copy import deepcopy
import tkinter as tk

from mpmath import mpf as precise
from mpmath import mp
mp.dps = 50
absolute_precision = 1e-10
relative_precision = 1e-8
def appxEq(x,y): return abs(precise(x)-precise(y)) < absolute_precision
def zeroish(x):  return abs(precise(x)) < absolute_precision 



global iconlib

marketdatalib = {}

TEMP = { #Universal temporary data dictionary
        'metrics' : {},
        'widgets' : {},
        'undo' : [{'addresses' : {},'assets' : {},'transactions' : {},'wallets' : {}}]
        } 
TEMP['undo'].extend([0]*49)

MISSINGDATA = '???'


### UTILITY FUNCTIONS
###==========================================
global timestamp
timestamp = 0

def ttt(string='reset'):
    '''\'reset\' prints the current time then sets to 0, \'start\' subtracts a startpoint, \'end\' adds an endpoint'''
    global timestamp
    if string == 'reset':
        print(str(timestamp) + ' ms')
        timestamp = 0
    elif string == 'start':
        timestamp -= time.time()*1000
    elif string == 'end':
        timestamp += time.time()*1000
    elif string == 'terminate':
        timestamp += time.time()*1000
        ttt('reset')



def acceptableTimeDiff(date1, date2, second_gap):
    '''True if the dates are within second_gap of eachother. False otherwise.'''
    d1 = datetime( int(date1[:4]), int(date1[5:7]), int(date1[8:10]), int(date1[11:13]), int(date1[14:16]), int(date1[17:19]) )
    d2 = datetime( int(date2[:4]), int(date2[5:7]), int(date2[8:10]), int(date2[11:13]), int(date2[14:16]), int(date2[17:19]) )
    s = timedelta(seconds=second_gap)
    if d1 > d2 - s and d1 < d2 + s: return True
    return False

def acceptableDifference(value1, value2, percent_gap):
    '''True if the values are within percent_gap of eachother. False otherwise.\n
        percent_gap is the maximum multiplier between value1 and value2, where 2 is a 1.02 multiplier, 0.5 is a 1.005 multiplier, and so on. '''
    v1 = precise(value1)
    v2 = precise(value2)
    p = precise(1+percent_gap/100)
    if v1 < v2 * p and v1 > v2 / p: #If value1 is within percent_gap of value2, then it is acceptable
        return True
    return False

def format_general(data, style=None, charlimit=0):
    toReturn = MISSINGDATA
    if style == 'alpha':        toReturn = str(data)
    elif style == 'integer':      
        try:                    toReturn = str(int(data))
        except: pass
    elif style == 'percent':      
        try:                    toReturn = format_number(float(data)*100, '.2f') + '%'
        except: pass
    elif style == 'penny':      toReturn = format_number(data, '.2f')
    elif style == 'accounting':   
        try:
            if float(data) < 0: toReturn = '('+format_number(abs(data), '.5f')+')'
            else:               toReturn = format_number(data, '.5f')
        except: pass
    elif style == '':           toReturn = format_number(data)
    if charlimit > 0 and len(toReturn) > charlimit:
        if '.' in toReturn and toReturn.index('.') > charlimit: return toReturn.split('.')[0] #Returns the number as an integer, if it is an integer longer than the charlimit
        return toReturn[0:charlimit].removesuffix('.') #Removes the decimal, if its the very last character
    return toReturn

def format_number(number, standard=None, bigNumber=False):
    '''Returns a string for the formatted version of a number. Mainly to shorten needlessly long numbers.
    \nnumber - the number to be formatted
    \nstandard - a bit of code 
    \n'''
    #If the number isn't a number, it might be missing market data
    try: number = float(number)
    except: return MISSINGDATA

    #If we set a certain formatting standard, then its this
    if standard: return format(float(number), standard)

    #Otherwise, we have fancy formatting
    if abs(number) >= 1000000000000000:   #In quadrillions
        return format(number/1000000000000000) + ' QD'
    elif abs(number) >= 1000000000000:   #In trillions
        return format(number/1000000000000,'.1f') + ' T'
    elif abs(number) >= 1000000000:   #In billions
        return format(number/1000000000,'.1f') + ' B'
    elif abs(number) >= 1000000:   #In millions
        return format(number/1000000,'.1f') + ' M'
    elif abs(number) >= 1:       #If number greater than 1, show all digits and 2 following the decimal
        return format(number, '.2f')
    elif abs(number) >= .0001:   #If the number is tiny and greater than 0.0001, show those 4 digits following the decimal
        return format(number, '.4f')
    elif abs(number) > 0:        #If number less than .0001, use scientific notation with 3 values of meaning after the decimal
        return format(number,'.3E')
    else:
        return '0.00'


### LIBRARIES
###==========================================

palettelib = {      #standardized colors for the whole program
        'profit':       '#00ff00',
        'neutral':      '#cccccc',
        'loss':         '#ff0000',
        'default_info_color':  '#ffffff',
        'missingdata':  '#ff00ff',

        'grid_header':      '#0066aa',
        'grid_highlight':   '#004466',
        'grid_bg':          '#003355',
        'grid_text':        '#ffffff',

        'light':        '#0066aa',  #555555
        'medium':       '#004466',  #555555
        'dark':         '#003355',  #333333
        'menu':         '#555555',
        'menudark':     '#333333',
        'accent':       '#550000',
        'accentdark':   '#400000',

        'entry':        '#000000',
        'entrycursor':  '#ffffff',
        'entrytext':    '#ffff00',

        'scrollnotch':'#f0f0f0',
        'tooltipbg' : '#fff0dd',
        'tooltipfg' : '#660000',

        'purchase':         '#00aa00',  'purchasetext':         '#005d00',
        'purchase_crypto_fee':  '#00aa00',  'purchase_crypto_feetext':  '#005d00',
        'sale':             '#d80000',  'saletext':             '#740000',
        'gift_in':          '#44cc44',  'gift_intext':          '#007700',
        'gift_out':         '#44cc44',  'gift_outtext':         '#007700',
        'expense':          '#ee4444',  'expensetext':          '#aa0000',
        'card_reward':      '#aa00aa',  'card_rewardtext':      '#440044',
        'income':           '#aa00aa',  'incometext':           '#440044',
        'transfer_in':      '#4488ff',  'transfer_intext':      '#0044bb',
        'transfer_out':     '#4488ff',  'transfer_outtext':     '#0044bb',
        'trade':            '#ffc000',  'tradetext':            '#d39700',
        
        'error':        '#ff0000',  'errortext':        '#000000',
    }

def initializeIcons():  #unfortunately, this has to be a function, as it has to be declared AFTER the first tkinter instance is initialized
    global iconlib
    fs = int(225/setting('font')[1])
    fs15=int(fs*1.5)
    iconlib = {
        'new' :  tk.PhotoImage(format='PNG', file='icons/new.png').subsample(fs,fs),
        'load' : tk.PhotoImage(format='PNG', file='icons/load.png').subsample(fs,fs),
        'save' : tk.PhotoImage(format='PNG', file='icons/save.png').subsample(fs,fs),
        'settings2' : tk.PhotoImage(format='PNG', file='icons/settings2.png').subsample(fs,fs),
        'info2' : tk.PhotoImage(format='PNG', file='icons/info2.png').subsample(fs,fs),
        'profiles' : tk.PhotoImage(format='PNG', file='icons/profiles.png').subsample(fs,fs),
        'undo' : tk.PhotoImage(format='PNG', file='icons/undo.png').subsample(fs,fs),
        'redo' : tk.PhotoImage(format='PNG', file='icons/redo.png').subsample(fs,fs),

        'arrow_up' : tk.PhotoImage(format='PNG', file='icons/arrow_up.png').subsample(fs,fs),
        'arrow_down' : tk.PhotoImage(format='PNG', file='icons/arrow_down.png').subsample(fs,fs),
        
        'settings' : tk.PhotoImage(format='PNG', file='icons/settings.png').subsample(fs15,fs15),
        'info' : tk.PhotoImage(format='PNG', file='icons/info.png').subsample(fs15,fs15),
    }

portfolioinfolib = {
    'number_of_transactions': {     'format':'integer', 'color' : None,         'name':'# Transactions',    'headername':'# Transactions'},
    'number_of_assets': {           'format':'integer', 'color' : None,         'name':'# Assets',          'headername':'# Assets'},
    'value': {                      'format':'penny',   'color' : None,         'name':'Value',             'headername':'Value'},
    'day_change': {                 'format':'penny',   'color' : 'profitloss', 'name':'24-Hour Δ',         'headername':'24-Hr Δ'},
    'day%': {                       'format':'percent', 'color' : 'profitloss', 'name':'24-Hour %',         'headername':'24-Hr %'},
    'week%': {                      'format':'percent', 'color' : 'profitloss', 'name':'7-Day %',           'headername':'7-Day %'},
    'month%': {                     'format':'percent', 'color' : 'profitloss', 'name':'30-Day %',          'headername':'30-Day %'},
    'unrealized_profit_and_loss':{  'format':'penny',   'color' : 'profitloss', 'name':'Unrealized P&L',    'headername':'Unreal P&L'},
    'unrealized_profit_and_loss%':{ 'format':'percent', 'color' : 'profitloss', 'name':'Unrealized P&L %',  'headername':'Unreal P&L %'},
}

assetinfolib = { #Dictionary of useful attributes describing asset info
    'ticker': {                     'format': 'alpha',      'color' : None,             'name':'Ticker',            'headername':'Ticker'},
    'name':{                        'format': 'alpha',      'color' : None,             'name':'Name',              'headername':'Name'},
    'class':{                       'format': 'alpha',      'color' : None,             'name':'Asset Class',       'headername':'Class'},
    'holdings':{                    'format': '',           'color' : None,             'name':'Holdings',          'headername':'Holdings'},
    'price':{                       'format': '',           'color' : None,             'name':'Price',             'headername':'Spot\nPrice'},
    'marketcap':{                   'format': '',           'color' : None,             'name':'Market Cap',        'headername':'Market\nCap'},
    'value':{                       'format': 'penny',      'color' : None,             'name':'Value',             'headername':'Value'},
    'volume24h':{                   'format': '',           'color' : None,             'name':'24hr Volume',       'headername':'24 Hr\nVolume'},
    'day_change':{                  'format': 'penny',      'color' : 'profitloss',     'name':'24-Hour Δ',         'headername':'24-Hr Δ'},
    'day%':{                        'format': 'percent',    'color' : 'profitloss',     'name':'24-Hour %',         'headername':'24-Hr %'},
    'week%':{                       'format': 'percent',    'color' : 'profitloss',     'name':'7-Day %',           'headername':'7-Day %'},
    'month%':{                      'format': 'percent',    'color' : 'profitloss',     'name':'30-Day %',          'headername':'30-Day %'},
    'portfolio%':{                  'format': 'percent',    'color' : None,             'name':'Portfolio Weight',  'headername':'Portfolio\nWeight'},
    'cash_flow':{                   'format': 'penny',      'color' : 'profitloss',     'name':'Cash Flow',         'headername':'Cash\nFlow'},
    'net_cash_flow':{               'format': 'penny',      'color' : 'profitloss',     'name':'Net Cash Flow',     'headername':'Net Cash\nFlow'},
    'realized_profit_and_loss':{    'format': 'penny',      'color' : 'profitloss',     'name':'Realized P&L',      'headername':'Real\nP&L'},
    'tax_capital_gains':{           'format': 'penny',      'color' : 'profitloss',     'name':'Capital Gains',     'headername':'Capital\nGains'},
    'tax_income':{                  'format': 'penny',      'color' : None,             'name':'Income',            'headername':'Taxable\nIncome'},
    'unrealized_profit_and_loss':{  'format': 'penny',      'color' : 'profitloss',     'name':'Unrealized P&L',    'headername':'Unreal\nP&L'},
    'unrealized_profit_and_loss%':{ 'format': 'percent',    'color' : 'profitloss',     'name':'Unrealized P&L %',  'headername':'Unreal\nP&L %'},
    'average_buy_price':{           'format': '',           'color' : None,             'name':'Average Buy Price', 'headername':'Avg Buy\nPrice'},
}

transinfolib = {
    'date':{            'format':'alpha',      'color':None,         'name':'Date (UTC)',    'headername':'Date (UTC)'     },
    'type':{            'format':'alpha',      'color':'type',       'name':'Type',          'headername':'Type'           },
    'wallet':{          'format':'alpha',      'color':None,         'name':'Wallet',        'headername':'Wallet'         },
    'loss_asset':{      'format':'alpha',      'color':None,         'name':'Loss Asset',    'headername':'Loss\nAsset'    },
    'loss_quantity':{   'format':'',           'color':None,         'name':'Loss Quantity', 'headername':'Loss\nQuantity' },
    'loss_price':{      'format':'',           'color':None,         'name':'Loss Price',    'headername':'Loss\nPrice'    },
    'fee_asset':{       'format':'alpha',      'color':None,         'name':'Fee Asset',     'headername':'Fee\nAsset'     },
    'fee_quantity':{    'format':'',           'color':None,         'name':'Fee Quantity',  'headername':'Fee\nQuantity'  },
    'fee_price':{       'format':'',           'color':None,         'name':'Fee Price',     'headername':'Fee\nPrice'     },
    'gain_asset':{      'format':'alpha',      'color':None,         'name':'Gain Asset',    'headername':'Gain\nAsset'    },
    'gain_quantity':{   'format':'',           'color':None,         'name':'Gain Quantity', 'headername':'Gain\nQuantity' },
    'gain_price':{      'format':'',           'color':None,         'name':'Gain Price',    'headername':'Gain\nPrice'    },

    'value':{           'format':'',           'color':None,         'name':'Value',         'headername':'Value'          },
    'quantity':{        'format':'accounting', 'color':'accounting', 'name':'Quantity',      'headername':'Quantity'       },
    'price':{           'format':'',           'color':None,         'name':'Price',         'headername':'Price'          },
}

forks_and_duplicate_tickers_lib = { #If your purchase was before this date, it converts the ticker upon loading the JSON file. This is for assets which have changed tickers over time.
    'CGLDzc':   ('CELOzc', '9999/12/31 00:00:00'),
    'LUNAzc':   ('LUNCzc', '2022/05/28 00:00:00')
}

def prettyClasses():
    '''AAlib function which returns a list of asset classes by their pretty name'''
    toReturn = []
    for c in assetclasslib: toReturn.append(assetclasslib[c]['name'])
    return toReturn

def uglyClass(name):
    '''AAlib function which returns the short class tag given its longer name'''
    for c in assetclasslib:
        if assetclasslib[c]['name'] == name:    return c
    return '' #Return blank string if we fail to find the class letter

assetclasslib = {  #List of asset classes, by name tag
    'c' : {
        'name':'Crypto',
        'validTrans' : ['purchase','purchase_crypto_fee','sale','gift_in','gift_out','card_reward','income','expense','transfer_in','transfer_out','trade'] 
    },
    's' : {
        'name':'Stock',
        'validTrans' : ['purchase','sale','gift_in','gift_out','transfer_in','transfer_out'] 
    },
    'f' : {
        'name':'Fiat',
        'validTrans' : ['purchase','sale','gift_in','gift_out','transfer_in','transfer_out'] 
    }
}

def uglyTrans(pretty):
    for ugly in pretty_trans:
        if pretty_trans[ugly] == pretty:
            return ugly

pretty_trans = {
    'purchase':             'Purchase',
    'purchase_crypto_fee':  'Purchase w / Crypto Fee',
    'sale':                 'Sale',
    'gift_out':             'Gift OUT',
    'gift_in':              'Gift IN',
    'card_reward':          'Card Reward',
    'income':               'Income',
    'expense':              'Expense',
    'transfer_out':         'Transfer OUT',
    'transfer_in':          'Transfer IN',
    'trade':                'Trade',
}

trans_priority = {  #Dictionary that sorts simultaneous transactions by what makes sense
    'purchase':             0,  #In only
    'card_reward':          1,  #In only
    'income':               2,  #In only
    'gift_in':              3,  #In only
    'purchase_crypto_fee':  4,  #Definitively both
    'trade':                5,  #Definitively both
    'transfer_out':         6,  #Kinda both
    'transfer_in':          7,  #Kinda both
    'gift_out':             8,  #Out only
    'expense':              9,  #Out only
    'sale':                 10,  #Out only
}

valid_transaction_data_lib = {
    'purchase':             ['type', 'date', 'wallet', 'description',               'loss_quantity',                            'fee_quantity',              'gain_asset', 'gain_quantity'],
    'purchase_crypto_fee':  ['type', 'date', 'wallet', 'description',               'loss_quantity',               'fee_asset', 'fee_quantity', 'fee_price', 'gain_asset', 'gain_quantity'              ],
    'sale':                 ['type', 'date', 'wallet', 'description', 'loss_asset', 'loss_quantity',                            'fee_quantity',                            'gain_quantity'],
    'gift_out':             ['type', 'date', 'wallet', 'description', 'loss_asset', 'loss_quantity',               'fee_asset', 'fee_quantity', 'fee_price'],
    'gift_in':              ['type', 'date', 'wallet', 'description',                                                                                        'gain_asset', 'gain_quantity', 'gain_price'],
    'card_reward':          ['type', 'date', 'wallet', 'description',                                                                                        'gain_asset', 'gain_quantity', 'gain_price'],
    'income':               ['type', 'date', 'wallet', 'description',                                                                                        'gain_asset', 'gain_quantity', 'gain_price'],
    'expense':              ['type', 'date', 'wallet', 'description', 'loss_asset', 'loss_quantity', 'loss_price', 'fee_asset', 'fee_quantity', 'fee_price'],
    'transfer_out':         ['type', 'date', 'wallet', 'description', 'loss_asset', 'loss_quantity',               'fee_asset', 'fee_quantity', 'fee_price',                                            ],
    'transfer_in':          ['type', 'date', 'wallet', 'description',                                              'fee_asset', 'fee_quantity', 'fee_price', 'gain_asset', 'gain_quantity'              ],
    'trade':                ['type', 'date', 'wallet', 'description', 'loss_asset', 'loss_quantity', 'loss_price', 'fee_asset', 'fee_quantity', 'fee_price', 'gain_asset', 'gain_quantity'              ],
}

defsettingslib = { # A library containing all of the default settings
    'portHeight': 1080,
    'portWidth': 1920,
    'font': ['Calibri',16],
    'font2': ['Courier New',16],
    'itemsPerPage':30,
    'startWithLastSaveDir': True,
    'lastSaveDir': '',
    'offlineMode': True,
    'header_portfolio': list(assetinfolib),
    'header_asset': ["date", "type", "wallet", "quantity", "value", "price"],
    'sort_asset': ['ticker', False],
    'sort_trans': ['date', False],
    'CMCAPIkey': '',
    'accounting_method': 'hifo',
    "base_currency": "USDzf",
}
settingslib = deepcopy(defsettingslib)

def setting(request, mult=1, set=None):
    '''Returns the value of the requested Auto-Accountant setting\n
        Settings include: palette[color], font \n
        For fonts, set mult=float to scale the font relative to the default size. Returns a font size no smaller than 10'''
    if set:
        settingslib[request] = set
        return
    if request[0:4] == 'font':
        if int(settingslib[request][1] * mult) < 10: #10 is the minimum font size
            return (settingslib[request][0], 10)
        return (settingslib[request][0], int(settingslib[request][1] * mult))
    return settingslib[request]

def set_setting(request, newValue):
    settingslib[request] = newValue

def saveSettings():
    json.dump(settingslib, open('settings.json', 'w'), indent=4, sort_keys=True)

def loadSettings():
    global settingslib
    settingslib = deepcopy(defsettingslib)
    try:
        settings_JSON = json.load(open('settings.json', 'r'))
        for setting in defsettingslib:
            try:    
                if type(settingslib[setting])==type(settings_JSON[setting]): settingslib[setting] = settings_JSON[setting]
            except: pass
    except:
        print('||ERROR|| Could not load settings.json, reverting to default settings')

def palette(color):
    try:    return palettelib[color]
    except: return "#ff00ff" #error color

def icons(icon):
    return iconlib[icon]

