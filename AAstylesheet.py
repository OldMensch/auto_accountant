



def mix_hex(hex1:str, hex2:str, factor:float=0.5):
    '''factor=0.25 results in 25% hex1 and 75% hex2. Default is 50/50'''
    r,g,b = int(hex1[1:3], 16), int(hex1[3:5], 16), int(hex1[5:7], 16)
    r2,g2,b2 = int(hex2[1:3], 16), int(hex2[3:5], 16), int(hex2[5:7], 16)
    r2,g2,b2 = int(r*factor+r2*(1-factor)),int(g*factor+g2*(1-factor)),int(b*factor+b2*(1-factor))
    r2,g2,b2 = hex(r2).removeprefix('0x'),hex(g2).removeprefix('0x'),hex(b2).removeprefix('0x')
    r2,g2,b2 = '0'*(len(r2)==1)+r2,'0'*(len(g2)==1)+g2,'0'*(len(b2)==1)+b2 # adds 0 if hex value is 0f or smaller
    return '#'+r2+g2+b2

def palette_qdarkstyle():   # The default color palette of qdarkstyle
    return {
    # Grays
    '#19232D': '#19232D',   # The main background color
    '#37414F': '#37414F',   # QMenu, and QTreeView/QListView/QTableView/QColumnView in some cases
    '#455364': '#455364',   # Buttons and borders
    '#54687A': '#54687A',   # QPushButton/QToolButton hover, QTabBar selected
    '#60798B': '#60798B',   # Scrollbar, button pressed/checked, QToolButton pressed/checked, QToolBox tab selected 
    '#9DA9B5': '#9DA9B5',   # disabled font color
    '#E0E1E3': '#E0E1E3',   # font color

    # Accent Color
    '#26486B': '#26486B',   # Disabled background color of several widgets
    '#346792': '#346792',   # QToolTip, QMenuBar focused, highlighted text, QScrollBar hover, QProgressBar, hover for most editing widgets
    '#1A72BB': '#1A72BB',   # QMenuBar selection, hovering/focusing on many widgets
    '#259AE9': '#259AE9',   # QTabBar selected
    }

def palette_file_explorer():    # uses blacks/grays of Windows file explorer for main colors, accent color uses Windows' accent color (nifty!)
    accent = '#00abff'
    return {
    # Grays
    '#19232D': '#191919', 
    '#37414F': '#202020', 
    '#455364': '#292929',
    '#54687A': '#2d2d2d',
    '#60798B': '#333333', 
    '#9DA9B5': '#777777',
    '#E0E1E3': '#ffffff',

    # Accent Color
    '#26486B': mix_hex(accent,'#000000', .25),
    '#346792': mix_hex(accent,'#000000', .40), 
    '#1A72BB': mix_hex(accent,'#000000', .55),
    '#259AE9': mix_hex(accent,'#000000', .70)
    }


def palette_accentless():    # uses blacks/grays of Windows file explorer for main colors, accent color uses Windows' accent color (nifty!)
    accent = '#00abff' #'#888888'
    return {
    # Grays
    '#19232D': '#191919', 
    '#37414F': '#202020', 
    '#455364': '#2D2D2D',
    '#54687A': '#494949',
    '#60798B': '#5d5d5d', 
    '#9DA9B5': '#bbbbbb',#bcc0c4
    '#E0E1E3': '#eeeeee',#e9e9ea

    # Accent Color
    '#26486B': mix_hex(accent,'#000000', .30),
    '#346792': mix_hex(accent,'#000000', .45), 
    '#1A72BB': mix_hex(accent,'#000000', .60),
    '#259AE9': mix_hex(accent,'#000000', .75)
    }


def calc_palette(style:str=''): # Creates and returns the palette to overwrite qdarkstyle with
    match style:
        case 'file_explorer':   return palette_file_explorer()
        case 'accentless':      return palette_accentless()
        case other:             return palette_qdarkstyle()
    
UNIVERSAL_PALETTE = calc_palette('accentless')

class UNI_PALETTE:  # This is how we (more easily) access the palette from within our code
    # Base colors
    B1 = UNIVERSAL_PALETTE['#19232D'] # Darkest
    B2 = UNIVERSAL_PALETTE['#37414F']
    B3 = UNIVERSAL_PALETTE['#455364']
    B4 = UNIVERSAL_PALETTE['#54687A']
    B5 = UNIVERSAL_PALETTE['#60798B']
    B6 = UNIVERSAL_PALETTE['#9DA9B5']
    B7 = UNIVERSAL_PALETTE['#E0E1E3'] # Brightest

    # Accent Color
    A1 = UNIVERSAL_PALETTE['#26486B'] # Darkest
    A2 = UNIVERSAL_PALETTE['#346792']
    A3 = UNIVERSAL_PALETTE['#1A72BB']
    A4 = UNIVERSAL_PALETTE['#259AE9'] # Brightest


def get_custom_qdarkstyle():
    '''IMPORTANT!!! Must be called AFTER QApplication is instantiated'''
    import qdarkstyle 
    stylesheet = qdarkstyle.load_stylesheet_pyside2()

    for color in UNIVERSAL_PALETTE:
        stylesheet = stylesheet.replace(color, UNIVERSAL_PALETTE[color])

    return stylesheet