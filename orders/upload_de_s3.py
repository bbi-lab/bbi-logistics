import boto3
import re
import logging
from os import path, environ, listdir, environ
from botocore.exceptions import ClientError
from datetime import datetime
from pathlib import Path

# Set up logging
LOG_LEVEL = environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig()
LOG = logging.getLogger(__name__)
LOG.setLevel(LOG_LEVEL)

base_dir = base_dir = Path(__file__).resolve().parent.parent.resolve()


def most_recent_order_today():
    data_dir = path.join(base_dir, 'data')
    files = [
        f for f in listdir(path.join(data_dir))
        if path.isfile(path.join(data_dir, f))
        and re.match(r'DeliveryExpressOrder\d{4}_\d{2}_\d{2}_\d{2}_\d{2}.csv',
                     path.basename(f)) and datetime.
        strptime(path.basename(f), 'DeliveryExpressOrder%Y_%m_%d_%H_%M.csv'
                 ).date() == datetime.today().date()
    ]

    files.sort(key=lambda x: datetime.strptime(
        x, 'DeliveryExpressOrder%Y_%m_%d_%H_%M.csv'),
               reverse=True)

    return path.join(data_dir, files[0]) if files else None


def upload_file_to_s3(local_fp, s3_fp, object_name):
    '''uploads a file to s3'''
    s3_client = boto3.client('s3')

    try:
        response = s3_client.upload_file(local_fp, s3_fp, object_name + '/' + path.basename(local_fp), ExtraArgs={'ServerSideEncryption': 'AES256'})
    except ClientError as e:
        LOG.error(e)
        return False

    return True


def main():
    order = most_recent_order_today()
    s3_path = 'bbi-logistics-orders'
    upload_file_to_s3(order, s3_path, 'delivery_express')


if __name__ == '__main__':
    main()
