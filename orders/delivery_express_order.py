#!/usr/bin/env python3

import sys, logging, os
from datetime import datetime
from urllib.parse import urlparse
from redcap import Project
import pandas as pd
import envdir

# Place all modules within this script's path
base_dir = os.path.abspath(__file__ + "/../../")
sys.path.append(base_dir)

from etc.ordering_script_config_map import PROJECT_DICT

# Set up envdir
envdir.open(os.path.join(base_dir, '.env/redcap'))

# Set up logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig()
LOG = logging.getLogger(__name__)
LOG.setLevel(LOG_LEVEL)

# Set up static data
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
AIRS_ORDER_FIELDS = [
    "Order Date", "Today Tomorrow", "Street Address 2", "Apt Number 2",
    "City 2", "State 2", "Zipcode 2", "Delivery Instructions",
    "Pickup Location"
]
AIRS_ORDER_FIELDS_2 = [
    "Order Date 2", "Today Tomorrow 2", "Street Address 3",
    "Apt Number 3", "City 3", "State 3", "Zipcode 3",
    "Delivery Instructions 2", "Pickup Location 2"
]


# TODO: Lets build out a utils package for some of these supporting functions
def init_project(project_name):
    '''Fetch content of order reports for a given `project`'''
    LOG.info(f'Initializing REDCap data for {project_name}')

    if project_name in ["HCT", "Cascadia"]:
        url = urlparse(os.environ.get("HCT_REDCAP_API_URL"))
    elif project_name == "AIRS":
        url = urlparse(os.environ.get("AIRS_REDCAP_API_URL"))
    else:
        url = urlparse(os.environ.get("REDCAP_API_URL"))

    api_key = os.environ.get(
        f"REDCAP_API_TOKEN_{url.netloc}_{PROJECT_DICT[project_name]['project_id']}"
    )

    LOG.debug(f'Initializing REDCap project <{project_name}> from API endpoint: <{url.geturl()}>')
    return Project(url.geturl(), api_key)


def get_redcap_report(redcap_project, project_name, report_id = None):
    '''Get the order report for a given redcap project'''
    if not report_id:
        LOG.debug(f'Fetching `report_id` from config for project <{project_name}>')
        report_id = PROJECT_DICT[project_name]['Report Id']
    else:
        LOG.debug(f'Using passed `report_id` <{report_id}>')

    LOG.info(f'Fetching report <{report_id}> for project <{project_name}>')

    report = redcap_project.export_reports(
        report_id=report_id,
        format='df'
    ).rename(columns=PROJECT_DICT[project_name])

    LOG.debug(f'Original report <{report_id}> for project <{project_name}> has <{len(report)}> rows.')
    return report


def filter_hct_orders(orders):
    '''Filter HCT `orders` to those that we need to create orders for'''
    LOG.debug(f'Filtering <{len(orders)}> HCT Orders. Setting order `Project Name` to HCT.')
    orders['Project Name'] = 'HCT'

    # Get original address row from HCT enrollment arm
    original_address = orders.filter(like='enrollment_arm_1', axis=0)

    # Get encounter arm records, drop records without an order date,
    # grab the most recent order on a per-participant basis, then set
    # their address to the most recently provided one.
    orders = orders.filter(
        like='encounter_arm_1', axis=0
    ).dropna(subset=['Order Date']
    ).query("~index.duplicated(keep='last')"
    ).apply(
        lambda row: use_best_address(original_address, row, 'enrollment_arm_1'), axis=1
    )

    return orders


def determine_airs_order(row):
    '''Determine which of the two AIRS orders to use'''
    # Can use order fields 2 if more than one of those fields is available
    if row.loc[AIRS_ORDER_FIELDS_2].notnull().sum() > 1:
        LOG.debug(f'Using alternate order fields for <{row.name}>.')

        order = row.loc[AIRS_ORDER_FIELDS_2]
        order.index = AIRS_ORDER_FIELDS

    # Otherwise we can use the original order fields
    else:
        LOG.debug(f'Using original order fields for <{row.name}>.')
        order = row.loc[AIRS_ORDER_FIELDS]

    return order


def filter_airs_orders(orders):
    '''Filters AIRS `orders` to those that we need to create orders for'''
    LOG.debug(f'Filtering <{len(orders)}> AIRS Orders. Setting order `Project Name` to AIRS.')
    orders['Project Name'] = 'AIRS'

    # Get original address row from AIRS enrollment arm
    original_address = orders.filter(like='screening_and_enro_arm_1', axis=0)

    # Get weekly records, drop records without an order date,
    # reset the index on redcap events, only keep the most
    # recent event in each index and then set the index again.
    orders = orders.filter(
        like='week', axis=0
    ).dropna(subset=['Order Date', 'Order Date 2'], how='all'
    ).reset_index(level='redcap_event_name'
    ).query("~index.duplicated(keep='last')"
    ).set_index('redcap_event_name', append=True)

    # Determine what AIRS order to use (up to 2 weekly orders are allowed for AIRS)
    orders.loc[:, AIRS_ORDER_FIELDS] = orders.apply(determine_airs_order, axis=1)

    # Get the most recent address supplied by the participant
    orders = orders.apply(
        lambda row: use_best_address(original_address, row, 'screening_and_enro_arm_1'), axis=1
    )

    return orders


def assign_cascadia_location(orders):
    '''Assign orders to the desired Cascadia sublocation'''
    LOG.debug(f'Assigning Cascadia sublocations to each order record.')
    orders['Project Name'] = orders[['Project Name']].apply(
        lambda x: 'CASCADIA_SEA' if x['Project Name'] == 2 else 'CASCADIA_PDX', axis=1
    )

    # ensure that we convert column type from int to str
    orders['Project Name'] = orders['Project Name'].astype(str)

    return orders


def filter_cascadia_orders(orders):
    '''Filters Cascadia `orders` to those that we need to create orders for'''
    LOG.debug(f'Filtering <{len(orders)}> Cascadia orders.')

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
    # which have a designated pickup time and have a swab trigger. We can drop records
    # which do not have a order date. We only need to schedule max one pickup per
    # participant so can simply keep the final index entry associated with them. Finally
    # we should also apply the best address for each remaining row of the order sheet.
    orders = orders[
        (orders['redcap_repeat_instrument'] == 'symptom_survey') &
        (orders['ss_return_tracking'].isna()) &
        any(orders[['Pickup 1', 'Pickup 2']].notna()) &
        (orders['ss_trigger_swab'])
    ].dropna(subset=['Order Date']
    ).query("~index.duplicated(keep='last')"
    ).apply(lambda record: use_best_address(enrollment_records, record), axis=1)

    # Set today tomorrow variable based on pickup time preference
    orders['Today Tomorrow'] = orders[['Pickup 1']].apply(lambda x: 0 if x['Pickup 1'] == 1 else 1, axis=1)
    orders['Notification Pref'] = 'email'

    orders = assign_cascadia_location(orders)

    return orders


def format_longitudinal(orders, project):
    '''
    Reduce logitudinal projects to 1 order per row. Filter rows to those
    we need to create orders for based on logic unique to each project.
    '''

    if PROJECT_DICT[project]['project_type'] != 'longitudinal':
        LOG.info(f'No need to format <{project}>. <{PROJECT_DICT[project]["project_type"]}> is not longitudinal')
        return orders

    LOG.info(f'Reformatting <{project}> as a longitudinal project.')

    # Cast order date as a datetime and replace any NA values
    orders['Order Date'] = pd.to_datetime(orders['Order Date'])
    orders['Order Date'].replace('', pd.NA, inplace=True)

    if project == 'HCT':
        orders = filter_hct_orders(orders)

    elif project == 'AIRS':
        orders = filter_airs_orders(orders)

    elif project == 'Cascadia':
        orders = filter_cascadia_orders(orders)

    LOG.info(f'<{len(orders)}> orders remain for <{project}> after filtering.')
    return orders


def use_best_address(enrollment_records, replacement_record, event=''):
    '''
    if there is not a replacement address use the original address for a
    specific order. Orders are filtered based on record_id and event. A custom
    event may be specified
    '''

    # grab the index we need to update on and filter enrollment records by this index to get the
    # enrollment associated with this row/participant.
    record_index = replacement_record.name if not event else (replacement_record.name[0], event)
    LOG.info(f'Determining best address for record {record_index}')

    enrollment_record = enrollment_records.filter(items=[record_index], axis=0).squeeze(axis=0)
    updated_record = replacement_record.copy()

    # If all replacement address columns exist and they are not null, use those fields.
    # Otherwise we should use the address in the enrollment record.
    if set(REPLACEMENT_ADDRESS_COLS).issubset(replacement_record.index) and replacement_record[REPLACEMENT_ADDRESS_COLS].notnull().any():
        LOG.debug(f'Replacing enrollment address with replacement address on record <{record_index}>')
        updating = True
        replacement_columns = REPLACEMENT_ADDRESS_COLS
    else:
        LOG.debug(f'Using original enrollment address, no valid replacement address, on record <{record_index}>')
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


def format_id(orders, project, new_index = None):
    '''
    Format the correct Record Id for project orders. Use `new_index` if passed.
    Default to using `Record Id` and `redcap_event_name`
    '''
    LOG.info(f'Attempting to format order IDs for the current project.')

    # We want to use ptid for Cascadia as the Record Id
    if project == 'Cascadia':
        LOG.debug(f'Maintaining <ptid> record formatting for <{project}> orders.')

    # Use the record id for non-Cascadia projects
    else:
        new_index = ['Record Id', 'redcap_event_name'] if not new_index else new_index
        LOG.debug(f'Formatting by <{new_index}> for <{project}> orders.')
        orders.index.names = new_index
        orders.reset_index(level=0, inplace=True)

    # Ensure all record ids are integers and not floats
    orders['Record Id'] = pd.to_numeric(
        orders['Record Id'], downcast='integer'
    )

    return orders


def export_orders(orders, fp):
    """Export orders to a provided filepath `fp`."""
    LOG.debug(f'Exporting Orders to <{fp}>')

    orders.to_csv(os.path.join(base_dir, fp), index=False)


def main():
    '''Gets orders from redcap and combine them in a csv file'''
    order_export = pd.DataFrame(columns=EXPORT_COLS, dtype='string')

    for project in PROJECT_DICT:
        LOG.info(f'Generating Kit Orders for <{project}>')

        # TODO: Overhaul this error handling method into something more robust
        try:
            redcap_project = init_project(project)
            project_orders = get_redcap_report(redcap_project, project)
        except Exception as err:
            LOG.error(f'Failed to generate Kit Orders for <{project}>')
            LOG.error(f'{err}', exc_info=1)
            continue

        orders = len(project_orders.index.get_level_values(0).unique())
        LOG.info(f'Started with <{orders}> possible new kit orders in <{project}>.')

        if orders:
            project_orders = format_longitudinal(project_orders, project)
            project_orders = format_id(project_orders, project)

            # Some columns can be typed as a float64 (X.X) which causes issues with the
            # import to delivery express. Downcast those columns.
            project_orders['Today Tomorrow'] = pd.to_numeric(
                project_orders['Today Tomorrow'], downcast='integer'
            )
            project_orders['Zipcode'] = pd.to_numeric(
                project_orders['Zipcode'], downcast='integer'
            )

            # Subset orders by export desired columns
            project_orders = project_orders[
                project_orders.columns.intersection(EXPORT_COLS)
            ]

            LOG.debug(f'Appending <{len(project_orders)}> from <{project}> to the order sheet.')
            order_export = pd.concat([order_export, project_orders], ignore_index=True)

            LOG.info(f'<{len(order_export)}> total orders after concatenation of <{project}> orders.')
        else:
            LOG.info(f'Skipping orders for <{project}>, nothing in the report. <{len(order_export)}> total orders.')

    # format the apt number nicely if it exists
    order_export['Apt Number'] = order_export['Apt Number'].apply(
        lambda x: f' {x}' if not pd.isna(x) else pd.NA
    )

    export_orders(order_export, f'data/DeliveryExpressOrder{datetime.now().strftime("%Y_%m_%d_%H_%M")}.csv')

    LOG.info(f"Orders saved. Summary of orders generated by this run: \n \
        {order_export.groupby(['Project Name']).size().reset_index(name='counts')}")


if __name__ == "__main__":
    main()
