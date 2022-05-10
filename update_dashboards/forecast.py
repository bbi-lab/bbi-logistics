#!/usr/bin/env python3

import os
import re
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


def main():

    #get google sheets database
    client = get_gspread_client(
        base_dir / f'.config/logistics-db-1615935272839-a608db2dc31d')

    #sheet with how many pcdeqc are completed for each day
    pcdeqcSheet = client.open('Logistics Data').worksheet('kits')
    #3 week average tests by project and weekday used for future forecasting
    forecastSheet = client.open('forecast_db').worksheet('forecast_db')

    #variable names for each project
    projectDict = {
        'SCAN English': {
            "project_id": "22461",
            'pcdeqc': 'samp_process_date',
            'Zipcode': 'home_zipcode_2'
        },
        'SCAN Spanish': {
            "project_id": "22475",
            'pcdeqc': 'samp_process_date',
            'Zipcode': 'home_zipcode_2'
        },
        'SCAN Russian': {
            "project_id": "22472",
            'pcdeqc': 'samp_process_date',
            'Zipcode': 'home_zipcode_2'
        },
        'SCAN Trad Chinese': {
            "project_id": "22474",
            'pcdeqc': 'samp_process_date',
            'Zipcode': 'home_zipcode_2'
        },
        'SCAN Vietnamese': {
            "project_id": "22477",
            'pcdeqc': 'samp_process_date',
            'Zipcode': 'home_zipcode_2'
        },
        'HCT': {
            "project_id": "45",
            'pcdeqc': 'samp_process_date',
            'Zipcode': 'core_zipcode_2'
        }
    }

    today = datetime.datetime.today()
    pcdeqc = pd.DataFrame(pcdeqcSheet.get_all_records())
    #most recent date pcdeqc was completed
    recentDate = max(pd.to_datetime(pcdeqc['Date'])).strftime('%Y-%m-%d')
    print('Since: ' + str(recentDate))

    if recentDate != datetime.datetime.strftime(today - datetime.timedelta(1),
                                                '%Y-%m-%d'):
        recentDate = recentDate + ' 24:00'
        returnedSamples = []
        #loops through all projects and gets project name and date sample was scanned into lab
        for project in projectDict:
            returnedSamples.extend(
                getSamplesInLab(project, recentDate, projectDict))
        returnedSamples = pd.DataFrame(returnedSamples)

        #checks if no reults before data manipulation
        if len(returnedSamples.index) == 0:
            print('no rows added. pcdeqc up to date')
        else:
            returnedSamples = aggregate_data(returnedSamples, today)
            #format for google sheets import
            import_to_pcdeqc(returnedSamples, pcdeqcSheet)

    create_forecast(pcdeqcSheet, forecastSheet, today)


def get_gspread_client(auth_file):
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(auth_file, scope)
    return (gspread.authorize(creds))


def getSamplesInLab(project, date, projectDict):
    #when sample was scanned in at lab and zipcode
    fields = [projectDict[project]['pcdeqc'], projectDict[project]['Zipcode']]
    #filter for all values after recent date
    filter = f"[event-name][{str(projectDict[project]['pcdeqc'])}] > \"{str(date)}\""

    if project == "HCT":
        url = urlparse(os.environ.get("HCT_REDCAP_API_URL"))
    else:
        url = urlparse(os.environ.get("REDCAP_API_URL"))
    data = {
        'token':
        os.environ.get(
            f"REDCAP_API_TOKEN_{url.netloc}_{projectDict[project]['project_id']}"
        ),
        'content':
        'record',
        'format':
        'json',
        'type':
        'flat',
        'fields':
        ",".join(map(str, fields)),
        'rawOrLabel':
        'label',
        'rawOrLabelHeaders':
        'raw',
        'returnFormat':
        'json',
        'filterLogic':
        filter
    }
    print('fetching records from ' + str(project))
    r = requests.post(url.geturl(), data=data)
    results = r.json()

    formattedResults = []
    for record in results:
        row = {}
        zipcode = record[projectDict[project]['Zipcode']]
        #SCAN language projects have dirty zipcode fields: <span lang='es'> 98115 </span>
        if re.search('^<', zipcode):
            zipcode = re.findall('[0-9][0-9][0-9][0-9][0-9]', zipcode)[0]
        #if a scan project, differs between SCAN King and SCAN Pierce
        if re.search('SCAN+', project):
            if zipcode in [
                    '98101', '98102', '98103', '98104', '98105', '98106',
                    '98107', '98108', '98109', '98112', '98115', '98116',
                    '98117', '98118', '98119', '98121', '98122', '98125',
                    '98126', '98133', '98134', '98136', '98144', '98146',
                    '98154', '98155', '98164', '98177', '98178', '98195',
                    '98199', '98004', '98005', '98006', '98007', '98008',
                    '98033', '98034', '98039', '98040', '98056', '98059',
                    '98011', '98028', '98001', '98002', '98003', '98023',
                    '98030', '98031', '98032', '98042', '98047', '98055',
                    '98057', '98058', '98148', '98166', '98168', '98188',
                    '98198', '98010', '98022', '98038', '98045', '98051',
                    '98065', '98027', '98029', '98052', '98074', '98075',
                    '98092', '98070', '98014', '98077', '98053', '98024',
                    '98072', '98019'
            ]:
                row['project'] = 'SCAN King'
            elif zipcode in [
                    '98409', '98406', '98404', '98402', '98411', '98413',
                    '98419', '98418', '98415', '98401', '98405', '98416',
                    '98417', '98403', '98388', '98466', '98303', '98351',
                    '98464', '98465', '98333', '98349', '98407', '98335',
                    '98394', '98395', '98528', '98332', '98329', '98431',
                    '98430', '98439', '98327', '98493', '98438', '98433',
                    '98496', '98497', '98498', '98499', '98467', '98444',
                    '98446', '98445', '98447', '98448', '98408', '98391',
                    '98422', '98352', '98443', '98390', '98372', '98354',
                    '98424', '98421', '98375', '98374', '98371', '98373',
                    '98580', '98387', '98397', '98330', '98398', '98304',
                    '98348', '98558', '98328', '98344', '98338', '98323',
                    '98396', '98360', '98385', '98321'
            ]:
                row['project'] = 'SCAN Pierce'
            else:
                row['project'] = 'SCAN Other'
        else:
            row['project'] = project
        row['date'] = record[projectDict[project]['pcdeqc']]
        #add dictionary row with project and date to returned list
        formattedResults.append(row)
    return (formattedResults)


def aggregate_data(returnedSamples, today):
    returnedSamples['date'] = pd.to_datetime(
        returnedSamples['date']).dt.strftime('%Y-%m-%d')
    #excludes today's samples since partial days would not be used in forecasting
    returnedSamples = returnedSamples[
        returnedSamples['date'] != today.strftime('%Y-%m-%d')]
    print('fetched ' + str(len(returnedSamples.index)) + ' rows')
    table = returnedSamples.groupby(['date',
                                     'project']).agg({'project': 'count'})
    return table


def import_to_pcdeqc(returnedSamples, pcdeqcSheet):
    index = returnedSamples.index.tolist()
    values = returnedSamples.values.tolist()
    pcdeqcImport = []

    for i in range(len(index)):
        pcdeqcImport.append(list(index[i]) + values[i])

    pcdeqcSheet.insert_rows(pcdeqcImport, next_available_row(pcdeqcSheet))
    print('added ' + str(len(pcdeqcImport)) + ' rows to pcdeqc')


def next_available_row(worksheet):
    '''find next available row in a given sheet'''
    str_list = list(filter(None, worksheet.col_values(1)))
    return len(str_list) + 1


def create_forecast(pcdeqcSheet, forecastSheet, today):
    #create forecast based off pcdeqc
    pcdeqc = pd.DataFrame(pcdeqcSheet.get_all_records())
    pcdeqc['Date'] = pd.to_datetime(pcdeqc['Date'])

    #21 day average (22 is used to account for today being excluded)
    pcdeqc = pcdeqc[pcdeqc['Date'] >= today - datetime.timedelta(22)]

    weekDays = [
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
        "Sunday"
    ]
    pcdeqc['weekday'] = pcdeqc['Date'].apply(lambda x: weekDays[x.weekday()])

    pcdeqc['Date'] = pcdeqc['Date'].dt.strftime('%Y-%m-%d')

    pcdeqc = pcdeqc[['Project', 'weekday',
                     'Date']].groupby(['Project', 'weekday']).count()
    print(pcdeqc)

    #when the forecast was created
    pcdeqc['forecasted'] = today.strftime('%Y-%m-%d')

    index = pcdeqc.index.tolist()
    values = pcdeqc.values.tolist()
    forecastImport = []

    for i in range(len(index)):
        forecastImport.append(list(index[i]) + values[i])
    print(forecastImport)
    forecastSheet.insert_rows(forecastImport,
                              next_available_row(forecastSheet),
                              value_input_option='USER_ENTERED')
    print('updated forecast')


if __name__ == "__main__":
    main()