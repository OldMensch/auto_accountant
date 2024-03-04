

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
	
* IMPROVE ERROR HANDLING:
	- Add a button that lets you see all the erroneous transactions together
      	I ought to improve "Bad Transaction" detection. There exists some code already, but its a bit messy. That ought to be fixed.
		Stuff to check (The STUPID check!):
		- No integer overflow
		- Maximum string length, cut off by defined maximum length in AAlib (since all Decimal objects are permanently stored as strings)
		- Various constraints on data entry (positive-only, size constraints, etc
	- All of this ought to be in a single method, contained under the Transaction class. 
	- Consider modifying the transaction editor, so that I can enter almost whatever I please into the different boxes
		To combat errors, every time a character is entered into any of the entry boxes, a command is trun to check for errors
		If errors are found, the erroneous boxes will be colored red or something, and a little error message will appear below
		
		This will allow for more efficient and robust editing of transactions

* ISSUE: Some kind of way to prevent transactions with missing data from re-importing	
	- If an imported transaction was missing data, then we fill out that data, the transaction's hash code changes. Then, if we import the same transaction list again, a duplicate of this transaction is added to our porfolio. This is a bad issue!
		SOLUTION 1: the first time a transaction is loaded, it is hashed (as I do it now), and given a PERMANENT unique ID, that always refers to that exact transaction

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

* REFACTORING: CODE ORGANIZATION:
	- Separate large methods into multiple smaller parts for better organization. 
	- Consider separating methods inside of AA__main__ into a separate class
	- Consider segregating the GUI from the algorithmic code: moving the algorithmic code into its own class as much as possible
		This is difficult for dialogue boxes, which have tons of GUI-algorithmic interaction. 

* TAXES
	- Fix the code for calculating tax information so that it actually works
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


	
	
	
	
	
	
	
	
	

