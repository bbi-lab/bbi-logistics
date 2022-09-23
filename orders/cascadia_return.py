#!/usr/bin/env python3
import envdir, os, logging
from utils.redcap import init_project, get_redcap_report, format_longitudinal
from utils.delivery_express import get_de_orders, format_orders_import
from utils.cascadia import filter_cascadia_orders

base_dir = os.path.abspath(__file__ + "/../../")
envdir.open(os.path.join(base_dir, '.env/de'))
envdir.open(os.path.join(base_dir, '.env/redcap'))

# set up logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig()
LOG = logging.getLogger(__name__)
LOG.setLevel(LOG_LEVEL)

PROJECT = "Cascadia"

def main():
    redcap_project = init_project(PROJECT)
    redcap_orders = get_redcap_report(redcap_project, PROJECT)
    redcap_enrollments = get_redcap_report(redcap_project, PROJECT, 2401)

    if len(redcap_orders) == 0:
        LOG.info(f'No orders to process, exiting...')
        return

    redcap_orders = format_longitudinal(redcap_orders, PROJECT)
    redcap_orders = filter_cascadia_orders(redcap_orders, redcap_enrollments)

    redcap_orders = redcap_orders.astype({'Record Id': int})
    redcap_orders['orderId'] = redcap_orders.dropna(
        subset=['Record Id']).apply(get_de_orders, axis=1
    )
    formatted_import = format_orders_import(redcap_orders)

    if len(formatted_import):
        LOG.info(f'Importing {len(formatted_import)} new return orders to REDCap.')
        redcap_project.import_records(formatted_import, overwrite='overwrite')
    else:
        LOG.info('No new return orders remain after filtering. No imports necessary to REDCap.')


if __name__ == "__main__":
    # TODO: add command line option to skip redcap import during testing
    main()
