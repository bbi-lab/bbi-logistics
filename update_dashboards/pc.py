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
	print('Getting PC REDCap data')
	pc_data = pd.DataFrame(get_pc_redcap_data())

	print('Importing PC data')
	import_pc(pc_data.replace('',pd.NA), sheet.worksheet('pc'))

	print('Getting Group Enrollment REDCap data')
	ge_data = pd.DataFrame(get_ge_redcap_data()).apply(lambda x: pd.to_datetime(x).dt.strftime('%Y-%m-%d'))

	print('Importing Group Enrollment data')
	import_ge(ge_data, sheet.worksheet('ge'))

	sheet.worksheet('update').update('A2', datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d %H:%M'))

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
		'results_sub',
		'feedback_sub',
		'time_fu']
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
	# data = data.apply(lambda x: data.drop())

	data.to_csv('original_pc.csv')

	null_issues = data.loc[(data['highlevel_sub'].isnull()) &
		(data['enrollment_sub'].isnull()) &
		(data['redcap_sub'].isnull()) &
		(data['shipping_sub'].isnull()) &
		(data['testing_sub'].isnull()) &
		(data['feedback_sub'].isnull()) &
		(data['results_sub'].isnull()), ['call_date', 'time_fu', 'study']]
	null_issues[['category','issue']] = [pd.NA, pd.NA]

	data = pd.melt(data, id_vars=['call_date', 'time_fu', 'study'], value_vars=['highlevel_sub',
		'enrollment_sub','redcap_sub','shipping_sub','testing_sub','results_sub', 'feedback_sub']
		).rename(columns={'variable': 'category', 'value': 'issue'}
		).dropna(subset=['issue']
		).append(null_issues)

	follow_up_data = data.dropna(subset=['time_fu']
		).drop('call_date',axis=1
		).rename(columns={'time_fu': 'call_date'})
	follow_up_data['call_date'] = follow_up_data.apply(lambda x: pd.to_datetime(x['call_date']).strftime('%Y-%m-%d'), axis=1)

	data = data.drop('time_fu', axis=1
		).append(follow_up_data
		).fillna('')

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