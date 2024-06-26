import json
import logging
import os

import boto3
from aws_lambda_powertools import Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from common.response import dumps_default
from libs.utils import response_error

client = boto3.client('apigateway')

tracer = Tracer()

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get('LOG_LEVEL') or logging.ERROR)


@tracer.capture_lambda_handler
def handler(event: dict, context: LambdaContext):
    logger.info(f'event: {event}')
    logger.info(f'ctx: {context}')

    try:
        response = client.get_export(
            restApiId=event['requestContext']['apiId'],
            stageName='prod',
            exportType='oas30',
        )

        oas = response['body'].read()
        json_schema = json.loads(oas)
        json_schema = replace_null(json_schema)

        payload = {
            'isBase64Encoded': False,
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': '*',
                'Access-Control-Allow-Methods': '*',
                'Access-Control-Allow-v': True,
            },
            'body': json.dumps(json_schema, default=dumps_default)
        }

        return payload
    except Exception as e:

        return response_error(e)


def replace_null(data):
    if isinstance(data, dict):
        for key, value in data.items():
            if value is None:
                data[key] = {
                    "type": "null",
                    "description": "Last Key for Pagination"
                }
            else:
                data[key] = replace_null(value)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if item is None:
                data[i] = {
                    "type": "null",
                    "description": "Last Key for Pagination"
                }
            else:
                data[i] = replace_null(item)
    return data
