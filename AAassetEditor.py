from AAlib import *
from AAmessageBox import MessageBox

import tkinter as tk
from functools import partial as p



class AssetEditor(tk.Toplevel):
    def __init__(self, upper, a):  #upper is a reference to the original PortfolioApp, master is a reference to the TopLevel GUI 
        '''Opens a new asset editor for asset \'a\' for editing\n
            upper - a reference to the tkinter window which called this editor\n
            If no \'a\' is entered, the new transaction editor will open'''
        super().__init__()
        self.configure(bg=palette('dark'))
        self.protocol('WM_DELETE_WINDOW', self.comm_cancel) #makes closing the window identical to hitting cancel
        self.grab_set()       #You can only interact with this window now
        self.focus_set()
        self.resizable(False,False)  #So you cant resize this window

        if a==1:
            self.title('Create Asset')
        else:
            self.title('Edit Asset')

        self.upper, self.oldID= upper, a

        self.AssetClasses = []    #creates a list of all the asset classes names
        for c in assetclasslib:
            self.AssetClasses.append(assetclasslib[c]['name'])

        self.create_GUI()
        self.create_MENU()
        self.create_ENTRIES()

        #BINDINGS
        #==============================
        self.bind('<Escape>', self._esc)

        self.update()    #Necessary, so that geometry() has the correct window dimensions
        self.geometry('+%d+%d' % ( (self.winfo_screenwidth()-self.winfo_width())/2 + self.winfo_x()-self.winfo_rootx(),
                                                    (self.winfo_screenheight()-self.winfo_height())/2 ))#centers the window in the middle of the screen
        

    def create_GUI(self):
        #GUI CREATION
        #==============================
        self.GUI = {}

        self.GUI['transEditorFrame'] = tk.Frame(self, bg=palette('accent'))

        self.GUI['title'] = tk.Label(self.GUI['transEditorFrame'], fg=palette('entrycursor'), bg=palette('accent'), font=settings('font'))
        if self.oldID==1:
            self.GUI['title'].configure(text='Create Asset')
        else:
            self.GUI['title'].configure(text='Edit '+str(self.oldID.split('z')[0])+' Asset')

        self.GUI['entryFrame'] = tk.Frame(self.GUI['transEditorFrame'], bg=palette('light'))
        self.GUI['menuFrame'] = tk.Frame(self.GUI['transEditorFrame'])

        #GUI RENDERING
        #==============================
        self.GUI['transEditorFrame'].grid(padx=(20,20), pady=(20,20))

        self.GUI['title'].grid(column=0,row=0, pady=(20,20))
        self.GUI['entryFrame'].grid(column=0,row=2)
        self.GUI['menuFrame'].grid(column=0,row=3, pady=(20,20))

    def create_MENU(self):
        #MENU CREATION
        #==============================
        self.MENU = {}

        #SAVE/CANCEL buttons
        self.MENU['save'] = tk.Button(self.GUI['menuFrame'], text='Save', bg=palette('entry'), fg='#00ff00', font=settings('font'), command=self.comm_save)
        self.MENU['cancel'] = tk.Button(self.GUI['menuFrame'], text='Cancel', bg=palette('entry'), fg='#ff0000', font=settings('font'), command=self.comm_cancel)
        self.MENU['delete'] = tk.Button(self.GUI['menuFrame'], text='Delete', bg='#ff0000', fg='#000000', font=settings('font'), command=self.comm_deleteAsset)

        #MENU RENDERING
        #==============================

        #SAVE/CANCEL buttons
        self.MENU['save'].pack(side='left')
        self.MENU['cancel'].pack(side='left')
        if self.oldID != 1:
            self.MENU['delete'].pack(side='left')

    def create_ENTRIES(self):        
        #STRING VARIABLES
        #==============================
        self.TEMP = {       #These are the default values for all inputs            
            'ticker':       tk.StringVar(self, value=''),     
            'name':         tk.StringVar(self, value=''),
            'class':         tk.StringVar(self, value='-NO TYPE SELECTED-'),
            'desc':         tk.StringVar(self, value='')
        }
        if self.oldID != 1:  #If not NEW, replace default value with what you're actually editing
            self.TEMP['ticker'].set(self.oldID.split('z')[0])
            self.TEMP['name'].set(PERM['assets'][self.oldID]['name'])
            self.TEMP['class'].set(assetclasslib[self.oldID.split('z')[1]]['name'])
            self.TEMP['desc'].set(PERM['assets'][self.oldID]['desc'])

        #WIDGETS
        #==============================
        self.ENTRIES = {}
        self.LABELS = {}

        #ENTRIES
        #==============
        widthsetting = 24

        for entry in ['ticker','name']:
            self.ENTRIES[entry] = tk.Entry(self.GUI['entryFrame'], textvariable=self.TEMP[entry], width=widthsetting, bg=palette('entry'), fg=palette('entrytext'), insertbackground=palette('entrycursor'), disabledbackground=palette('dark'), disabledforeground=palette('entrycursor'), font=settings('font'))
        
        self.ENTRIES['desc'] = tk.Text(self.GUI['entryFrame'], wrap='word', bg=palette('entry'), fg=palette('entrytext'), insertbackground=palette('entrycursor'), font=settings('font'), height=8,width=widthsetting)
        self.ENTRIES['desc'].insert(0.0, self.TEMP['desc'].get())
        
        self.ENTRIES['class'] = tk.OptionMenu(self.GUI['entryFrame'], self.TEMP['class'], *self.AssetClasses)
        self.ENTRIES['class'].configure(bg=palette('entry'), fg=palette('entrycursor'), font=settings('font'), highlightthickness=0)

        #Entry restrictions

        def validTicker(new, char):
            if char == ' ':
                return False
            if len(new) > 24:
                return False
            return True
        valTicker = self.register(validTicker)
        self.ENTRIES['ticker'].configure(validate='key', vcmd=(valTicker, '%P', '%S'))

        def validName(new):
            if len(new) > 24:
                return False
            return True
        valName = self.register(validName)
        self.ENTRIES['name'].configure(validate='key', vcmd=(valName, '%P'))
        
        #LABELS
        #==============
        labelText = ['Ticker','Name','Class','Description']
        labelKeys = ['ticker','name','class','desc']
        for key in range(len(labelKeys)):
            self.LABELS[labelKeys[key]] = tk.Label(self.GUI['entryFrame'], text=labelText[key], bg=palette('light'), fg=palette('entrycursor'), font=settings('font',0.5))


        #RENDERING
        #==============================

        self.LABELS['ticker']   .grid(column=0,row=0, sticky='NS')
        self.ENTRIES['ticker']  .grid(column=1,row=0, sticky='NS')

        self.LABELS['name']     .grid(column=0,row=1, sticky='NS')
        self.ENTRIES['name']    .grid(column=1,row=1, sticky='NS')

        self.LABELS['class']     .grid(column=0,row=2, sticky='NS')
        self.ENTRIES['class']    .grid(column=1,row=2, sticky='NSEW')

        self.LABELS['desc']     .grid(column=0,row=3, sticky='NS')
        self.ENTRIES['desc']    .grid(column=1,row=3, sticky='NS')
        
    def updateProfileInstance(self, newID=None):    #Deletes instances of this asset from profiles. Adds 'newID' back into those profiles, if specified
        '''If an asset name is modified, or An asset is deleted, that change has to be applied to profiles. This does that.'''
        profiles = PERM['profiles']
        for p in profiles:
            if self.oldID in profiles[p]['assets']:    #if this asset is in there, pop it
                profiles[p]['assets'].pop(profiles[p]['assets'].index(self.oldID))
                if newID != None:
                    profiles[p]['assets'].append(newID)


    def comm_deleteAsset(self):
        PERM['assets'].pop(self.oldID)      #removal from permanent data
        self.updateProfileInstance()        #removal from profiles
        self.upper.metrics()
        self.upper.render(None, True)
        self.upper.undo_save()
        self.comm_cancel()


    def comm_save(self):
        #DATA CULLING AND CONVERSION PART I
        #==============================
        #converts all tk.StringVar's to their proper final format
        TEMP2 = {
            'name' : self.TEMP['name'].get().rstrip().lstrip(),
            'desc' : self.ENTRIES['desc'].get(1.0,'end').rstrip().lstrip(),
            'trans': {}
        }
        #If this isn't a brand new asset, import the old transaction data
        if self.oldID != 1: TEMP2['trans'] = PERM['assets'][self.oldID]['trans']
        
        ID = self.TEMP['ticker'].get().upper()
        for c in assetclasslib:     #adds the asset class tag to the end of the asset's name
            if self.TEMP['class'].get() == assetclasslib[c]['name']:
                ID += 'z' + c
                break

        # CHECKS
        #==============================
        #new ticker will be unique?
        if ID in PERM['assets'] and ID != self.oldID:
            MessageBox(self, 'ERROR!', 'An asset already exists with the same ticker and asset class!')
            return

        #Ticker isn't an empty string?
        if ID == '':
            MessageBox(self, 'ERROR!', 'Must enter a ticker')
            return

        #Asset class hasn't gone unselected
        if self.TEMP['class'].get() == '-NO TYPE SELECTED-':
            MessageBox(self, 'ERROR!', 'Must select an asset class')
            return
        #If not new and the asset class has been changed, make sure all old transactions are still valid under the new asset class
        if self.oldID != 1 and self.oldID.split('z')[1] != ID.split('z')[1]:
            for t in PERM['assets'][self.oldID]['trans']:
                if PERM['assets'][self.oldID]['trans'][t]['type'] not in assetclasslib[ID.split('z')[1]]['validTrans']:    #if transaction t's trans. type is NOT one of the valid types...
                    MessageBox(self, 'ERROR!', 'This asset contains transactions which are impossible for asset class \'' + assetclasslib[ID.split('z')[1]]['name'] + '\'.')
                    return

        #Name isn't an empty string?
        if TEMP2['name'] == '':
            MessageBox(self, 'ERROR!', 'Must enter a name')
            return


        #ASSET SAVING AND OVERWRITING
        #==============================
        #Create a NEW asset, or overwrite the old one
        PERM['assets'][ID] = TEMP2

        if self.oldID not in [1,ID]: #ID CHANGE: The ID was modified. Deletes the old asset
            PERM['assets'].pop(self.oldID)  #removal of old asset
            self.updateProfileInstance(ID)  #renaming of instances of this asset within profiles

        self.upper.metrics_ASSET(ID)
        self.upper.render(self.upper.asset, True)
        self.upper.undo_save()
        self.comm_cancel()

    def _esc(self,event):    #Exit this window
        self.comm_cancel()
    def comm_cancel(self):  
        self.upper.grab_set()
        self.upper.focus_set()
        self.destroy()  #no extra commands, so that closing the window is functionally identical to cancellation






