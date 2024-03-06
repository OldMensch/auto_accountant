

---
# NOTES FOR AUTO-ACCOUNTANT:

* INFO/STATS INTEGRATION: Integrate info/stats panels into the main window where the GRID is currently

* EXCHANGE API INTEGRATION: Integrate APIs into my program so that I can instantly and effortlessly import new transactions without having to download stupid files first
	- Coinbase API
	- Gemini API

* GRAND LEDGER:
	- fix tickerclass names (remove tickerclasses altogether)
* NO MORE "TICKERCLASS": This brings the program towards 3rd Normal Form
	- remove the "tickerclass" item altogether when working with assets
	- requires reworking of the transaction editor code - no longer just "loss_asset", now it will be "loss_ticker" and "loss_class"
	- Requires reworking what data saves to files, primarily for transaction data
	- Requires pulling my hair out
	

* Pythonic tricks:
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
	
* IMPROVE ERROR HANDLING:
	- Transactions/Assets need to have new functions:
		- .add_error(type, msg)
		- .clear_error(type)

* THE IMPORT DUPLICATION ISSUE: Some kind of way to prevent transactions with missing data from re-importing	
	- If an imported transaction was missing data, then we fill out that data, the transaction's hash code changes. Then, if we import the same transaction list again, a duplicate of this transaction is added to our porfolio. This is a bad issue!
		SOLUTION 2: if a newly imported transaction has an error, it is permanently saved to the JSON in a new category "import_errors"
			This is good since we only really care about transactions we fixed
		SOLUTION 3: all transactions have "origin" variable,
			Origin tag denotes: when they were imported (and to what wallet), or that the user made it
			EX:		origin: imported12-12-2024 12:13:23binance
			problem: user might totally change transaction when editing, and it should not preserve the ID after that


* MULTI-THREADING:
	- AAmetrics: perform_automatic_accounting
		Modify it such that it takes advantage of multithreading to improve performance.
		This will be tricky :
		- figuring out how to divvy up the transactions to be processed
		- Having to synchronize multiple threads
		- ensuring that the HIFO/LIFO/FIFO results are always the same: no race condition
		- figuring out how many threads to create
		- avoiding race conditions
	- Loading JSON data
		Thought: Divide instantiation of transactions into multiple threads. For each transaction in the JSON, throw that transaction into the instantiation stack of another thread. Threads do hard work of creating Transaction objects, then pass these objects back to the main thread's execution stack, to be added to the MAIN_PORTFOLIO object

* TAXES
	- Rewrite tax code
	- Create a variable, using user-defined tax rate(s), to calculate how much they owe in taxes since january 1 this year. Maybe let the user pull up a chart which shows their

* GRAPHS
	- Create informative graphs which show chronological data displayed daily/monthly/annually, for individual cryptos or the whole portfolio
		- shows total holdings over time
		- shows 

STORING OF DATA
* FASTER UNDO/REDO SAVES (Maybe rename these to "deltasaves", indicating they save a change of state)
	- Instead of saving a copy of the entire portfolio to memory, just save the part whose state changed before/after
		UPSIDE:		This will make undo/redo really really fast
		DOWNSIDE: 	This intoduces a lot of potential bugs, if done improperly
	
- SAVE COMPRESSION: Compress the JSON files before saving them, with a custom file extension. 
		
- SAVE FILES OPEN PROGRAM: Have windows open Auto-Accountant w/ the save file loaded when you double-click on one of these save files. This means 
	having a custom file extension associated with my program, and having the program recognize that it is receiving a file to load in.
	
- AUTOSAVES: Automatically save the portfolio every minute, or maybe every so many changes, to a "temp" file. The file is deleted if the program terminates normally. If not, the file is automatically loaded and a prompt pops up, "the program was terminated abnormally, load autosave file?"
	- DON'T save UNDO saves to disk: this would be a huge waste of processing power


USER FRIENDLINESS:
* THE GRID: Fancier GRID functionality ideas:
	- Alternating gray/darker gray for rows of the table to improve readability

* Add more conventional shortcuts to the program:
	Ctrl-Shift-S: Save as
	Ctrl-O: Open/Load
	
	... others?
	
* More integration, less sub-windows
	- For example, instead of having editor errors as a popup, integtrate most them into the editor window itself
	- Integrate infostats windows into where the GRID is currently... maybe even use the GRID itself for formatting?
	
- Properly implement Fiats as an asset class
	- Implementing non-USD fiats themselves is easy, and I can load their market data from YahooFinance just like stocks
	- Implementing the ability to have a base currency that ISN'T USD is VERY difficult, since all transactions prices are currently known and based in USD. It changes how assets have performed over time, especially if the foreign fiat is unstable relative to USD


	
	
	
	
	
	
	
	
	

