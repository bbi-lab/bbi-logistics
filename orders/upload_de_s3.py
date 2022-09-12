import logging, os
from pathlib import Path
from utils.s3 import upload_file, LOGISTICS_S3_BUCKET, LOGISTICS_DE_PATH
from utils.common import most_recent_matching_order

# Set up logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig()
LOG = logging.getLogger(__name__)
LOG.setLevel(LOG_LEVEL)

BASE_DIR = Path(__file__).resolve().parent.parent.resolve()
DATA_DIR = os.path.join(BASE_DIR, 'data')


def main():
    order = most_recent_matching_order(DATA_DIR, 'DeliveryExpressOrder*')
    LOG.info(f'Preparing to upload order form <{order}> to S3.')

    # TODO: lets add a command line flag to not upload by default.
    success = upload_file(order, LOGISTICS_S3_BUCKET, LOGISTICS_DE_PATH)

    if success:
        LOG.info(f'File successfully uploaded to <{LOGISTICS_S3_BUCKET}/{LOGISTICS_DE_PATH}>.')
    else:
        LOG.error(f'File upload to <{LOGISTICS_S3_BUCKET}/{LOGISTICS_DE_PATH}> failed.')


if __name__ == '__main__':
    main()
