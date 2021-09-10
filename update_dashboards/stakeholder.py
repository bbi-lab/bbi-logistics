#!/usr/bin/env python3

import re
import json
import gspread
import requests
import datetime
import numpy as np
import pandas as pd
from pathlib import Path
from oauth2client.service_account import ServiceAccountCredentials

base_dir = Path(__file__).resolve().parent.parent.resolve()

def main():
	pd.options.mode.chained_assignment = None
	print("Connecting to Google Sheets")
	# creates conneciton to google sheets
	client = get_gspread_client(base_dir / f'.conf/logistics-db-1615935272839-a608db2dc31d')

	# link to SCAN King External Metrics Google sheets
    # https://docs.google.com/spreadsheets/d/12PyvtpD8QlMSUzWYGiB4GfA29bSfLz8Ke_0UNN_6Jus/edit#gid=0
	sheet = client.open('SCAN GV External Metrics')

	# Import data from downloaded metabase file
	# Query:
	print('Getting ID3C data')
	data = pd.read_csv(base_dir / f'data/id3c_scan_data.csv')
	data.dropna(subset=['encountered'])
	print(data.shape)

	# Filter out all non king county by Zipcode
	print('Filtering to King County')
	data = filter_king_puma(data)
	print(data.shape)

	# GV requested pre IRB data
	# print('Filtering to SCAN IRB')
	# data = data[data['encountered'] > '2020-06-10']
	# print(data.shape)
	import_samples(data, sheet.worksheet('Samples'))
	import_sex(data, sheet.worksheet('Sex'))
	import_age(data, sheet.worksheet('Age'))
	import_language(data, sheet.worksheet('Language'))
	import_race_ethnicity(data, sheet.worksheet('Race'))

def get_gspread_client(auth_file):
	scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
	creds = ServiceAccountCredentials.from_json_keyfile_name(auth_file, scope)
	return(gspread.authorize(creds))

def filter_king_puma(data):
	puma = [
		'11601',
		'11602',
		'11603',
		'11604',
		'11605',
		'11606',
		'11607',
		'11608',
		'11609',
		'11610',
		'11611',
		'11612',
		'11613',
		'11614',
		'11615',
		'11616',
		''
	]
	data['puma'] = data['puma'].apply(lambda puma: '' if pd.isna(puma) else str(int(puma % 100000)))
	return(data[data['puma'].isin(puma)])

def import_samples(data, sheet):
	print('Importing Sample Data')
	sample_data = data[['encountered','scan_study_arm','priority_code', 'puma', 'present']]
	sample_data.fillna('', inplace=True)
	sheet.delete_rows(2, sheet.row_count)
	sheet.append_rows(sample_data.values.tolist(), value_input_option='USER_ENTERED')

def import_sex(data, sheet):
	print('Importing Sex Data')
	data = data.groupby(['encountered','sex'], as_index=False
		).agg({'sample_id':'count'})
	sheet.delete_rows(2, sheet.row_count)
	sheet.append_rows(data.values.tolist(), value_input_option='USER_ENTERED')

def import_age(data, sheet):
	print('Importing Age Data')
	data['age bucket'] = data.apply(lambda row: get_age_bucket(row['age']), axis = 1)
	data = data.groupby(['encountered','age bucket'], as_index=False
		).agg({'sample_id':'count'})
	sheet.delete_rows(2, sheet.row_count)
	sheet.append_rows(data.values.tolist(), value_input_option='USER_ENTERED')

def get_age_bucket(age):
	if pd.isna(age):
		return('Missing')
	age = int(age)
	if age >= 80:
		return('80+ years')
	elif age >=	70:
		return('70-79 years')
	elif age >=	60:
		return('60-69 years')
	elif age >=	50:
		return('50-59 years')
	elif age >=	40:
		return('40-49 years')
	elif age >=	30:
		return('30-39 years')
	elif age >=	20:
		return('20-29 years')
	elif age >=	0:
		return('0-19 years')
	else:
		return('Missing')

def import_language(data, sheet):
	print('Importing Language Data')
	data = data.groupby(['encountered', 'language_enrolled'], as_index=False
		).agg({'sample_id':'count'})
	sheet.delete_rows(2, sheet.row_count)
	sheet.append_rows(data.values.tolist(), value_input_option='USER_ENTERED')

def import_race_ethnicity(data, sheet):
	print('Importing Race & Ethnicity Data')
	#data = data.dropna(subset=['hispanic_or_latino', 'race'])
	data['race_and_ethnicity'] = data.apply(lambda row: get_race_and_ethniciy(row['race'], row['hispanic_or_latino']), axis=1)
	data = data.groupby(['encountered','race_and_ethnicity'], as_index=False
		).agg({'sample_id':'count'})
	sheet.delete_rows(2, sheet.row_count)
	sheet.append_rows(data.values.tolist(), value_input_option='USER_ENTERED')

def get_race_and_ethniciy(race, ethnicity):
	try:
		if race is np.nan:
			return('Missing')
		elif ethnicity == 1:
			return('Hispanic or Latino, any Race')
		elif re.search('other+|,', race):
			return('Other/Multi, Non Hisp.')
		elif re.search('white+', race):
			return('White, not Hispanic')
		elif re.search('americanIndianOrAlaskaNative+', race):
			return('Amer. Indian or Alaska Native')
		elif re.search('blackOrAfricanAmerican+', race):
			return('Black, not Hispanic')
		elif re.search('asian+', race):
			return('Asian, not Hispanic')
		elif re.search('nativeHawaiian+', race):
			return('NH/OPI')
	except Exception as e:
		print('Error: %s, race: %s, eth: %s'% (e, race, ethnicity))
#find next available row in a given sheet

if __name__ == "__main__":
    main()
