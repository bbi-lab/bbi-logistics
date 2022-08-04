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
    "Pref First Name", "Last Name", "Street Address", "Apt Number", "City", "State",
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

            # the patient should be enrolled and consented to get any kits
            if not (any(pt_data['enrollment_survey_complete'] == 2) and any(pt_data['consent_form_complete'] == 2)):
                continue

            # if no swab barcodes have been completed they need a welcome kit
            if not any(pt_data['swab_barcodes_complete'] == 2):
                kits_needed['welcome'][participant] = 1
                continue # if they dont have welcome kit yet, they definitely don't need anything else

            # current barcodes a pt has
            kit_barcodes = pt_data.loc[
                pt_data['redcap_repeat_instrument'] == 'swab_barcodes', barcode_columns
            ].notna().sum(axis=1).sum()

            # current barcodes a pt has returned
            kit_returns = pt_data.loc[
                pt_data['redcap_repeat_instrument'] == 'symptom_survey', 'ss_return_tracking'
            ].count()

            # if a pt has less than 3 total kits they will need more shipped
            num_kits = kit_barcodes - kit_returns
            if num_kits < 3:
                ship = True

            # number of kits needed to get inventory to 6
            kits_needed['resupply'][participant] = max(6 - num_kits, 0)

            if any(pt_data['es_ptid'].isin(serial_pts)):
                kits_needed['serial'][participant] = 1

        if kits_needed['welcome'] or ship or kits_needed['serial']:
            address = get_household_address(order_report, house_id)

        # send welcome kits to patients in a household that are enrolled
        if kits_needed['welcome']:
            welcome_kits_needed = sum(kits_needed['welcome'].values())
            orders = append_order(orders, house_id, 3, welcome_kits_needed, address)

        # resupply entire house
        if ship:
            resupply_kits_needed = sum(kits_needed['resupply'].values())
            orders = append_order(orders, house_id, 1, resupply_kits_needed, address)

        if kits_needed['serial']:
            for pt, _ in kits_needed['serial'].items():
                orders = append_order(orders, house_id, 2, 1, address)

    export_orders(orders)


def append_order(orders, household, sku, quantity, address):
    """
    Append household orders to the broader order form
    """
    # don't append orders lacking a valid address
    if any(pd.isna(address['Street Address'])) and any(pd.isna(address['City'])) and any(pd.isna(address['State'])):
        return orders

    if quantity > 20 and sku == 1:  # seperate replenishment kits into other order becaues of max shippment size
        orders = append_order(orders, household, sku, quantity - 20, address)
        quantity = 20
    if quantity > 4 and sku == 3:  # seperate welcome kits into other order because of max shippment size
        orders = append_order(orders, household, sku, quantity - 4, address)
        quantity = 4

    address['SKU'] = sku
    address['Quantity'] = quantity
    address['OrderID'] = generate_order_number(address, orders)
    address['Household ID'] = household

    return pd.concat([orders, address], join='inner', ignore_index=True)


def get_household_address(household_records, house_id):
    """Get the most up to date address from a household"""
    enroll_address = get_enrollment_address(household_records.loc[house_id])
    updated_address = get_most_recent_address(household_records.loc[house_id])

    # use the more recent symptom survey address if one exists
    address = enroll_address if updated_address is None else updated_address

    # always use original delivery instructions since symptom survey has no
    # additional dropoff instructions
    address['Pref First Name']       = get_best_first_name(enroll_address)
    address['Last Name']             = enroll_address['Last Name']
    address['Email']                 = enroll_address['Phone']
    address['Phone']                 = enroll_address['Phone']
    address['Delivery Instructions'] = enroll_address['Delivery Instructions']

    address['Project Name'] = 'Cascadia_SEA' if address[
        'Project Name'
    ].values == 2 else 'Cascadia_PDX'
    address['Zipcode'] = address['Zipcode'].astype(int) if not pd.isna(
        address['Zipcode'].values
    ) else ''

    return address[address.columns.intersection(export_columns)]


def get_most_recent_address(household_records):
    """Get the most recent address provided by a household"""
    # get a households symptom surveys, which may hold additional addresses
    symptom_surveys = household_records[household_records['redcap_repeat_instrument'] == 'symptom_survey'].copy()
    symptom_surveys['ss_date_1'] = symptom_surveys['ss_date_1'].astype('datetime64')

    # sort symptom survey by most recently completed
    # note: we assume non-empty values for `Street Address 2`, `City 2`, and `State 2`
    # implies a 'complete' address. The appended `2` indicates the value is from the
    # symptom survey and not the enrollment survey
    symptom_surveys = symptom_surveys.sort_values(by='ss_date_1', ascending = False)
    complete_addresses = symptom_surveys[
                            ~(
                                (pd.isna(symptom_surveys['Street Address 2'])) &
                                (pd.isna(symptom_surveys['City 2'])) &
                                (pd.isna(symptom_surveys['State 2']))
                            )
                        ].copy()

    if not complete_addresses.empty:
        complete_addresses['Street Address'] = complete_addresses['Street Address 2']
        complete_addresses['Apt Number'] = complete_addresses['Apt Number 2']
        complete_addresses['City'] = complete_addresses['City 2']
        complete_addresses['State'] = complete_addresses['State 2']
        complete_addresses['Zipcode'] = complete_addresses['Zipcode 2']

        return complete_addresses.iloc[[0]]
    else:
        return None


def get_enrollment_address(household_records):
    """
    Get the address from the head of household in a passed household's
    enrollment event.
    """
    # get the head of house id, which is the first non NaN value in this household's data set.
    # We have to reset the index to avoid a duplicated index error and then grab the index of the
    # actual head of house record based on the head of house id
    tmp = household_records.copy()
    tmp.reset_index(level=0, inplace=True)
    head_of_house_idx = int(tmp.iloc[
        tmp["HH Reporter"].notna().idxmax()
    ]['HH Reporter'])
    return household_records.loc[[f'{head_of_house_idx}_arm_1']].query('redcap_repeat_instrument.isna()')


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


def get_best_first_name(enroll_address):
    '''
    Return the preferred first name of the participant if it exists or their
    full first name if it does not.
    '''
    pref_first_name = enroll_address.iloc[0]['Pref First Name']
    if not pd.isna(pref_first_name):
        return pref_first_name
    else:
        return enroll_address.iloc[0]['First Name']


def export_orders(orders):
    # print(orders.groupby(['Project Name']).size() \
    #             .reset_index(name='counts'))
    orders.to_csv(path.join(
        base_dir,
        f'data/USPSOrder{datetime.now().strftime("%Y_%m_%d_%H_%M")}.csv'),
                  index=False)


if __name__ == '__main__':
    main()
