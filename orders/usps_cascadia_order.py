#!/usr/bin/env python3
import os, sys, logging, envdir, datetime, argparse
import pandas as pd
from utils.redcap import init_project, get_redcap_report, get_cascadia_study_pause_reports
from utils.common import USPS_EXPORT_COLS, LOGISTICS_S3_BUCKET, LOGISTICS_USPS_PATH, export_orders
from utils.cascadia import append_order, get_household_address, participant_under_study_pause, household_needs_resupply, household_fully_consented_and_enrolled, get_participant_kit_count

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
MAX_KITS = 6

def main(args):
    project = init_project(PROJECT)
    order_report = get_redcap_report(project, PROJECT, '1144')
    serial_report = get_redcap_report(project, PROJECT, '1711')
    pause_report = get_cascadia_study_pause_reports(project)

    serial_pts = serial_report['results_ptid'] if len(serial_report) else []
    LOG.debug(f'Operating with <{len(serial_report)}> serial patients.')

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

        # first need to check if any participants in a househould need a resupply. If they do, we will
        # be resupplying ALL participants in the househould, even if they don't necessarily need it.
        needs_resupply = household_needs_resupply(house_id, participants, order_report, threshold=3)
        hh_fully_consented = household_fully_consented_and_enrolled(house_id, participants, order_report)
        LOG.debug(f'Resupply is set to <{needs_resupply}> for household <{house_id}>.')

        for participant in participants:
            LOG.debug(f'Working on participant <{participant}>.')
            pt_data = order_report.loc[[(house_id, participant)]]

            # the participant should be enrolled and consented to get any kits
            if not (any(pt_data['enrollment_survey_complete'] == 2) and any(pt_data['consent_form_complete'] == 2)):
                LOG.debug(f'Participant <{participant}> must be consented and enrolled to receive swab kits.')
                continue

            if participant_under_study_pause(pause_report, house_id, participant):
                LOG.info(f'Participant <{participant}> from household <{house_id}> is under study pause. Deliveries are stopped until the pause end date.')
                continue

            # if no swab barcodes have been completed and the household is fully enrolled + consented they need a welcome kit and won't need anything else
            if hh_fully_consented and not any(pt_data['swab_barcodes_complete'] == 2):
                LOG.debug(f'Adding a welcome kit to participant <{participant}> inventory as household <{house_id}> is fully consented + enrolled.')
                kits_needed['welcome'][participant] = 1
                continue

            if needs_resupply:
                num_kits = get_participant_kit_count(pt_data)
                LOG.debug(f'Participant has total {num_kits} usable kits.')

                kits_needed['resupply'][participant] = max(MAX_KITS - num_kits, 0)
                LOG.debug(f'Resupplying {kits_needed["resupply"][participant]} kits to participant <{participant}>.')

            if any(pt_data['es_ptid'].isin(serial_pts)):
                kits_needed['serial'][participant] = 1
                LOG.debug(f'Participant is starting serial swab program. Adding a serial kit to their inventory.')

            LOG.debug(f'Finished working on participant <{participant}>.')


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

    LOG.info(f"Summary of orders generated by this run: \n \
            {orders.groupby(['Project Name']).size().reset_index(name='counts')}")

    file_name = f'USPSOrder{datetime.datetime.now().strftime("%Y_%m_%d_%H_%M")}.csv'

    if args.save:
        export_orders(orders, os.path.join(BASE_DIR, f'data/{file_name}'))
        LOG.info(f'Successfully saved orders to <{os.path.join(BASE_DIR, f"data/{file_name}")}>.')
    else:
        LOG.debug(f"Skipping order save to disk with <--save={args.save}.>")

    if args.s3_upload:
        export_orders(orders, f's3://{LOGISTICS_S3_BUCKET}/{LOGISTICS_USPS_PATH}/{file_name}', s3=True)
        LOG.info(f'Successfully uploaded DE orders to <{LOGISTICS_S3_BUCKET}/{LOGISTICS_USPS_PATH}/{file_name}>')
    else:
        LOG.debug(f'Skipping order upload to S3 with <--s3-upload={args.s3_upload}>.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate and upload a delivery express order form for studies needing kit pickups.')
    parser.add_argument('--save', action='store_true', help='Flag to indicate the order form should be saved to the data directory.')
    parser.add_argument('--s3-upload', action='store_true', help='Flag to indicate the order form should be uploaded to S3.')

    main(parser.parse_args())
