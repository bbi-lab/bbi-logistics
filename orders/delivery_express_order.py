#!/usr/bin/env python3

from dataclasses import replace
import json
import sys
import logging
import os
from datetime import datetime
from turtle import update
from urllib.parse import urlparse
from redcap import Project
import pandas as pd
import envdir

base_dir = os.path.abspath(__file__ + "/../../")
envdir.open(os.path.join(base_dir, '.env/redcap'))
sys.path.append(base_dir)

# pylint: disable=import-error, wrong-import-position
from etc.redcap_variable_map import project_dict

LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig()
LOG = logging.getLogger(__name__)
LOG.setLevel(LOG_LEVEL)

EXPORT_COLS = [
    'Record Id', 'Today Tomorrow', 'Order Date', 'Project Name', 'First Name',
    'Last Name', 'Street Address', 'Apt Number', 'City', 'State', 'Zipcode',
    'Delivery Instructions', 'Email', 'Phone', 'Notification Pref',
    'Pickup Location'
]
CORE_ADDRESS_COLS = [
    'Street Address', 'Apt Number', 'City', 'State', 'Zipcode'
]
REPLACEMENT_ADDRESS_COLS = [
    'Street Address 2', 'Apt Number 2', 'City 2', 'State 2', 'Zipcode 2'
]
REPLACEMENT_METADATA = [
    'First Name', 'Last Name', 'Email', 'Phone', 'Notification Pref', 'Project Name'
]

# TODO: Lets build out a utils package for some of these supporting functions

def init_project(project):
    '''Fetch content of order reports for a given project'''
    LOG.info(f'Initializing REDCap data for {project}')

    if project in ["HCT", "Cascadia"]:
        url = urlparse(os.environ.get("HCT_REDCAP_API_URL"))
    elif project == "AIRS":
        url = urlparse(os.environ.get("AIRS_REDCAP_API_URL"))
    else:
        url = urlparse(os.environ.get("REDCAP_API_URL"))

    api_key = os.environ.get(
        f"REDCAP_API_TOKEN_{url.netloc}_{project_dict[project]['project_id']}"
    )

    LOG.debug(f'Initializing REDCap project <{project}> at API endpoint <{url.geturl()}>')
    return Project(url.geturl(), api_key)


# TODO: Change how report_id function input is handled
def get_redcap_orders(redcap_project, project, report_id=''):
    '''Get the order report for a given redcap project'''
    report_id = project_dict[project]['Report Id'] if not report_id else report_id
    LOG.debug(f'Fetching report <{report_id}> from project <{project}>')

    order_report = redcap_project.export_reports(
        report_id=report_id,
        format='df'
    ).rename(columns=project_dict[project])

    return order_report


def format_longitudinal(project, orders):
    '''Reduce logitudinal projects to 1 order per row'''

    if project_dict[project]['project_type'] != 'longitudinal':
        LOG.debug(f'No need to format <{project}>, <{project_dict[project]["project_type"]}> is not longitudinal')
        return orders

    LOG.debug(f'Reformatting <{project}>')
    orders['Order Date'] = pd.to_datetime(orders['Order Date'])
    orders['Order Date'].replace('', pd.NA, inplace=True)


    # TODO: Simplify pandas query logic in if/elses below and better document logic flow
    # TODO: break these out into functions
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

        # TODO: Clean this func up
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

        # enrollment records are non symptom survey records
        enrollment_records = orders[
            orders['redcap_repeat_instrument'] != 'symptom_survey'
        ].copy()

        # apply the project name mapping to each enrollment record. by default
        # it only appears on the first record.
        enrollment_records['Project Name'] = enrollment_records.apply(
            lambda x: enrollment_records.filter(
                items=[(x.name[0], '0_arm_1')], axis=0
            )['Project Name'].values[0],axis=1
        )

        # orders we must fulfill are symptom surveys without an existing tracking number
        # and which have a designated pickup time. We can drop records which do not have
        # a order date. We only need to schedule max one pickup per participant so can
        # simply keep the final index entry associated with them. Finally we should also
        # apply the best address for each remaining row of the order sheet.
        orders = orders[
            (orders['redcap_repeat_instrument'] == 'symptom_survey') &
            (orders['ss_return_tracking'].isna()) &
            any(orders[['Pickup 1', 'Pickup 2']].notna())
        ] \
        .dropna(subset=['Order Date']) \
        .query("~index.duplicated(keep='last')") \
        .apply(lambda record: use_best_address(enrollment_records, record), axis=1)

        orders['Today Tomorrow'] = orders.apply(lambda x: 0 if x['Pickup 1'] == 1 else 1, axis=1)
        orders['Notification Pref'] = 'email'

    return orders


def use_best_address(enrollment_records, replacement_record, event=''):
    '''
    if there is not a replacement address use the original address for a
    specific order. Orders are filtered based on record_id and event. A custom
    event may be specified
    '''

    # grab the index we need to update on and filter enrollment records by this index to get the
    # enrollment associated with this row.
    record_index = replacement_record.name if not event else (replacement_record.name[0], event)
    LOG.debug(f'Determining best address for record {record_index}')

    enrollment_record = enrollment_records.filter(items=[record_index], axis=0).squeeze(axis=0)
    updated_record = replacement_record.copy()

    # If all replacement address columns exist and they are not null, use those fields.
    # Otherwise we should use the address in the enrollment record.
    if set(REPLACEMENT_ADDRESS_COLS).issubset(replacement_record.index) and replacement_record[REPLACEMENT_ADDRESS_COLS].notnull().any():
        LOG.debug(f'Replacing enrollment address with replacement address on record <{record_index}>')
        updating = True
        replacement_columns = REPLACEMENT_ADDRESS_COLS
    else:
        LOG.debug(f'Using original enrollment address, no valid replacement addres, on record <{record_index}>')
        updating = False
        replacement_columns = CORE_ADDRESS_COLS

    # Replace address with the best one found
    for core, replacement in zip(CORE_ADDRESS_COLS, replacement_columns):
        updated_record[core] = replacement_record.loc[replacement] if updating else enrollment_record.loc[replacement]

    # Fill any empty metadata fields with existing values in original enrollment record
    for replacement in REPLACEMENT_METADATA:
        updated_metadata = replacement_record.get(replacement, pd.NA)
        updated_record[replacement] = updated_metadata if not pd.isna(updated_metadata) else enrollment_record.get(replacement)

    return updated_record


def map_scan_zipcodes(orders, project):
    '''maps raw to labeled zipcode values for SCAN projects'''
    if 'SCAN' in project:
        zipcode_map_fp = os.path.join(base_dir, 'etc/zipcode_variable_map.json')

        LOG.debug(f'Loading zipcode variable map from location <{zipcode_map_fp}>')

        with open(zipcode_map_fp, 'r', encoding="utf8") as file:
            zipcode_var_map = json.load(file)

        orders['Zipcode'] = orders['Zipcode'].apply(
            lambda x: zipcode_var_map['SCAN'][str(x)] if x != '' else x
        )

    else:
        LOG.debug(f'Skipping zipcode mapping for <{project}> (non-scan project)')

    return orders


def format_id(orders, project):
    # Use the record id for non-Cascadia projects
    if project != 'Cascadia':
        LOG.debug(f'Indexing by <Record ID> on project <{project}>')
        orders.index.names = ['Record Id', 'redcap_event_name']
        orders.reset_index(level=0, inplace=True)

    # We want to use ptid for Cascadia as the Record Id
    else:
        LOG.debug(f'Maintaining <ptid> record mapping on project <{project}>')

    # Ensure all record ids are integers and not floats
    orders['Record Id'] = pd.to_numeric(
        orders['Record Id'], downcast='integer'
    )
    return orders


def assign_project(row, project):
    '''Returns the DE project name for an order'''
    zipcode_map_fp = os.path.join(base_dir, 'etc/zipcode_county_map.json')
    LOG.debug(f'Loading zip code county map from location <{zipcode_map_fp}>')

    with open(zipcode_map_fp, 'r', encoding="utf8") as file:
        zipcode_county_map = json.load(file)

    LOG.debug(f'Attempting to assign <{row["Record Id"]}> to <{project}>')

    if 'SCAN' in project:
        if row['Zipcode'] in zipcode_county_map['SCAN KING']:
            return 'SCAN_KING'
        elif row['Zipcode'] in zipcode_county_map['SCAN PIERCE']:
            return 'SCAN_PIERCE'
        else:
            LOG.warn(f'Could not assign SCAN subproject for record <{row["Record Id"]}> in <{project}>')

    elif project == 'Cascadia':
        if row['Project Name'] == 2:
            return 'CASCADIA_SEA'
        elif row['Project Name'] == 1:
            return 'CASCADIA_PDX'
        else:
            LOG.warn(f'Could not assign Cascadia subproject for record <{row["Record Id"]}> in <{project}>')

    elif project == "HCT":
        return "HCT"

    elif project == "AIRS":
        return "AIRS"

    else:
        LOG.warn(f'Unknown project for record <{row["Record Id"]}> in <{project}>')

    return project


def export_orders(orders, fp):
    """Export orders to a provided filepath and log useful statistics"""
    LOG.debug(f'Exporting Orders to <{fp}>')
    LOG.info(f"Saving the below orders to the inputted data directory \n \
    {orders.groupby(['Project Name']).size().reset_index(name='counts')}")

    orders.to_csv(os.path.join(base_dir, fp), index=False)


def main():
    '''Gets orders from redcap and combine them in a csv file'''
    order_export = pd.DataFrame(columns=EXPORT_COLS, dtype='string')

    for project in project_dict:
        LOG.info(f'Generating Kit Orders for {project}')

        # TODO: Overhaul this error handling method into something more robust
        try:
            redcap_project = init_project(project)
            project_orders = get_redcap_orders(redcap_project, project)
        except Exception as err:
            LOG.error(f'Failed to generate Kit Orders for {project}')
            LOG.error(f'{err}', exc_info=1)
            continue

        orders = len(project_orders.index.get_level_values(0).unique())
        LOG.info(f'Generated <{orders}> Kit Orders for <{project}>')

        if orders:
            project_orders = format_longitudinal(project, project_orders)
            project_orders = map_scan_zipcodes(project_orders, project)
            project_orders = format_id(project_orders, project)

            # Assign each order row to the appropriate project
            project_orders['Project Name'] = project_orders.apply(
                lambda row: assign_project(row, project), axis=1
            )

            # Some rows were typed as a float64 (X.X) which caused issues with the
            # import to delivery express.
            project_orders['Today Tomorrow'] = pd.to_numeric(
                project_orders['Today Tomorrow'], downcast='integer'
            )
            project_orders['Zipcode'] = pd.to_numeric(
                project_orders['Zipcode'], downcast='integer'
            )

            project_orders = project_orders[
                project_orders.columns.intersection(EXPORT_COLS)
            ]
            order_export = pd.concat([order_export, project_orders], ignore_index=True)

    order_export['Apt Number'] = order_export['Apt Number'].apply(
        lambda x: f' {x}' if not pd.isna(x) else pd.NA
    )

    export_orders(order_export, f'data/DeliveryExpressOrder{datetime.now().strftime("%Y_%m_%d_%H_%M")}.csv')


if __name__ == "__main__":
    main()
