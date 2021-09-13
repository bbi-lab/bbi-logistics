#!/usr/bin/env python3

import os
import re
import json
import envdir
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

base_dir = Path(__file__).resolve().parent.parent.resolve()
envdir.open(base_dir / f'.env/redcap')

# set to run every X minutes

exportColumns = [
    'Record Id',
    'Today Tomorrow',
    'Order Date',
    'Project Name',
    'First Name',
    'Last Name',
    'Street Address',
    'Apt Number',
    'City',
    'State',
    'Zipcode',
    'Delivery Instructions',
    'Email',
    'Phone',
    'Notification Pref',
    'Pickup Location']
replaceAddressColumns = ['Street Address 2','Apt Number 2','City 2','State 2','Zipcode 2']
coreAddressColumns = ['Street Address','Apt Number','City','State','Zipcode']
otherReplace = ['First Name','Last Name','Delivery Instructions','Email','Phone','Notification Pref',]

def main():
    '''Gets orders from redcap and send them to dispatch'''
    # config file for variable name mapping across projects
    with open(base_dir / f'etc/redcap_variable_map.json', 'r') as f:
        projectDict = json.load(f)
    with open(base_dir / f'etc/zipcode_variable_map.json', 'r') as f:
        zipcode_var_map = json.load(f)
    with open(base_dir / f'etc/zipcode_county_map.json', 'r') as f:
        zipcode_county_map = json.load(f)

    order_export = pd.DataFrame(columns=exportColumns, dtype='string')

    for project in projectDict:
        print(f'Getting kit orders for {project}')
        # get data from redcap report and format
        order_data = get_redcap_orders(project, projectDict)
        if len(order_data.index) < 1:
            continue

        # clean data
        order_data = clean(order_data, project, zipcode_var_map)

        # add a column for what project the order belongs
        order_data['Project Name'] = order_data.apply( \
            lambda row: assign_project(row, project, zipcode_county_map), axis=1).astype('string')
        
        # only use columns specified in the the exportColumns array
        order_data = order_data[order_data.columns.intersection(exportColumns)]

        # combine orders in one data frame
        order_export = pd.concat([order_export, order_data], ignore_index=True)

    print(order_export.groupby(['Project Name']).size().reset_index(name='counts'))

    order_export.to_csv(base_dir / f'data/DeliveryExpressOrder{datetime.now().strftime("%Y_%m_%d_%H_%M")}.csv', \
        index=False)

    # TODO:
    # check for bad addresses by sending to DE then handeling bounce backs
    # import to DE results in an error
    # errors get routed to PC team email

def get_redcap_orders(project, projectDict):
    if project == "HCT":
        url = urlparse(os.environ.get("HCT_REDCAP_API_URL"))
    else:
        url = urlparse(os.environ.get("REDCAP_API_URL"))

    data = {
        'token': os.environ.get(f"REDCAP_API_TOKEN_{url.netloc}_{projectDict[project]['project_id']}"),
        'content': 'report',
        'report_id': projectDict[project]['Report Id'],
        'format': 'json',
        'type': 'flat',
        'rawOrLabel': 'raw',
        'rawOrLabelHeaders': 'raw',
        'exportCheckboxLabel': 'false',
        'returnFormat': 'json'
    }

    r = requests.post(url.geturl(),data=data)

    # normalize column names
    try:
        orders = pd.DataFrame(r.json(), dtype='string').rename(columns=projectDict[project])
    except:
        print(f'unable to create DataFrame with: {r.json()}')
        return

    # if there are columns that hint at possible replacement addresses
    if all(val in orders.columns for val in replaceAddressColumns):
        orders['Order Date'] = pd.to_datetime(orders['Order Date'])
        orders['Order Date'].replace('', pd.NA, inplace=True)

        # save original addresses
        original_address = orders.loc[orders['redcap_event_name'] == 'enrollment_arm_1']
        orders = orders.loc[~(orders['redcap_event_name'] == 'enrollment_arm_1')] \
            .dropna(subset=['Order Date']) \
            .sort_values(by='Order Date', ascending=False) \
            .drop_duplicates(subset=['Record Id'], keep='first')

        orders = orders.apply(lambda row: use_best_address(original_address, row), axis=1)

    return orders

def use_best_address(original_address, row):
    # if there is not a replacement address use the original address for a specific record_id
    original = original_address.loc[(original_address['Record Id'] == row['Record Id'])]
    if row[replaceAddressColumns].replace('',pd.NA).isnull().all():
        for val in coreAddressColumns:
            row[val] = original.iloc[0][val]
    else:
        update = row.loc[replaceAddressColumns]
        for val in coreAddressColumns:
            # the replacement fields have a trailing 2
            row[val] = update.loc[str(val+' 2')]
    for val in otherReplace:
        row[val] = original.iloc[0][val]
    return row

def clean(orders, project, zipcode_var_map):
    if re.search('SCAN', project):
        orders['Zipcode'] = orders.apply(lambda row: zipcode_var_map['SCAN'][row['Zipcode']], axis=1)
    return orders

def assign_project(row, project, zipcode_county_map):
    if project == 'HCT':
        return 'HCT'
    elif re.search('SCAN', project):
        if row['Zipcode'] in zipcode_county_map['SCAN KING']:
            return 'SCAN_KING'
        if row['Zipcode'] in zipcode_county_map['SCAN PIERCE']:
            return 'SCAN_PIERCE'
    return 'N/A'

if __name__ == "__main__":
    main()