"""order utilities for the AIRS project"""
import os, logging
from .common import use_best_address

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

# Set up logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig(
    format = "[%(asctime)s] %(name)-20s %(levelname)-8s %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S%z",
    level = LOG_LEVEL
)
LOG = logging.getLogger(__name__)


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

    LOG.info(f'<{len(orders)}> orders remain for AIRS after filtering.')
    return orders
