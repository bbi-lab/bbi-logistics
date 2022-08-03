#!/usr/bin/env python3

import json
import base64
from os import path, environ
from datetime import datetime as dt
import pandas as pd
import envdir
import requests
import logging

base_dir = path.abspath(__file__ + "/../../")
envdir.open(path.join(base_dir, '.env/de'))
envdir.open(path.join(base_dir, '.env/redcap'))

LOG_LEVEL = environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig()
LOG = logging.getLogger(__name__)
LOG.setLevel(LOG_LEVEL)

PROJECT = "Cascadia"

def main():
    redcap_project = init_project(PROJECT)
    redcap_orders = get_redcap_orders(redcap_project, PROJECT)

    if len(redcap_orders) == 0:
        LOG.info(f'No orders to process, exiting...')
        return

    redcap_orders = format_longitudinal(PROJECT, redcap_orders)
    redcap_orders['Project Name'] = redcap_orders.apply(
        lambda row: assign_project(row, PROJECT), axis=1
    )
    redcap_orders = redcap_orders.astype({'Record Id': int})
    redcap_orders['orderId'] = redcap_orders.dropna(
        subset=['Record Id']).apply(get_de_orders, axis=1
    )
    formatted_import = format_orders_import(redcap_orders)
    redcap_project.import_records(formatted_import, overwrite='overwrite')


def get_de_orders(redcap_order: pd.Series):
    url = "https://deliveryexpresslogistics.dsapp.io/integration/api/v1/orders/search"

    username_pass = bytearray(environ['AUTHORIZATION'], 'utf-8')
    base64_encoded = base64.b64encode(username_pass).decode('ascii')
    auth = f'Basic {base64_encoded}'

    payload = {
        "query": redcap_order.loc['Record Id'],
        "searchFields": ["referenceNumber1"]
    }
    headers = {'Authorization': auth, "Content-Type": "application/*+json"}

    LOG.debug(f'Making request to <{url}> with data <{payload}>')
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    de_orders = json.loads(response.text)

    LOG.info(f'Looking up order for pt: <{redcap_order["Record Id"]}>.')

    if de_orders['totalCount'] == 0:
        LOG.info(f'No orders found for <{redcap_order["Record Id"]}>.')
        return None

    return extract_data(redcap_order, de_orders)


def extract_data(redcap_order: pd.Series, de_orders: dict):
    for order in de_orders['items']:
        LOG.debug(f"DE record id is: {order['referenceNumber1']}; REDCap record id is: {redcap_order['Record Id']}")

        if str(order['referenceNumber1']) != str(redcap_order['Record Id']):
            LOG.warning(f'Record Ids do not match, skipping order out of an abundance of caution.')
            continue

        if not 'CASCADIA' in order['referenceNumber3']:
            LOG.warning('Project Names do not match, skipping order out of an abundance of caution')
            continue

        formatted_date = order['createdAt'][:19] + order['createdAt'][-6:].replace(':', '')
        created_date = dt.strptime(formatted_date, '%Y-%m-%dT%H:%M:%S%z').replace(tzinfo=None)
        order_date = redcap_order['Order Date']

        LOG.debug(f'DE Order Creation Date: <{created_date.date()}>. REDCap Order Date <{order_date.date()}>.')
        if (created_date > order_date):
            # referenceNumber1 record id
            # referenceNumber3 project
            LOG.info(f'Updating REDCap record with <{order["orderId"]}>.')
            return order['orderId']
        else:
            LOG.debug(f'DE Order creation date was before REDCap order creation date ({created_date.date()} < {order_date.date()}). Skipping order.')

    LOG.info(f'Skipped REDCap update for Record ID <{redcap_order["Record Id"]}>, nothing to update.')
    return None


def format_orders_import(orders):
    LOG.debug(f'Formatting <{len(orders)}> for import to REDCap.')
    return orders[
        ['orderId', 'redcap_repeat_instance', 'redcap_repeat_instrument']
    ].dropna(
        subset=['orderId']
    ).rename(
        columns={'orderId': 'ss_return_tracking'}
    ).reset_index().to_dict('records')


if __name__ == "__main__":
    from delivery_express_order import init_project, get_redcap_orders, format_longitudinal, assign_project
    main()
