# AUTO-ACCOUNTANT DEVELOPER NOTES:



# Design, GUI, and User-Friendliness

### Design/GUI

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

* HEADER COLORING
	- Make it more obvious which metric we're sorting by, and the direction it's sorting in.
	- Something like a light blue shade when sorting by it. and an up/down arrow based on direction
	- re-coloring/-formatting of header title controlled by GRID

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
	
- SAVE FILES OPEN PROGRAM: Have windows open Auto-Accountant w/ the save file loaded when you double-click on one of these save files. This means 
	having a custom file extension associated with my program, and having the program recognize that it is receiving a file to load in.

* SHORTCUTS - more keyboard shortcuts? Intuitive functionality? Drag&Drop?
	Ctrl-Shift-S: Save as
	Ctrl-O: Open/Load
	
	... others?

* FEWER POPUP MENUS
	
- Properly implement Fiats as an asset class
	- Implementing non-USD fiats themselves is easy, and I can load their market data from YahooFinance just like stocks
	- Implementing the ability to have a base currency that ISN'T USD is VERY difficult, since all transactions prices are currently known and based in USD. It changes how assets have performed over time, especially if the foreign fiat is unstable relative to USD

# Refactoring

- MAKE TRANSACTIONS CLEAN RAW_DATA ON IMPORT, NOT EXPORT
	- clean based on trans. type if type is defined
	- if type undefined, clean based on default_trans_data

- TRANSACTION CHECKS CONSISTENCY
	- Use Transaction(raw_data).get_metric('missing') as much as possible to determine when raw data are missing, instead of doing needless extra checks
	- Mainly this will affect the Transaction Editor

- DESTROY "TEMP", make its variables part of AutoAccountant class

* DESTROY METRICS CLASS
	- most methods are specific to assets, portfolios, even wallets. these methods should be moved to their respective object classes
	- the only method that should remain is auto_account, which when given a portfolio object will do its thing

* IMPROVE ERROR HANDLING:
	- Transactions/Assets need to have new functions:
		- .add_error(type, msg)
		- .clear_error(type)

# Performance Improvements

* PRE-FORMATTING - consider above, "destroy metrics class", before this
	- pre-format asset metrics
	- pre-format wallet metrics
	- pre-format portfolio metrics?

* FORMAT NUMBER PERFORMANCE FIX
	- format_number currently performs like ass: 450ms for 200,000 iterations!!! 
	- that's half a second of load time each time you load a 5300-transaction portfolio!!!! Not horrible... yet.
	- I should test whether this is O(n) or something worse (should be O(n) where n = # of transactions)

* FASTER UNDO/REDO SAVES (Maybe rename these to "statesaves", indicating they save a change of state)
	- Instead of saving a copy of the entire portfolio to memory, just save the part whose state changed before/after
	- maybe add statesave function to Portfolio: statesave always triggers whenever transaction/asset/wallet is added/removed from the portfolio, unless it is told not to.
		- now "new portfolio" and "load portfolio" will erase all statesave history. "

- SAVE COMPRESSION: Compress the JSON files before saving them, with a custom file extension. 

# Bugs and Issues

* THE IMPORT DUPLICATION ISSUE: Some kind of way to prevent transactions with missing data from re-importing	
	- If an imported transaction was missing data, then we fill out that data, the transaction's hash code changes. Then, if we import the same transaction again, a duplicate of this transaction is added to our porfolio. This is an issue!
		SOLUTION 2: if a newly imported transaction has an error, it is permanently saved to the JSON in a new category "import_errors"
			This is good since we only really care about transactions we fixed
		SOLUTION 3: all transactions have "origin" variable,
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
	



### Multi-Threading
- AAmetrics: auto_account
	Modify it such that it takes advantage of multithreading to improve performance.
	This will be tricky :
	- figuring out how to divvy up the transactions to be processed
	- Having to synchronize multiple threads
	- ensuring that the HIFO/LIFO/FIFO results are always the same: no race condition
	- figuring out how many threads to create
	- avoiding race conditions
- Loading JSON data
	Thought: Divide instantiation of transactions into multiple threads. For each transaction in the JSON, throw that transaction into the instantiation stack of another thread. Threads do hard work of creating Transaction objects, then pass these objects back to the main thread's execution stack, to be added to the MAIN_PORTFOLIO object


	

		


	

	
	
	
	
	
	
	
	
	

