

import json
import time
from enum import Enum
from datetime import datetime, timedelta, timezone
from copy import deepcopy
import sys, os
import textwrap
import AAstylesheet
from AAstylesheet import UNI_PALETTE


from PySide6.QtWidgets import (QLabel, QFrame, QGridLayout, QVBoxLayout, QPushButton, QHBoxLayout, QMenu, QMenuBar, QWidgetAction, QButtonGroup,
    QApplication, QMainWindow, QDialog, QMessageBox, QWidget, QTextEdit, QDateTimeEdit, QLineEdit, QPlainTextEdit,
    QComboBox, QListView, QListWidget, QAbstractItemView, QListWidgetItem, QFileDialog, QProgressBar, QScrollArea, QScrollBar, QStyle)
from PySide6.QtGui import (QPixmap, QFont, QIcon, QKeySequence, QWheelEvent, QMouseEvent, QFontMetrics, QHoverEvent, QCursor, QDoubleValidator, QDrag, 
    QDropEvent, QDragEnterEvent, QImage, QPainter, QActionGroup, QAction, QShortcut, QGuiApplication, QTextOption)
from PySide6.QtCore import (Qt, QSize, QTimer, QObject, Signal, Slot, QDateTime, QModelIndex, QEvent, QMargins, QMimeData, QPoint) 

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
        'undo' : [] # List of saves we can revert to if we make mistakes
        } 

MISSINGDATA = '???'


### UTILITY FUNCTIONS
###==========================================
global timestamp
global time_avg
global time_avg_windows
timestamp = 0
time_sum = 0
time_avg_windows = 0

def ttt(string:str='reset', *args, **kwargs):
    '''A timer for measuring program performance.\n
    \n\'reset\' prints the current time then sets to 0, 
    \n\'start\' sets a startpoint, 
    \n\'end\' sets an endpoint,
    \n\'terminate\' is end + reset,
    \n\'avg_save\' adds a start/end delta to a sum, and logs the number of saves,
    \n\'avg_end\' is end + avg_save,
    \n\'report\' reports the average delta length, and number of cycles.
    '''
    global timestamp
    global time_sum
    global time_avg_windows
    match string:
        case 'reset':
            print(str(timestamp) + ' ms')
            time_sum = 0
            time_avg_windows = 0
            timestamp = 0
        case 'start':
            timestamp -= time.time()*1000
        case 'end':
            timestamp += time.time()*1000
        case 'terminate':
            timestamp += time.time()*1000
            ttt('reset')
        case 'avg_save':
            time_sum += timestamp # adds start/end delta to time_sum
            time_avg_windows += 1 # indicates one save has been performed
            timestamp = 0
        case 'avg_end':
            ttt('end')
            ttt('avg_save')
        case 'report':
            if time_avg_windows ==  0: return 'No cycles to report'
            return f'{time_sum/time_avg_windows} ms, on average. \nSample size = {time_avg_windows}.\nTotal time = {time_sum}'

class InvokeMethod(QObject): # Credit: Tim Woocker from on StackOverflow. Allows any thread to tell the main thread to run something
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
    return f'<font style="{styleSheet}">{text}</font>' # Uses an 'f-String', a new Python 3.6 type of string formatting. Nifty!


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
    match style:
        case 'alpha':       toReturn = str(data)
        case 'integer':      
            try:            toReturn = str(int(data))
            except: pass
        case 'percent':      
            try:            toReturn = format_number(float(data)*100, '.2f') + '%'
            except: pass
        case 'penny':      toReturn = format_number(data, '.2f')
        case 'accounting':   
            try:
                if float(data) < 0: toReturn = '('+format_number(abs(data), '.5f')+')'
                else:               toReturn = format_number(data, '.5f')
            except: pass
        case '':           toReturn = format_number(data)

    # Shortens/lengthens the returned string, if there is a character limit
    if charlimit > 0 and len(toReturn) > charlimit:
        if '.' in toReturn and toReturn.index('.') > charlimit: return toReturn.split('.')[0] #Returns the number as an integer, if it is longer than the charlimit
        return toReturn[0:charlimit].removesuffix('.') #Removes the decimal, if its the very last character
    elif charlimit > 0 and len(toReturn) < charlimit:
        if '.' not in toReturn or 'e' in toReturn.lower():  return toReturn + '.' + ('0' * (charlimit - len(toReturn) - 1)) # If there's no decimal, add a decimal, then add 0's until we're at the charlimit
        else:                                               return toReturn + ('0' * (charlimit - len(toReturn))) # If there is a decimal, just add 0's until we're at the charlimit
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
    if standard: return f"{float(number):,{standard}}"

    #Otherwise, we have fancy formatting
    # Probably a clearner way to write this code?
    scales = (
        # Scale, rescaling, ending word, formatting code
        (10**15,    10**15, 'QD',   '.1f'),
        (10**12,    10**12, 'T',    '.1f'),
        (10**9,     10**9,  'B',    '.1f'),
        (10**6,     10**6,  'M',    '.1f'),
        (1,         1,      '',     '.2f'),
        (.0001,     1,      '',     '.4f'),
        (0,         1,      '',     '.3E'),
    )
    for size in scales:
        if abs(number) > size[0]:
            return f"{number/size[1]:,{size[3]}} {size[2]}"
    else:
        return '0.00'



### LIBRARIES
###==========================================

# STYLESHEETS
styleSheetLib = { # NOTE: Partial transparency doesn't seem to work

    # Good fonts: 
    #   Courier New
    #   Inconsolata Medium
    #   Calibri
    'universal':            "font-family: 'Calibri';",

    'GRID':                 "border: 0; border-radius: 0;",
    'GRID_data':          "background: transparent; border-color: transparent; border-width: -2px 2px -2px 2px; font-size: px; font-family: \'Inconsolata Medium\';",
    'GRID_header':           "background: "+UNI_PALETTE.B3+"; font-size: px; font-family: \'Inconsolata Medium\';",
    'GRID_error_hover':     "background: #ff0000;",
    'GRID_error_selection': "background: #cc0000;",
    'GRID_error_none':      "background: #880000;",
    'GRID_hover':           "background: "+UNI_PALETTE.A2+";",
    'GRID_selection':       "background: "+UNI_PALETTE.A1+";",
    'GRID_none':            "color: #ff0000; background: transparent;",
    
    'timestamp_indicator_online':   "background-color: transparent; color: #ffffff;",
    'timestamp_indicator_offline':   "background-color: #ff0000; color: #ffffff;",

    'title':                "background-color: transparent; color: #ffff00; font-family: 'Calibri'; font-size: 30px;",
    'subtitle':             "background-color: transparent; color: #ffff00; font-family: 'Calibri'; font-size: 15px;",
    'error':                "background-color: transparent; color: #ff0000; font-family: 'Courier New'; font-size: 15px;",
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

    'main_menu_button_disabled':    "background-color: "+UNI_PALETTE.B2+";",
    'main_menu_filtering':          "background-color: #ff5500;",
    'main_menu_button_enabled':     "",

    'entry':                "color: #ffff00; background: #000000; font-family: 'Courier New';",
    'disabledEntry':        "color: #aaaaaa; font-family: 'Courier New';",

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
def style(styleSheet:str): # returns the formatting for a given part of the GUI
    try:    return styleSheetLib[styleSheet]
    except: return ''

# ICONS
def loadIcons(): # loads the icons for the GUI
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
        'filter' : QPixmap(extra_dir+'icons/filter.png'),
        'undo' : QPixmap(extra_dir+'icons/undo.png'),
        'redo' : QPixmap(extra_dir+'icons/redo.png'),

        'arrow_up' : QPixmap(extra_dir+'icons/arrow_up.png'),
        'arrow_down' : QPixmap(extra_dir+'icons/arrow_down.png'),
        
        'settings' : QPixmap(extra_dir+'icons/settings.png'),
        'info' : QPixmap(extra_dir+'icons/info.png'),
    }
def icon(icon:str) -> QPixmap:      return iconlib[icon] # Returns a given icon for use in the GUI

# Copy of default values for Transaction object stored to improve efficiency
default_trans_data = {
    'date' :            None,
    'type' :            None,
    'wallet' :          None,
    'description' :     '',

    'loss_asset' :      None,
    'loss_quantity' :   None,
    'loss_price' :      None,
    'fee_asset' :       None,
    'fee_quantity' :    None,
    'fee_price' :       None,
    'gain_asset' :      None,
    'gain_quantity' :   None,
    'gain_price' :      None,
}
default_trans_metrics = dict(default_trans_data)
default_trans_metrics.update({
    'loss_value':       0,
    'fee_value':        0,
    'gain_value':       0,

    'basis_price':      0,      #The cost basis price

    'price':    {},     #Price, value, quantity by asset, for displaying
    'value':    {},
    'quantity': {},
    'balance': {},
    'all_assets':[],

    'hash':             None,
    'missing':          [],
    'dest_wallet':      None, # Re-calculated for transfers on metric calculation
})

# These are all of the available metrics to be displayed in the GRID for each display mode
default_headers = {
    'portfolio' : (
        "name","balance","ticker","price","average_buy_price",
        "portfolio%","marketcap","volume24h","day%","week%","month%",
        "cash_flow","value","projected_cash_flow",
        "unrealized_profit_and_loss%","realized_profit_and_loss",
        # Ones I will want to hide
        'class','day_change','tax_capital_gains','tax_income','unrealized_profit_and_loss',
        ),
    'asset': ('date', 'type', 'wallet', 'balance', 'quantity', 'value', 'price'),
    'grand_ledger': ('date','type','wallet',
        'loss_asset','loss_quantity','loss_price',
        'fee_asset','fee_quantity','fee_price',
        'gain_asset','gain_quantity','gain_price'
        ),
}


metric_formatting_lib = { # Includes formatting information for every metric in the program
    # Shared by portfolios, assets, and transactions
    'value':{                       'format': 'penny',      'color' : None,             'name':'Value',             'headername':'Value'},
    'description':{                 'format': 'alpha',      'color' : None,             'name':'Description',       'headername':'Description'},

    #Unique to portfolios and assets
    'day_change':{                  'format': 'penny',      'color' : 'profitloss',     'name':'24-Hour Δ',         'headername':'24-Hr Δ'},
    'day%':{                        'format': 'percent',    'color' : 'profitloss',     'name':'24-Hour %',         'headername':'24-Hr %'},
    'week%':{                       'format': 'percent',    'color' : 'profitloss',     'name':'7-Day %',           'headername':'7-Day %'},
    'month%':{                      'format': 'percent',    'color' : 'profitloss',     'name':'30-Day %',          'headername':'30-Day %'},
    'cash_flow':{                   'format': 'penny',      'color' : 'profitloss',     'name':'Cash Flow',         'headername':'Cash\nFlow'},
    'projected_cash_flow':{         'format': 'penny',      'color' : 'profitloss',     'name':'Projected Cash Flow',     'headername':'Projected\nCash Flow'},
    'realized_profit_and_loss':{    'format': 'penny',      'color' : 'profitloss',     'name':'Realized P&L',      'headername':'Real\nP&L'},
    'tax_capital_gains':{           'format': 'penny',      'color' : 'profitloss',     'name':'Capital Gains',     'headername':'Capital\nGains'},
    'tax_income':{                  'format': 'penny',      'color' : None,             'name':'Income',            'headername':'Taxable\nIncome'},
    'unrealized_profit_and_loss':{  'format': 'penny',      'color' : 'profitloss',     'name':'Unrealized P&L',    'headername':'Unreal\nP&L'},
    'unrealized_profit_and_loss%':{ 'format': 'percent',    'color' : 'profitloss',     'name':'Unrealized P&L %',  'headername':'Unreal\nP&L %'},
    'number_of_transactions': {     'format':'integer',     'color' : None,             'name':'# Transactions',    'headername':'# Transactions'},

    #Unique to portfolios
    'number_of_assets': {           'format':'integer',     'color' : None,             'name':'# Assets',          'headername':'# Assets'},

    # Unique to assets
    'ticker': {                     'format': 'alpha',      'color' : None,             'name':'Ticker',            'headername':'Ticker'},
    'name':{                        'format': 'alpha',      'color' : None,             'name':'Name',              'headername':'Name'},
    'class':{                       'format': 'alpha',      'color' : None,             'name':'Asset Class',       'headername':'Class'},
    'price':{                       'format': '',           'color' : None,             'name':'Price',             'headername':'Spot\nPrice'},
    'marketcap':{                   'format': '',           'color' : None,             'name':'Market Cap',        'headername':'Market\nCap'},
    'volume24h':{                   'format': '',           'color' : None,             'name':'24hr Volume',       'headername':'24 Hr\nVolume'},
    'portfolio%':{                  'format': 'percent',    'color' : None,             'name':'Portfolio Weight',  'headername':'Portfolio\nWeight'},
    'average_buy_price':{           'format': '',           'color' : None,             'name':'Average Buy Price', 'headername':'Avg Buy\nPrice'},

    # Shared by assets and transactions
    'balance':{                    'format': '',           'color' : None,             'name':'Balance',          'headername':'Balance'},

    #Unique to transactions
    'date':{            'format':'alpha',      'color':None,         'name':'Date (UTC)',    'headername':'Date (UTC)'     },
    'type':{            'format':'alpha',      'color':'type',       'name':'Type',          'headername':'Type'           },
    'wallet':{          'format':'alpha',      'color':None,         'name':'Wallet',        'headername':'Wallet'         },
    'loss_asset':{      'format':'alpha',      'color':None,         'name':'Loss Asset',    'headername':'Loss\nAsset'    },
    'fee_asset':{       'format':'alpha',      'color':None,         'name':'Fee Asset',     'headername':'Fee\nAsset'     },
    'gain_asset':{      'format':'alpha',      'color':None,         'name':'Gain Asset',    'headername':'Gain\nAsset'    },
    'loss_ticker':{     'format':'alpha',      'color':None,         'name':'Loss Ticker',    'headername':'Loss\nTicker'    },
    'fee_ticker':{      'format':'alpha',      'color':None,         'name':'Fee Ticker',     'headername':'Fee\nTicker'     },
    'gain_ticker':{     'format':'alpha',      'color':None,         'name':'Gain Ticker',    'headername':'Gain\nTicker'    },
    'loss_class':{      'format':'alpha',      'color':None,         'name':'Loss Class',    'headername':'Loss\nClass'    },
    'fee_class':{       'format':'alpha',      'color':None,         'name':'Fee Class',     'headername':'Fee\nClass'     },
    'gain_class':{      'format':'alpha',      'color':None,         'name':'Gain Class',    'headername':'Gain\nClass'    },
    'loss_quantity':{   'format':'accounting', 'color':None,         'name':'Loss Quantity', 'headername':'Loss\nQuantity' },
    'fee_quantity':{    'format':'accounting', 'color':None,         'name':'Fee Quantity',  'headername':'Fee\nQuantity'  },
    'gain_quantity':{   'format':'accounting', 'color':None,         'name':'Gain Quantity', 'headername':'Gain\nQuantity' },
    'loss_price':{      'format':'',           'color':None,         'name':'Loss Price',    'headername':'Loss\nPrice'    },
    'fee_price':{       'format':'',           'color':None,         'name':'Fee Price',     'headername':'Fee\nPrice'     },
    'gain_price':{      'format':'',           'color':None,         'name':'Gain Price',    'headername':'Gain\nPrice'    },

    'loss_value':{      'format':'',           'color':None,         'name':'Loss Value',    'headername':'Loss\nValue'    },
    'fee_value':{       'format':'',           'color':None,         'name':'Fee Value',     'headername':'Fee\nValue'     },
    'gain_value':{      'format':'',           'color':None,         'name':'Gain Value',    'headername':'Gain\nValue'    },

    'quantity':{        'format':'accounting', 'color':'accounting', 'name':'Quantity',      'headername':'Quantity'       },

    'ERROR':{           'format':'alpha',      'color':None,         'name':'ERROR',         'headername':'ERROR'       },
}

metric_desc_lib = { # Includes descriptions for all metrics: this depends on whether you are looking at the portfolio overall, individual assets, or individual transactions
    'portfolio':{
        #Unique to portfolios
        'number_of_transactions': "The total number of transactions across all assets",
        'number_of_assets': "",

        #Unique to portfolios and assets
        'value': "The USD value of all assets at current market prices.",
        'day_change': "The USD value gained/lost over the past day.",
        'day%': "The relative change in value over the past day.",
        'week%': "The relative change in value over the past week.",
        'month%': "The relative change in value over the past month.",
        'cash_flow': "The total USD which has gone in/out of all assets. 0$ is breakeven.",
        'projected_cash_flow': "Cash Flow + Value = Net Cash Flow. This is how much profit/loss you would have ever made, if you sold everything you own right now.",
        'tax_capital_gains': "The total value taxable as capital gains.",
        'tax_income': "The total value taxable as income.",
        'realized_profit_and_loss': "Measures the USD gained/lost on sold assets. Comparable to cash flow. ",
        'unrealized_profit_and_loss': "Measures the USD gained on unsold assets since their purchase.",
        'unrealized_profit_and_loss%': "The relative unrealized P&L of your asset. A basic measure of performance since purchasing the asset.",
    }, 
    'asset':{
        #Unique to portfolios and assets
        'value': "The USD value of this asset at current market price.",
        'day_change': "The absolute change in value over the past day.",
        'day%': "The relative change in value over the past day.",
        'week%': "The relative change in value over the past week.",
        'month%': "The relative change in value over the past month.",
        'cash_flow': "The total USD which has gone in/out of this asset. 0$ is breakeven.",
        'projected_cash_flow': "Cash Flow + Value = Proj. Cash Flow. This is how much profit/loss you would have ever made, if you sold everything you own right now.",
        'tax_capital_gains': "The total value taxable as capital gains.",
        'tax_income': "The total value taxable as income.",
        'realized_profit_and_loss': "Measures the USD gained/lost on sold assets. Comparable to cash flow. ",
        'unrealized_profit_and_loss': "Measures the USD gained on unsold assets since their purchase.",
        'unrealized_profit_and_loss%': "The relative unrealized P&L of your asset. A basic measure of performance since purchasing the asset.",

        # Unique to assets
        'ticker': "The ticker for this asset. BTC, ETH, etc.",
        'name': "The longer name of the asset. Bitcoin, Ethereum, etc.",
        'class': "The asset class: a stock, cryptocurrency, or fiat currency.",
        'price': "The current market value of this asset, per unit",
        'marketcap': "The total USD invested into this asset.",
        'balance': "The total units owned of this asset (tokens, stocks, etc.)",
        'volume24h': "The USD which has gone into/out of the asset in the past day.",
        'portfolio%': "The percentage of USD which this asset makes up in your overall portfolio.",
        'average_buy_price': "The average market price of all your assets at the time of their purchase.",
    }, 
    'transaction':{
        #Unique to transactions
        'date': "The date and time this transaction occurred. Note: Order fills are lumped together if they occurred simultaneously.",
        'type': "The nature of the transaction: purchase, sale, trade, etc.",
        'wallet': "The wallet or platform on which the transaction was held.",
        'loss_asset': "The asset lost from this transaction.",
        'loss_quantity': "The quantity lost of the loss asset.",
        'loss_price': "The USD market value of the loss asset at the time of the transaction.",
        'fee_asset': "The asset used to pay the fee.",
        'fee_quantity': "The quantity lost of the fee asset.",
        'fee_price': "The USD market value of the fee asset at the time of the transaction.",
        'gain_asset': "The asset gained from this transaction.",
        'gain_quantity': "The quantity gained of the gain asset.",
        'gain_price': "The USD market value of the gain asset at the time of the transaction.",
    
        'balance': "The total quantity held AFTER this transaction.",
        'quantity': "The quantity gained/lost for this asset in this transaction.",
        'value': "The USD value of the tokens involved in this transaction, for this asset.",
        'price': "The USD value per token in this transaction.",
    }
}

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

# List of assets which have changed tickers or have multiple tickers, so we can use the right one
forks_and_duplicate_tickers_lib = { #If your purchase was before this date, it converts the ticker upon loading the JSON file. Its possible a new asset took the ticker since.
    'CGLDzc':   ('CELOzc', '9999/12/31 00:00:00'), # Ticker is different on certain platforms
    'LUNAzc':   ('LUNCzc', '2022/05/28 00:00:00'),
}


# Translation dictionary between internal and display names for transaction types
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


#Dictionary that sorts simultaneous transactions by what makes sense
trans_priority = {  
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

# Indicates data to be stored, for each type of transaction
valid_transaction_data_lib = {
    'purchase':             ('type', 'date', 'wallet', 'description',               'loss_quantity',                            'fee_quantity',              'gain_asset', 'gain_quantity'),
    'purchase_crypto_fee':  ('type', 'date', 'wallet', 'description',               'loss_quantity',               'fee_asset', 'fee_quantity', 'fee_price', 'gain_asset', 'gain_quantity'              ),
    'sale':                 ('type', 'date', 'wallet', 'description', 'loss_asset', 'loss_quantity',                            'fee_quantity',                            'gain_quantity'),
    'expense':              ('type', 'date', 'wallet', 'description', 'loss_asset', 'loss_quantity', 'loss_price', 'fee_asset', 'fee_quantity', 'fee_price'),
    'trade':                ('type', 'date', 'wallet', 'description', 'loss_asset', 'loss_quantity', 'loss_price', 'fee_asset', 'fee_quantity', 'fee_price', 'gain_asset', 'gain_quantity'              ),
    'transfer_out':         ('type', 'date', 'wallet', 'description', 'loss_asset', 'loss_quantity',               'fee_asset', 'fee_quantity', 'fee_price',                                            ),
    'transfer_in':          ('type', 'date', 'wallet', 'description',                                              'fee_asset', 'fee_quantity', 'fee_price', 'gain_asset', 'gain_quantity'              ),
    'gift_out':             ('type', 'date', 'wallet', 'description', 'loss_asset', 'loss_quantity',               'fee_asset', 'fee_quantity', 'fee_price'),
    'gift_in':              ('type', 'date', 'wallet', 'description',                                                                                        'gain_asset', 'gain_quantity', 'gain_price'),
    'card_reward':          ('type', 'date', 'wallet', 'description',                                                                                        'gain_asset', 'gain_quantity', 'gain_price'),
    'income':               ('type', 'date', 'wallet', 'description',                                                                                        'gain_asset', 'gain_quantity', 'gain_price'),
}


# TIMEZONES
timezones = {
    'GMT':  ('[UTC+0] Greenwich Mean Time',                     0, 0),
    'UTC':  ('[UTC+0] Universal Coordinated Time',              0, 0),
    'ECT':  ('[UTC+1] European Central Time',                   1, 0),
    'EET':  ('[UTC+2] Eastern European Time',                   2, 0),
    'ART':  ('[UTC+2] (Arabic) Egypt Standard Time',            2, 0),
    'EAT':  ('[UTC+3] Eastern African Time',                    3, 0),
    'MET':  ('[UTC+3:30] Middle East Time',                     3, 30),
    'NET':  ('[UTC+4] Near East Time',                          4, 0),
    'PLT':  ('[UTC+5] Pakistan Lahore Time',                    5, 0),
    'IST':  ('[UTC+5:30] India Standard Time',                  5, 30),
    'BST':  ('[UTC+6] Bangladesh Standard Time',                6, 0),
    'VST':  ('[UTC+7] Vietnam Standard Time',                   7, 0),
    'CTT':  ('[UTC+8] China Taiwan Time',                       8, 0),
    'JST':  ('[UTC+9] Japan Standard Time',                     9, 0),
    'ACT':  ('[UTC+9:30] Australia Central Time',               9, 30),
    'AET':  ('[UTC+10] Australia Eastern Time',                 10, 0),
    'SST':  ('[UTC+11] Solomon Standard Time',                  11, 0),
    'NST':  ('[UTC+12] New Zealand Standard Time',              12, 0),
    'MIT':  ('[UTC-11] Midway Islands Time',                    -11, 0),
    'HST':  ('[UTC-10] Hawaii Standard Time',                   -10, 0),
    'AST':  ('[UTC-9] Alaska Standard Time',                    -9, 0),
    'PST':  ('[UTC-8] Pacific Standard Time',                   -8, 0),
    'PNT':  ('[UTC-7] Phoenix Standard Time',                   -7, 0),
    'MST':  ('[UTC-7] Mountain Standard Time',                  -7, 0),
    'CST':  ('[UTC-6] Central Standard Time',                   -6, 0),
    'EST':  ('[UTC-5] Eastern Standard Time',                   -5, 0),
    'IET':  ('[UTC-5] Indiana Eastern Standard Time',           -5, 0),
    'PRT':  ('[UTC-4] Puerto Rico and US Virgin Islands Time',  -4, 0),
    'CNT':  ('[UTC-3:30] Canada Newfoundland Time',             -3, -30),
    'AGT':  ('[UTC-3] Argentina Standard Time',                 -3, 0),
    'BET':  ('[UTC-3] Brazil Eastern Time',                     -3, 0),
    'CAT':  ('[UTC-1] Central African Time',                    -1, 0),
}
def unix_to_local_timezone(unix:int, tz_override:str=None) -> str:     #Converts internal UNIX/POSIX time integer to user's specified local timezone
    if tz_override: tz = timezones[tz_override]
    else:           tz = timezones[setting('timezone')]
    return str(datetime(1970, 1, 1) + timedelta(hours=tz[1], minutes=tz[2], seconds=unix))
def timezone_to_unix(iso:str, tz_override:str=None) -> int:
    iso = iso[0:19].replace('T',' ').replace('Z','') # remove poor formatting where relevant
    if tz_override: tz = timezones[tz_override]
    else:           tz = timezones[setting('timezone')]
    return int((datetime.fromisoformat(iso) - timedelta(hours=tz[1], minutes=tz[2]) - datetime(1970, 1, 1)).total_seconds())

# SETTINGS
settingslib = { # A library containing all of the default settings
    'font_size': 16,                            # Used to determine the scale of several GUI features in the program
    'itemsPerPage':30,                          # Number of items to display on one page
    'max_undo_saves': 100,                      # Maximum # of saved progress points, before we start deleting the oldest ones 
    'startWithLastSaveDir': True,               # Whether to start with our last opened portfolio, or always open a new one by default
    'lastSaveDir': '',                          # Our last opened portfolio's filepath
    'offlineMode': True,                        # Whether or not to start in offline/online mode
    'header_portfolio': list(default_headers['portfolio']),        # List of headers currently displayed when showing the portfolio
    'header_asset': list(default_headers['asset']),                # List of headers currently displayed when showing an asset
    'header_grand_ledger': list(default_headers['grand_ledger']),  # List of headers currently displayed when showing the grand ledger
    'sort_portfolio': ['ticker', False],        # Which column to sort our portfolio by, and whether this ought to be in reverse order
    'sort_asset': ['date', False],              # Which column to sort our asset by, and whether this ought to be in reverse order
    'sort_grand_ledger': ['date', False],       # Which column to sort our grand ledger by, and whether this ought to be in reverse order
    'CMCAPIkey': '',                            # Our CoinMarketCap API key, so we can get current crypto market data
    'accounting_method': 'hifo',                # Accounting method to use when performing automated calculations
    'timezone': 'GMT',                          # Timezone to report times in. Times are saved permanently in UNIX.
}
def setting(request:str, mult:float=1):
    '''Returns the value of the requested Auto-Accountant setting\n
        Settings include: palette[color], font \n
        For fonts, set mult=float to scale the font relative to the default size. Returns a font size no smaller than 10'''
    if request[0:4] == 'font' and request != 'font_size':
        if int(settingslib[request][1] * mult) < 10: #10 is the minimum font size
            return (settingslib[request][0], 10)
        return (settingslib[request][0], int(settingslib[request][1] * mult))
    return settingslib[request]
def set_setting(setting:str, newValue):     settingslib[setting] = newValue
def saveSettings():
    with open('settings.json', 'w') as file:
        json.dump(settingslib, file, indent=4, sort_keys=True)
def loadSettings():
    '''Loads all settings for the program, if the file can be found. This method should only ever be called once.'''
    global settingslib
    # Tries to open our settings JSON file. If this fails, 
    try:
        with open('settings.json', 'r') as file:
            settings_JSON = json.load(file)
    except:
        print('||ERROR|| Could not load settings.json, reverting to default settings')
        return
    
    # Tries to load each setting. We perform a minimal check just to make sure we have the right datatype. This doesn't prevent all errors, however.
    for setting in settingslib:
        try:    
            if type(settingslib[setting])==type(settings_JSON[setting]): 
                set_setting(setting, settings_JSON[setting])
        except: pass 


