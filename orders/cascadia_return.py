#!/usr/bin/env python3

import json
import base64
from os import path, environ
from datetime import datetime as dt
import pandas as pd
import envdir
import requests

base_dir = path.abspath(__file__ + "/../../")
envdir.open(path.join(base_dir, '.env/de'))
envdir.open(path.join(base_dir, '.env/redcap'))


def main():
    redcap_project = init_project('Cascadia')
    redcap_orders = get_redcap_orders(redcap_project, 'Cascadia')
    redcap_orders = format_longitudinal('Cascadia', redcap_orders)
    redcap_orders['orderId'] = redcap_orders.dropna(
        subset=['Record Id']).apply(get_de_orders, axis=1)

    formatted_import = format_orders_import(redcap_orders)
    print(formatted_import)
    # cascadia_redcap.import_records([data], overwrite='overwrite')


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
    print(f'looking up order for pt: {redcap_order["Record Id"]}')
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    de_orders = json.loads(response.text)
    if de_orders['totalCount'] == 0:
        print(f'no orders found for {redcap_order["Record Id"]}')
        return pd.NA
    return extract_data(redcap_order, de_orders)


def extract_data(redcap_order: pd.Series, de_orders: dict):
    for order in de_orders['items']:
        if (order['referenceNumber1'] != redcap_order['Record Id']):
            continue
        formatted_date = order['createdAt'][:25] + order['createdAt'][
            26:30] + order['createdAt'][31:]
        created_date = dt.strptime(
            formatted_date, '%Y-%m-%dT%H:%M:%S.%f%z').replace(tzinfo=None)
        order_date = redcap_order['Order Date']
        print(f'{created_date.date()}  |  {order_date.date()}')
        if (created_date > order_date):
            # referenceNumber1 record id
            # referenceNumber3 project
            print(f'update record with {order["orderId"]}')
            return order['orderId']
    print('did not update redcap')
    return pd.NA


def format_orders_import(orders):
    return orders[[
        'orderId', 'redcap_repeat_instance', 'redcap_repeat_instrument'
    ]].dropna(subset=['orderId']).rename(columns={
        'orderId': 'ss_return_tracking'
    }).reset_index().to_dict('records')


if __name__ == "__main__":
    from delivery_express_order import init_project, get_redcap_orders, format_longitudinal
    main()
