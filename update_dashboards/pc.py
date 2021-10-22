#!/usr/bin/env python3

import os
import json
import envdir
import gspread
import requests
import datetime
import pandas as pd
from pathlib import Path
from functools import reduce
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

	sheet = client.open('Logistics Data')

	# Export all records from SCAN redcap
	# print('Getting PC REDCap data')
	# pc_data = pd.DataFrame(get_pc_redcap_data())

	# print('Importing PC data')
	# import_pc(pc_data, sheet.worksheet('pc'))

	print('Getting Group Enrollment REDCap data')
	ge_data = pd.DataFrame(get_ge_redcap_data()).apply(lambda x: pd.to_datetime(x).dt.strftime('%Y-%m-%d'))

	print('Importing Group Enrollment data')
	import_ge(ge_data, sheet.worksheet('ge'))

def get_gspread_client(auth_file):
	scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
	creds = ServiceAccountCredentials.from_json_keyfile_name(auth_file, scope)
	return(gspread.authorize(creds))

def get_pc_redcap_data():
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

def get_ge_redcap_data():
	export_feilds = [
		'consent_date',
		'attempt_1',
		'attempt_2',
		'attempt_3',
		'referral_date']
	url = urlparse(os.environ.get("REDCAP_API_URL"))

	formData = {
		'token':os.environ.get(f"REDCAP_API_TOKEN_{url.netloc}_21991"),
		'content':'record',
		'format':'json',
		'type': 'flat',
		'fields':",".join(map(str, export_feilds)),
		'rawOrLabel':'label',
		'returnFormat':'json',
		}
	r = requests.post(url.geturl(),data=formData)
	return(r.json())

def import_ge(data, sheet):
	attempts = pd.concat([data['attempt_1'],data['attempt_2'],data['attempt_3']], ignore_index=True).value_counts(dropna=True)
	attmepts = pd.DataFrame(attempts.reset_index()
		).rename(columns={'index':'date',0:'attempts'})
	enrollments = pd.DataFrame(data['consent_date'].value_counts(dropna=True).reset_index()
		).rename(columns={'index':'date','consent_date':'enrollments'})
	referrals = pd.DataFrame(data['referral_date'].value_counts(dropna=True).reset_index()
		).rename(columns={'index':'date','referral_date':'referrals'})
	dfs = [referrals, attmepts, enrollments]
	df_final = reduce(lambda left,right: pd.merge(left,right,on='date',how='outer'), dfs)

	sheet.delete_rows(2, sheet.row_count)

	try:
		sheet.append_rows(df_final.fillna(0).values.tolist(), value_input_option='USER_ENTERED')
	except Exception as e:
		print(f'Error inserting data {e}')
		sheet.append_rows([['']])

if __name__ == "__main__":
    main()