"""Shared order utilities for redcap project data manipulation"""
import os, logging, glob
import pandas as pd

# Set up logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig()
LOG = logging.getLogger(__name__)
LOG.setLevel(LOG_LEVEL)

# Logistics S3 paths
LOGISTICS_S3_BUCKET = 'bbi-logistics-orders'
LOGISTICS_DE_PATH = 'delivery_express'
LOGISTICS_USPS_PATH = 'usps'

# Export columns for Delivery Express pickup orders
DE_EXPORT_COLS = [
    'Record Id', 'Today Tomorrow', 'Order Date', 'Project Name', 'First Name',
    'Last Name', 'Street Address', 'Apt Number', 'City', 'State', 'Zipcode',
    'Delivery Instructions', 'Email', 'Phone', 'Notification Pref',
    'Pickup Location'
]
# Export columns for USPS delivery orders
USPS_EXPORT_COLS = [
    "OrderID", "Household ID", "Quantity", "SKU", "Order Date", "Project Name",
    "Pref First Name", "Last Name", "Street Address", "Apt Number", "City", "State",
    "Zipcode", "Delivery Instructions", "Email", "Phone"
]
# Columns used for participant address manipulation
CORE_ADDRESS_COLS = [
    'Street Address', 'Apt Number', 'City', 'State', 'Zipcode'
]
REPLACEMENT_ADDRESS_COLS = [
    'Street Address 2', 'Apt Number 2', 'City 2', 'State 2', 'Zipcode 2'
]
REPLACEMENT_METADATA = [
    'First Name', 'Last Name', 'Email', 'Phone', 'Notification Pref', 'Project Name'
]


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


def export_orders(orders, fp, s3=False):
    """Export orders to a provided filepath `fp`"""
    LOG.debug(f'Exporting Orders to <{fp}>')
    if s3:
        orders.to_csv(fp, index=False, storage_options={'s3_additional_kwargs': {'ServerSideEncryption': 'AES256'}})
    else:
        orders.to_csv(fp, index=False)
