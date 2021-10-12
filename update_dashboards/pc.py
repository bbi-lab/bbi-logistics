#!/usr/bin/env python3

import os
import json
import envdir
import gspread
import requests
import datetime
import pandas as pd
from pathlib import Path
from urllib.parse import urlparse
from oauth2client.service_account import ServiceAccountCredentials

base_dir = Path(__file__).resolve().parent.parent.resolve()
envdir.open(base_dir / f'.env/redcap')

base_dir = Path(__file__).resolve().parent.parent.resolve()
envdir.open(base_dir / f'.env/redcap')

def main():

	print("Connecting to Google Sheets")
	# creates conneciton to google sheets
	client = get_gspread_client(base_dir / f'.config/logistics-db-1615935272839-a608db2dc31d')

	sheet = client.open('Logistics Weekly Review')

	# Export all records from SCAN redcap
	print('Getting REDCap data')
	data = pd.DataFrame(get_redcap_data())

	import_pc(data, sheet.worksheet('pc'))
	# data.to_csv('out.csv')

def get_gspread_client(auth_file):
	scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
	creds = ServiceAccountCredentials.from_json_keyfile_name(auth_file, scope)
	return(gspread.authorize(creds))

def get_redcap_data():
	export_feilds = [
		'call_date',
		'study',
		'highlevel_sub',
		'enrollment_sub',
		'redcap_sub',
		'shipping_sub',
		'testing_sub',
		'results_sub']
	url = urlparse(os.environ.get("REDCAP_API_URL"))

	formData = {
		'token':os.environ.get(f"REDCAP_API_TOKEN_{url.netloc}_23594"),
		'content':'record',
		'format':'json',
		'type': 'flat',
		'fields':",".join(map(str, export_feilds)),
		'rawOrLabel':'label',
		'returnFormat':'json',
		}
	r = requests.post(url.geturl(),data=formData)
	return(r.json())


def import_pc(data, sheet):
	print('Importing PC Data')
	data = pd.melt(data, id_vars=['call_date', 'study'], value_vars=['highlevel_sub',
		'enrollment_sub','redcap_sub','shipping_sub','testing_sub','results_sub']
		).rename(columns={'variable': 'category', 'value': 'issue'}
		).replace('',pd.NA
		).dropna(subset=['issue']
		).replace(pd.NA,'')

	sheet.delete_rows(2, sheet.row_count)
	try:
		sheet.append_rows(data.values.tolist(), value_input_option='USER_ENTERED')
	except Exception as e:
		print(f'Error inserting data {e}')
		sheet.append_rows([['']])

if __name__ == "__main__":
    main()