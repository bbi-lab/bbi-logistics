#!/usr/bin/env python3

import re
import os
import json
import envdir
import gspread
import requests
import datetime
from pathlib import Path
from urllib.parse import urlparse
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

#variable mapping for each REDCap project
projectDict = {
    'SCAN English': {
        "project_id": "22461",
        'Record Id': 'record_id',
        'Collection': 'pre_scan_barcode',
        'BEMS': 'back_end_scan',
        'Zipcode': 'home_zipcode_2'
    },
    'SCAN Spanish': {
        "project_id": "22475",
        'Record Id': 'record_id',
        'Collection': 'pre_scan_barcode',
        'BEMS': 'back_end_scan',
        'Zipcode': 'home_zipcode_2'
    },
    'SCAN Russian': {
        "project_id": "22472",
        'Record Id': 'record_id',
        'Collection': 'pre_scan_barcode',
        'BEMS': 'back_end_scan',
        'Zipcode': 'home_zipcode_2'
    },
    'SCAN Trad Chinese': {
        "project_id": "22474",
        'Record Id': 'record_id',
        'Collection': 'pre_scan_barcode',
        'BEMS': 'back_end_scan',
        'Zipcode': 'home_zipcode_2'
    },
    'SCAN Vietnamese': {
        "project_id": "22477",
        'Record Id': 'record_id',
        'Collection': 'pre_scan_barcode',
        'BEMS': 'back_end_scan',
        'Zipcode': 'home_zipcode_2'
    },
    'HCT': {
        "project_id": "45",
        'Record Id': 'record_id',
        'Collection': 'pre_scan_barcode',
        'BEMS': 'back_end_scan',
        'Zipcode': 'core_zipcode_2',
        'Zipcode2': 'core_zipcode'
    },
    'AIRS': {
        "project_id": "1372",
        'Record Id': 'subject_id',
        'Collection': 'pre_scan_barcode',
        'BEMS': 'back_end_scan',
        'Zipcode': 'enr_mail_zip',
        'Zipcode2': 'wk_mail_zip'
    }
}

base_dir = Path(__file__).resolve().parent.parent.resolve()
envdir.open(base_dir / f'.env/redcap')

exportFields = ['Record Id', 'Collection', 'BEMS', 'Zipcode']
columns = ['Project', 'Record Id', 'Collection', 'BEMS', 'Zipcode']


def main():
    with open(base_dir / f'etc/zipcode_county_map.json', 'r') as f:
        zipcode_county_map = json.load(f)
    print("Connecting to Google Sheets")
    #creates conneciton to google sheets
    client = get_gspread_client(
        base_dir / f'.config/logistics-db-1615935272839-a608db2dc31d')

    #links variables to ship_out_db sheets
    db = client.open('Logistics Data').worksheet('kits')
    doc = client.open('Logistics Data').worksheet('kits_update')

    lastImport = doc.acell('A2').value
    print('{: <30}{}'.format('Getting kits shipped after:', str(lastImport)))

    shipOutData = []
    for p in (p for p in projectDict if p == 'AIRS'):
        shipOutData.extend(getRecords(p, lastImport, zipcode_county_map))

    print('{: <30}{}'.format('S&S kits shipped:', str(len(shipOutData))))
    db.insert_rows(shipOutData, next_available_row(db))
    doc.update(
        'A2',
        datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d %H:%M'))


def get_gspread_client(auth_file):
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(auth_file, scope)
    return gspread.authorize(creds)


def next_available_row(worksheet):
    str_list = list(filter(None, worksheet.col_values(1)))
    return len(str_list) + 1


def getEvents(project):
    if project == 'HCT':
        url = urlparse(os.environ.get("HCT_REDCAP_API_URL"))
    elif project == "AIRS":
        url = urlparse(os.environ.get("AIRS_REDCAP_API_URL"))
    else:
        url = urlparse(os.environ.get("REDCAP_API_URL"))

    data = {
        'token':
        os.environ.get(
            f"REDCAP_API_TOKEN_{url.netloc}_{projectDict[project]['project_id']}"
        ),
        'content':
        'event',
        'format':
        'json',
    }
    events = requests.post(url.geturl(), data=data)
    events = events.json()
    projectEvents = []
    for e in events:
        projectEvents.append(e['unique_event_name'])
    return projectEvents


def getScanProject(zipcode, zipcode_county_map):
    if zipcode in zipcode_county_map['SCAN KING']:
        return ('SCAN King')
    elif zipcode in zipcode_county_map['SCAN PIERCE']:
        return ('SCAN Pierce')
    else:
        return ('SCAN Other')


def getZipcodes(needZip, project):
    if project == 'HCT':
        zipcodeID = projectDict[project]['Zipcode2']
        url = urlparse(os.environ.get("HCT_REDCAP_API_URL"))
    elif project == "AIRS":
        zipcodeID = projectDict[project]['Zipcode2']
        url = urlparse(os.environ.get("AIRS_REDCAP_API_URL"))
    else:
        zipcodeID = projectDict[project]['Zipcode']
        url = urlparse(os.environ.get("REDCAP_API_URL"))

    zipFields = [zipcodeID, projectDict[project]['Record Id']]

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
        'events':
        'enrollment_arm_1',
        'fields':
        ",".join(map(str, zipFields)),
        'rawOrLabel':
        'label',
        'returnFormat':
        'json',
        'records':
        ",".join(map(str, needZip))
    }
    r = requests.post(url.geturl(), data=data)
    results = r.json()
    otherZips = pd.DataFrame(results)
    otherZips = otherZips[[projectDict[project]['Record Id'], zipcodeID
                           ]].set_index(projectDict[project]['Record Id'])
    return otherZips


def getRecords(project, date, zipcode_county_map):
    #get events
    projectEvents = getEvents(project)
    #format fields for records export
    formattedFields = []
    for f in exportFields:
        formattedFields.append(projectDict[project][f])

    if project == 'HCT':
        url = urlparse(os.environ.get("HCT_REDCAP_API_URL"))
    elif project == "AIRS":
        url = urlparse(os.environ.get("AIRS_REDCAP_API_URL"))
    else:
        url = urlparse(os.environ.get("REDCAP_API_URL"))

    #export records
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
        'events':
        ",".join(map(str, projectEvents)),
        'fields':
        ",".join(map(str, formattedFields)),
        'rawOrLabel':
        'label',
        'returnFormat':
        'json',
        'filterLogic':
        '[event-name][' + str(projectDict[project]['BEMS']) + '] >= "' +
        str(date) + '"'
    }
    r = requests.post(url.geturl(), data=data)
    results = r.json()
    print('{: <30}{: <30}'.format(
        str(project) + ' shipped:', str(len(results))))
    if len(results) == 0:
        return (results)
    records = pd.DataFrame(results)
    records = records[formattedFields]
    records.set_index(projectDict[project]['Record Id'])

    #list of records that have empty zip
    zipcode = projectDict[project]['Zipcode']
    needZip = records[projectDict[project]['Record Id']][records[zipcode] ==
                                                         '']

    #corrects known language zipcode formatting
    records[zipcode] = records[zipcode].apply(lambda x: re.findall(
        '[0-9][0-9][0-9][0-9][0-9]', x)[0] if re.search('^<', x) else x)

    #assign project name to records
    if project in ('HCT', 'Childcare', 'SSD'):
        records['project'] = project
    elif re.search('SCAN+', project):
        records['project'] = records[zipcode].apply(
            lambda x: getScanProject(x, zipcode_county_map))

    #for logitudinal if the zipcode is not in the same event as the bems date
    if len(needZip) != 0 and not (re.search('SCAN+', project)):
        otherZips = getZipcodes(needZip, project)
        records.update(otherZips, join='left')

    records = records.drop(
        [projectDict[project]['Record Id'], 'pre_scan_barcode'], axis=1)
    return records.values.tolist()


if __name__ == "__main__":
    main()
