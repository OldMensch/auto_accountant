
from functools import partial as p
import tkinter as tk
import datetime

from AAlib import *



#This is the superclass for dialogue boxes for Auto-Accountant. It is used by:
# Address Manager       |   Selecting addresses to edit
# Address Editor        |   New address, Editing addresses associated with wallets (Used by the IMPORT functions to automatically figure out where assets come from and go to)
# Asset Editor          |   New Asset, Editing assets' Ticker, Name, Class, Description
# Message Box           |   Displaying Text, save/save and close/cancel/delete/ok operations
# Profile Editor        |   New/Deleting profiles, Editing name of a profile
# Profile Manager       |   Creating new profiles, 
# Transaction Editor    |   New Transaction, editing various transaction info
# Wallet Editor         |   New wallet, Editing wallet name/description
# Wallet Manager        |   Selecting wallets to edit




class Dialogue(tk.Toplevel):
    def __init__(self, upper, title):  #upper is a reference to the original PortfolioApp, master is a reference to the TopLevel GUI 
        '''The generalized dialogue superclass for Auto-Accountant'''
        super().__init__()

        self.configure(bg=palette('dark'))
        self.grab_set()     #You can only interact with this window now
        self.focus_set()    #Pulls this window to the front
        self.resizable(False,False)  #So you cant resize this window
        self.title(title)
        self.bind('<Escape>', self.comm_default)    #Pressing escape performs the default operation
        self.protocol('WM_DELETE_WINDOW', self.comm_default) #makes pressing the X button on the window equivalent to the default button

        self.upper = upper

        #==============================
        # GUI FRAMEWORK
        #==============================

        ### Initialization
        self.GUI = {}

        self.GUI['mainFrame'] =     tk.Frame(self, bg=palette('accentdark'))        #Contains everything else

        if title != '':     #The title of the box
            self.GUI['title'] =         tk.Label(self.GUI['mainFrame'], text=title, fg="#ffffff", bg=palette('accentdark'), font=setting('font', 1.25))
        self.GUI['primaryFrame'] =  tk.Frame(self.GUI['mainFrame'], bg=palette('accent'))   #contains all the important content of the dialogue box
        self.GUI['menuFrame'] =     tk.Frame(self.GUI['mainFrame'])     #contains all the 'cancel', 'ok', 'delete', 'save', and whatever other buttons you want

        ### Rendering
        self.GUI['mainFrame']   .pack(padx=(20,20), pady=(20,20))
        self.GUI['title']       .grid(row=0, pady=(20,20))
        self.GUI['primaryFrame'].grid(row=1, sticky="NSEW")
        self.GUI['menuFrame']   .grid(row=2, pady=(20,20))



    #==============================
    # MODULAR FRAMEWORK - commands to add labels, entry boxes, dropdowns, text boxes and more
    #==============================

    def add_label(self, column, row, text, fg=palette('entrycursor'), bg=palette('light'), columnspan=1, rowspan=1):
        label = tk.Label(self.GUI['primaryFrame'], text=text, bg=bg, fg=fg, font=setting('font', 0.75))
        label.grid(column=column,row=row,columnspan=columnspan,rowspan=rowspan,sticky="NSEW")
        return label

    def add_entry(self, column, row, text, fg=palette('entrytext'), bg=palette('entry'), insertbackground=palette('entrycursor'), width=32, height=8, format=None, charLimit=None, columnspan=1,rowspan=1):
        if format == 'description':     box = DescEntry(self.GUI['primaryFrame'], text, fg, bg, insertbackground, width, height)
        elif format == 'auto':          box = AutoEntryBox(self.GUI['primaryFrame'], text, fg, bg, insertbackground, width)
        else:                           box = EntryBox(self.GUI['primaryFrame'], text, fg, bg, insertbackground, width, format, charLimit)
        box.grid(column=column,row=row,columnspan=columnspan,rowspan=rowspan,sticky="NSEW")
        return box
    
    def add_dropdown_list(self, column, row, items, defaultItem='', currentItem='', selectCommand=None):
        dropdown = DropdownList(self.GUI['primaryFrame'], items, defaultItem, currentItem, selectCommand)
        dropdown.grid(column=column,row=row,sticky="EW")
        return dropdown

    def add_text_display(self, column, row, text='', fg=palette('entrycursor'), bg=palette('dark'), font=setting('font', 0.75), width=32, height=8):
        '''Adds an uninteractive textbox to the primaryFrame'''
        textbox = TextBox(self.GUI['primaryFrame'], text=text, state='disabled', fg=fg, bg=bg, font=font, height=height, width=width,wrap='word')
        textbox.grid(column=column,row=row,sticky='EW',padx=(0,0))
        return textbox

    def add_menu_button(self, text, bg="#000000", fg="#ffffff", command=None):
        '''Adds a button to the menu'''
        tk.Button(self.GUI['menuFrame'], text=text, bg=bg, fg=fg, font=setting('font'), command=command).pack(side='left')

    def add_selection_list(self, column, row, items, checkList, allowMultipleSelection=False, title='', width=32, height=10, truncate=False, sort='alpha', button_command=None, rowspan=1,columnspan=1):
        '''Adds a scrollable list, from which you can select a singular, or multiple items'''
        selection = SelectionList(self.GUI['primaryFrame'], items, checkList, allowMultipleSelection, title, width, height, truncate, sort, button_command)
        selection.grid(column=column, row=row, rowspan=rowspan, columnspan=columnspan, sticky="NS")
        return selection




    def center_dialogue(self):
        '''Updates positioning data and centers the dialogue box
        \nThis is the SLOWEST command of all, since \'self.update()\' performs tons of calculations.
        \n Maybe consider looking for a workaround to centering the dialogue.'''
        self.update()    #Necessary, so that geometry() has the correct window dimensions
        self.geometry('+%d+%d' % ( (self.winfo_screenwidth()-self.winfo_width())/2 + self.winfo_x()-self.winfo_rootx(),
                                                    (self.winfo_screenheight()-self.winfo_height())/2 ))#centers the window in the middle of the screen



    def comm_default(self, *args): #Command bound to the ESC key and Close Window button. Set to close the window by default, but can be changed
        self.close()

    def close(self):
        self.upper.grab_set()
        self.upper.focus_set()
        self.destroy()


class AutoEntryBox(tk.Entry):
    def __init__(self, upper, text, fg=palette('entrytext'), bg=palette('entry'), insertbackground=palette('entrycursor'), width=32, format=None):
        '''An automatically-updating display of text'''
        super().__init__(upper, text=text, disabledforeground=fg, disabledbackground=bg, insertbackground=insertbackground, font=setting('font2'), width=width, state='disabled')
        self.format = format
        self.text = tk.StringVar(self, value=text)
        self.configure(textvariable=self.text)
        
        
    def entry(self):
        '''Returns the content of the entry box, without whitespace. Floats are formatted.'''
        toReturn = self.text.get().rstrip().lstrip()
        if self.format in ['float', 'pos_float'] and toReturn in ['','.','-']:
            return '0'
        else:   
            return toReturn

class EntryBox(tk.Entry):
    def __init__(self, upper, text, fg=palette('entrytext'), bg=palette('entry'), cursor=palette('entrycursor'), width=32, format=None, charLimit=None, d_fg=palette('entrycursor'), d_bg=palette('dark')):
        '''For entering 1-line text, dates, floats, positive-only floats. Length can be limited.'''
        super().__init__(upper, text=text, fg=fg, bg=bg, readonlybackground=d_bg, insertbackground=cursor, font=setting('font2'), width=width)
        self.format = format
        self.text = tk.StringVar(self, value=text) #The actual, changing data variable of the entrybox
        self.configure(textvariable=self.text)
        self.fg, self.d_fg = fg, d_fg
        self.setting = False #True when we're changing the content of the entry box. Avoids "valid date" and "valid float" checks.
        
        if format in ['float', 'pos_float']: #Floats, and positive-only floats
            def validFloat(new, char):
                if self.setting: return True
                if charLimit != None and len(new) > charLimit:  return False
                if char == ' ':                 return False    # no spaces
                if new == '' or new == '.':     return True     #these just become 0 when saving
                elif format == 'float' and new == '-':    return True #This also just becomes 0
                try: 
                    float(new)  #must be convertible to a number
                    if format == 'pos_float' and float(new) < 0:                      #cant be negative
                        return False
                    return True
                except:
                    return False
            valFloat = self.register(validFloat)
            self.configure(validate='key', vcmd=(valFloat, '%P', '%S'))

        elif format == 'date':
            self.configure(justify='center')
            def validDate(d):       #dear fuck why is this so complicated to perform!!!!!!!
                if self.setting: return True
                self.selection_clear()
                i = self.index('insert')
                if len(d.get()) < 19:
                    d.insert(i, '0')
                    d.insert(i, '0')
                    self.icursor(i)
                    for ignore in ['/',' ',':']:
                        if d.get()[i-1] == ignore:
                            self.icursor(i-1)
                elif not d.get()[i-1].isdigit():
                    d.delete(i-1)
                    return
                elif i > 19:
                    d.delete(19)
                    return
                for ignore in ['/',' ',':']:
                    if d.get()[i] == ignore:
                        e = d.get()[i-1]
                        d.delete(i-1)
                        d.delete(i)
                        d.insert(i, e)
                        self.icursor(i+1)
                        return
                d.delete(i)
            def validDate2(char):
                if self.setting: return True
                if len(char) > 1 or not char.isdigit():
                    return False    
                return True
            
            valDate = self.register(validDate2)
            self.configure(validate='key', vcmd=(valDate, '%S'))
            self.text.trace('w', lambda name, index, mode, sv=self: validDate(sv))

        elif charLimit != None:
            def validLength(new):
                if self.setting: return True
                if charLimit != None and len(new) > charLimit:  return False
                return True
            valLength = self.register(validLength)
            self.configure(validate='key', vcmd=(valLength, '%P'))
        
    def entry(self):
        '''Returns the content of the entry box, without whitespace. Floats are formatted.'''
        toReturn = self.text.get().rstrip().lstrip()
        if self.format in ['float', 'pos_float'] and toReturn in ['','.','-']:
            return '0'
        else:   
            return toReturn
    
    def set(self, string):
        '''Changes the content of the entry box to specified string. \n
        WARNING: This does not check whether the string is a valid input!'''
        self.setting = True
        self.text.set(string)
        self.setting = False
    
    def disable(self):  self.configure(state='readonly',fg=self.d_fg)
    def enable(self):   self.configure(state='normal',fg=self.fg)
    def clear(self):    self.text.set('')

class DescEntry(tk.Text):
    def __init__(self, upper, text, fg=palette('entrytext'), bg=palette('entry'), insertbackground=palette('entrycursor'), width=32, height=8, d_fg=palette('entrycursor'), d_bg=palette('dark')):
        super().__init__(upper, wrap='word', fg=fg, bg=bg, insertbackground=insertbackground, font=setting('font2'), height=height ,width=width)
        self.insert(0.0, text)
        self.fg, self.bg, self.d_fg, self.d_bg = fg, bg, d_fg, d_bg
    def entry(self):
        '''Returns the content of the description box, without whitespace'''
        return self.get(1.0,'end').rstrip().lstrip()

    def disable(self):      self.configure(state='disabled', fg=self.d_fg, bg=self.d_bg)
    def enable(self):       self.configure(state='normal', fg=self.fg, bg=self.bg)
    def set(self, string):  
        self.clear()
        self.insert(0.0, string)
    def clear(self):        self.delete(1.0,'end')

class DropdownList(tk.OptionMenu): #Single-selection-only, dropdown version of a SelectionList
    def __init__(self, upper, items, defaultItem='', currentItem='', selectCommand=None, fg=palette('entrytext'), bg=palette('entry'), d_fg=palette('entrycursor'), d_bg=palette('dark')):
        self.defaultItem = defaultItem
        self.selectCommand = selectCommand
        self.bg, self.d_bg = bg, d_bg
        if currentItem == '':   self.currentItem = tk.StringVar(upper, defaultItem)
        else:                   self.currentItem = tk.StringVar(upper, currentItem)

        def alphaKey(e):    return e.lower()
        items = list(items)
        items.sort(key=alphaKey)
        if defaultItem in items:    items.remove(defaultItem)
        items.insert(0, defaultItem)

        super().__init__(upper, self.currentItem, *items, command=self.select_command)
        self.configure(fg=fg, bg=bg, font=setting('font2'), highlightthickness=0, disabledforeground=d_fg)
    
    def select_command(self, *kwargs):
        if self.selectCommand != None:  self.selectCommand(kwargs[0]) #kwargs[0] is the item just selected. This throws that into your custom command

    def entry(self):
        '''Returns the content of the dropdown'''
        return self.currentItem.get()
    
    def disable(self):      self.configure(state='disabled', bg=self.d_bg)
    def enable(self):       self.configure(state='normal', bg=self.bg)
    def set(self, string):  self.currentItem.set(string)
    def clear(self):        self.currentItem.set(self.defaultItem)

class TextBox(tk.Text): #Simple textbox that allows for mixed color, highlighting, and fonts
    def __init__(self, upper, text='', state='normal', fg=palette('entrycursor'), bg=palette('dark'), font=setting('font', 0.75), height=8, width=32, wrap='word', spacing1=0,spacing2=0,spacing3=0):
        super().__init__(upper, fg=fg, bg=bg, font=font, height=height, width=width, wrap=wrap, bd=-1, spacing1=spacing1, spacing2=spacing2, spacing3=spacing3)
        if state == 'readonly': #In a 'readonly' state, text can't be copied. It's basically just a more complex label. Disabled at least allows for highlighting text.
            new_bind_tags = list(self.bindtags())
            new_bind_tags.remove('Text')            # Removing the bind tag 'Text' removes all the functionality of the tk.Text widget
            self.bindtags(new_bind_tags)
            self.configure(cursor='')
        self.default_state = state
        self.tagID = 0
        self.insert(0.0, text)
        if state!= 'readonly': self.configure(state=self.default_state)
    
    def insert_text(self, text, fg=None, bg=None, font=None, justify='left'):
        '''Insert a bit of text into the textbox, specifying colors if you want'''
        if self.default_state=='disabled': self.configure(state='normal') #Can only insert text when it isn't disabled

        self.tag_config(self.tagID, foreground=fg, background=bg, font=font, justify=justify)
        self.insert('insert', text, (self.tagID))
        self.tagID += 1
            
        if self.default_state=='disabled': self.configure(state=self.default_state)

    def insert_triplet(self, text1, text2, text3, fg=None, bg=None, font=None, justify='left'):
        self.insert_text(text1)
        self.insert_text(text2, fg=fg, bg=bg, font=font, justify=justify)
        self.insert_text(text3)
        self.newline()
    
    def newline(self):
        '''Moves point of insertion to the next line in the text box'''
        if self.default_state=='disabled': self.configure(state='normal') #Can only insert text when it isn't disabled
        self.insert('insert', '\n')
        if self.default_state=='disabled': self.configure(state=self.default_state)
    
    def clear(self):    
        '''Deletes all text and clears all color/font formatting'''
        if self.default_state=='disabled': self.configure(state='normal') #Can only insert text when it isn't disabled
        self.clear_formatting()
        self.delete('0.0','end')
        if self.default_state=='disabled': self.configure(state=self.default_state)
    
    def clear_formatting(self):
        '''Clears all color/font formatting'''
        for tag in self.tag_names():
            self.tag_delete(tag)
        self.tagID = 0
    def force_formatting(self, fg=None, bg=None, font=None, justify='left'):
        '''Sets format for the entire textbox'''
        self.clear_formatting()
        self.tag_config(self.tagID, foreground=fg, background=bg, font=font, justify=justify)
        self.tag_add(self.tagID, '1.0', self.index('end'))
        self.tagID += 1


class SelectionList(tk.Frame):  #Selection list object
    def __init__(self, upper, items, checkList, allowMultipleSelection=False, title='', width=32, height=10, truncate=False, sort='alpha', button_command=None):
        super().__init__(upper, bg=palette('accentdark')) #Contructs the tk.Frame object
        self.checkList = checkList  #Boolean indicating whether or not selecting items is permanent, or performs a function on selection
        self.allowMultipleSelection = allowMultipleSelection #If a checklist, boolean indicates whether only one, or multiple items can be selected at once.
        self.width, self.height = width, height
        self.command = button_command
        self.truncate=truncate

        self.items = []
        self.buttons = []
        self.menu_buttons = []
        self.selection = []

        #Places a title on top of the selectionList
        if title != '':
            tk.Label(self, text=title, fg=palette('entrycursor'), bg=palette('accentdark'), font=setting('font', 0.75)).grid(column=0,row=0, sticky="NSEW",pady=(10,10))
        
        #Initializes the itemFrame, itemCanvas, and scrollbar for the menu
        self.itemCanvas = tk.Canvas(self, bg=palette('accent'), highlightthickness=0)
        self.itemFrame = tk.Frame(self.itemCanvas, bg=palette('accent'))
        scrollbar = tk.Scrollbar(self, orient='vertical', command=self.itemCanvas.yview)
        self.itemCanvas.configure(yscrollcommand=scrollbar.set)
        self.itemCanvas.create_window(0, 0, window=self.itemFrame, anchor=tk.NW)
        self.itemCanvas.grid(column=0,row=1,sticky='NSEW')
        scrollbar.grid(column=1,row=1,sticky='NS')
        
        #Properly sets the width of the itemCanvas, for the case that there are no items
        self.__add_button()
        self.buttons[0].update()
        self.trueWidth = self.buttons[0].winfo_width()
        self.trueHeight = self.buttons[0].winfo_height()
        self.__remove_button()
        self.itemCanvas.configure(width=self.trueWidth, height=self.trueHeight*height)

        #Initializes the Menu, which can have no buttons, or stuff like "Clear Selection" and "Invert Selection" or whatever
        self.menuFrame = tk.Frame(self, bg=palette('accentdark'))
        self.menuFrame.grid(column=0,row=2,pady=(20,20))


        self.sortMode = sort
        self.update_items(items)
    
    def _mousewheel(self, event):
        scrollDir = event.delta/120
        delta = setting('font')[1]*2    #bigger font size means faster scrolling!
        if self.itemFrame.winfo_y() > -delta and scrollDir > 0:
            self.itemCanvas.yview_moveto(0)
        else:
            self.itemCanvas.yview_moveto( (-self.itemFrame.winfo_y()-delta*scrollDir) / self.itemFrame.winfo_height() )

    def add_menu_button(self, text, bg="#000000", fg="#ffffff", command=None):
        '''Adds a button to the selection list menu'''
        self.menu_buttons.append(tk.Button(self.menuFrame, text=text, bg=bg, fg=fg, font=setting('font', 0.75), command=command))
        self.menu_buttons[len(self.menu_buttons)-1].pack(side='left')

    def set_selection(self, selectionList):   
        '''Sets the selection to contain the items in selectionList.
        \nIf any items in this list are not in self.items, they are simply ignored.
        \nIf \'checkList\' is false, raises an exception,
        \nif \'allowMultipleSelection\' is false, raises an exception when setting the selection to more than one thing'''
        selectionList = list(selectionList)
        if not self.checkList:
            raise ValueError('||ERROR|| Tried to set selection to anything while \'checkList\' set to false')
        if not self.allowMultipleSelection and len(selectionList) > 1:
            raise ValueError('||ERROR|| Tried to set selection to more than 1 value while \'allowMultipleSelection\' set to false')
        self.selection.clear()
        for item in self.items:
            if item in selectionList: #As long as this item can actually be selected...
                self.selection.append(item)
                self.buttons[self.items.index(item)].config(bg='#ffffff',fg='#000000')
            else:
                self.buttons[self.items.index(item)].config(bg='#000000',fg='#ffffff')

    def clear_selection(self):
        '''Clears the selection'''
        self.selection.clear()
        for button in self.buttons: button.config(bg='#000000',fg='#ffffff')
    def invert_selection(self):
        '''Inverts the selection'''
        self.selection = list(set(self.items).difference(set(self.selection))) #Difference of sets is the inversion of selection
        for i in range(len(self.items)): 
            if self.items[i] in self.selection:     self.buttons[i].config(bg='#ffffff',fg='#000000')
            else:                                   self.buttons[i].config(bg='#000000',fg='#ffffff')

    def update_items(self, items):  
        '''Clears the selection and replaces the items with a new set of items'''
        self.clear_selection()
        if self.items == items: return #If the list is literally identical, do nothing. We still clear the selection for consistency, though.
        self.items = list(items)
        #Sorts the new list of items
        def alphaKey(e):    return e.lower()
        def floatKey(e):    return float(e)
        if self.sortMode == 'float':    self.items.sort(key=floatKey)
        else:                           self.items.sort(key=alphaKey)
        #Updates the total number of buttons to match self.items
        while len(self.buttons) != len(self.items):
            if len(self.buttons) > len(self.items): self.__remove_button()
            else:                                   self.__add_button()
        #Updates all of the button names
        for i in range(len(self.items)):
            textToBe = self.items[i]
            #Truncates the string, if we have specified it
            if self.truncate and self.width > 3 and self.width-3 < len(textToBe):   textToBe = textToBe[0:self.width-3]+'...'
            self.buttons[i].configure(text=textToBe)
        #Updates the scrollbar
        self.itemFrame.update()  
        beeBox = self.itemFrame.bbox('ALL')
        self.itemCanvas.configure(scrollregion=beeBox)  #0ms!!!!

    def __remove_button(self):    
        self.buttons.pop().destroy()
    def __add_button(self):
        button = tk.Button(self.itemFrame, bg='#000000', fg='#ffffff', font=setting('font2', 0.75), width=self.width, command=p(self.button_command, len(self.buttons), self.command) )
        self.buttons.append(button)
        button.grid(column=0,row=len(self.buttons)-1)
        button.bind('<MouseWheel>', self._mousewheel)


    def button_command(self, i, command=None):
        '''The default command for a button'''
        item = self.items[i] #This is the name of the button that was pressed.

        #No selection by default, single selection for checklists, multi-selection for checklists with allowMultipleSelection
        if self.checkList:
            if item in self.selection:
                self.selection.remove(item)
                self.buttons[i].config(bg='#000000',fg='#ffffff')
            else:
                if self.allowMultipleSelection:     self.selection.append(item)
                else:                               
                    if len(self.selection) == 1: self.buttons[self.items.index(self.selection[0])].config(bg='#000000',fg='#ffffff') #Turns the other button black
                    self.selection = [item] #Changes the selection to only be the new item
                self.buttons[i].config(bg='#ffffff',fg='#000000')
        
        #Optional custom command to be run after the button is pressed. Always throws the just-selected item and whole selection into the command, to be used at will.
        if command != None: command(item, self.selection)

    def disable(self): #Disables functionality of all buttons
        for button in self.buttons:         button.configure(state='disabled')
        for button in self.menu_buttons:    button.configure(state='disabled')
    def enable(self):  #Enables functionality of all buttons
        for button in self.buttons:         button.configure(state='normal')
        for button in self.menu_buttons:    button.configure(state='normal')



