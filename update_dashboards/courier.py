#!/usr/bin/env python3

import gspread
import datetime
import pandas as pd
from pathlib import Path
from oauth2client.service_account import ServiceAccountCredentials

base_dir = Path(__file__).resolve().parent.parent.resolve()

def main():
	print("Connecting to Google Sheets")
	# creates conneciton to google sheets with google api
	client = get_gspread_client(base_dir / f'.config/logistics-db-1615935272839-a608db2dc31d')
	# links variables to courier_db sheets
	db = client.open('courier_db').worksheet("courier_db")

	print("Calculating missing dates")
	# find what dates in the google sheets are missing
	missing_dates = get_missing_dates(db)

	print('Getting KPI and exceptions data')
	data = []
	# loop through the missing days and check for shipping kpi and exceptions sheets
	for day in missing_dates:
		date = datetime.datetime.strptime(day, '%m/%d/%y')
		try:
			# make call to get the data from both sheets
			data.extend(get_courier_data(client, date))
		# catch exception for calling a sheet that does not exist
		except gspread.exceptions.SpreadsheetNotFound as e:
			print('No sheet found for {}'.format(str(day)))
		except TypeError as e:
			print('KPI or exceptions returned length 0 for {}'.format(str(day)))
	print('{: <30}{}'.format('Total import rows:',str(len(data))))
	db.insert_rows(data, next_available_row(db))

# takes a string for a location of a json file containing the google api credentials
# returns the gspread authentication variable
def get_gspread_client(auth_file):
	scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
	creds = ServiceAccountCredentials.from_json_keyfile_name(auth_file, scope)
	return(gspread.authorize(creds))

# takes a gspread google sheet variable
# returns the missing dates between 3/21/2021 (earliest date) and today
def get_missing_dates(db):
	today = datetime.datetime.today()
	courier = pd.DataFrame(db.get_all_records())
	courierDates = pd.unique(courier['date'])
	realDates = pd.date_range(datetime.datetime(2021,3,21), today).strftime('%-m/%-d/%y')
	diffDates = list(set(realDates)-set(courierDates))
	diffDates.sort()
	return(diffDates)

# takes a gspread authentication variable and string of a date
# returns a table containing the number of orders, false trips, lates, by study for the given date
def get_courier_data(client, date):
	# connects to the kpi and exceptions in google sheets
	kpi = client.open('UW Brotman KPIs Excel'+str(datetime.datetime.strftime(date,'%-m_%-d_%Y'))).get_worksheet(0)
	exceptions = client.open('UW Brotman Exceptions Excel'+str(datetime.datetime.strftime(date,'%-m_%-d_%Y'))).get_worksheet(0)

	# create dataframes for both sheets
	kpiDF = pd.DataFrame(kpi.get_all_records())
	exceptionsDF = pd.DataFrame(exceptions.get_all_records())

	# cathes if the file contains nothing
	if len(kpiDF.index) == 0 or len(exceptionsDF.index) == 0:
		return

	# column names
	columns = ['CreateDate', 'ProjectName', 'Out/Return', 'FalseTrip', 'Late']
	# combine the kpi and exceptions data, gorup by, and aggregate
	table = pd.concat([kpiDF[columns], exceptionsDF[columns]], ignore_index=True
		).groupby(['CreateDate','ProjectName','Out/Return'],
		).agg({
			'Out/Return':'count',
			'FalseTrip':sum,
			'Late':sum,
		})
	# reset index does not work with two Out/Return columns so renaming to orders
	table.columns = ['orders', 'ft', 'late']
	table.reset_index(inplace=True)
	print('{: <30}{}'.format(str(date.date())+' Orders:',str(sum(table['orders']))))
	return(table.values.tolist())

#returns the next empty row in a sheet
def next_available_row(worksheet):
	str_list = list(filter(None, worksheet.col_values(1)))
	return len(str_list)+1

if __name__ == "__main__":
    main()
