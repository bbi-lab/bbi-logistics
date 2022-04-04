#!/usr/bin/env python3

from datetime import datetime
import sys
from os import path
import pandas as pd
from delivery_express_order import init_project, get_redcap_orders
import envdir

base_dir = path.abspath(__file__ + "/../../")
envdir.open(path.join(base_dir, '.env/redcap'))
sys.path.append(base_dir)

export_columns = [
    "OrderID", "Household ID", "Quantity", "SKU", "Order Date", "Project Name",
    "First Name", "Last Name", "Street Address", "Apt Number", "City", "State",
    "Zipcode", "Delivery Instructions", "Email", "Phone"
]


def main():
    project = init_project('Cascadia')
    order_report = get_redcap_orders(project, 'Cascadia', '144246')

    barcode_columns = [f'assign_barcode_{i}' for i in range(1, 10)]

    orders = pd.DataFrame(columns=export_columns)
    household_ids = set(i[0] for i in order_report.index)

    for house_id in household_ids:
        ship = False
        kits_needed = {
            'resupply': {},  # {"0": 2, "1": 1, "3": 4}
            'welcome': {}  # {"2": 1}
        }

        participants = set(i[1] for i in order_report.index
                           if i[0] == house_id and i[1] != 'household_arm_1')

        for participant in participants:
            pt_data = order_report.loc[[(house_id, participant)]]

            if not any(pt_data['swab_barcodes_complete'] == 2):
                kits_needed['welcome'][participant] = 1
                continue

            kit_barcodes = pt_data.loc[pt_data['redcap_repeat_instrument'] ==
                                       'swab_barcodes', barcode_columns] \
                                    .notna().sum(axis=1).sum()

            kit_returns = pt_data.loc[pt_data['redcap_repeat_instrument'] ==
                                      'symptom_survey', 'ss_return_tracking'] \
                                    .count()

            num_kits = kit_barcodes - kit_returns
            if num_kits <= 2:
                ship = True
            # number of kits needed to get inventory to 6
            kits_needed['resupply'][participant] = max(6 - num_kits, 0)

        if kits_needed['welcome'] or ship:
            address = get_house_address(order_report, house_id)

        if kits_needed['welcome']:
            welcome_kits_needed = sum(kits_needed['welcome'].values())
            orders = append_order(orders, 3, welcome_kits_needed, address)

        if ship:
            # resupply entire house
            resupply_kits_needed = sum(kits_needed['resupply'].values())
            orders = append_order(orders, 2, resupply_kits_needed, address)

    export_orders(orders)


def append_order(orders, sku, quantity, address):
    if quantity > 20:  # seperate into other order becaues of max shippment size
        orders = append_order(orders, sku, quantity - 20, address)
        quantity = 20
    address['SKU'] = sku
    address['Quantity'] = quantity
    address['OrderID'] = generate_order_number(address, orders)
    address['Household ID'] = address.index[0][0]
    address['Project Name'] = 'Cascadia_SEA' if address[
        'State'].values == 'WA' else 'Cascadia_PDX'
    return pd.concat([orders, address], join='inner', ignore_index=True)


def get_house_address(order_report, house_id):
    address = order_report.loc[[(house_id, '0_arm_1')]] \
        .query('redcap_repeat_instrument.isna()')
    return address[address.columns.intersection(export_columns)]


def generate_order_number(address, orders):
    order_id = f'{datetime.now().strftime("%Y%m%d")}{address.index[0][0]}'
    while order_id in orders['OrderID'].values:
        if (not order_id[len(order_id) - 1].isalpha()):
            order_id = order_id + 'a'
        else:
            order_id[len(order_id) -
                     1] = chr(ord(order_id[len(order_id) - 1]) + 1)
    return order_id


def export_orders(orders):
    # print(orders.groupby(['Project Name']).size() \
    #             .reset_index(name='counts'))
    orders.to_csv(path.join(
        base_dir,
        f'data/USPSOrder{datetime.now().strftime("%Y_%m_%d_%H_%M")}.csv'),
                  index=False)


if __name__ == '__main__':
    main()
