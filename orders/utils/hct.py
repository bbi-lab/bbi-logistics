"""order utilities for the HCT project"""
import os, logging
from .common import use_best_address

# Set up logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig()
LOG = logging.getLogger(__name__)
LOG.setLevel(LOG_LEVEL)


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
