
from AAlib import *



class DateEntry(QDateTimeEdit): # For entering datetimes in the ISO format yyyy-MM-dd hh:mm:ss
    def __init__(self, text:str, *args, **kwargs):
        super().__init__(displayFormat='yyyy-MM-dd hh:mm:ss', dateTime=datetime.fromisoformat(text), *args, **kwargs)
    
    def entry(self) -> str:             return self.text()
    def set(self, text:str) -> None:    self.setDateTime(datetime.fromisoformat(text))

class Entry(QLineEdit): # For entering text, floats, and positive-only floats
    def __init__(self, text:str, format:str=None, maxLength:int=-1, *args, **kwargs):
        super().__init__(text=text, maxLength=maxLength, *args, **kwargs)
        self.format = format
        
        # Input restriction
        if format == 'float':       self.setValidator(QDoubleValidator())
        if format == 'pos_float':   self.setValidator(QDoubleValidator(bottom=0))

    def setReadOnly(self, val:bool) -> None: 
        if val: self.setStyleSheet(style('disabledEntry'))
        else:   self.setStyleSheet(style('entry'))
        super().setReadOnly(val)     
    def entry(self) -> str:
        toReturn = self.text().rstrip().lstrip()
        if self.format in ('float', 'pos_float') and toReturn in ('','.','-'):
                return '0'
        else:   return toReturn
    def set(self, text:str) -> None:      self.setText(text)
    
class DescEntry(QPlainTextEdit): # For entering lots of text
    def __init__(self, text:str, *args, **kwargs):
        super().__init__(text, *args, **kwargs)

    def setReadOnly(self, val:bool) -> None: 
        if val: self.setStyleSheet(style('disabledEntry'))
        else:   self.setStyleSheet(style('entry'))
        super().setReadOnly(val)     
    def entry(self) -> str:             return self.toPlainText().rstrip().lstrip()
    def set(self, text:str) -> None:  self.setPlainText(text)

class DropdownEntry(QComboBox): #Single-selection only, dropdown version of a ListEntry
    def __init__(self, dictionary:dict, default:str=None, current=None, selectCommand=None, sortOptions=False, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.default = default # A default display string which IS NOT in the lookup dictionary
        self.lookup_dict = {} # A dictionary allowing us to look up the objects by their display name
        self.sortOptions = sortOptions # items sorted alphabetically when true

        self.update_dict(dictionary)
        if current: self.set(current)               # Sets the currently selected item

        if selectCommand:    # If we specify a command, the list activates that command every time we select something, and send it the selected item
            def send_current_item():    selectCommand(self.entry())
            self.activated.connect(send_current_item)
    
    def setReadOnly(self, val:bool) -> None: 
        '''Toggles appearance and ability to use the dropdown'''
        if val: self.setStyleSheet(style('disabledEntry'))
        else:   self.setStyleSheet(style('entry'))
        self.setDisabled(val)
    def entry(self) -> str:
        '''returns the selected item, or None if the default item is selected'''
        if self.currentText()==self.default:        return None
        return self.lookup_dict[self.currentText()]
    def set(self, item) -> None:    
        '''The currently selected item is set to this.\n
        It must be the value which will be selected, NOT THE DISPLAY TEXT'''
        self.setCurrentText({value:key for key,value in self.lookup_dict.items()}[item])
    def update_dict(self, dictionary:dict=None) -> None: 
        '''Deletes all previous items, adds in new items\n
        Dict keys must be display names, values are the actual objects which the .entry() command returns'''

        if dictionary == None:  self.lookup_dict = {}           # If we specify None, we clear the dictionary
        else:                   self.lookup_dict = dictionary   # Otherwise, set our dict to the new one

        self.clear() # Remove previous items

        if self.default: self.addItem(self.default)     # Adds a "default" item, if specified
        if self.sortOptions:
            to_sort = list(dictionary.keys())
            to_sort.sort()
            self.addItems(to_sort)                # Adds all the other items you can select
        else:
            self.addItems(dictionary.keys())                # Adds all the other items you can select



class ListEntry(QListWidget): # Single- or multi-item selection list
    def __init__(self, dictionary:dict=None, current:list=None, mode='single', selectCommand=None, *args, **kwargs):
        super().__init__(uniformItemSizes=True, *args, **kwargs)
        self.mode = mode

        self.lookup_dict = {} # A dictionary allowing us to look up the objects by their display name

        #Allows for selection of multiple items
        if mode=='multi':   self.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # Adds all of our items in for the first time, if specified
        if dictionary: self.update_dict(dictionary)
        if current: self.set(current)
        
        # If we specify a command, the list object activates that command every time we select an item, and sends it the item
        if selectCommand:    
            def send_current_item():    selectCommand(self.entry())
            self.activated.connect(send_current_item)

    # Returns the value, or list of values, which the display text maps to. 
    # So, if the values are wallet objects, we get those back. 
    def entry(self):    
        if self.mode == 'single':
            return self.lookup_dict[self.currentItem().text()]
        else:
            return [self.lookup_dict[item.text()] for item in self.selectedItems()]
    def set(self, current:list) -> None:
        '''Sets the selection to specified items'''
        # De-selects previously selected items
        for itemindex in self.selectionModel().selectedIndexes():
            self.itemFromIndex(itemindex).setSelected(False)

        # Selects what we want, unless the list is empty
        if current == [] or current == None: return
        
        for i in range(self.count()):   # Iterates through QListWidget's QListWidgetItem's, activating the ones we want
            if self.item(i).text() in current:    self.item(i).setSelected(True)
    
    def update_dict(self, dictionary:dict=None) -> None: 
        '''Deletes all previous items, adds in new items\n
        Dict keys must be display names, values are the actual objects which the .entry() command returns'''

        if dictionary == None: self.lookup_dict = {} # If we specify None, we clear the dictionary
        else: self.lookup_dict = dictionary # Otherwise, set our dict to the new one

        self.clear() # Remove previous items

        for key, value in dictionary.items(): # Add new items: keys are the display names, values unused here 
            self.addItem(QListWidgetItem(key))
         

class Dialog(QDialog):
    def __init__(self, upper, title='', errormsg='', styleSheet=style('dialog')):  #upper is a reference to the original PortfolioApp, master is a reference to the TopLevel GUI 
        '''The generalized dialog superclass for Auto-Accountant'''
        super().__init__(upper, styleSheet=styleSheet)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False) # Removes the pointless question mark from the dialog box
        self.setWindowTitle(title)
        self.setModal(True) # Can't interact with main window until this one closes

        self.upper = upper

        #==============================
        # GUI FRAMEWORK
        #==============================

        ### Initialization
        self.GUI = {}
        
        self.GUI['masterLayout'] = QVBoxLayout()
        self.setLayout(self.GUI['masterLayout'])

        if title != '':     #The title of the box
            self.GUI['title'] =     QLabel(title, alignment=Qt.AlignCenter, styleSheet=style('title'))

        self.GUI['primaryLayout'] = QGridLayout() # Contains whatever content we really want for our dialog. Controlled by our modular system below
        self.GUI['primaryFrame'] = QFrame(self, layout=self.GUI['primaryLayout'])

        self.GUI['menuLayoutSpacer'] = QHBoxLayout()  # I ONLY need this to add spacers before/after the menu buttons, BEFORE they are all added
        self.GUI['menuFrameSpacer'] = QWidget(self, layout=self.GUI['menuLayoutSpacer'])
        self.GUI['menuLayout'] = QHBoxLayout() # Buttons like "OK" and "CANCEL" and "SAVE", etc.
        self.GUI['menuFrame'] = QWidget(self, layout=self.GUI['menuLayout'])

        self.GUI['errormsg'] =     QTextEdit(errormsg, readOnly=True, styleSheet=style('error')) # Potential error message that can popup
        self.GUI['errormsg'].setHidden(True)

        ### Rendering
        if title != '':
            self.GUI['masterLayout'].addWidget(self.GUI['title'])
        self.GUI['masterLayout'].addWidget(self.GUI['primaryFrame'])
        self.GUI['masterLayout'].addWidget(self.GUI['errormsg'])
        self.GUI['masterLayout'].addWidget(self.GUI['menuFrameSpacer'])
        self.GUI['menuLayoutSpacer'].addStretch(1)
        self.GUI['menuLayoutSpacer'].addWidget(self.GUI['menuFrame'])
        self.GUI['menuLayoutSpacer'].addStretch(1)


    def display_error(self, msg):
        self.GUI['errormsg'].setText(msg)
        self.GUI['errormsg'].setHidden(False)
    def hide_error(self):
        self.GUI['errormsg'].setHidden(True)


    #==============================
    # MODULAR GUI FRAMEWORK - commands to add labels, entry boxes, dropdowns, text boxes and more
    #==============================
    
    def add_label(self, text, column, row, columnspan=1, rowspan=1, *args, **kwargs) -> QLabel:
        '''Adds a basic label for displaying text'''
        label = QLabel(text, *args, **kwargs)
        self.GUI['primaryLayout'].addWidget(label, row, column, rowspan, columnspan)
        return label
    
    def add_scrollable_text(self, text, column, row, columnspan=1, rowspan=1, wordWrap=True, *args, **kwargs) -> QTextEdit:
        '''Adds an uneditable, but scrollable textbox widget'''
        label = QTextEdit('', readOnly=True, *args, **kwargs)
        label.setText(text)
        if not wordWrap: label.setWordWrapMode(QTextOption.NoWrap)
        self.GUI['primaryLayout'].addWidget(label, row, column, rowspan, columnspan)
        return label

    def add_entry(self, text, column, row, columnspan=1,rowspan=1, format=None, maxLength=-1, *args, **kwargs):
        '''A box for entering text.\n
        Format can be 'description', 'date', 'float', or 'pos_float' to restrict entry formatting'''
        if format == 'description':     box = DescEntry(text, styleSheet=style('entry'), *args, **kwargs)
        elif format == 'date':          box = DateEntry(text, styleSheet=style('entry'), *args, **kwargs)
        else:                           box = Entry(text, format, maxLength=maxLength, styleSheet=style('entry'), *args, **kwargs)
        
        self.GUI['primaryLayout'].addWidget(box, row, column, rowspan, columnspan)
        return box
    
    def add_dropdown_list(self, dictionary, column, row, columnspan=1,rowspan=1, default='', current='', selectCommand=None, sortOptions=False, *args, **kwargs) -> DropdownEntry:
        '''Adds a dropdown list, from which you can select a single item'''
        dropdown = DropdownEntry(dictionary, default, current, selectCommand, styleSheet=style('entry'), sortOptions=sortOptions, *args, **kwargs)
        self.GUI['primaryLayout'].addWidget(dropdown, row, column, rowspan, columnspan)
        return dropdown

    def add_menu_button(self, text, command=None, spacer='  ', *args, **kwargs) -> None:
        '''Adds a button to the menu at the bottom of the dialog
        \nNOTE: Spaces are added to the button title for a better look
        '''
        self.GUI['menuLayout'].addWidget(QPushButton(spacer+text+spacer, clicked=command, fixedHeight=icon('size').height(), *args, **kwargs))
    
    def add_list_entry(self, dictionary:dict, column, row, current=None, rowspan=1,columnspan=1, mode='single', selectCommand=None, *args, **kwargs) -> ListEntry:
        '''Adds a scrollable list, from which you can select a singular, or multiple items\n
        Except, it requires a dictionary mapping display text to actual values. .entry() returns the actual values. '''
        selection = ListEntry(dictionary, current, mode, selectCommand, *args, **kwargs)
        self.GUI['primaryLayout'].addWidget(selection, row, column, rowspan, columnspan)
        return selection
