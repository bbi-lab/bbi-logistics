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
    project = "Cascadia"
    redcap_project = init_project(project)
    redcap_orders = get_redcap_orders(redcap_project, project)
    if len(redcap_orders) == 0:
        print('no orders')
        return
    redcap_orders = format_longitudinal(project, redcap_orders)
    redcap_orders['Project Name'] = redcap_orders.apply(
        lambda row: assign_project(row, project), axis=1)
    redcap_orders['orderId'] = redcap_orders.dropna(
        subset=['Record Id']).apply(get_de_orders, axis=1)

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
    print(f'looking up order for pt: {redcap_order["Record Id"]}')
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    de_orders = json.loads(response.text)
    if de_orders['totalCount'] == 0:
        print(f'no orders found for {redcap_order["Record Id"]}')
        return pd.NA
    return extract_data(redcap_order, de_orders)


def extract_data(redcap_order: pd.Series, de_orders: dict):
    for order in de_orders['items']:
        print(
            f"DE record id: {order['referenceNumber1']} real record id: {redcap_order['Record Id']}"
        )
        if str(order['referenceNumber1']) != str(redcap_order['Record Id']):
            print('Record Ids do not match')
            continue
        if not 'CASCADIA' in order['referenceNumber3']:
            print('Project Names do not match')
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
    from delivery_express_order import init_project, get_redcap_orders, format_longitudinal, assign_project
    main()
