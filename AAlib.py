from AAlib import *
import json
import time

import tkinter as tk

global iconlib

PERM = {} #Universal permanent savedata dictionary

TEMP = { #Universal temporary data dictionary
        "metrics" : {},
        "widgets" : {},
        "undo" : [{"assets" : {},"wallets" : {},"profiles" : {}}]
        } 
TEMP["undo"].extend([0]*99)



### UTILITY FUNCTIONS
###==========================================
global timestamp
timestamp = 0

def ttt(string="reset"):
    """\'reset\' prints the current time then sets to 0, \'start\' subtracts a startpoint, \'end\' adds an endpoint"""
    global timestamp
    if string == "reset":
        print(str(timestamp) + " ms")
        timestamp = 0
    elif string == "start":
        timestamp -= time.time()
    elif string == "end":
        timestamp += time.time()

def format_number(number, standard=None):
    #If the number isn't a number, it might be missing market data
    try: number = float(number)
    except: return "MISSINGDATA"

    #If we set a certain formatting standard, then its this
    if standard != None:
        return format(float(number), standard)

    negative = 1
    if number < 0:
        negative = -1
        number = -number
    #Otherwise, we have fancy formatting
    if number >= 1000000:   #If number greater than 1 million, use scientific notation with 3 values of meaning after the decimal
        return format(negative*number,'.3E')
    elif number >= 1:       #If number greater than 1, show all digits and 2 following the decimal
        return format(negative*number, '.2f')
    elif number >= .0001:   #If the number is tiny and greater than 0.0001, show those 4 digits following the decimal
        return format(negative*number, '.4f')
    elif number > 0:        #If number less than .0001, use scientific notation with 3 values of meaning after the decimal
        return format(negative*number,'.3E')
    else:
        return "0.00"



### LIBRARIES
###==========================================
settingslib = {
    "font": ["Courier New",20],
    "lastSaveDir": "C:/Users/sevan/Desktop/Auto-Accountant/TEST3.JSON",
    "offlineMode": True,
    "orientation": "rows",
    "portHeight": 1080,
    "portWidth": 1920,
    "sort_asset": "alpha",
    "sort_trans": "alpha",
    "startWithLastSaveDir": True,
    "tooltipFade": 20,
    "tooltipPopup": 1
}

palettelib = {      #standardized colors for the whole program
        "error":"#ff00ff",

        "light":        "#0066aa",  #555555
        "dark":         "#003355",  #333333
        "accent":       "#550000",
        "accentdark":   "#400000",

        "entry":        "#000000",
        "entrycursor":  "#ffffff",
        "entrytext":    "#ffff00",

        "scrollnotch":"#f0f0f0",
        "tooltipbg" : "#fff0dd",
        "tooltipfg" : "#660000",

        "gift":     "#44cc44",  "gifttext":     "#007700",
        "expense":  "#ee4444",  "expensetext":  "#aa0000",
        "purchase": "#00aa00",  "purchasetext": "#005d00",
        "sale":     "#d80000",  "saletext":     "#740000",
        "stake":    "#aa00aa",  "staketext":    "#440044",
        "transfer": "#4488ff",  "transfertext": "#0044bb"
    }

def initializeIcons():  #unfortunately, this has to be a function, as it has to be declared AFTER the first tkinter instance is initialized
    global iconlib
    fs = int(225/settings("font")[1])
    fs15=int(fs*1.5)
    iconlib = {
        "new" :  tk.PhotoImage(format="PNG", file="icons/new.png").subsample(fs,fs),
        "load" : tk.PhotoImage(format="PNG", file="icons/load.png").subsample(fs,fs),
        "save" : tk.PhotoImage(format="PNG", file="icons/save.png").subsample(fs,fs),
        "settings2" : tk.PhotoImage(format="PNG", file="icons/settings2.png").subsample(fs,fs),
        "info2" : tk.PhotoImage(format="PNG", file="icons/info2.png").subsample(fs,fs),
        "profiles" : tk.PhotoImage(format="PNG", file="icons/profiles.png").subsample(fs,fs),
        "undo" : tk.PhotoImage(format="PNG", file="icons/undo.png").subsample(fs,fs),
        "redo" : tk.PhotoImage(format="PNG", file="icons/redo.png").subsample(fs,fs),
        
        "settings" : tk.PhotoImage(format="PNG", file="icons/settings.png").subsample(fs15,fs15),
        "info" : tk.PhotoImage(format="PNG", file="icons/info.png").subsample(fs15,fs15),
    }

assetclasslib = {  #List of asset classes, by name tag
    "c" : {
        "name":"Cryptocurrency",
        "validTrans" : ["purchase","sale","gift","expense","stake","transfer"] 
    },
    "s" : {
        "name":"Stock",
        "validTrans" : ["purchase","sale","gift","transfer"] 
    }
}

translib = {    #list of data to permanently retain for each transaction type
    "purchase":     ["date", "wallet",            "tokens", "usd",                       "desc"],
    "sale":         ["date", "wallet",            "tokens", "usd",                       "desc"],
    "gift":         ["date", "wallet",            "tokens",        "price",              "desc"],
    "expense":      ["date", "wallet",            "tokens",        "price",              "desc"],
    "stake":        [        "wallet",            "tokens",                 "stakeType", "desc"],
    "transfer":     ["date", "wallet", "wallet2",                                        "desc"],
}


def settings(request, mult=1, set=None):
    """Returns the value of the requested Auto-Accountant setting\n
        Settings include: palette[color], font \n
        For fonts, set mult=float to scale the font relative to the default size. Returns a font size no smaller than 10"""
    if set != None:
        settingslib[request] = set
        return
    if request == "font":
        if int(settingslib["font"][1] * mult) < 10:
            return (settingslib["font"][0], 10)
        return (settingslib["font"][0], int(settingslib["font"][1] * mult))
    return settingslib[request]

def saveSettings():
    json.dump(settingslib, open("settings.json", 'w'), indent=4, sort_keys=True)

def loadSettings():
    global settingslib
    try:
        loaded_settings = json.load(open("settings.json", 'r'))
        for setting in loaded_settings:
            settingslib[setting] = loaded_settings[setting]
    except:
        print("||ERROR|| Could not load settings.json, using default settings")

def palette(color):
    return palettelib[color]

def icons(icon):
    return iconlib[icon]