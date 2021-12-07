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
	# links variables to courier sheet
	db = client.open('Logistics Data').worksheet("courier")

	print("Calculating missing dates")
	# find what dates in the google sheets are missing
	missing_dates = get_missing_dates(db)

	print(missing_dates)

	print('Getting KPI and exceptions data')
	data = []

	for day in missing_dates:
		try:
			data.extend(get_courier_data(client, day))

		except gspread.exceptions.SpreadsheetNotFound:
			print('No sheet found for {}'.format(day))

		except TypeError as e:
			print(f'KPI or exceptions returned length 0 for {day} {e}')

	print('{: <30}{}'.format('Total import rows:', str(len(data))))
	db.insert_rows(data, next_available_row(db))
	client.open('Logistics Data').worksheet('update').update('B2',
		datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d %H:%M'))


# takes a string for a location of a json file containing the google api credentials
# returns the gspread authentication variable
def get_gspread_client(auth_file):
	scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
	creds = ServiceAccountCredentials.from_json_keyfile_name(auth_file, scope)
	return(gspread.authorize(creds))


# takes a gspread google sheet variable
# returns the missing dates between 3/21/2021 (earliest date) and today
def get_missing_dates(db):
	today = datetime.datetime.today()
	courier = pd.DataFrame(db.get_all_records())
	try:
		courierDates = pd.unique(courier['date'])
	except KeyError:
		courierDates = []
	realDates = pd.Series(pd.date_range(datetime.datetime(2021, 3, 21), today))
	realDates = realDates.apply(lambda x: x.strftime("%m/%d/%y").lstrip("0").replace("/0", "/"))
	diffDates = list(set(realDates)-set(courierDates))
	return(diffDates)


# takes a gspread authentication variable and string of a date
# returns a table containing the number of orders, false trips, lates, by study for the given date
def get_courier_data(client, date):
	# connects to the kpi and exceptions in google sheets
	kpi = client.open(f'UW Brotman KPIs Excel{date.replace("/","_")}').get_worksheet(0)
	exceptions = client.open(f'UW Brotman Exceptions Excel{date.replace("/","_")}').get_worksheet(0)

	# create dataframes for both sheets
	kpiDF = pd.DataFrame(kpi.get_all_records())
	exceptionsDF = pd.DataFrame(exceptions.get_all_records())

	# cathes if the file contains nothing
	if len(kpiDF.index) == 0 or len(exceptionsDF.index) == 0:
		return

	# column names
	columns = ['OrderNumber', 'CreateDate', 'ProjectName', 'Out/Return',
			   'PUZip', 'DLZip', 'FalseTrip', 'Late']

	# The exceptions table does not have PUZip or DLZip but it may be added in the future.
	# Setting to empty values since columns are needed for the concat
	try:
		exceptionsDF[['PUZip','DLZip']]
	except KeyError:
		exceptionsDF[['PUZip','DLZip']] = ['', '']

	# combine the kpi and exceptions data and drop duplicate orders
	table = pd.concat([kpiDF[columns], exceptionsDF[columns]], ignore_index=True
		).drop_duplicates(subset=['OrderNumber'])

	table['ParticipantZip'] = table.apply(participant_zip, axis=1)

	table = table.groupby(['CreateDate', 'ProjectName', 'Out/Return', 'ParticipantZip'],
		).agg({
			'Out/Return': 'count',
			'FalseTrip': sum,
			'Late': sum,
		})
	# reset index does not work with two Out/Return columns so renaming to orders
	table.columns = ['orders', 'ft', 'late']
	table.reset_index(inplace=True)
	print('{: <30}{}'.format(str(date.date())+' Orders:', str(sum(table['orders']))))
	return(table.values.tolist())


# finds the participant's zipcode based on an order's Out/Return value
def participant_zip(x):
	return x['PUZip'] if x['Out/Return'] == 'Return' else x['DLZip']


# returns the next empty row in a sheet
def next_available_row(worksheet):
	str_list = list(filter(None, worksheet.col_values(1)))
	return len(str_list)+1


if __name__ == "__main__":
	main()
