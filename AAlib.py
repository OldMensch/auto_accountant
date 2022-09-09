from AAlib import *
import json
import time
from copy import deepcopy

import tkinter as tk

global iconlib
MISSINGDATA = '???'


PERM = {} #Universal permanent savedata dictionary

TEMP = { #Universal temporary data dictionary
        'metrics' : {},
        'widgets' : {},
        'undo' : [{'assets' : {},'wallets' : {},'profiles' : {}}]
        } 
TEMP['undo'].extend([0]*49)



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
        print(str(timestamp) + ' ms')
        timestamp = 0


def format_number(number, standard=None, bigNumber=False):
    '''Returns a string for the formatted version of a number. Mainly to shorten needlessly long numbers.
    \nnumber - the number to be formatted
    \nstandard - a bit of code 
    \n'''
    #If the number isn't a number, it might be missing market data
    try: number = float(number)
    except: return MISSINGDATA

    #If we set a certain formatting standard, then its this
    if standard != None:
        return format(float(number), standard)

    #Otherwise, we have fancy formatting
    if abs(number) >= 1000000000000:   #In trillions
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
defsettingslib = {
    'font': ['Calibri',16],
    'lastSaveDir': 'C:/Users/sevan/Desktop/Auto-Accountant/TEST3.JSON',
    'offlineMode': True,
    'itemsPerPage':30,
    'header_portfolio': ['ticker', 'name', 'class', 'holdings', 'price', 'marketcap', 'value', 'volume24h', 'day_change', 'day%', 'week%', 'month%', 'portfolio%'],
    'header_asset': ['date','type', 'tokens', 'usd', 'price', 'wallets'],
    'portHeight': 1080,
    'portWidth': 1920,
    'sort_asset': ['ticker', False],
    'sort_trans': ['date', False],
    'startWithLastSaveDir': True,
    'tooltipFade': 20,
    'tooltipPopup': 1,
    'CMCAPIkey': '',
    'accounting_method': 'hifo',
}
settingslib = deepcopy(defsettingslib)

palettelib = {      #standardized colors for the whole program
        'error':'#ff00ff',

        'profit':       '#00ff00',
        'loss':         '#ff0000',

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

        'gift':     '#44cc44',  'gifttext':     '#007700',
        'expense':  '#ee4444',  'expensetext':  '#aa0000',
        'purchase': '#00aa00',  'purchasetext': '#005d00',
        'sale':     '#d80000',  'saletext':     '#740000',
        'transfer': '#4488ff',  'transfertext': '#0044bb',
        ' MISSINGWALLET': '#ff0000', ' MISSINGWALLETtext': '#000000'
    }

def initializeIcons():  #unfortunately, this has to be a function, as it has to be declared AFTER the first tkinter instance is initialized
    global iconlib
    fs = int(225/settings('font')[1])
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

assetinfolib = { #Dictionary of useful attributes describing asset info
    'ticker': {                     'format': 'alpha',      'color' : None,             'name':'Ticker',                            'headername':'Ticker'},
    'name':{                        'format': 'alpha',      'color' : None,             'name':'Name',                              'headername':'Name'},
    'class':{                       'format': 'alpha',      'color' : None,             'name':'Asset Class',                       'headername':'Class'},
    'holdings':{                    'format': '',           'color' : None,             'name':'Holdings',                          'headername':'Holdings'},
    'price':{                       'format': '',           'color' : None,             'name':'Price',                             'headername':'Spot\nPrice'},
    'marketcap':{                   'format': '',           'color' : None,             'name':'Market Cap',                        'headername':'Market\nCap'},
    'value':{                       'format': '.2f',        'color' : None,             'name':'Value',                             'headername':'Value'},
    'volume24h':{                   'format': '',           'color' : None,             'name':'24hr Volume',                       'headername':'24 Hr\nVolume'},
    'day_change':{                  'format': '.2f',        'color' : 'profitloss',     'name':'24-Hour Δ',                         'headername':'24-Hr Δ'},
    'day%':{                        'format': 'percent',    'color' : 'profitloss',     'name':'24-Hour %',                         'headername':'24-Hr %'},
    'week%':{                       'format': 'percent',    'color' : 'profitloss',     'name':'7-Day %',                           'headername':'7-Day %'},
    'month%':{                      'format': 'percent',    'color' : 'profitloss',     'name':'30-Day %',                          'headername':'30-Day %'},
    'portfolio%':{                  'format': 'percent',    'color' : None,             'name':'Portfolio Weight',                  'headername':'Portfolio\nWeight'},
    'cash_flow':{                   'format': '.2f',        'color' : 'profitloss',     'name':'Cash Flow',                         'headername':'Cash\nFlow'},
    'net_cash_flow':{               'format': '.2f',        'color' : 'profitloss',     'name':'Net Cash Flow',                     'headername':'Net Cash\nFlow'},
    'realized_profit_and_loss':{    'format': '.2f',        'color' : 'profitloss',     'name':'Realized P&L (Capital Gains/Loss)', 'headername':'Real\nP&L'},
    'unrealized_profit_and_loss':{  'format': '.2f',        'color' : 'profitloss',     'name':'Unrealized P&L',                    'headername':'Unreal\nP&L'},
    'unrealized_profit_and_loss%':{ 'format': 'percent',    'color' : 'profitloss',     'name':'Unrealized P&L %',                  'headername':'Unreal\nP&L %'},
    'average_buy_price':{           'format': '',           'color' : None,             'name':'Average Buy Price',                 'headername':'Avg Buy\nPrice'},
}

transinfolib = {
    'date':{    'format':'alpha',   'color':None,    'name':'Date',                'headername':"Date"             },
    'type':{    'format':'alpha',   'color':'type',  'name':'Type',                'headername':"Type"             },
    'tokens':{  'format':'',        'color':None,    'name':'Tokens',              'headername':"Tokens"           },
    'usd':{     'format':'.2f',     'color':None,    'name':'USD',                 'headername':"USD"              },
    'price':{   'format':'',        'color':None,    'name':'Price',               'headername':"Price"            },
    'wallet':{  'format':'alpha',   'color':None,    'name':'Wallet',              'headername':"Wallet"           },
    'wallet2':{ 'format':'alpha',   'color':None,    'name':'Destination Wallet',  'headername':"Dest.\nWallet"    },
    'wallets':{ 'format':'alpha',   'color':None,    'name':'Wallets',             'headername':"Wallets"          },
}

assetclasslib = {  #List of asset classes, by name tag
    'c' : {
        'name':'Crypto',
        'validTrans' : ['purchase','sale','gift','expense','transfer'] 
    },
    's' : {
        'name':'Stock',
        'validTrans' : ['purchase','sale','gift','transfer'] 
    }
}

translib = {    #list of data to permanently retain for each transaction type. Other data is discarded to save space.
    'purchase':     ['wallet',            'type', 'tokens', 'usd',           'desc'],
    'sale':         ['wallet',            'type', 'tokens', 'usd',           'desc'],
    'gift':         ['wallet',            'type', 'tokens',        'price',  'desc'],
    'expense':      ['wallet',            'type', 'tokens',        'price',  'desc'],
    'transfer':     ['wallet', 'wallet2', 'type', 'tokens',                  'desc'],
}


def settings(request, mult=1, set=None):
    '''Returns the value of the requested Auto-Accountant setting\n
        Settings include: palette[color], font \n
        For fonts, set mult=float to scale the font relative to the default size. Returns a font size no smaller than 10'''
    if set != None:
        settingslib[request] = set
        return
    if request == 'font':
        if int(settingslib['font'][1] * mult) < 10:
            return (settingslib['font'][0], 10)
        return (settingslib['font'][0], int(settingslib['font'][1] * mult))
    return settingslib[request]

def saveSettings():
    json.dump(settingslib, open('settings.json', 'w'), indent=4, sort_keys=True)

def loadSettings():
    global settingslib
    try:
        loaded_settings = json.load(open('settings.json', 'r'))
        for setting in loaded_settings:
            settingslib[setting] = loaded_settings[setting]
    except:
        print('||ERROR|| Could not load settings.json, using default settings')

def palette(color):
    return palettelib[color]

def icons(icon):
    return iconlib[icon]

