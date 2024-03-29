
# Python default libraries
import sys, os, json, time, webbrowser, copy, requests, math, textwrap, glob
from enum import Enum
from datetime import datetime, timedelta, timezone
from copy import deepcopy
from functools import partial as p
from typing import List, Dict, Any, Tuple
from io import StringIO

# Defines precision of DECIMAL objects in the program: specified to be 100 decimals here
import decimal
decimal.getcontext().prec = 100
from decimal import Decimal

# 3rd-party
from PySide6.QtWidgets import (QLabel, QFrame, QGridLayout, QVBoxLayout, QPushButton, QHBoxLayout, QMenu, QMenuBar,
    QApplication, QMainWindow, QDialog, QWidget, QTextEdit, QDateTimeEdit, QLineEdit, QPlainTextEdit,
    QComboBox, QListWidget, QAbstractItemView, QListWidgetItem, QFileDialog, QProgressBar, QScrollArea)
from PySide6.QtGui import (QPixmap, QFont, QIcon, QKeySequence, QWheelEvent, QMouseEvent, QFontMetrics, QHoverEvent, QDrag, QDoubleValidator, 
    QDropEvent, QDragEnterEvent, QActionGroup, QAction, QShortcut, QGuiApplication, QTextOption)
from PySide6.QtCore import (Qt, QSize, QTimer, QObject, Signal, Slot, QDateTime, QModelIndex, QEvent, QMargins, QMimeData, QPoint) 
import pandas as pd
import numpy as np

# In-house
import AAstylesheet
from AAstylesheet import UNI_PALETTE

absolute_precision = Decimal(1e-80)
relative_precision = Decimal(1e-8)
def appxEq(x,y):    return abs(Decimal(x)-Decimal(y)) < absolute_precision
def zeroish(x):     return abs(Decimal(x)) < absolute_precision 

def appxEqPrec(x:Decimal,y:Decimal): return abs(x-y) < absolute_precision
def zeroish_prec(x:Decimal):     return abs(x) < absolute_precision 




global iconlib

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

def isValidURL(URL) -> bool:
    """Returns true if pinged URL returns \'200\' status code, false otherwise"""
    return requests.request('GET', URL).status_code == 200

def HTMLify(text, styleSheet:str=''): # Uses a styleSheet to format HTML text
    '''Given text and style sheet, returns string with HTML formatting. QT automatically applies HTML formatting.'''
    if text == '': return ''
    if styleSheet == '': return text
    return f'<font style="{styleSheet}">{text}</font>'


def acceptableTimeDiff(unix_date1:int, unix_date2:int, second_gap:int) -> bool:
    '''True if the dates are within second_gap of eachother. False otherwise.'''
    return abs(unix_date2-unix_date1) < second_gap

def acceptableDifference(v1:Decimal, v2:Decimal, percent_gap:float) -> bool:
    '''True if the values are within percent_gap of eachother. False otherwise.\n
        percent_gap is the maximum multiplier between value1 and value2, where 2 is a 1.02 multiplier, 0.5 is a 1.005 multiplier, and so on. '''
    p = Decimal(1+percent_gap/100)
    return v1 < v2 * p and v1 > v2 / p #If value1 is within percent_gap of value2, then it is acceptable


def format_metric(data, textFormat:str, colorFormat:str=None, charLimit:int=0, styleSheet:str='') -> str:
    """Formats given metric, according to defined styling, with defined maximum charLimit
    \ndata - raw data for metric. must be valid raw datatype
    \ntextFormat - formatting code for text
    \ncolorFormat - formatting code for color
    \ncharLimit - maximum number of characters
    \nstyleSheet - OVERRIDES all HTML formatting when specified (this includes colors)
    """
    # NOTE: for 5600 transactions:
    # TOTAL: 70,000 cycles, ~110ms total
    #   Dynamic metrics: 6500 cycles, ~10ms on reformat metrics (fantastic!!!)
    #   Static metrics: 63500 cycles, `100ms on initialize from JSON
    #   
    #   format_number calls: 40000 cycles, ~83ms on initialize from JSON
    if data==None:  return ''
    
    match textFormat:
        # Input should be int
        case 'date':        toReturn = unix_to_local_timezone(data) # data is an int
        # Input should be str
        case 'type':        toReturn = trans_type_formatting_lib[data]['name']
        case 'desc':        
            if len(data) > 40-3:
                toReturn = f'{data[0:40-3]}...' # description limited to 20 characters at most
            else:
                toReturn = data
        case 'class':       toReturn = class_lib[data]['name']
        case 'alpha':       
            if charLimit and charLimit < len(data): toReturn = f'{data[0:charLimit-3]}...'
            else: toReturn = data
        # Input should be Decimal/float/int
        case 'integer':      
            toReturn = data
        case 'percent':      
            toReturn = format_number(data, '2%', charLimit=charLimit)
        case 'penny':       toReturn = format_number(data, '2f', charLimit=charLimit)
        case 'accounting':   
            if data < 0:    toReturn = f'({format_number(abs(data))})'
            else:           toReturn = f'{format_number(data)}&nbsp;'
        case 'currency':        toReturn = format_number(data, charLimit=charLimit)
        case other:         raise Exception(f'||ERROR|| Unknown metric text formatting style {textFormat}')
         
    # Like 20ms out of 450ms for 230000 cycles
    if styleSheet == '' and colorFormat is not None: # Only calculate color formatting if colorFormat specified and no stylesheet
        match colorFormat:
            case 'type':        styleSheet = style(data)
            case 'profitloss':
                if   data > 0:  styleSheet = style('profit')
                elif data < 0:  styleSheet = style('loss')
                else:           styleSheet = style('neutral')
            case 'accounting':
                if data < 0:    styleSheet = style('loss')
            case other:         raise Exception(f'||ERROR|| Unknown metric color formatting style {colorFormat}')
              
    return HTMLify(toReturn, styleSheet)

scales = (
        # Scale, rescaling, ending word, formatting code
        (.0001,     1,      '',     '3E'),
        (.01,       1,      '',     '4f'),
        (10**6,     1,      '',     '2f'),
        (10**9,     10**6,  ' M',   '1f'),
        (10**12,    10**9,  ' B',   '1f'),
        (10**15,    10**12, ' T',   '1f'),
        (10**18,    10**15, '',     '3E'),
    )

# Currently only used by format_metric
def format_number(number, formatting_code:str=None, charLimit:int=0) -> str:
    '''Returns a string for the formatted version of a number. Mainly to shorten needlessly long numbers.
    \nnumber - the number to be formatted. must be an integer/float/decimal
    \formatting_code - specifies formatting
    \n'''
    # if formatting_code specified, do this
    if formatting_code is not None and charLimit==0: 
        return f"{number:{charLimit},.{formatting_code}}"
    
    if formatting_code and formatting_code[1]=='%': # Specifically for percents, when charLimit specified
         number *= 100
    
    # if charLimit specified, do this
    if number == 0: 
        if charLimit > 0:   return f'{0:{charLimit}f}'
        else:               return '0.00'
    if charLimit > 0:
        num_str = str(number)
        if charLimit > len(num_str.split('.')[0]):     
            return f'{num_str[0:charLimit]:0<{charLimit}}' # integer shorter than charLimit: just cutoff number
        if charLimit > len(num_str):     
            return f'{number:0<{charLimit}}'
        min_scientific_notation_length = 3 + (num_str[0]=='-') + len(f'{number:E}'.split('E')[1])
        if charLimit > min_scientific_notation_length: # (first digit + decimal) + negative sign + scientific notation (E, +/-, power)
            return f'{number:.{min_scientific_notation_length}E}'
        else: raise Exception(f'||ERROR|| Formatting charLimit {charLimit} too short for scientific notation')

    #Otherwise, we have fancy formatting
    ABS_NUM = abs(number) #1/3rd of lag here
    for size in scales:
        if ABS_NUM < size[0]:
            return f"{number/size[1]:,.{size[3]}}{size[2]}"


### LIBRARIES
###==========================================

# STYLESHEETS
styleSheetLib = { # NOTE: Partial transparency doesn't seem to work

    # Good fonts: 
    #   Courier New - monospaced
    #   Inconsolata Medium - monospaced
    #   Calibri
    'universal':            "font-family: 'Calibri';",

    'GRID':                 "border: 0; border-radius: 0;",
    'GRID_data':            "background: transparent; border-color: transparent; font-size: px; font-family: \'Inconsolata Medium\';",
    'GRID_header':          f"background: {UNI_PALETTE.B3}; font-size: px; font-family: \'Inconsolata Medium\';",
    'GRID_error_hover':     "background: #ff0000;",
    'GRID_error_selection': "background: #cc0000;",
    'GRID_error_none':      "background: #880000;",
    'GRID_hover':           f"background: {UNI_PALETTE.A2};",
    'GRID_selection':       f"background: {UNI_PALETTE.A1};",
    'GRID_row_even':        "background: transparent;",
    'GRID_row_odd':         f"background: {UNI_PALETTE.B2};",
    
    'timestamp_indicator_online':   "background-color: transparent; color: #ffffff;",
    'timestamp_indicator_offline':  "background-color: #ff0000; color: #ffffff;",

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

    'neutral':              f"color: {UNI_PALETTE.B6};",
    'profit':               "color: #00ff00;",
    'loss':                 "color: #ff0000;",

    'main_menu_button_disabled':    f"background-color: {UNI_PALETTE.B2};",
    'main_menu_filtering':          """
        QPushButton { background-color: #ff5500; }
        QPushButton:hover { background-color: #ff7700; }
        QPushButton:pressed { background-color: #ff9900; }""",

    'entry':                "color: #ffff00; background: #000000; font-family: 'Courier New';",
    'disabledEntry':        "color: #aaaaaa; font-family: 'Courier New';",

    'purchase':             'background: #00aa00;',  'purchase_dark':              'background: #005d00;',
    'purchase_crypto_fee':  'background: #00aa00;',  'purchase_crypto_fee_dark':   'background: #005d00;',
    'sale':                 'background: #d80000;',  'sale_dark':                  'background: #740000;',
    'gift_in':              'background: #44cc44;',  'gift_in_dark':               'background: #007700;',
    'gift_out':             'background: #44cc44;',  'gift_out_dark':              'background: #007700;',
    'expense':              'background: #ee4444;',  'expense_dark':               'background: #aa0000;',
    'card_reward':          'background: #aa00aa;',  'card_reward_dark':           'background: #440044;',
    'income':               'background: #aa00aa;',  'income_dark':                'background: #440044;',
    'transfer_in':          'background: #4488ff;',  'transfer_in_dark':           'background: #0044bb;',
    'transfer_out':         'background: #4488ff;',  'transfer_out_dark':          'background: #0044bb;',
    'trade':                'background: #ffc000;',  'trade_dark':                 'background: #d39700;',
}
def style(styleSheet:str): # returns the formatting for a given part of the GUI
    try:    return styleSheetLib[styleSheet]
    except: raise Exception(f'||ERROR|| Unknown style, \'{styleSheet}\'')

# ICONS
def loadIcons(): # loads the icons for the GUI
    global iconlib
    
    #Makes the icons work when compiled using PyInstaller
    if hasattr(sys, "_MEIPASS"):    extra_dir = sys._MEIPASS+'\\'
    else:                           extra_dir = ''
    # pulls ALL icons from icons folder
    iconlib = {icon_name.split('\\').pop().split('.')[0]:QPixmap(icon_name) for icon_name in glob.glob(f'{extra_dir}icons\\*.png')}
    iconlib['size'] = QSize(2.5*setting('font_size'), 2.5*setting('font_size'))
    iconlib['size2'] = QSize(3*setting('font_size'), 3*setting('font_size'))
def icon(icon:str) -> QPixmap:      return iconlib[icon] # Returns a given icon for use in the GUI

#List of asset classes, by name tag
class_lib = {  
    'c' : {
        'name':'Crypto',
        'validTrans' : ('purchase','purchase_crypto_fee','sale','gift_in','gift_out','card_reward','income','expense','transfer_in','transfer_out','trade'),
        'yahooFinanceSuffix':'-USD'
    },
    's' : {
        'name':'Stock',
        'validTrans' : ('purchase','sale','gift_in','gift_out','transfer_in','transfer_out'),
        'yahooFinanceSuffix':''
    },
    'f' : {
        'name':'Fiat',
        'validTrans' : ('purchase','sale','gift_in','gift_out','transfer_in','transfer_out'),
        'yahooFinanceSuffix':'USD=X'
    }
}

# DEFAULT TRANSACTION DATA
default_trans_data = {
    'date','type','wallet','description', # description is optional

    'loss_ticker','loss_class','loss_quantity','loss_price',
    'fee_ticker','fee_class','fee_quantity','fee_price', # fees optional
    'gain_ticker','gain_class','gain_quantity','gain_price',
}
trans_metrics_to_format = default_trans_data.union({
    'loss_value','fee_value','gain_value', # values
    'price','value','quantity','balance', # asset-specific metrics
})

# METRICS
# These are all of the available metrics to be displayed in the GRID for each display mode
default_headers = {
    'portfolio' : (
        "name","balance","ticker","price","average_buy_price",
        "portfolio%","marketcap","volume24h","day%","week%","month%",
        "cash_flow","value","projected_cash_flow",
        'unrealized_profit_and_loss',"unrealized_profit_and_loss%","realized_profit_and_loss",
        "cost_basis",
        # Ones I will want to hide
        'class',
        ),
    'asset': ('date', 'type', 'wallet', 'balance', 'quantity', 'value', 'price','description'),
    'grand_ledger': ('date','type','wallet',
        'loss_ticker','loss_class','loss_quantity','loss_price',
        'fee_ticker', 'fee_class', 'fee_quantity','fee_price',
        'gain_ticker','gain_class','gain_quantity','gain_price',
        'description',
        ),
}

metric_formatting_lib = { # Includes formatting information for every metric in the program
    # Shared by portfolios, assets, and transactions
    'value':{                       'asset_specific':True, 'nativeType':'decimal','format': 'penny',      'color' : None,             'name':'Value',             'headername':'Value'},
    'description':{                 'asset_specific':False,'nativeType':'str',    'format': 'desc',       'color' : None,             'name':'Description',       'headername':'Description'},

    #Unique to portfolios and assets
    'day%':{                        'asset_specific':False,'nativeType':'decimal','format': 'percent',    'color' : 'profitloss',     'name':'24-Hour %',         'headername':'24-Hr %'},
    'week%':{                       'asset_specific':False,'nativeType':'decimal','format': 'percent',    'color' : 'profitloss',     'name':'7-Day %',           'headername':'7-Day %'},
    'month%':{                      'asset_specific':False,'nativeType':'decimal','format': 'percent',    'color' : 'profitloss',     'name':'30-Day %',          'headername':'30-Day %'},
    'cash_flow':{                   'asset_specific':False,'nativeType':'decimal','format': 'penny',      'color' : 'profitloss',     'name':'Cash Flow',         'headername':'Cash\nFlow'},
    'projected_cash_flow':{         'asset_specific':False,'nativeType':'decimal','format': 'penny',      'color' : 'profitloss',     'name':'Projected Cash Flow',     'headername':'Projected\nCash Flow'},
    'realized_profit_and_loss':{    'asset_specific':False,'nativeType':'decimal','format': 'penny',      'color' : 'profitloss',     'name':'Realized P&L',      'headername':'Real\nP&L'},
    'unrealized_profit_and_loss':{  'asset_specific':False,'nativeType':'decimal','format': 'penny',      'color' : 'profitloss',     'name':'Unrealized P&L',    'headername':'Unreal\nP&L'},
    'unrealized_profit_and_loss%':{ 'asset_specific':False,'nativeType':'decimal','format': 'percent',    'color' : 'profitloss',     'name':'Unrealized P&L %',  'headername':'Unreal\nP&L %'},
    'number_of_transactions': {     'asset_specific':False,'nativeType':'int',    'format': 'integer',    'color' : None,             'name':'# Transactions',    'headername':'# Transactions'},
    'cost_basis': {                 'asset_specific':False,'nativeType':'decimal','format': 'penny',      'color' : None,             'name':'Cost Basis',        'headername':'Cost\nBasis'},

    #Unique to portfolios
    'number_of_assets': {           'asset_specific':False,'nativeType':'int',    'format':'integer',     'color' : None,             'name':'# Assets',          'headername':'# Assets'},

    # Unique to assets
    'ticker': {                     'asset_specific':False,'nativeType':'str',    'format': 'alpha',      'color' : None,             'name':'Ticker',            'headername':'Ticker'},
    'name':{                        'asset_specific':False,'nativeType':'str',    'format': 'alpha',      'color' : None,             'name':'Name',              'headername':'Name'},
    'class':{                       'asset_specific':False,'nativeType':'str',    'format': 'class',      'color' : None,             'name':'Asset Class',       'headername':'Class'},
    'price':{                       'asset_specific':True, 'nativeType':'decimal','format': 'currency',   'color' : None,             'name':'Price',             'headername':'Spot\nPrice'},
    'marketcap':{                   'asset_specific':False,'nativeType':'decimal','format': 'currency',   'color' : None,             'name':'Market Cap',        'headername':'Market\nCap'},
    'volume24h':{                   'asset_specific':False,'nativeType':'decimal','format': 'currency',   'color' : None,             'name':'24hr Volume',       'headername':'24 Hr\nVolume'},
    'portfolio%':{                  'asset_specific':False,'nativeType':'decimal','format': 'percent',    'color' : None,             'name':'Portfolio Weight',  'headername':'Portfolio\nWeight'},
    'average_buy_price':{           'asset_specific':False,'nativeType':'decimal','format': 'currency',   'color' : None,             'name':'Average Buy Price', 'headername':'Avg Buy\nPrice'},

    # Shared by assets and transactions
    'balance':{         'asset_specific':True, 'nativeType':'decimal','format': 'currency',  'color' : None,       'name':'Balance',       'headername':'Balance'},

    #Unique to transactions
    'date':{            'asset_specific':False,'nativeType':'int',    'format':'date',       'color':None,         'name':'Date (UTC)',    'headername':'Date (UTC)'     },
    'type':{            'asset_specific':False,'nativeType':'str',    'format':'type',       'color':'type',       'name':'Type',          'headername':'Type'           },
    'wallet':{          'asset_specific':False,'nativeType':'str',    'format':'alpha',      'color':None,         'name':'Wallet',        'headername':'Wallet'         },
    'loss_ticker':{     'asset_specific':False,'nativeType':'str',    'format':'alpha',      'color':None,         'name':'Loss Ticker',   'headername':'Loss\nTicker'   },
    'fee_ticker':{      'asset_specific':False,'nativeType':'str',    'format':'alpha',      'color':None,         'name':'Fee Ticker',    'headername':'Fee\nTicker'    },
    'gain_ticker':{     'asset_specific':False,'nativeType':'str',    'format':'alpha',      'color':None,         'name':'Gain Ticker',   'headername':'Gain\nTicker'   },
    'loss_class':{      'asset_specific':False,'nativeType':'str',    'format':'class',      'color':None,         'name':'Loss Class',    'headername':'Loss\nClass'    },
    'fee_class':{       'asset_specific':False,'nativeType':'str',    'format':'class',      'color':None,         'name':'Fee Class',     'headername':'Fee\nClass'     },
    'gain_class':{      'asset_specific':False,'nativeType':'str',    'format':'class',      'color':None,         'name':'Gain Class',    'headername':'Gain\nClass'    },
    'loss_quantity':{   'asset_specific':False,'nativeType':'decimal','format':'accounting', 'color':None,         'name':'Loss Quantity', 'headername':'Loss\nQuantity' },
    'fee_quantity':{    'asset_specific':False,'nativeType':'decimal','format':'accounting', 'color':None,         'name':'Fee Quantity',  'headername':'Fee\nQuantity'  },
    'gain_quantity':{   'asset_specific':False,'nativeType':'decimal','format':'accounting', 'color':None,         'name':'Gain Quantity', 'headername':'Gain\nQuantity' },
    'loss_price':{      'asset_specific':False,'nativeType':'decimal','format':'currency',   'color':None,         'name':'Loss Price',    'headername':'Loss\nPrice'    },
    'fee_price':{       'asset_specific':False,'nativeType':'decimal','format':'currency',   'color':None,         'name':'Fee Price',     'headername':'Fee\nPrice'     },
    'gain_price':{      'asset_specific':False,'nativeType':'decimal','format':'currency',   'color':None,         'name':'Gain Price',    'headername':'Gain\nPrice'    },

    'loss_value':{      'asset_specific':False,'nativeType':'decimal','format':'currency',   'color':None,         'name':'Loss Value',    'headername':'Loss\nValue'    },
    'fee_value':{       'asset_specific':False,'nativeType':'decimal','format':'currency',   'color':None,         'name':'Fee Value',     'headername':'Fee\nValue'     },
    'gain_value':{      'asset_specific':False,'nativeType':'decimal','format':'currency',   'color':None,         'name':'Gain Value',    'headername':'Gain\nValue'    },

    'quantity':{        'asset_specific':True, 'nativeType':'decimal','format':'accounting', 'color':'accounting', 'name':'Quantity',      'headername':'Quantity'       },

    'ERROR':{           'asset_specific':False,'nativeType':'str',    'format':'alpha',      'color':None,         'name':'ERROR',         'headername':'ERROR'       },
}

asset_specific_metrics = [metric for metric in metric_formatting_lib if metric_formatting_lib[metric]['asset_specific']]

metric_desc_lib = { # Includes descriptions for all metrics: this depends on the item which the metric is describing
    'portfolio':{
        #Unique to portfolios
        'number_of_transactions': "The total number of transactions across all assets",
        'number_of_assets': "",

        #Unique to portfolios and assets
        'value': "The USD value of all assets at current market prices.",
        'day%': "The relative change in value over the past day.",
        'week%': "The relative change in value over the past week.",
        'month%': "The relative change in value over the past month.",
        'cash_flow': "The total USD which has gone in/out of all assets. 0$ is breakeven.",
        'projected_cash_flow': "Cash Flow + Value = Net Cash Flow. This is how much profit/loss you would have ever made, if you sold everything you own right now.",
        'realized_profit_and_loss': "Measures the USD gained/lost on sold assets. Comparable to cash flow. ",
        'unrealized_profit_and_loss': "Measures the USD gained on unsold assets since their purchase.",
        'unrealized_profit_and_loss%': "The relative unrealized P&L of your asset. A basic measure of performance since purchasing the asset.",
    }, 
    'asset':{
        #Unique to portfolios and assets
        'value': "The USD value of this asset at current market price.",
        'day%': "The relative change in value over the past day.",
        'week%': "The relative change in value over the past week.",
        'month%': "The relative change in value over the past month.",
        'cash_flow': "The total USD which has gone in/out of this asset. 0$ is breakeven.",
        'projected_cash_flow': "Cash Flow + Value = Proj. Cash Flow. This is how much profit/loss you would have ever made, if you sold everything you own right now.",
        'realized_profit_and_loss': "Measures the USD gained/lost on sold assets. Comparable to cash flow. ",
        'unrealized_profit_and_loss': "Value - Cost Basis = Unreal P&L. Total unrealized P&L for current balance.",
        'unrealized_profit_and_loss%': "Value / Cost Basis = Unreal P&L %. Basic indicator of asset performance. Green means in-profit, red not in-profit.",
        'cost_basis':'Value of the current balance, at time of aquisition',

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
        'description':'Message written by user or importation method',
        'loss_ticker': "The asset lost from this transaction.",
        'fee_ticker': "The asset used to pay the fee.",
        'gain_ticker': "The asset gained from this transaction.",
        'loss_class': "Asset class of the gain asset.",
        'fee_class': "Asset class of the gain asset.",
        'gain_class': "Asset class of the gain asset.",
        'loss_quantity': "The quantity lost of the loss asset.",
        'fee_quantity': "The quantity lost of the fee asset.",
        'gain_quantity': "The quantity gained of the gain asset.",
        'loss_price': "The USD market value of the loss asset at the time of the transaction.",
        'fee_price': "The USD market value of the fee asset at the time of the transaction.",
        'gain_price': "The USD market value of the gain asset at the time of the transaction.",
    
        'balance': "The total quantity held AFTER this transaction.",
        'quantity': "The quantity gained/lost for this asset in this transaction.",
        'value': "The USD value of the tokens involved in this transaction, for this asset.",
        'price': "The USD value per token in this transaction.",
    }
}

# TRANSACTION TYPE
#Dictionary that sorts simultaneous transactions by what makes sense
trans_type_formatting_lib = {  
    'purchase':             {'priority':0,  'name':'Purchase',},#In only
    'purchase_crypto_fee':  {'priority':4,  'name':'Purchase w / Crypto Fee',},#Definitively both
    'sale':                 {'priority':10, 'name':'Sale',},#Out only
    'gift_out':             {'priority':8,  'name':'Gift OUT',},#Out only
    'gift_in':              {'priority':3,  'name':'Gift IN',},#In only
    'card_reward':          {'priority':1,  'name':'Card Reward',},#In only
    'income':               {'priority':2,  'name':'Income',},#In only
    'expense':              {'priority':9,  'name':'Expense',},#Out only
    'transfer_out':         {'priority':6,  'name':'Transfer OUT',},#Kinda both
    'transfer_in':          {'priority':7,  'name':'Transfer IN',},#Kinda both
    'trade':                {'priority':5,  'name':'Trade',},#Definitively both
}
# Certain transaction types always have the same inferred metrics. For example, purchases always have a loss asset of fiat USD, which has a price of 1$
trans_type_static_inference = {
    'purchase':             {'loss_ticker':'USD','loss_class':'f','loss_price':1,'fee_ticker':'USD','fee_class':'f','fee_price':1,},
    'purchase_crypto_fee':  {'loss_ticker':'USD','loss_class':'f','loss_price':1,                   'fee_class':'c',},
    'sale':                 {                                                    'fee_ticker':'USD','fee_class':'f','fee_price':1,'gain_ticker':'USD','gain_class':'f','gain_price':1,},
    'expense':              {}, # Nothing inferrable at all
    'trade':                {}, # Can infer gain price, but this is a dynamic inference
    'transfer_out':         {}, # Nothing inferrable at all
    'transfer_in':          {}, # Nothing inferrable at all
    'gift_out':             {}, # Nothing inferrable at all
    'gift_in':              {}, # Nothing inferrable at all
    'card_reward':          {}, # Nothing inferrable at all
    'income':               {}, # Nothing inferrable at all

}
# Only this data is saved to JSON, depending on transaction type
trans_type_minimal_set = {
    'purchase':             {'type', 'date', 'wallet', 'description',                              'loss_quantity',                                          'fee_quantity',              'gain_ticker', 'gain_class', 'gain_quantity'},
    'purchase_crypto_fee':  {'type', 'date', 'wallet', 'description',                              'loss_quantity',               'fee_ticker', 'fee_class', 'fee_quantity', 'fee_price', 'gain_ticker', 'gain_class', 'gain_quantity'},
    'sale':                 {'type', 'date', 'wallet', 'description', 'loss_ticker', 'loss_class', 'loss_quantity',                                          'fee_quantity',                                           'gain_quantity'},
    'expense':              {'type', 'date', 'wallet', 'description', 'loss_ticker', 'loss_class', 'loss_quantity', 'loss_price', 'fee_ticker', 'fee_class', 'fee_quantity', 'fee_price'},
    'trade':                {'type', 'date', 'wallet', 'description', 'loss_ticker', 'loss_class', 'loss_quantity', 'loss_price', 'fee_ticker', 'fee_class', 'fee_quantity', 'fee_price', 'gain_ticker', 'gain_class', 'gain_quantity'},
    'transfer_out':         {'type', 'date', 'wallet', 'description', 'loss_ticker', 'loss_class', 'loss_quantity',               'fee_ticker', 'fee_class', 'fee_quantity', 'fee_price'},
    'transfer_in':          {'type', 'date', 'wallet', 'description',                                                             'fee_ticker', 'fee_class', 'fee_quantity', 'fee_price', 'gain_ticker', 'gain_class', 'gain_quantity'},
    'gift_out':             {'type', 'date', 'wallet', 'description', 'loss_ticker', 'loss_class', 'loss_quantity',               'fee_ticker', 'fee_class', 'fee_quantity', 'fee_price'},
    'gift_in':              {'type', 'date', 'wallet', 'description',                                                                                                                     'gain_ticker', 'gain_class', 'gain_quantity', 'gain_price'},
    'card_reward':          {'type', 'date', 'wallet', 'description',                                                                                                                     'gain_ticker', 'gain_class', 'gain_quantity', 'gain_price'},
    'income':               {'type', 'date', 'wallet', 'description',                                                                                                                     'gain_ticker', 'gain_class', 'gain_quantity', 'gain_price'},
}

# THIRD PARTY DATA
third_party_source_lib = {
    'Binance' :          {'openFileFormat':'CSV Files (*.csv)'},
    'Coinbase' :         {'openFileFormat':'CSV Files (*.csv)'},
    'Coinbase Pro' :     {'openFileFormat':'CSV Files (*.csv)'},
    'Etherscan' :        {'openFileFormat':'CSV Files (*.csv)', 'twoFileAddendum':(' ETH', ' ERC-20')},
    'Gemini' :           {'openFileFormat':"XLSX Files (*.xlsx)"},
    'Gemini Earn/Grow' : {'openFileFormat':"XLSX Files (*.xlsx)"},
    'Yoroi' :            {'openFileFormat':'CSV Files (*.csv)'},
}

# SETTINGS
settingslib = { # A library containing all of the default settings
    'font_size': 16,                            # Used to determine the scale of several GUI features in the program
    'itemsPerPage':30,                          # Number of items to display on one page
    'max_mementos': 100,                      # Maximum # of saved progress points, before we start deleting the oldest ones 
    'startWithLastSaveDir': True,               # Whether to start with our last opened portfolio, or always open a new one by default
    'lastSaveDir': '',                          # Our last opened portfolio's filepath
    'is_offline': True,                         # Whether or not to start in offline/online mode
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

# ASSETS WHICH HAVE CHANGED TICKERS OVER TIME
forks_and_duplicate_tickers_lib = { #If your purchase was before this date, it converts the ticker upon loading the JSON file. Its possible a new asset took the ticker since.
    'c':{ 
        'CGLD':   ('CELO', timezone_to_unix('9999-12-31 00:00:00', 'UTC')), # Ticker is different on certain platforms
        'LUNA':   ('LUNC', timezone_to_unix('2022-05-28 00:00:00', 'UTC')), # LUNA crash event, May 28 2022, "Terra 2.0"
        }, 
}