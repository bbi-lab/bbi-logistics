#!/usr/bin/env python3
import envdir, os, logging, sys, argparse

BASE_DIR = os.path.abspath(__file__ + "/../../../")
sys.path.append(BASE_DIR)

from ordering.utils.redcap import init_project, get_redcap_report, format_longitudinal, import_records_batched
from ordering.utils.delivery_express import get_de_orders, format_orders_import
from ordering.utils.cascadia import filter_cascadia_orders

envdir.open(os.path.join(BASE_DIR, '.env/de'))
envdir.open(os.path.join(BASE_DIR, '.env/redcap'))

LOG = logging.getLogger('ordering.scripts.cascadia_return')
PROJECT = "Cascadia"

def main(args):
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
        if args.import_to_redcap:
            LOG.info(f'Importing {len(formatted_import)} new return orders to REDCap.')
            import_records_batched(redcap_project, formatted_import)
        else:
            LOG.info(f'Skipping import to REDCap due to <--import={args.import_to_redcap}>.')
    else:
        LOG.info('No new return orders remain after filtering. No imports necessary to REDCap.')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Update REDCap records with existing orders from the Delivery Express API.')
    parser.add_argument('--import-to-redcap', action='store_true', help='Flag to indicate whether order numbers should be imported into REDCap.')

    main(parser.parse_args())
