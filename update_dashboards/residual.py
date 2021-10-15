#!/usr/bin/env python3

import gspread
import pandas as pd
from pathlib import Path
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

base_dir = Path(__file__).resolve().parent.parent.resolve()

def main():
	print("Connecting to Google Sheets")
	# creates conneciton to google sheets
	client = get_gspread_client(base_dir / f'.config/logistics-db-1615935272839-a608db2dc31d')

	# link to Google sheet
	sheet = client.open('Residuals Dashboard')

	# Import data from ID3C
	print('Getting ID3C data')
	data = pd.read_csv(base_dir / f'data/id3c_scan_residual_data.csv')
	data.fillna('', inplace=True)
	print(data.shape)

	import_data(data.values.tolist(), sheet.worksheet('data'))

	sheet.worksheet('update').update('A2', datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M'))

def get_gspread_client(auth_file):
	scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
	creds = ServiceAccountCredentials.from_json_keyfile_name(auth_file, scope)
	return(gspread.authorize(creds))

def import_data(data, sheet):
	print('Importing Data')
	sheet.delete_rows(2, sheet.row_count)
	try:
		sheet.append_rows(data, value_input_option='USER_ENTERED')
	except:
		print('Error inserting data')
		sheet.append_rows([['']])

if __name__ == "__main__":
    main()
