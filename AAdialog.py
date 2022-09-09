
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

class DropdownEntry(QComboBox): #Single-selection-only, dropdown version of a SelectionList
    def __init__(self, items, default=None, current=None, selectCommand=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default = default

        if default: self.addItem(default)           # Adds a "default" item, if specified
        self.addItems(items)                        # Adds all the other items you can select
        if current: self.setCurrentText(current)    # Sets the currently selected item

        if selectCommand:    # If we specify a command, the list activates that command every time we select something, and send it the selected item
            def send_current_item():    selectCommand(self.entry())
            self.activated.connect(send_current_item)
    
    def setReadOnly(self, val:bool) -> None: 
        if val: self.setStyleSheet(style('disabledEntry'))
        else:   self.setStyleSheet(style('entry'))
        self.setDisabled(val)
    def isDefault(self) -> bool:        return self.entry()==self.default
    def entry(self) -> str:             return self.currentText()
    def set(self, text:str) -> None:    self.setCurrentText(text)

class ListEntry(QListWidget): # Single- or multi-item selection list
    def __init__(self, items:list, current:list=None, mode='single', selectCommand=None, *args, **kwargs):
        super().__init__(uniformItemSizes=True, *args, **kwargs)
        self.mode = mode

        #Allows for selection of multiple items
        if mode=='multi':   self.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # Adds all items to the list, selects them if they are in current
        for item in items:
            itemToAdd = QListWidgetItem(item)
            self.addItem(itemToAdd)
            if current and item in current: itemToAdd.setSelected(True)
        
        if selectCommand:    # If we specify a command, the list activates that command every time we select something, and send it the selected item
            def send_current_item():    selectCommand(self.entry())
            self.activated.connect(send_current_item)

    def entry(self):    # Returns string or list of strings, depending on mode    
        if self.mode == 'single':
            return self.currentItem().text()
        else:
            toReturn = list()
            for itemindex in self.selectionModel().selectedIndexes():
                toReturn.append(self.itemFromIndex(itemindex).text())
            return toReturn
    def set(self, items:list) -> None:
        # De-selects previously selected items
        for itemindex in self.selectionModel().selectedIndexes():
            self.itemFromIndex(itemindex).setSelected(False)

        # Selects what we want
        for i in range(self.count()):   # Iterates through QListWidget's QListWidgetItem's, activating the ones we want
            if self.item(i).text() in items:    self.item(i).setSelected(True)
    
    def update_items(self, items:list) -> None: # Deletes all previous items, adds in new specified list
        items = list(items)
        # Deletes all the old options
        self.clear()
        # Adds in all the new ones
        def alphaKey(e):    return e.lower()
        items.sort(key=alphaKey)
        for item in items:
            self.addItem(item)
        
        

class Dialog(QDialog):
    def __init__(self, upper, title='', styleSheet=style('dialog')):  #upper is a reference to the original PortfolioApp, master is a reference to the TopLevel GUI 
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

        self.GUI['primaryLayout'] = QGridLayout()
        self.GUI['primaryFrame'] = QFrame(self, layout=self.GUI['primaryLayout'])

        self.GUI['menuLayout'] = QHBoxLayout()
        self.GUI['menuFrame'] = QWidget(self, layout=self.GUI['menuLayout'])

        ### Rendering
        if title != '':
            self.GUI['masterLayout'].addWidget(self.GUI['title'])
        self.GUI['masterLayout'].addWidget(self.GUI['primaryFrame'])
        self.GUI['masterLayout'].addWidget(self.GUI['menuFrame'])


    #==============================
    # MODULAR GUI FRAMEWORK - commands to add labels, entry boxes, dropdowns, text boxes and more
    #==============================

    def add_label(self, text, column, row, columnspan=1, rowspan=1, *args, **kwargs) -> QLabel:
        label = QLabel(text, *args, **kwargs)
        self.GUI['primaryLayout'].addWidget(label, row, column, rowspan, columnspan)
        return label
    
    def add_scrollable_text(self, text, column, row, columnspan=1, rowspan=1, *args, **kwargs) -> QTextEdit:
        '''Adds an uneditable, but scrollable textbox widget'''
        label = QTextEdit(text, readOnly=True, *args, **kwargs)
        self.GUI['primaryLayout'].addWidget(label, row, column, rowspan, columnspan)
        return label

    def add_entry(self, text, column, row, columnspan=1,rowspan=1, format=None, maxLength=-1, *args, **kwargs):
        if format == 'description':     box = DescEntry(text, styleSheet=style('entry'), *args, **kwargs)
        elif format == 'date':          box = DateEntry(text, styleSheet=style('entry'), *args, **kwargs)
        else:                           box = Entry(text, format, maxLength=maxLength, styleSheet=style('entry'), *args, **kwargs)
        
        self.GUI['primaryLayout'].addWidget(box, row, column, rowspan, columnspan)
        return box
    
    def add_dropdown_list(self, items, column, row, columnspan=1,rowspan=1, default='', current='', selectCommand=None, *args, **kwargs) -> DropdownEntry:
        dropdown = DropdownEntry(items, default, current, selectCommand, styleSheet=style('entry'), *args, **kwargs)
        self.GUI['primaryLayout'].addWidget(dropdown, row, column, rowspan, columnspan)
        return dropdown

    def add_menu_button(self, text, command=None, *args, **kwargs) -> None:
        '''Adds a button to the menu'''
        self.GUI['menuLayout'].addWidget(QPushButton(text, clicked=command, fixedHeight=icon('size').height(), *args, **kwargs))

    def add_list_entry(self, items, column, row, current=None, rowspan=1,columnspan=1, mode='single', selectCommand=None, *args, **kwargs) -> ListEntry:
        '''Adds a scrollable list, from which you can select a singular, or multiple items'''
        selection = ListEntry(items, current, mode, selectCommand, *args, **kwargs)
        self.GUI['primaryLayout'].addWidget(selection, row, column, rowspan, columnspan)
        return selection