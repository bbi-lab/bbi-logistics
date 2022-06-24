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
    order_report = get_redcap_orders(project, 'Cascadia', '1144')
    serial_report = get_redcap_orders(project, 'Cascadia', '1711')
    serial_pts = serial_report['results_ptid'] if len(serial_report) else []

    barcode_columns = [f'assign_barcode_{i}' for i in range(1, 10)]

    orders = pd.DataFrame(columns=export_columns)
    household_ids = set(i[0] for i in order_report.index)

    for house_id in household_ids:
        ship = False
        kits_needed = {
            'resupply': {},  # {"0": 2, "1": 1, "3": 4}
            'welcome': {},  # {"2": 1}
            'serial': {}  # {"6": 1}
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

            if pt_data['es_ptid'] in serial_pts:
                kits_needed['serial'][participant] = 1

        if kits_needed['welcome'] or ship or kits_needed['serial']:
            address = get_house_address(order_report, house_id)

        # do not send welcome kits unless everyone has completed the enrollment survey
        if kits_needed['welcome'] and not any(
                order_report.loc[[house_id],
                                 'enrollment_survey_complete'] == 0):
            welcome_kits_needed = sum(kits_needed['welcome'].values())
            orders = append_order(orders, 3, welcome_kits_needed, address)

        if ship:
            # resupply entire house
            resupply_kits_needed = sum(kits_needed['resupply'].values())
            orders = append_order(orders, 1, resupply_kits_needed, address)

        if kits_needed['serial']:
            for pt, _ in kits_needed['serial'].items():
                orders = append_order(orders, 2, 1, address)

    export_orders(orders)


def append_order(orders, sku, quantity, address):
    if quantity > 20 and sku == 1:  # seperate replenishment kits into other order becaues of max shippment size
        orders = append_order(orders, sku, quantity - 20, address)
        quantity = 20
    if quantity > 4 and sku == 3:  # seperate welcome kits into other order becaues of max shippment size
        orders = append_order(orders, sku, quantity - 4, address)
        quantity = 4
    address['SKU'] = sku
    address['Quantity'] = quantity
    address['OrderID'] = generate_order_number(address, orders)
    address['Household ID'] = address.index[0][0]
    return pd.concat([orders, address], join='inner', ignore_index=True)


def get_house_address(order_report, house_id):
    address = order_report.loc[[(house_id, '0_arm_1')]] \
        .query('redcap_repeat_instrument.isna()')
    address['Project Name'] = 'Cascadia_SEA' if address[
        'Project Name'].values == 2 else 'Cascadia_PDX'
    address['Zipcode'] = address['Zipcode'].astype(int) if not pd.isna(
        address['Zipcode'].values) else ''
    return address[address.columns.intersection(export_columns)]


def generate_order_number(address, orders):
    order_id = f'{datetime.now().strftime("%y%m%d")}{address.index[0][0]}'
    while order_id in orders['OrderID'].values:
        if (not order_id[len(order_id) - 1].isalpha()):
            order_id = order_id + 'a'
        else:
            l = list(order_id)
            l[len(l) - 1] = chr(ord(l[len(l) - 1]) + 1)
            order_id = ''.join(l)
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
