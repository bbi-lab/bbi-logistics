"""order utilities for interacting with the REDCap projects"""
import os, logging, sys
import pandas as pd
from redcap import Project
from urllib.parse import urlparse
from .airs import filter_airs_orders
from .hct import filter_hct_orders
from .cascadia import filter_cascadia_orders

# Place all modules within this script's path
# TODO: structure directory better so we don't need this
base_dir = os.path.abspath(__file__ + "/../../../")
sys.path.append(base_dir)

from etc.ordering_script_config_map import PROJECT_DICT

STUDY_PAUSE_REPORT_IDS = [1897, 1900]

# Set up logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig()
LOG = logging.getLogger(__name__)
LOG.setLevel(LOG_LEVEL)


def init_project(project_name):
    '''Fetch content of order reports for a given `project`'''
    LOG.info(f'Initializing REDCap data for {project_name}')

    if project_name in ["HCT", "Cascadia"]:
        url = urlparse(os.environ.get("HCT_REDCAP_API_URL"))
    elif project_name == "AIRS":
        url = urlparse(os.environ.get("AIRS_REDCAP_API_URL"))
    else:
        url = urlparse(os.environ.get("REDCAP_API_URL"))

    api_key = os.environ.get(
        f"REDCAP_API_TOKEN_{url.netloc}_{PROJECT_DICT[project_name]['project_id']}"
    )

    LOG.debug(f'Initializing REDCap project <{project_name}> from API endpoint: <{url.geturl()}>')
    return Project(url.geturl(), api_key)


def format_longitudinal(orders, project):
    '''
    Reduce logitudinal projects to 1 order per row. Filter rows to those
    we need to create orders for based on logic unique to each project.
    '''
    if PROJECT_DICT[project]['project_type'] != 'longitudinal':
        LOG.info(f'No need to format <{project}>. <{PROJECT_DICT[project]["project_type"]}> is not longitudinal')
        return orders

    LOG.info(f'Reformatting <{project}> as a longitudinal project.')

    # Cast order date as a datetime and replace any NA values
    orders['Order Date'] = pd.to_datetime(orders['Order Date'])
    orders['Order Date'].replace('', pd.NA, inplace=True)

    if project == 'HCT':
        orders = filter_hct_orders(orders)

    elif project == 'AIRS':
        orders = filter_airs_orders(orders)

    elif project == 'Cascadia':
        orders = filter_cascadia_orders(orders)

    LOG.info(f'<{len(orders)}> orders remain for <{project}> after filtering.')
    return orders


def get_redcap_report(redcap_project, project_name, report_id = None):
    '''Get the order report for a given redcap project'''
    if not report_id:
        LOG.debug(f'Fetching `report_id` from config for project <{project_name}>')
        report_id = PROJECT_DICT[project_name]['Report Id']
    else:
        LOG.debug(f'Using passed `report_id` <{report_id}>')

    LOG.info(f'Fetching report <{report_id}> for project <{project_name}>')

    report = redcap_project.export_reports(
        report_id=report_id,
        format='df'
    ).rename(columns=PROJECT_DICT[project_name])

    LOG.debug(f'Original report <{report_id}> for project <{project_name}> has <{len(report)}> rows.')
    return report.sort_index()
