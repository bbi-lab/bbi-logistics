#!/usr/bin/env python3

import re
import json
import sys
from os import environ, path
from datetime import datetime
from urllib.parse import urlparse
from redcap import Project
import pandas as pd
import envdir

base_dir = path.abspath(__file__ + "/../../")
envdir.open(path.join(base_dir, '.env/redcap'))
sys.path.append(base_dir)

# pylint: disable=import-error, wrong-import-position
from etc.redcap_variable_map import project_dict

exportColumns = [
    'Record Id', 'Today Tomorrow', 'Order Date', 'Project Name', 'First Name',
    'Last Name', 'Street Address', 'Apt Number', 'City', 'State', 'Zipcode',
    'Delivery Instructions', 'Email', 'Phone', 'Notification Pref',
    'Pickup Location'
]


def main():
    '''Gets orders from redcap and combine them in a csv file'''
    order_export = pd.DataFrame(columns=exportColumns, dtype='string')

    for project in project_dict:  # (p for p in project_dict if p != 'Cascadia'):
        print(f'Kit orders for {project}: ', end='')
        try:
            redcap_project = init_project(project)
            project_orders = get_redcap_orders(redcap_project, project)
        except Exception as err:
            print('Error!')
            with open(path.join(base_dir, 'data/err.txt'), 'a') as log:
                log.write(repr(err))
            continue
        orders = len(project_orders.index.get_level_values(0).unique())
        print(orders)
        if orders < 1:
            continue
        project_orders = format_orders(project_orders, project)
        order_export = pd.concat([order_export, project_orders],
                                 ignore_index=True)
    export_orders(order_export)
    # TODO: import to DE


def init_project(project):
    '''Fetch content of order reports for a given project'''
    if project == "HCT":
        url = urlparse(environ.get("HCT_REDCAP_API_URL"))
    elif project == "AIRS":
        url = urlparse(environ.get("AIRS_REDCAP_API_URL"))
    else:
        url = urlparse(environ.get("REDCAP_API_URL"))
    api_key = environ.get(
        f"REDCAP_API_TOKEN_{url.netloc}_{project_dict[project]['project_id']}")
    return Project(url.geturl(), api_key)


def get_redcap_orders(redcap_project, project, report_id=''):
    order_report = redcap_project.export_reports(
        report_id=project_dict[project]['Report Id']
        if not report_id else report_id,
        format='df').rename(columns=project_dict[project])
    return order_report


def format_orders(project_orders, project):
    project_orders = format_longitudinal(project, project_orders)
    project_orders = map_scan_zipcodes(project_orders, project)
    project_orders = format_id(project_orders, project)
    project_orders['Project Name'] = project_orders.apply(
        lambda row: assign_project(row, project), axis=1)
    # only use columns specified in the exportColumns
    project_orders = project_orders[project_orders.columns.intersection(
        exportColumns)]
    return project_orders


def format_longitudinal(project, orders):
    '''Reduce logitudinal projects to 1 order per row'''
    if project_dict[project]['project_type'] != 'longitudinal':
        return orders
    orders['Order Date'] = pd.to_datetime(orders['Order Date'])
    orders['Order Date'].replace('', pd.NA, inplace=True)

    if project == 'HCT':
        original_address = orders.filter(like='enrollment_arm_1', axis=0)
        orders = orders.filter(like='encounter_arm_1', axis=0) \
            .dropna(subset=['Order Date']) \
            .query("~index.duplicated(keep='last')") \
            .apply(lambda row: use_best_address(original_address, row, 'enrollment_arm_1'), axis=1)

    if project == 'AIRS':
        order_fields_2 = [
            "Order Date 2", "Today Tomorrow 2", "Street Address 3",
            "Apt Number 3", "City 3", "State 3", "Zipcode 3",
            "Delivery Instructions 2", "Pickup Location 2"
        ]
        order_fields = [
            "Order Date", "Today Tomorrow", "Street Address 2", "Apt Number 2",
            "City 2", "State 2", "Zipcode 2", "Delivery Instructions",
            "Pickup Location"
        ]
        original_address = orders.filter(like='screening_and_enro_arm_1',
                                         axis=0)
        orders = orders.filter(like='week', axis=0) \
            .dropna(subset=['Order Date', 'Order Date 2'], how='all') \
            .reset_index(level='redcap_event_name') \
            .query("~index.duplicated(keep='last')") \
            .set_index('redcap_event_name', append=True)

        def determine_order(row):
            if row.loc[order_fields_2].notnull().sum() > 1:
                order = row.loc[order_fields_2]
                order.index = order_fields
            else:
                order = row.loc[order_fields]
            return order

        orders.loc[:, order_fields] = orders.apply(determine_order, axis=1)
        orders = orders.apply(lambda row: use_best_address(
            original_address, row, 'screening_and_enro_arm_1'),
                              axis=1)

    elif project == 'Cascadia':
        original_address = orders[
            orders['redcap_repeat_instrument'] != 'symptom_survey']
        orders = orders[orders['redcap_repeat_instrument'] == 'symptom_survey'] \
            .dropna(subset=['Order Date']) \
            .query("~index.duplicated(keep='last')") \
            .apply(lambda row: use_best_address(original_address, row, '0_arm_1'), axis=1)
        orders['Today Tomorrow'] = orders.apply(lambda x: 0
                                                if x['Pickup 1'] == 1 else 1,
                                                axis=1)
    return orders


def use_best_address(original_address, row, event=''):
    '''if there is not a replacement address use the original address for a
    specific order Orders are filtered based on record_id and event. A custom
    event may be specified'''
    replace_address_columns = [
        'Street Address 2', 'Apt Number 2', 'City 2', 'State 2', 'Zipcode 2'
    ]
    core_address_columns = [
        'Street Address', 'Apt Number', 'City', 'State', 'Zipcode'
    ]
    other_replace = [
        'First Name', 'Last Name', 'Delivery Instructions', 'Email', 'Phone',
        'Notification Pref', 'Record Id'
    ]
    record_index = row.name if not event else (row.name[0], event)
    original = original_address.filter(items=[record_index], axis=0)

    if set(replace_address_columns).issubset(
            row.index) and row[replace_address_columns].notnull().any():
        update = row.loc[replace_address_columns]
        for val in core_address_columns:
            # the replacement fields has a trailing 2
            row[val] = update.loc[str(val + ' 2')]
    else:
        for val in core_address_columns:
            row[val] = original.iloc[0][val]
    for val in other_replace:
        try:
            row[val] = original.iloc[0][val]
        except KeyError:
            pass
    return row


def map_scan_zipcodes(orders, project):
    '''maps raw to labeled zipcode values'''
    if not re.search('SCAN', project):
        return orders
    with open(path.join(base_dir, 'etc/zipcode_variable_map.json'),
              'r',
              encoding="utf8") as file:
        zipcode_var_map = json.load(file)
    orders['Zipcode'] = orders['Zipcode'].apply(
        lambda x: zipcode_var_map['SCAN'][str(x)] if x != '' else x)
    return orders


def format_id(orders, project):
    # We want to use ptid for Cascadia as the Record Id
    if project == 'Cascadia':
        return orders
    orders.index.names = ['Record Id', 'redcap_event_name']
    orders.reset_index(level=0, inplace=True)
    return orders


def assign_project(row, project):
    '''Returns the DE project name for an order'''
    with open(path.join(base_dir, 'etc/zipcode_county_map.json'),
              'r',
              encoding="utf8") as file:
        zipcode_county_map = json.load(file)
    if re.search('SCAN', project):
        if row['Zipcode'] in zipcode_county_map['SCAN KING']:
            return 'SCAN_KING'
        if row['Zipcode'] in zipcode_county_map['SCAN PIERCE']:
            return 'SCAN_PIERCE'
    if project == 'Cascadia':
        if row['State'] == 'WA':
            return 'CASCADIA_SEA'
        if row['State'] == 'OR':
            return 'CASCADIA_PDX'
    if project == "HCT":
        return "HCT"
    if project == "AIRS":
        return "AIRS"
    print(f'Unknown project for record {row["Record Id"]} in {project}')
    return project


def export_orders(orders):
    print(orders.groupby(['Project Name']).size() \
                .reset_index(name='counts'))
    orders.to_csv(path.join(
        base_dir,
        f'data/DeliveryExpressOrder{datetime.now().strftime("%Y_%m_%d_%H_%M")}.csv'
    ),
                  index=False)


if __name__ == "__main__":
    main()
