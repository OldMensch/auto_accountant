
import json
import time
from datetime import datetime, timedelta
from copy import deepcopy
import sys, os

import AAstylesheet
from AAstylesheet import UNI_PALETTE

from PySide2.QtWidgets import (QLabel, QFrame, QGridLayout, QVBoxLayout, QPushButton, QHBoxLayout, QMenu, QMenuBar, QAction, 
    QShortcut, QApplication, QMainWindow, QDialog, QDesktopWidget, QMessageBox, QWidget, QTextEdit, QDateTimeEdit, QLineEdit, QPlainTextEdit, QActionGroup,
    QComboBox, QListView, QListWidget, QAbstractItemView, QListWidgetItem, QFileDialog, QProgressBar, QScrollArea, QScrollBar, QStyle)
from PySide2.QtGui import (QPixmap, QFont, QIcon, QKeySequence, QWheelEvent, QMouseEvent, QFontMetrics, QHoverEvent, QCursor, QDoubleValidator, QDrag, 
    QDropEvent, QDragEnterEvent, QImage, QPainter)
from PySide2.QtCore import Qt, QSize, QTimer, QObject, Signal, Slot, QDateTime, QModelIndex, QEvent, QMargins, QMimeData, QTextDecoder

import decimal
decimal.getcontext().prec = 100
from decimal import Decimal

absolute_precision = Decimal(1e-80)
relative_precision = Decimal(1e-8)
def appxEq(x,y):    return abs(Decimal(x)-Decimal(y)) < absolute_precision
def zeroish(x):     return abs(Decimal(x)) < absolute_precision 

def appxEqPrec(x:Decimal,y:Decimal): return abs(x-y) < absolute_precision
def zeroish_prec(x:Decimal):     return abs(x) < absolute_precision 



global iconlib

marketdatalib = {}

TEMP = { #Universal temporary data dictionary
        'metrics' : {},
        'widgets' : {},
        'undo' : [{'assets' : {},'transactions' : {},'wallets' : {}}]
        } 
TEMP['undo'].extend([0]*49)

MISSINGDATA = '???'


### UTILITY FUNCTIONS
###==========================================
global timestamp
global time_avg
global time_avg_windows
timestamp = 0
time_sum = 0
time_avg_windows = 0

def ttt(string:str='reset'):
    '''\'reset\' prints the current time then sets to 0, \'start\' subtracts a startpoint, \'end\' adds an endpoint'''
    global timestamp
    global time_sum
    global time_avg_windows
    if string == 'reset':
        print(str(timestamp) + ' ms')
        time_sum = 0
        time_avg_windows = 0
        timestamp = 0
    elif string == 'start':
        timestamp -= time.time()*1000
    elif string == 'end':
        timestamp += time.time()*1000
    elif string == 'terminate':
        timestamp += time.time()*1000
        ttt('reset')
    elif string == 'avg_save':
        time_sum += timestamp
        time_avg_windows += 1
        timestamp = 0
    elif string == 'avg_end':
        ttt('end')
        ttt('avg_save')
    elif string == 'average_report':
        print(str(time_sum/time_avg_windows) + ' ms, on average. Sample size = '+str(time_avg_windows))

class InvokeMethod(QObject): # Credit: Tim Woocker from on StackOverflow
    def __init__(self, method):
        '''Can be called from any thread to run any function on the main thread'''
        super().__init__()

        main_thread = QApplication.instance().thread()
        self.moveToThread(main_thread)
        self.setParent(QApplication.instance())
        self.method = method
        self.called.connect(self.execute)
        self.called.emit()

    called = Signal()

    @Slot()
    def execute(self):
        self.method()
        # trigger garbage collector
        self.setParent(None)


def HTMLify(text, styleSheet:str=''): # Uses a styleSheet to format HTML text
    if text == '': return ''
    if styleSheet == '': return text
    return '<font style="'+styleSheet+'">'+text+'</font>'


def acceptableTimeDiff(unix_date1:int, unix_date2:int, second_gap:int) -> bool:
    '''True if the dates are within second_gap of eachother. False otherwise.'''
    return abs(unix_date2-unix_date1) < second_gap

def acceptableDifference(v1:Decimal, v2:Decimal, percent_gap:float) -> bool:
    '''True if the values are within percent_gap of eachother. False otherwise.\n
        percent_gap is the maximum multiplier between value1 and value2, where 2 is a 1.02 multiplier, 0.5 is a 1.005 multiplier, and so on. '''
    p = Decimal(1+percent_gap/100)
    return v1 < v2 * p and v1 > v2 / p #If value1 is within percent_gap of value2, then it is acceptable

def format_general(data:str, style:str=None, charlimit:int=0) -> str:
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

def format_number(number:float, standard:str=None) -> str:
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

styleSheetLib = { # NOTE: Partial transparency doesn't seem to work

    # Good fonts: 
    #   Courier New
    #   Inconsolata Medium
    #   Calibri
    'universal':            "font-family: 'Calibri';",

    'GRID':                 "border: 0; border-radius: 0;",
    'GRID_column':          "background: transparent; border-color: transparent; border-width: -2px 2px -2px 2px; font-size: px; font-family: \'Inconsolata Medium\';",
    'GRID_label':           "background: "+UNI_PALETTE.B3+"; font-size: px; font-family: \'Inconsolata Medium\';",
    'GRID_error_hover':     "background: #ff0000;",
    'GRID_error_selection': "background: #cc0000;",
    'GRID_error_none':      "background: #880000;",
    'GRID_hover':           "background: "+UNI_PALETTE.A2+";",
    'GRID_selection':       "background: "+UNI_PALETTE.A1+";",
    'GRID_none':            "color: #ff0000; background: transparent;",
                            

    'title':                "background-color: #000000; color: #ffff00; font-family: 'Calibri'; font-size: 30px;",
    'subtitle':             "background-color: #000000; color: #ffff00; font-family: 'Calibri'; font-size: 15px;",
    'dialog':               "font-family: 'Calibri'; font-size: 20px;",
    'displayFont':          "border: 0; font-family: 'Calibri'; font-size: 20px;",
    'info_pane':            "font-family: 'Calibri'; font-size: 20px;",
    'info':                 "font-family: 'Courier New';",

    'save':                 "background: #0077bb;",
    'delete':               "background: #ff0000;",
    'new':                  "background: #00aa00;",

    'progressBar':          "QProgressBar, QProgressBar::Chunk {background-color: #00aa00; color: #000000}",

    'neutral':              "color: "+UNI_PALETTE.B6+";",
    'profit':               "color: #00ff00;",
    'loss':                 "color: #ff0000;",

    'entry':                "color: #ffff00; background: #000000; font-family: 'Courier New';",
    'disabledEntry':        "color: #aaaaaa; font-family: 'Courier New';",
    'test': """
            QPushButton             {background: #660000;} 
            QPushButton:hover       {background: #bb0000;}
            QPushButton:pressed     {background: #ff0000;}
            """,
    
    'purchase':             'background: #00aa00;',  'purchasetext':              'background: #005d00;',
    'purchase_crypto_fee':  'background: #00aa00;',  'purchase_crypto_feetext':   'background: #005d00;',
    'sale':                 'background: #d80000;',  'saletext':                  'background: #740000;',
    'gift_in':              'background: #44cc44;',  'gift_intext':               'background: #007700;',
    'gift_out':             'background: #44cc44;',  'gift_outtext':              'background: #007700;',
    'expense':              'background: #ee4444;',  'expensetext':               'background: #aa0000;',
    'card_reward':          'background: #aa00aa;',  'card_rewardtext':           'background: #440044;',
    'income':               'background: #aa00aa;',  'incometext':                'background: #440044;',
    'transfer_in':          'background: #4488ff;',  'transfer_intext':           'background: #0044bb;',
    'transfer_out':         'background: #4488ff;',  'transfer_outtext':          'background: #0044bb;',
    'trade':                'background: #ffc000;',  'tradetext':                 'background: #d39700;',
}

def style(styleSheet:str):
    try:    return styleSheetLib[styleSheet]
    except: return ''


def loadIcons():
    global iconlib
    
    #Makes the icons work when the images are stored inside the compiled EXE file
    if hasattr(sys, "_MEIPASS"):    extra_dir = sys._MEIPASS+'/'
    else:                           extra_dir = ''
    iconlib = {
        'size' : QSize(2.5*setting('font_size'), 2.5*setting('font_size')),         # Size of icons
        'size2' : QSize(3*setting('font_size'), 3*setting('font_size')),

        'icon' : QIcon(extra_dir+'icons/logo.png'),
        'logo' : QPixmap(extra_dir+'icons/logo.png'),
        'bullet' : QPixmap(extra_dir+'icons/bullet.png'),

        'new' : QPixmap(extra_dir+'icons/new.png'),
        'load' : QPixmap(extra_dir+'icons/load.png'),
        'save' : QPixmap(extra_dir+'icons/save.png'),
        'settings2' : QPixmap(extra_dir+'icons/settings2.png'),
        'info2' : QPixmap(extra_dir+'icons/info2.png'),
        'profiles' : QPixmap(extra_dir+'icons/profiles.png'),
        'undo' : QPixmap(extra_dir+'icons/undo.png'),
        'redo' : QPixmap(extra_dir+'icons/redo.png'),

        'arrow_up' : QPixmap(extra_dir+'icons/arrow_up.png'),
        'arrow_down' : QPixmap(extra_dir+'icons/arrow_down.png'),
        
        'settings' : QPixmap(extra_dir+'icons/settings.png'),
        'info' : QPixmap(extra_dir+'icons/info.png'),
    }

def icon(icon:str) -> QPixmap:
    return iconlib[icon]



assetinfolib = ( #list of mutable info headers for the Portfolio rendering view
    'ticker','name','class',
    'holdings','price','marketcap',
    'value','volume24h','day_change',
    'day%','week%','month%',
    'portfolio%','cash_flow','net_cash_flow',
    'realized_profit_and_loss','tax_capital_gains','tax_income','unrealized_profit_and_loss',
    'unrealized_profit_and_loss%','average_buy_price'
)

transinfolib = ('date', 'type', 'wallet', 'quantity', 'value', 'price') #list of (currently immutable) info headers for the Asset rendering view

info_format_lib = {
    #Unique to portfolios
    'number_of_transactions': {     'format':'integer', 'color' : None,         'name':'# Transactions',    'headername':'# Transactions'},
    'number_of_assets': {           'format':'integer', 'color' : None,         'name':'# Assets',          'headername':'# Assets'},

    #Unique to portfolios and assets
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

    #Unique to transactions
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

    'quantity':{        'format':'accounting', 'color':'accounting', 'name':'Quantity',      'headername':'Quantity'       },
}

forks_and_duplicate_tickers_lib = { #If your purchase was before this date, it converts the ticker upon loading the JSON file. This is for assets which have changed tickers over time.
    'CGLDzc':   ('CELOzc', '9999/12/31 00:00:00'),
    'LUNAzc':   ('LUNCzc', '2022/05/28 00:00:00')
}

def prettyClasses() -> list:
    '''Returns a list of all asset classes, keyed by their longer prettier name'''
    # This is using LIST COMPREHENSION. Very useful! Shorter code! Pythonic!
    # It allows me to create a list with a for loop in one little line
    return [assetclasslib[c]['name'] for c in assetclasslib] 

def uglyClass(name:str) -> str:
    '''AAlib function which returns the short class tag given its longer name'''
    for c in assetclasslib:
        if assetclasslib[c]['name'] == name:    return c
    return None #Return None if we fail to find the class letter

assetclasslib = {  #List of asset classes, by name tag
    'c' : {
        'name':'Crypto',
        'validTrans' : ('purchase','purchase_crypto_fee','sale','gift_in','gift_out','card_reward','income','expense','transfer_in','transfer_out','trade')
    },
    's' : {
        'name':'Stock',
        'validTrans' : ('purchase','sale','gift_in','gift_out','transfer_in','transfer_out')
    },
    'f' : {
        'name':'Fiat',
        'validTrans' : ('purchase','sale','gift_in','gift_out','transfer_in','transfer_out') 
    }
}

def uglyTrans(pretty:str) -> str:
    '''AAlib function which returns the program's name for a transaction type from its pretty type name'''
    for ugly in pretty_trans:
        if pretty_trans[ugly] == pretty: return ugly

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
    'purchase':             ('type', 'date', 'wallet', 'description',               'loss_quantity',                            'fee_quantity',              'gain_asset', 'gain_quantity'),
    'purchase_crypto_fee':  ('type', 'date', 'wallet', 'description',               'loss_quantity',               'fee_asset', 'fee_quantity', 'fee_price', 'gain_asset', 'gain_quantity'              ),
    'sale':                 ('type', 'date', 'wallet', 'description', 'loss_asset', 'loss_quantity',                            'fee_quantity',                            'gain_quantity'),
    'gift_out':             ('type', 'date', 'wallet', 'description', 'loss_asset', 'loss_quantity',               'fee_asset', 'fee_quantity', 'fee_price'),
    'gift_in':              ('type', 'date', 'wallet', 'description',                                                                                        'gain_asset', 'gain_quantity', 'gain_price'),
    'card_reward':          ('type', 'date', 'wallet', 'description',                                                                                        'gain_asset', 'gain_quantity', 'gain_price'),
    'income':               ('type', 'date', 'wallet', 'description',                                                                                        'gain_asset', 'gain_quantity', 'gain_price'),
    'expense':              ('type', 'date', 'wallet', 'description', 'loss_asset', 'loss_quantity', 'loss_price', 'fee_asset', 'fee_quantity', 'fee_price'),
    'transfer_out':         ('type', 'date', 'wallet', 'description', 'loss_asset', 'loss_quantity',               'fee_asset', 'fee_quantity', 'fee_price',                                            ),
    'transfer_in':          ('type', 'date', 'wallet', 'description',                                              'fee_asset', 'fee_quantity', 'fee_price', 'gain_asset', 'gain_quantity'              ),
    'trade':                ('type', 'date', 'wallet', 'description', 'loss_asset', 'loss_quantity', 'loss_price', 'fee_asset', 'fee_quantity', 'fee_price', 'gain_asset', 'gain_quantity'              ),
}


timezones = {
    'GMT':  ('Greenwich Mean Time',                     0, 0),
    'UTC':  ('Universal Coordinated Time',              0, 0),
    'ECT':  ('European Central Time',                   1, 0),
    'EET':  ('Eastern European Time',                   2, 0),
    'ART':  ('(Arabic) Egypt Standard Time',            2, 0),
    'EAT':  ('Eastern African Time',                    3, 0),
    'MET':  ('Middle East Time',                        3, 30),
    'NET':  ('Near East Time',                          4, 0),
    'PLT':  ('Pakistan Lahore Time',                    5, 0),
    'IST':  ('India Standard Time',                     5, 30),
    'BST':  ('Bangladesh Standard Time',                6, 0),
    'VST':  ('Vietnam Standard Time',                   7, 0),
    'CTT':  ('China Taiwan Time',                       8, 0),
    'JST':  ('Japan Standard Time',                     9, 0),
    'ACT':  ('Australia Central Time',                  9, 30),
    'AET':  ('Australia Eastern Time',                  10, 0),
    'SST':  ('Solomon Standard Time',                   11, 0),
    'NST':  ('New Zealand Standard Time',               12, 0),
    'MIT':  ('Midway Islands Time',                     -11, 0),
    'HST':  ('Hawaii Standard Time',                    -10, 0),
    'AST':  ('Alaska Standard Time',                    -9, 0),
    'PST':  ('Pacific Standard Time',                   -8, 0),
    'PNT':  ('Phoenix Standard Time',                   -7, 0),
    'MST':  ('Mountain Standard Time',                  -7, 0),
    'CST':  ('Central Standard Time',                   -6, 0),
    'EST':  ('Eastern Standard Time',                   -5, 0),
    'IET':  ('Indiana Eastern Standard Time',           -5, 0),
    'PRT':  ('Puerto Rico and US Virgin Islands Time',  -4, 0),
    'CNT':  ('Canada Newfoundland Time',                -3, -30),
    'AGT':  ('Argentina Standard Time',                 -3, 0),
    'BET':  ('Brazil Eastern Time',                     -3, 0),
    'CAT':  ('Central African Time',                    -1, 0),
}

def unix_to_local_timezone(unix:int, tz_override:str=None) -> str:     #Converts internal UNIX/POSIX time integer to user's specified local timezone
    if tz_override: tz = timezones[tz_override]
    else:           tz = timezones[setting('timezone')]
    return str(datetime(1970, 1, 1) + timedelta(hours=tz[1], minutes=tz[2]) + timedelta(seconds=unix))
def timezone_to_unix(iso:str, tz_override:str=None) -> int:
    if tz_override: tz = timezones[tz_override]
    else:           tz = timezones[setting('timezone')]
    return int((datetime.fromisoformat(iso) - timedelta(hours=tz[1], minutes=tz[2]) - datetime(1970, 1, 1)).total_seconds())


defsettingslib = { # A library containing all of the default settings
    'portHeight': 1080,
    'portWidth': 1920,
    'font_size': 16,
    'itemsPerPage':30,
    'startWithLastSaveDir': True,
    'lastSaveDir': '',
    'offlineMode': True,
    'header_portfolio': list(assetinfolib),
    'header_asset': list(transinfolib),
    'sort_asset': ('ticker', False),
    'sort_trans': ('date', False),
    'CMCAPIkey': '',
    'accounting_method': 'hifo',
    'base_currency': 'USDzf',
    'timezone': 'GMT',
}
settingslib = deepcopy(defsettingslib)

def setting(request:str, mult:float=1):
    '''Returns the value of the requested Auto-Accountant setting\n
        Settings include: palette[color], font \n
        For fonts, set mult=float to scale the font relative to the default size. Returns a font size no smaller than 10'''
    if request[0:4] == 'font' and request != 'font_size':
        if int(settingslib[request][1] * mult) < 10: #10 is the minimum font size
            return (settingslib[request][0], 10)
        return (settingslib[request][0], int(settingslib[request][1] * mult))
    return settingslib[request]

def set_setting(request:str, newValue):
    settingslib[request] = newValue

def saveSettings():
    with open('settings.json', 'w') as file:
        json.dump(settingslib, file, indent=4, sort_keys=True)

def loadSettings():
    global settingslib
    settingslib = deepcopy(defsettingslib)
    try:
        with open('settings.json', 'r') as file:
            settings_JSON = json.load(file)
        for setting in defsettingslib:
            try:    
                if type(settingslib[setting])==type(settings_JSON[setting]): settingslib[setting] = settings_JSON[setting]
            except: pass
    except:
        print('||ERROR|| Could not load settings.json, reverting to default settings')


