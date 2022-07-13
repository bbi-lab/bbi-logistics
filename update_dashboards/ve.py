#!/usr/bin/env python3

from pathlib import Path
import gspread
import csv

from oauth2client.service_account import ServiceAccountCredentials

base_dir = Path(__file__).resolve().parent.parent.resolve()


def main():
    client = get_gspread_client(
        base_dir / '.config/logistics-db-1615935272839-a608db2dc31d')

    sheet = client.open('Vaccine Effectivness Dashboard')

    sheets = [
        'Vaccine Doses', 'Vaccination Status', 'Infection Probability',
        'Screening Method', 'VE Variant'
    ]

    for s in sheets:
        data = get_data(base_dir / f'data/{s.replace(" ","_").lower()}.csv')
        import_data(data, sheet.worksheet(s))


def get_gspread_client(auth_file):
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(auth_file, scope)
    return (gspread.authorize(creds))


def get_data(file):
    with open(file, encoding='utf-8') as csvfile:
        data = csv.reader(csvfile)
        next(data)
        return list(data)


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
