# AUTO-ACCOUNTANT DEVELOPER NOTES:



# Design, GUI, and User-Friendliness

### Design/GUI

* UNDO/REDO NOTIFICATION
	- add a little text message to the bottom-bar, when memento loaded, it pops up displaying a message for 5, 10 or so seconds
	- maybe make it more generalized: consider other messages to put into it like "saved"! when saving the portfolio

- NEW VIEWS: 
	- INFO/STATS
		- Integrate info/stats panels into the main window where the GRID is currently
		- have a giant scrollable textbox replace the GRID 
	- WALLETS
		- Like the "portfolio" view, but shows wallets instead of assets,
		and shows new wallet-specific metrics like USD and such
		- opening a wallet will show transactions under it
			- transactions here same as under grandledger: same metrics shown
		- requires calculating a lot more wallet-specific metrics like total USD value, asset balances, etc.
	* ERRORS/WARNINGS LOG
		- all printed program messages are saved to a log, which can be displayed.

* "BROWSER TABS" FOR VIEWS
	- For selecting different views, the user can simply click on tabs at the top of the screen like in a browser
	- tabs for: portfolio_assets, portfolio_wallets, grand_ledger, error_log
	- no tabs for: portfolio_stats, asset_stats, wallet_stats, asset_ledger, wallet_ledger

* GRAPHS
	- Create informative graphs which show chronological data displayed daily/monthly/annually, for individual cryptos or the whole portfolio
		- shows total holdings over time
		- shows value of holdings over time (requires historical market data)
	- these are probably accessible via the GRID row right click menu 

### User-Friendliness

* GRID
	- SEAMLESS PAGES
		- Use QTableView to implement "Lazy Loading"
		- Lazy Loading:
			- Only what's visible is rendered
		- Upside: no more pages, user can just scroll though an entire ledger
		- Upside: Zoom is way more flexible: no complex rescaling neccesary anymore
		- Upside: should hopefully remove the QScrollArea lag spike
		- Downside: GRID totally needs revamping: now will need to be multiple rows instead of one QLabel per column

	* "NEW TRANSACTION" COLOR
		- After creating/importing transactions, they should be highlighted green or smthg
		- Need to decide: how does "new" color state clear? should user press a button?

* BETTER IMPORTING
	- Current problems:
		1. * Coinbase prices inaccurate (consider omitting bad data instead, user can fix this)
		2. * Gemini transfer-outs missing fee data
		3. * Gemini balance inaccurate
		4. Gemini Earn "admin" withdrawals to nowhere (must wait for case to end)
		5. Gemini Earn -> Gemini "tardy transfers": several times, transfers fail to link because they are recorded days apart by each side of Gemini
		6. Lack of transaction data to import:
			- Old Electrum Wallet
			- Alchemix Farm
			- FTX
			- Flexa Capacity
		7. Coinbase data has duplicate transactions, and cut-off descriptions for newer transactions, making it needlessly difficult to remove the bad transactions. I can remove most, but there are two (under ADA) which have to be manually removed. 
	- Consider implementing a way for users to more easily manually link unlinked transfers
		- or instead, maybe, after failing to link normally, it "tries harder", and looks for the most likely transaction? One nearest in date/quantity?

* AUTOFIND PRICE BUTTONS IN TRANSACTION EDITOR
	- Button next to loss/fee/gain price, which automatically estimates the price based on what the user put in for the respective asset/class and date

* HELP BUTTONS
	- Provide detailed information about metric calculation
	- Provide detailed information in the transaction editor about transactions
	- Some kind of tutorial on how to use the program
		- how to import/create transactions
		- how to fix different kinds of errors
	 

* EXCHANGE API INTEGRATION: Integrate APIs into my program so that I can instantly and effortlessly import new transactions without having to download stupid files first
	- Coinbase API
	- Gemini API

- TAX FORM CALCULATION
	- Rewrite tax form code
	- New tax dialog window, prompts user to select desired form, and desired fiscal year
	- try and figure out if I can automatically generate a PDF or fill out the IRS form, programmatically

- AUTOSAVES: 
	- Automatically save the portfolio every minute or 30 secs, to a "temp" file. 
	- The file is deleted if the program terminates normally. Otherwise, the file is detected on boot and a prompt pops up, "the program was terminated abnormally, load autosave file?"
	- Autosave file only needs to contain data from UNDO mementos. When the autosave is loaded, it just re-applies the user's changes to the original file
	
- SAVE FILES OPEN PROGRAM: Have windows open Auto-Accountant w/ the save file loaded when you double-click on one of these save files. This means having a custom file extension associated with my program, and having the program recognize that it is receiving a file to load in.

* SHORTCUTS - more keyboard shortcuts? Intuitive functionality? Drag&Drop?
	- Ctrl-O: Open/Load
	- Ctrl-C: Copy transactions
	- Ctrl-V: paste transactions
	- ... others?

* FEWER POPUP MENUS - more direct integration into the main window
	
- Properly implement Fiats as an asset class
	- Implementing non-USD fiats themselves is easy, and I can load their market data from YahooFinance just like stocks
	- Implementing the ability to have a base currency that ISN'T USD is VERY difficult, since all transactions prices are currently known and based in USD. It changes how assets have performed over time, especially if the foreign fiat is unstable relative to USD

# Refactoring

- MAKE TRANSACTIONS CLEAN RAW_DATA ON IMPORT INSTEAD OF EXPORT
	- clean based on trans. type if type is defined
	- if type undefined, clean based on default_trans_data
	
* DESTROY METRICS CLASS
	- most methods are specific to assets, portfolios, even wallets. these methods should be moved to their respective object classes
	- the only method that should remain is auto_account, which when given a portfolio object will do its thing

* IMPROVED ERROR HANDLING:
	- Transactions/Assets need to have new functions:
		- .add_error(type, msg)
		- .clear_error(type)
		- .clear_non_data_errors()
	- type/msg will just be a dict of errors now: {type:msg}

# Performance Improvements

* FORMAT_METRIC PERFORMANCE BOOST
	- make it faster... but how???

* STARTUP PERFORMANCE BOOST
	- Current lag is due to QScrollArea resizing - this can be fixed if I reprogram the GRID to use QTableView, combined with lazy loading for seamless pages

* PRE-FORMATTING
	- pre-format wallet metrics (once wallet view implemented)

- SAVE COMPRESSION: Compress the JSON files before saving them, with a custom file extension. 

### Multi-Threading
- OFF-THREAD SAVING
	- Saving the portfolio should be handled by another thread

- MULTI-THREADED METRICS:
	- Idea 1: Separate metric calculation onto multiple threads
		- Difficulties:
			- figuring out how to divvy up the transactions among threads
			- figuring out where the split occurs
			- Having to synchronize multiple threads
			- how many threads to create? Answer: os.cpu_count()
			- It seems that the auto_accounting function cannot be multithreaded
	- Idea 2: Only one new thread. When user makes changes, metric recalculation starts but doesn't "lag" the program
		- Calculate .metrics() on a second thread off of the main one
			- stops if user does new/load/merge
			- restarts when user makes more changes and metrics is called again
		- Indicator: there should be a little icon or smthg that tells the user that the app is "re-calculating..." or "auto-accounting..."

- MULTI-THREADED OBJECT INSTANTIATION
	- This affects only large loads:
		- Loading big portfolio for the first time
		- Importing lots of transactions from CSV/XLSX
	- Thought: Divide instantiation of transactions into multiple threads. For each transaction in the JSON, throw that transaction into the instantiation stack of another thread. Threads do hard work of creating Transaction objects, then pass these objects back to the main thread's execution stack, to be added to the MAIN_PORTFOLIO object 
- MULTI-THREADED GRID COLUMN POPULATION
	- will this work?

# Other

### Pythonic Tricks
- More F-strings
- list/dictionary comprehension
- match/case statements, instead of "elif elif elif..."
- Replace "try" statements with "in DICT" where possible. "In LIST" is actually worse, though.
	IN DICT is better than TRY/IN SET is better than IN TUPLE is better than IN LIST
- For any nested dictionaries, instead of using the basic dictionary, use 'from collections import defaultdict as dd'
This allows us to create, say dict['key']['subkey'] even if 'key' doesn't currently exist
(Generally I avoid having nested dictionaries though - now instead I use object-oriented programming)

* IMPORTANT NOTE ABOUT STRINGS
	- It is entirely unneccessary to replace all of the strings in the program with a universal library the strings are pulled from
	- I tried this; it had 0 impact on performance
	- Python probably creates a universal library for strings like I did when it compiles the program, to vastly boost efficiency
	




	

		


	

	
	
	
	
	
	
	
	
	

