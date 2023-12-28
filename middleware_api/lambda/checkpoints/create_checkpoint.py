import datetime
import datetime
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

import boto3

from common.ddb_service.client import DynamoDbUtilsService
from common.response import bad_request, internal_server_error, created, accepted
from libs.common_tools import get_base_checkpoint_s3_key, \
    batch_get_s3_multipart_signed_urls
from libs.data_types import CheckPoint, CheckPointStatus, MultipartFileReq
from libs.utils import get_user_roles, get_permissions_by_username

checkpoint_table = os.environ.get('CHECKPOINT_TABLE')
bucket_name = os.environ.get('S3_BUCKET')
checkpoint_type = ["Stable-diffusion", "embeddings", "Lora", "hypernetworks", "ControlNet", "VAE"]
user_table = os.environ.get('MULTI_USER_TABLE')
upload_by_url_lambda_name = os.environ.get('UPLOAD_BY_URL_LAMBDA_NAME')
CN_MODEL_EXTS = [".pt", ".pth", ".ckpt", ".safetensors", ".yaml"]

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ddb_service = DynamoDbUtilsService(logger=logger)
MAX_WORKERS = 10

lambda_client = boto3.client('lambda')


@dataclass
class CreateCheckPointEvent:
    checkpoint_type: str
    params: dict[str, Any]
    filenames: [MultipartFileReq] = None
    urls: [str] = None


def handler(raw_event, context):
    request_id = context.aws_request_id
    event = CreateCheckPointEvent(**json.loads(raw_event['body']))

    if event.urls:
        for url in event.urls:
            resp = lambda_client.invoke(
                FunctionName=upload_by_url_lambda_name,
                InvocationType='Event',
                Payload=json.dumps({
                    'checkpoint_type': event.checkpoint_type,
                    'params': event.params,
                    'url': url,
                })
            )
            logger.info(resp)
        return accepted(message='Checkpoint creation in progress, please check later')

    _type = event.checkpoint_type
    headers = {
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
    }
    try:
        base_key = get_base_checkpoint_s3_key(_type, 'custom', request_id)
        presign_url_map = batch_get_s3_multipart_signed_urls(
            bucket_name=bucket_name,
            base_key=base_key,
            filenames=event.filenames
        )

        checkpoint_params = {}
        if event.params is not None and len(event.params) > 0:
            checkpoint_params = event.params

        checkpoint_params['created'] = str(datetime.datetime.now())
        checkpoint_params['multipart_upload'] = {}
        multiparts_resp = {}
        for key, val in presign_url_map.items():
            checkpoint_params['multipart_upload'][key] = {
                'upload_id': val['upload_id'],
                'bucket': val['bucket'],
                'key': val['key'],
            }
            multiparts_resp[key] = val['s3_signed_urls']

        filenames_only = []
        for f in event.filenames:
            file = MultipartFileReq(**f)
            filenames_only.append(file.filename)

        if len(filenames_only) == 0:
            return bad_request(message='no checkpoint name (file names) detected', headers=headers)

        user_roles = ['*']
        creator_permissions = {}
        if 'creator' in event.params and event.params['creator']:
            user_roles = get_user_roles(ddb_service, user_table, event.params['creator'])
            creator_permissions = get_permissions_by_username(ddb_service, user_table, event.params['creator'])

        if 'checkpoint' not in creator_permissions or \
                ('all' not in creator_permissions['checkpoint'] and 'create' not in creator_permissions['checkpoint']):
            return bad_request(message='user has no permissions to create a model', headers=headers)

        checkpoint = CheckPoint(
            id=request_id,
            checkpoint_type=_type,
            s3_location=f's3://{bucket_name}/{base_key}',
            checkpoint_names=filenames_only,
            checkpoint_status=CheckPointStatus.Initial,
            params=checkpoint_params,
            timestamp=datetime.datetime.now().timestamp(),
            allowed_roles_or_users=user_roles
        )
        ddb_service.put_items(table=checkpoint_table, entries=checkpoint.__dict__)
        data = {
            'checkpoint': {
                'id': request_id,
                'type': _type,
                's3_location': checkpoint.s3_location,
                'status': checkpoint.checkpoint_status.value,
                'params': checkpoint.params
            },
            's3PresignUrl': multiparts_resp
        }
        return created(data=data, headers=headers)
    except Exception as e:
        logger.error(e)
        return internal_server_error(headers=headers, message=str(e))
