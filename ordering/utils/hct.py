"""order utilities for the HCT project"""
import logging
from .common import use_best_address

LOG = logging.getLogger(__name__)


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

    LOG.info(f'<{len(orders)}> orders remain for HCT after filtering.')
    return orders
