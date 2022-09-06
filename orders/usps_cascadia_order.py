#!/usr/bin/env python3
import os, sys, logging, envdir, datetime
import pandas as pd
from utils.redcap import init_project, get_redcap_report, get_cascadia_study_pause_reports
from utils.common import USPS_EXPORT_COLS, export_orders
from utils.cascadia import append_order, get_household_address, participant_under_study_pause

# Place all modules within this script's path
BASE_DIR = os.path.abspath(__file__ + "/../../")
sys.path.append(BASE_DIR)

# Set up envdir
envdir.open(os.path.join(BASE_DIR, '.env/redcap'))

# Set up logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig()
LOG = logging.getLogger(__name__)
LOG.setLevel(LOG_LEVEL)

PROJECT = 'Cascadia'

def main():
    project = init_project(PROJECT)
    order_report = get_redcap_report(project, PROJECT, '1144')
    serial_report = get_redcap_report(project, PROJECT, '1711')
    pause_report = get_cascadia_study_pause_reports(project)

    serial_pts = serial_report['results_ptid'] if len(serial_report) else []
    LOG.debug(f'Operating with <{len(serial_report)}> serial patients.')

    # Set up each of the 10 possible barcode columns
    barcode_columns = [f'assign_barcode_{i}' for i in range(1, 10)]

    orders = pd.DataFrame(columns=USPS_EXPORT_COLS)
    household_ids = set(i[0] for i in order_report.index)

    for house_id in household_ids:
        LOG.debug(f'Working on household <{house_id}>.')

        # Each key in these dictionaries represents a patient_id and each
        # value represents the number of kits they require. See example below.
        kits_needed = {
            'resupply': {},  # {"0": 2, "1": 1, "3": 4}
            'welcome': {},  # {"2": 1}
            'serial': {}  # {"6": 1}
        }

        participants = set(
            i[1] for i in order_report.index if i[0] == house_id and i[1] != 'household_arm_1'
        )
        LOG.debug(f'<{len(participants)}> participants exist within household <{house_id}>')

        for participant in participants:
            LOG.debug(f'Working on participant <{participant}>.')
            pt_data = order_report.loc[[(house_id, participant)]]

            # the participant should be enrolled and consented to get any kits
            if not (any(pt_data['enrollment_survey_complete'] == 2) and any(pt_data['consent_form_complete'] == 2)):
                LOG.debug(f'Participant <{participant}> must be consented and enrolled to receive swab kits.')
                continue

            # if no swab barcodes have been completed they need a welcome kit and won't need anything else
            if not any(pt_data['swab_barcodes_complete'] == 2):
                LOG.debug(f'Participant <{participant}> has no complete swabs. Adding a welcome kit to their inventory.')
                kits_needed['welcome'][participant] = 1
                continue

            if participant_under_study_pause(pause_report, house_id, participant):
                LOG.info(f'Participant <{participant}> from household <{house_id}> is under study pause. Deliveries are stopped until the pause end date.')
                continue

            # current barcodes a pt has
            kit_barcodes = pt_data.loc[
                pt_data['redcap_repeat_instrument'] == 'swab_barcodes', barcode_columns
            ].notna().sum(axis=1).sum()

            # current barcodes a pt has returned
            kit_returns = pt_data.loc[
                pt_data['redcap_repeat_instrument'] == 'symptom_survey', 'ss_return_tracking'
            ].count()

            num_kits = kit_barcodes - kit_returns
            LOG.debug(f'Participant has total <{kit_barcodes}> kits with <{kit_returns}> returned. {num_kits} usable kits.')

            if num_kits < 3:
                kits_needed['resupply'][participant] = max(6 - num_kits, 0)
                LOG.debug(f'Resupplying {kits_needed["resupply"][participant]} kits to participant <{participant}>.')

            if any(pt_data['es_ptid'].isin(serial_pts)):
                kits_needed['serial'][participant] = 1
                LOG.debug(f'Participant is starting serial swab program. Adding a serial kit to their inventory.')


        if kits_needed['welcome'] or kits_needed['resupply'] or kits_needed['serial']:
            address = get_household_address(order_report, house_id)

        if kits_needed['resupply']:
            resupply_kits_needed = sum(kits_needed['resupply'].values())
            orders = append_order(orders, house_id, 1, resupply_kits_needed, address)

        if kits_needed['serial']:
            for pt, _ in kits_needed['serial'].items():
                orders = append_order(orders, house_id, 2, 1, address)

        if kits_needed['welcome']:
            welcome_kits_needed = sum(kits_needed['welcome'].values())
            orders = append_order(orders, house_id, 3, welcome_kits_needed, address)

    export_orders(orders, os.path.join(BASE_DIR, f'data/USPSOrder{datetime.datetime.now().strftime("%Y_%m_%d_%H_%M")}.csv'))

    LOG.info(f"Orders saved. Summary of orders generated by this run: \n \
        {orders.groupby(['Project Name']).size().reset_index(name='counts')}")


if __name__ == '__main__':
    main()
