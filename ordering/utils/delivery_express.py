"""order utilities for interacting with delivery express data"""
import os, logging, json, base64, requests, time
import pandas as pd
from datetime import datetime as dt

LOG = logging.getLogger(__name__)


def get_de_orders(redcap_order: pd.Series, max_retries = 5):
    """get existing DE orders for Cascadia from DE API Endpoint"""
    url = "https://deliveryexpresslogistics.dsapp.io/integration/api/v1/orders/search"

    username_pass = bytearray(os.environ['AUTHORIZATION'], 'utf-8')
    base64_encoded = base64.b64encode(username_pass).decode('ascii')
    auth = f'Basic {base64_encoded}'

    payload = {
        "query": redcap_order.loc['Record Id'],
        "searchFields": ["referenceNumber1"]
    }
    headers = {'Authorization': auth, "Content-Type": "application/*+json"}

    # with the cascadia project growing, we sometimes run into issues making requests
    # to the DE servers. we should retry failed requests up to a point, backing off
    # with each additional failure.
    attempts = 0
    delay = 0.5
    factor = 2
    while attempts < max_retries:
        LOG.debug(f'Making request number <{attempts + 1}> to <{url}> with data <{payload}>')

        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            response.raise_for_status()
            break

        except (requests.exceptions.ConnectionError, requests.exceptions.HTTPError, requests.exceptions.Timeout) as exc:
            attempts += 1
            if attempts == max_retries:
                LOG.error(f'Aborting request to Delivery Express servers for participant <{redcap_order["Record Id"]}> after <{attempts}>.', exc_info=exc)
                raise
            else:
                LOG.warning(f'Attempt <{attempts}> to reach the Delivery Express servers failed with: {exc} Retrying in <{delay}> seconds.')
                time.sleep(delay)
                delay = delay * factor

    de_orders = json.loads(response.text)
    LOG.info(f'Looking up order for pt: <{redcap_order["Record Id"]}>.')

    if de_orders['totalCount'] == 0:
        LOG.info(f'No orders found for <{redcap_order["Record Id"]}>.')
        return None

    return extract_de_orders(redcap_order, de_orders)


def extract_de_orders(redcap_order: pd.Series, de_orders: dict):
    """Extract DE orders and join to REDCap data"""
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
            LOG.info(f'Preparing to update REDCap record with <{order["orderId"]}>.')
            return order['orderId']
        else:
            LOG.debug(f'DE Order creation date was before REDCap order creation date ({created_date.date()} < {order_date.date()}). Skipping order.')

    LOG.info(f'Skipped REDCap update for Record ID <{redcap_order["Record Id"]}>, nothing to update.')
    return None


def format_orders_import(orders):
    """Format the DE orders so they may be imported into REDCap"""
    LOG.debug(f'Formatting and verifying <{len(orders)}> records for import to REDCap.')
    return orders[
        ['orderId', 'redcap_repeat_instance', 'redcap_repeat_instrument']
    ].dropna(
        subset=['orderId']
    ).rename(
        columns={'orderId': 'ss_return_tracking'}
    ).reset_index().to_dict('records')
