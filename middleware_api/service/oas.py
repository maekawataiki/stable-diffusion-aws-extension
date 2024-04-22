import json
import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional

import boto3
from aws_lambda_powertools import Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from libs.common_tools import DecimalEncoder
from libs.utils import response_error

client = boto3.client('apigateway')

tracer = Tracer()

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get('LOG_LEVEL') or logging.ERROR)

esd_version = os.environ.get("ESD_VERSION")


@dataclass
class Tag:
    name: str
    description: str

    def to_dict(self):
        return {"name": self.name, "description": self.description}


@dataclass
class Parameter:
    name: str
    description: str
    location: str
    schema: Optional[dict] = None

    def to_dict(self):
        return {"name": self.name, "description": self.description, "in": self.location}


@dataclass
class APISchema:
    summary: str
    tags: List[str]
    parameters: Optional[List[Parameter]] = field(default_factory=list)


header_user_name = Parameter(name="username", description="Request Username", location="header")
query_limit = Parameter(name="limit", description="Limit Per Page", location="query")

tags = [
    Tag(name="Service", description="Service API").to_dict(),
    Tag(name="Roles", description="Manage Roles").to_dict(),
    Tag(name="Users", description="Manage Users").to_dict(),
    Tag(name="Endpoints", description="Manage Endpoints").to_dict(),
    Tag(name="Checkpoints", description="Manage Checkpoints").to_dict(),
    Tag(name="Inferences", description="Manage Inferences").to_dict(),
    Tag(name="Executes", description="Manage Executes").to_dict(),
    Tag(name="Datasets", description="Manage Datasets").to_dict(),
    Tag(name="Trainings", description="Manage Trainings").to_dict(),
    Tag(name="Prepare", description="Sync files to Endpoint").to_dict(),
    Tag(name="Sync", description="Sync Message from Endpoint").to_dict(),
    Tag(name="Others", description="Others API").to_dict()
]

summaries = {
    "RootAPI": APISchema(
        summary="Root API",
        tags=["Service"]
    ),
    "Ping": APISchema(
        summary="Ping API",
        tags=["Service"]
    ),
    "ListRoles": APISchema(
        summary="List Roles",
        tags=["Roles"],
        parameters=[
            header_user_name
        ]
    ),
    "GetInferenceJob": APISchema(
        summary="Get Inference Job",
        tags=["Inferences"],
        parameters=[
            header_user_name
        ]
    ),
    "CreateRole": APISchema(
        summary="Create Role",
        tags=["Roles"],
        parameters=[
            header_user_name
        ]
    ),
    "DeleteRoles": APISchema(
        summary="Delete Roles",
        tags=["Roles"],
        parameters=[
            header_user_name
        ]
    ),
    "GetTraining": APISchema(
        summary="Get Training",
        tags=["Trainings"],
        parameters=[
            header_user_name
        ]
    ),
    "ListCheckpoints": APISchema(
        summary="List Checkpoints",
        tags=["Checkpoints"],
        parameters=[
            header_user_name,
            Parameter(name="username", description="Filter by username", location="query"),
        ]
    ),
    "CreateCheckpoint": APISchema(
        summary="Create Checkpoint",
        tags=["Checkpoints"],
        parameters=[
            header_user_name
        ]
    ),
    "DeleteCheckpoints": APISchema(
        summary="Delete Checkpoints",
        tags=["Checkpoints"],
        parameters=[
            header_user_name
        ]
    ),
    "StartInferences": APISchema(
        summary="Start Inference Job",
        tags=["Inferences"],
        parameters=[
            header_user_name
        ]
    ),
    "ListExecutes": APISchema(
        summary="List Executes",
        tags=["Executes"],
        parameters=[
            header_user_name
        ]
    ),
    "CreateExecute": APISchema(
        summary="Create Execute",
        tags=["Executes"],
        parameters=[
            header_user_name
        ]
    ),
    "DeleteExecutes": APISchema(
        summary="Delete Executes",
        tags=["Executes"],
        parameters=[
            header_user_name
        ]
    ),
    "GetApiOAS": APISchema(
        summary="Get OAS",
        tags=["Service"],
        parameters=[
            header_user_name
        ]
    ),
    "ListUsers": APISchema(
        summary="List Users",
        tags=["Users"],
        parameters=[
            header_user_name
        ]
    ),
    "CreateUser": APISchema(
        summary="Create User",
        tags=["Users"],
        parameters=[
            header_user_name
        ]
    ),
    "DeleteUsers": APISchema(
        summary="Delete Users",
        tags=["Users"],
        parameters=[
            header_user_name
        ]
    ),
    "ListTrainings": APISchema(
        summary="List Trainings",
        tags=["Trainings"],
        parameters=[
            header_user_name
        ]
    ),
    "CreateTraining": APISchema(
        summary="Create Training",
        tags=["Trainings"],
        parameters=[
            header_user_name
        ]
    ),
    "DeleteTrainings": APISchema(
        summary="Delete Trainings",
        tags=["Trainings"],
        parameters=[
            header_user_name
        ]
    ),
    "GetExecute": APISchema(
        summary="Get Execute",
        tags=["Executes"],
        parameters=[
            header_user_name
        ]
    ),
    "ListDatasets": APISchema(
        summary="List Datasets",
        tags=["Datasets"],
        parameters=[
            header_user_name
        ]
    ),
    "CropDataset": APISchema(
        summary="Create new Crop Dataset",
        tags=["Datasets"],
        parameters=[
            header_user_name
        ]
    ),
    "UpdateCheckpoint": APISchema(
        summary="Update Checkpoint",
        tags=["Checkpoints"],
        parameters=[
            header_user_name
        ]
    ),
    "CreateDataset": APISchema(
        summary="Create Dataset",
        tags=["Datasets"],
        parameters=[
            header_user_name
        ]
    ),
    "DeleteDatasets": APISchema(
        summary="Delete Datasets",
        tags=["Datasets"],
        parameters=[
            header_user_name
        ]
    ),
    "GetDataset": APISchema(
        summary="Get Dataset",
        tags=["Datasets"],
        parameters=[
            header_user_name
        ]
    ),
    "UpdateDataset": APISchema(
        summary="Update Dataset",
        tags=["Datasets"],
        parameters=[
            header_user_name
        ]
    ),
    "ListInferences": APISchema(
        summary="List Inferences",
        tags=["Inferences"],
        parameters=[
            header_user_name
        ]
    ),
    "CreateInferenceJob": APISchema(
        summary="Create Inference Job",
        tags=["Inferences"],
        parameters=[
            header_user_name
        ]
    ),
    "DeleteInferenceJobs": APISchema(
        summary="Delete Inference Jobs",
        tags=["Inferences"],
        parameters=[
            header_user_name
        ]
    ),
    "ListEndpoints": APISchema(
        summary="List Endpoints",
        tags=["Endpoints"],
        parameters=[
            header_user_name
        ]
    ),
    "CreateEndpoint": APISchema(
        summary="Create Endpoint",
        tags=["Endpoints"],
        parameters=[
            header_user_name
        ]
    ),
    "DeleteEndpoints": APISchema(
        summary="Delete Endpoints",
        tags=["Endpoints"],
        parameters=[
            header_user_name
        ]
    ),
    "SyncMessage": APISchema(
        summary="Sync Message",
        tags=["Sync"],
        parameters=[
            header_user_name
        ]
    ),
    "GetSyncMessage": APISchema(
        summary="Get Sync Message",
        tags=["Sync"],
        parameters=[
            header_user_name
        ]
    ),
    "CreatePrepare": APISchema(
        summary="Create Prepare",
        tags=["Prepare"],
        parameters=[
            header_user_name
        ]
    ),
    "GetPrepare": APISchema(
        summary="Get Prepare",
        tags=["Prepare"],
        parameters=[
            header_user_name
        ]
    ),
}


@tracer.capture_lambda_handler
def handler(event: dict, context: LambdaContext):
    logger.info(f'event: {event}')
    logger.info(f'ctx: {context}')

    api_id = event['requestContext']['apiId']

    try:
        response = client.get_export(
            restApiId=api_id,
            stageName='prod',
            exportType='oas30',
            accepts='application/json',
            parameters={
                'extensions': 'apigateway'
            }
        )

        oas = response['body'].read()
        json_schema = json.loads(oas)
        json_schema = replace_null(json_schema)
        json_schema['info']['version'] = esd_version.split('-')[0]

        json_schema['servers'] = [
            {
                "url": "https://{ApiId}.execute-api.{Region}.{Domain}/prod/",
                "variables": {
                    "ApiId": {
                        "default": "xxxxxx"
                    },
                    "Region": {
                        "default": "ap-northeast-1"
                    },
                    "Domain": {
                        "default": "amazonaws.com"
                    },
                }
            }
        ]

        json_schema['tags'] = tags

        for path in json_schema['paths']:
            for method in json_schema['paths'][path]:
                meta = supplement_schema(json_schema['paths'][path][method])
                json_schema['paths'][path][method]['summary'] = meta.summary
                json_schema['paths'][path][method]['tags'] = meta.tags
                json_schema['paths'][path][method]['parameters'] = merge_parameters(meta,
                                                                                    json_schema['paths'][path][method])

        json_schema['paths'] = dict(sorted(json_schema['paths'].items(), key=lambda x: x[0]))

        payload = {
            'isBase64Encoded': False,
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': '*',
                'Access-Control-Allow-Methods': '*',
                'Access-Control-Allow-Credentials': True,
            },
            'body': json.dumps(json_schema, cls=DecimalEncoder, indent=2)
        }

        return payload
    except Exception as e:
        return response_error(e)


def merge_parameters(schema: APISchema, item: dict):
    if not schema.parameters:
        return []

    if 'parameters' not in item or len(item['parameters']) == 0:
        item['parameters'] = []
        for param in schema.parameters:
            item['parameters'].append(param.to_dict())
        return item['parameters']

    for param in schema.parameters:

        update = False
        for original_para in item['parameters']:
            if param.name == original_para['name'] and param.location == original_para['in']:
                update = True
                original_para.update(param.to_dict())

        if update is False:
            item['parameters'].append(param.to_dict())

    return item['parameters']


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


def supplement_schema(method: any):
    if 'operationId' in method:
        if method['operationId'] in summaries:
            item: APISchema = summaries[method['operationId']]
            if item.parameters:
                parameters = item.parameters
            else:
                parameters = []

            return APISchema(
                summary=item.summary + f" ({method['operationId']})",
                tags=item.tags,
                parameters=parameters
            )

        return APISchema(
            summary=method['operationId'],
            tags=["Others"],
            parameters=[]
        )

    return APISchema(
        summary="",
        tags=["Others"],
        parameters=[]
    )
