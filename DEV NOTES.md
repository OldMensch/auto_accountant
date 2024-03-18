# AUTO-ACCOUNTANT DEVELOPER NOTES:



# Design, GUI, and User-Friendliness

### Design/GUI

* MEMENTO CHANGE NOTIFICATION
	- add a little text message to the bottom-bar, when undo/redo triggered, it pops up displaying a message for 5, 10 or so seconds
	- might also be able to have other messages in it

* INFO/STATS INTEGRATION: Integrate info/stats panels into the main window where the GRID is currently

- NEW VIEW: WALLETS
	- Like the "portfolio" view, but shows wallets instead of assets,
	and shows new wallet-specific metrics like USD and such
	- opening a wallet will show transactions under it
		- transactions here same as under grandledger: same metrics shown
	- requires calculating a lot more wallet-specific metrics like total USD value, asset balances, etc.

* NEW VIEW: ERRORS/WARNINGS LOG
	- all printed program messages are saved to a log, which can be displayed.

* "BROWSER TABS" FOR VIEW SELECTION
	- For selecting different views, the user can simply click on tabs at the top of the screen like in a browser
	- Will not include asset_ledger view and wallet_ledger view

* THE GRID: Fancier GRID functionality ideas:
	- Alternating lighter/darker gray for rows of the table to improve readability

* GRAPHS
	- Create informative graphs which show chronological data displayed daily/monthly/annually, for individual cryptos or the whole portfolio
		- shows total holdings over time
		- shows 

### User-Friendliness

* SEAMLESS PAGES
	- Use QScrollArea to implement "Lazy Loading"
	- Lazy Loading:
		- Only what's visible is rendered
	- Upside: no more pages, user can just scroll though an entire ledger
	- Upside: Zoom is way more flexible: no complex rescaling neccesary anymore
	- Downside: GRID totally needs revamping: now will need to be multiple rows instead of one QLabel per column

* EASIER IMPORTING
	- Current problems:
		- Gemini Earn "admin" withdrawals to nowhere (must wait for case to end)
		- Gemini Earn -> Gemini "tardy transfers": several times, transfers fail to link because they are recorded days apart by each side of Gemini
		- Lack of transaction data to import:
			- Old Electrum Wallet
			- Alchemix Farm
			- FTX
			- Flexa Capacity
		- Coinbase data has duplicate transactions, and cut-off descriptions for newer transactions, making it needlessly difficult to remove the bad transactions. I can remove most, but there are two (under ADA) which have to be manually removed. 
	- Consider implementing a way for users to more easily manually link unlinked transfers
		- or instead, maybe, after failing to link normally, it "tries harder" and expands the time-delay bubble to like 3 days or smthg

* AUTOFIND PRICE FOR TRANSACTION EDITOR
	- Button next to loss/fee/gain price, which automatically estimates the price based on what the user put in for the respective asset/class

* HEADER COLORING
	- Make it more obvious which metric we're sorting by, and the direction it's sorting in.
	- Something like a light blue shade when sorting by it. and an up/down arrow based on direction
	- re-coloring/-formatting of header title controlled by GRID

* NEW TRANSACTION COLORING
	- After creating/importing transactions, they are highlighted green or smthg
	- Need to decide: how does "new" color state clear? should user press a button?

* WEBSITE LINKS FOR MORE INFO
	- When in "Portfolio_Assets" view, right clicking on a row will give you the option to:
		- Go to YahooFinance.com for stocks/fiats
		- Go to StockAnalysis.com for stocks/fiats/cryptocurrencies
		- Go to CoinMarketCap.com for cryptocurrencies <- this requires knowing CMC's special long name for the crypto, retrievable from market data library
	- Then, it's as easy as:
		```python
		import webbrowser
		webbrowser.open("http://THE_WEBSITE.com")
		```

* HELP BUTTONS
	- Provide detailed information about metric calculation
	- Provide detailed information in the transaction editor about transactions 

* EXCHANGE API INTEGRATION: Integrate APIs into my program so that I can instantly and effortlessly import new transactions without having to download stupid files first
	- Coinbase API
	- Gemini API

- TAX FORM CALCULATION
	- Rewrite tax code
	- Create a variable, using user-defined tax rate(s), to calculate how much they owe in taxes since january 1 this year. Maybe let the user pull up a chart which shows their

- AUTOSAVES: Automatically save the portfolio every minute, or maybe every so many changes, to a "temp" file. The file is deleted if the program terminates normally. If not, the file is automatically loaded and a prompt pops up, "the program was terminated abnormally, load autosave file?"
	- DON'T save UNDO saves to disk: this would be a huge waste of processing power
	
- SAVE FILES OPEN PROGRAM: Have windows open Auto-Accountant w/ the save file loaded when you double-click on one of these save files. This means having a custom file extension associated with my program, and having the program recognize that it is receiving a file to load in.

* SHORTCUTS - more keyboard shortcuts? Intuitive functionality? Drag&Drop?
	- Ctrl-Shift-S: Save as
	- Ctrl-O: Open/Load
	- Ctrl-C: Copy transactions
	- Ctrl-V: paste transactions
	- ... others?

* FEWER POPUP MENUS
	
- Properly implement Fiats as an asset class
	- Implementing non-USD fiats themselves is easy, and I can load their market data from YahooFinance just like stocks
	- Implementing the ability to have a base currency that ISN'T USD is VERY difficult, since all transactions prices are currently known and based in USD. It changes how assets have performed over time, especially if the foreign fiat is unstable relative to USD

# Refactoring

- MAKE TRANSACTIONS CLEAN RAW_DATA ON IMPORT, NOT EXPORT
	- clean based on trans. type if type is defined
	- if type undefined, clean based on default_trans_data

- DESTROY "TEMP", make its variables part of AutoAccountant class

* DESTROY METRICS CLASS
	- most methods are specific to assets, portfolios, even wallets. these methods should be moved to their respective object classes
	- the only method that should remain is auto_account, which when given a portfolio object will do its thing

* IMPROVE ERROR HANDLING:
	- Transactions/Assets need to have new functions:
		- .add_error(type, msg)
		- .clear_error(type)
		- .clear_non_data_errors()
	- type/msg will just be a dict of errors now: {type:msg}

# Performance Improvements

* FORMAT_METRIC PERFORMANCE BOOST
	- make it faster... but how???

* STARTUP PERFORMANCE BOOST
	- Figure out how to make instantiation of QScrollArea not 160ms long
	- figure out how to make self.showMaximized() not 175ms long

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
		- Loading portfolio for the first time
		- Importing transactions from CSV/XLSX
	- Thought: Divide instantiation of transactions into multiple threads. For each transaction in the JSON, throw that transaction into the instantiation stack of another thread. Threads do hard work of creating Transaction objects, then pass these objects back to the main thread's execution stack, to be added to the MAIN_PORTFOLIO object 
- MULTI-THREADED GRID COLUMN POPULATION
	- will this work?

# Bugs and Issues

* THE IMPORT DUPLICATION ISSUE: Some kind of way to prevent transactions with missing data from re-importing	
	- If an imported transaction was missing data, then we fill out that data, the transaction's hash code changes. Then, if we import the same transaction again, a duplicate of this transaction is added to our porfolio. This is an issue!
		- SOLUTION 2: if a newly imported transaction has an error, it is permanently saved to the JSON in a new category "import_errors"
			This is good since we only really care about transactions we fixed
		- SOLUTION 3: all transactions have "origin" variable,
			Origin tag denotes: when they were imported (and to what wallet), or that the user made it
			EX:		origin: imported12-12-2024 12:13:23binance
			problem: user might totally change transaction when editing, and it should not preserve the ID after that

# Other

### Pythonic Tricks
- See if f-strings can shorten code anywhere
	* NOTE: variables in f-strings CAN BE FORMATTED! like so: f'this is normal text, this isn\'t: {my_float_var:.2f}'
	* They can be formatted algorithmically by doing the following: f"here is a float: {the_float:{formatting_code_var}}"
- See if I can use list/dictionary comprehension to shorten code and improve efficiency
- See if I can use match/case statements instead of many elif elif elif...
- Replace "try" statements with "in DICT" where possible. "In LIST" is actually worse, though.
	IN DICT is better than TRY/IN SET is better than IN TUPLE is better than IN LIST
- For any nested dictionaries, instead of using the basic dictionary, use 'from collections import defaultdict as dd'
This allows us to create, say dict['key']['subkey'] even if 'key' doesn't currently exist
(Generally I avoid having nested dictionaries though - now instead I use object-oriented programming)

* IMPORTANT NOTE ABOUT STRINGS
	- It is entirely unneccessary to replace all of the strings in the program with a universal library the strings are pulled from
	- I tried this; it had 0 impact on performance
	- Python probably creates a universal library for strings like I did when it compiles the program, to vastly boost efficiency
	




	

		


	

	
	
	
	
	
	
	
	
	

