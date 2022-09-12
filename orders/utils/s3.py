"""order utilities for interacting with our S3 bucket"""
import boto3
import logging, os
from botocore.exceptions import ClientError

LOGISTICS_S3_BUCKET = 'bbi-logistics-orders'
LOGISTICS_DE_PATH = 'delivery_express'
LOGISTICS_USPS_PATH = 'usps'

# Set up logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig()
LOG = logging.getLogger(__name__)
LOG.setLevel(LOG_LEVEL)


def upload_file(file_to_upload, bucket_name, object_name):
    '''uploads a file to s3'''
    s3_client = boto3.client('s3')
    LOG.debug(f'Set up client to upload file <{file_to_upload}> to S3 bucket <{bucket_name}>.')

    # ensure our object name is relative to the directory structure
    object_name = object_name + '/' + os.path.basename(file_to_upload)

    try:
        LOG.debug(f'Uploading S3 Object <{object_name}> to <{bucket_name}>.')
        s3_client.upload_file(file_to_upload, bucket_name, object_name, ExtraArgs={'ServerSideEncryption': 'AES256'})

    except ClientError as e:
        LOG.error(e)
        return False

    return True
