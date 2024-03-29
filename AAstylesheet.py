import qdarkstyle 



def get_windows_accent():
    '''Returns the two colors used by Windows 10/11 for its accent palette
    \nThe first color is lighter, the second color is darker'''
    viable=[]
    try:
        import winreg
        access_registry = winreg.ConnectRegistry(None,winreg.HKEY_CURRENT_USER)

        accentcolorkey = winreg.OpenKey(access_registry,'Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Accent')
        value = str(winreg.QueryValueEx(accentcolorkey, 'AccentPalette')[0]).removeprefix('b')
        value = value.replace(value[0],'')
        value = value.split('\\x00')
        for S in value: 
            if S.count('\\x') == 3: viable.append('#'+S.replace('\\x',''))
        if '#881798' in viable: viable.remove('#881798') # Some weird hexadecimal that appears sometimes, some random purple color
    except: pass
    
    if len(viable) < 1: # We failed to retrieve the windows palette, so just use some generic color palette instead
        return '#1A72BB'
    return viable[0]

def mix_hex(hex1:str, hex2:str, factor:float=0.5):
    '''Mixes hex color codes. \'factor\' is % of first color:
    \nfactor=0.25 results in 25% hex1 and 75% hex2. Default is 50/50'''
    if factor < 0 or factor > 1:    raise ValueError(f'||ERROR|| Cannot mix colors with ratio of {factor}, ratio must be between 0 and 1')
    r,g,b = int(hex1[1:3], 16), int(hex1[3:5], 16), int(hex1[5:7], 16)
    r2,g2,b2 = int(hex2[1:3], 16), int(hex2[3:5], 16), int(hex2[5:7], 16)
    r3,g3,b3 = int(r*(1-factor)+r2*factor),int(g*(1-factor)+g2*factor),int(b*(1-factor)+b2*factor)
    r3,g3,b3 = hex(r3),hex(g3),hex(b3)
    return f'#{r3[2:]:0>2}{g3[2:]:0>2}{b3[2:]:0>2}' # removes 0x prefixes, fills in with 0s if neccessary


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

def palette_file_explorer():    # grays stolen from Windows file explorer, accent color is Windows' accent color (nifty!)
    accent = get_windows_accent()
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
    '#26486B': mix_hex('#000000',accent, .25),
    '#346792': mix_hex('#000000',accent, .40), 
    '#1A72BB': mix_hex('#000000',accent, .55),
    '#259AE9': mix_hex('#000000',accent, .70)
    }


def palette_accentless():    # Uses blacks/grays for primary colors, accented with "jeans blue"
    accent = '#00abff' # jeans-blue accent color
    return {
    # Grays
    '#19232D': mix_hex('#000000','#ffffff', .1),    # The main background color
    '#37414F': mix_hex('#000000','#ffffff', .128),  # QMenu, and QTreeView/QListView/QTableView/QColumnView in some cases
    '#455364': mix_hex('#000000','#ffffff', .18),   # Buttons and borders
    '#54687A': mix_hex('#000000','#ffffff', .29),   # QPushButton/QToolButton hover, QTabBar selected
    '#60798B': mix_hex('#000000','#ffffff', .365),  # Scrollbar, button pressed/checked, QToolButton pressed/checked, QToolBox tab selected 
    '#9DA9B5': mix_hex('#000000','#ffffff', .735),  # disabled font color
    '#E0E1E3': mix_hex('#000000','#ffffff', .935),  # font color

    # Accent Color
    '#26486B': mix_hex('#000000',accent, .30),
    '#346792': mix_hex('#000000',accent, .45), 
    '#1A72BB': mix_hex('#000000',accent, .60),
    '#259AE9': mix_hex('#000000',accent, .75),
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

    # Reds (mainly for ERROR)
    R1 = '#880000' # default
    R2 = '#cc0000' # hovering(button), selected(grid)
    R3 = '#ff0000' # pressed(button), hovering(grid)

    # Oranges (mainly for filtering)
    F1 = '#ff5500' # default
    F2 = '#ff7700' # hovering
    F3 = '#ff9900' # pressed

    # Greens (mainly for filtering)
    G1 = '#006600' # default
    G2 = '#008800' # hovering
    G3 = '#00aa00' # pressed
    G4 = '#00ee00' # profit text color

    # Header color (for titles, subtitles, entry boxes)
    H = '#ffff00'


def get_custom_master_stylesheet():
    '''Returns default PySide6 StyleSheet, with base and accent colors replaced with a custom palette'''
    DEFAULT_STYLESHEET = qdarkstyle._load_stylesheet(qt_api='pyside6')
    with open('default_stylesheet.txt','w') as file:
        file.write(DEFAULT_STYLESHEET)

    for color in UNIVERSAL_PALETTE:
        DEFAULT_STYLESHEET = DEFAULT_STYLESHEET.replace(color, UNIVERSAL_PALETTE[color])

    return DEFAULT_STYLESHEET