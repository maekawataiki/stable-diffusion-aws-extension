import base64
import datetime
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, List, Optional

import boto3
import sagemaker
import tomli
import tomli_w
from common import const
from common.const import LoraTrainType
from common.ddb_service.client import DynamoDbUtilsService
from common.response import (
    accepted,
    bad_request,
    created,
    forbidden,
    internal_server_error,
    not_found,
)
from common.util import get_s3_presign_urls, load_json_from_s3, save_json_to_file
from libs.common_tools import DecimalEncoder, split_s3_path
from libs.data_types import (
    CheckPoint,
    CheckPointStatus,
    TrainJob,
    TrainJobStatus,
)
from libs.utils import get_permissions_by_username, get_user_roles
from common.stepfunction_service.client import StepFunctionUtilsService

bucket_name = os.environ.get("S3_BUCKET")
train_table = os.environ.get("TRAIN_TABLE")
checkpoint_table = os.environ.get("CHECKPOINT_TABLE")
user_table = os.environ.get("MULTI_USER_TABLE")
region_name = os.environ.get("AWS_REGION")
instance_type = os.environ.get("INSTANCE_TYPE")
sagemaker_role_arn = os.environ.get("TRAIN_JOB_ROLE")
image_uri = os.environ.get("TRAIN_ECR_URL")
user_topic_arn = os.environ.get("USER_EMAIL_TOPIC_ARN")
training_stepfunction_arn = os.environ.get('TRAINING_SAGEMAKER_ARN')

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL") or logging.ERROR)

ddb_service = DynamoDbUtilsService(logger=logger)
s3 = boto3.client("s3", region_name=region_name)


@dataclass
class Event:
    train_type: str
    params: dict[str, Any]
    creator: str
    filenames: Optional[List[str]] = None
    lora_train_type: Optional[str] = LoraTrainType.KOHYA.value


def _update_toml_file_in_s3(
    bucket_name: str, file_key: str, new_file_key: str, updated_params
):
    """Update and save a TOML file in an S3 bucket

    Args:
        bucket_name (str): S3 bucket name to save the TOML file
        file_key (str): TOML template file key
        new_file_key (str): TOML file with merged parameters
        updated_params (_type_): parameters to be merged
    """
    try:
        response = s3.get_object(Bucket=bucket_name, Key=file_key)
        toml_content = response["Body"].read().decode("utf-8")
        toml_data = tomli.loads(toml_content)

        # Update parameters in the TOML data
        for section, params in updated_params.items():
            if section in toml_data:
                for key, value in params.items():
                    toml_data[section][key] = value
            else:
                toml_data[section] = params

        updated_toml_content = tomli_w.dumps(toml_data)
        s3.put_object(Bucket=bucket_name, Key=new_file_key, Body=updated_toml_content)
        logger.info(f"Updated '{file_key}' in '{bucket_name}' successfully.")

    except Exception as e:
        logger.error(f"An error occurred when updating Kohya toml: {e}")


def _json_encode_hyperparameters(hyperparameters):
    """Encode hyperparameters

    Args:
        hyperparameters : hyperparameters to be encoded

    Returns:
        Encoded hyperparameters
    """
    new_params = {}
    for k, v in hyperparameters.items():
        json_v = json.dumps(v, cls=DecimalEncoder)
        v_bytes = json_v.encode("ascii")
        base64_bytes = base64.b64encode(v_bytes)
        base64_v = base64_bytes.decode("ascii")
        new_params[k] = base64_v

    return new_params


def _trigger_sagemaker_training_job(
    train_job: TrainJob, ckpt_output_path: str, train_job_name: str
):
    """Trigger SageMaker training job

    Args:
        train_job (TrainJob): training job metadata
        ckpt_output_path (str): S3 path to store the trained model file
        train_job_name (str): training job name
    """
    hyperparameters = _json_encode_hyperparameters(
        {
            "sagemaker_program": "extensions/sd-webui-sagemaker/sagemaker_entrypoint_json.py",
            "params": train_job.params,
            "s3-input-path": train_job.input_s3_location,
            "s3-output-path": ckpt_output_path,
            "training-type": train_job.params[
                "training_type"
            ],  # Available value: "dreambooth", "kohya"
        }
    )

    final_instance_type = instance_type
    if (
        "training_params" in train_job.params
        and "training_instance_type" in train_job.params["training_params"]
        and train_job.params["training_params"]["training_instance_type"]
    ):
        final_instance_type = train_job.params["training_params"][
            "training_instance_type"
        ]

    est = sagemaker.estimator.Estimator(
        image_uri,
        sagemaker_role_arn,
        instance_count=1,
        instance_type=final_instance_type,
        volume_size=125,
        base_job_name=f"{train_job_name}",
        hyperparameters=hyperparameters,
        job_id=train_job.id,
    )
    est.fit(wait=False)

    while not est._current_job_name:
        time.sleep(1)

    train_job.sagemaker_train_name = est._current_job_name
    
    stepfunctions_client = StepFunctionUtilsService(logger=logger)
    sfn_input = {
        "train_job_id": train_job.id,
        "train_job_name": train_job.sagemaker_train_name,
    }
    sfn_arn = stepfunctions_client.invoke_step_function(
        training_stepfunction_arn, sfn_input
    )
    # todo: use batch update, this is ugly!!!
    search_key = {"id": train_job.id}
    ddb_service.update_item(
        table=train_table,
        key=search_key,
        field_name="sagemaker_train_name",
        value=est._current_job_name,
    )
    train_job.job_status = TrainJobStatus.Training
    ddb_service.update_item(
        table=train_table,
        key=search_key,
        field_name="job_status",
        value=TrainJobStatus.Training.value,
    )
    train_job.sagemaker_sfn_arn = sfn_arn
    ddb_service.update_item(
        table=train_table, key=search_key, field_name="sagemaker_sfn_arn", value=sfn_arn
    )


def _start_training_job(train_job_id: str):
    raw_train_job = ddb_service.get_item(
        table=train_table, key_values={"id": train_job_id}
    )
    if raw_train_job is None or len(raw_train_job) == 0:
        return internal_server_error(
            message=f"no such train job with id({train_job_id})"
        )

    train_job = TrainJob(**raw_train_job)
    train_job_name = train_job.model_id

    raw_checkpoint = ddb_service.get_item(
        table=checkpoint_table, key_values={"id": train_job.checkpoint_id}
    )
    if raw_checkpoint is None:
        return internal_server_error(
            message=f"checkpoint with id {train_job.checkpoint_id} is not found"
        )

    checkpoint = CheckPoint(**raw_checkpoint)

    _trigger_sagemaker_training_job(train_job, checkpoint.s3_location, train_job_name)

    return {
        "statusCode": 200,
        "job": {
            "id": train_job.id,
            "status": train_job.job_status.value,
            "created": train_job.timestamp,
            "trainType": train_job.train_type,
            "params": train_job.params,
            "input_location": train_job.input_s3_location,
        },
    }


def _create_training_job(raw_event, context):
    """Create a training job

    Returns:
        Training job in JSON format
    """
    request_id = context.aws_request_id
    event = Event(**json.loads(raw_event["body"]))
    logger.info(json.dumps(json.loads(raw_event["body"])))
    _lora_train_type = event.lora_train_type

    creator_permissions = get_permissions_by_username(
        ddb_service, user_table, event.creator
    )
    if "train" not in creator_permissions or (
        "all" not in creator_permissions["train"]
        and "create" not in creator_permissions["train"]
    ):
        return forbidden(
            message=f"user {event.creator} has not permission to create a train job"
        )

    if _lora_train_type.lower() == LoraTrainType.KOHYA.value:
        # Kohya training
        base_key = f"{_lora_train_type.lower()}/train/{request_id}"
        input_location = f"{base_key}/input"
        toml_dest_path = f"{input_location}/{const.KOHYA_TOML_FILE_NAME}"
        toml_template_path = "template/" + const.KOHYA_TOML_FILE_NAME
        if event.model_id is None:
            event.model_id = const.KOHYA_MODEL_ID

        if (
            "training_params" not in event.params
            or "s3_model_path" not in event.params["training_params"]
            or "s3_data_path" not in event.params["training_params"]
        ):
            raise ValueError(
                "Missing train parameters, s3_model_path and s3_data_path should be in training_params"
            )

        # Merge user parameter, if no config_params is defined, use the default value in S3 bucket
        if "config_params" in event.params:
            updated_parameters = event.params["config_params"]
            _update_toml_file_in_s3(
                bucket_name, toml_template_path, toml_dest_path, updated_parameters
            )
        else:
            # Copy template file and make no changes as no config parameters are defined
            s3.copy_object(
                CopySource={"Bucket": bucket_name, "Key": toml_template_path},
                Bucket=bucket_name,
                Key=toml_dest_path,
            )

        event.params["training_params"][
            "s3_toml_path"
        ] = f"s3://{bucket_name}/{toml_dest_path}"
    else:
        raise ValueError(
            f"Invalid lora train type: {_lora_train_type}, the valid value is {LoraTrainType.KOHYA.value}."
        )

    event.params["training_type"] = _lora_train_type.lower()
    user_roles = get_user_roles(ddb_service, user_table, event.creator)
    checkpoint = CheckPoint(
        id=request_id,
        checkpoint_type=event.train_type,
        s3_location=f"s3://{bucket_name}/{base_key}/output",
        checkpoint_status=CheckPointStatus.Initial,
        timestamp=datetime.datetime.now().timestamp(),
        allowed_roles_or_users=user_roles,
    )
    ddb_service.put_items(table=checkpoint_table, entries=checkpoint.__dict__)
    train_input_s3_location = f"s3://{bucket_name}/{input_location}"

    train_job = TrainJob(
        id=request_id,
        model_id=event.model_id,
        job_status=TrainJobStatus.Initial,
        params=event.params,
        train_type=event.train_type,
        input_s3_location=train_input_s3_location,
        checkpoint_id=checkpoint.id,
        timestamp=datetime.datetime.now().timestamp(),
        allowed_roles_or_users=[event.creator],
    )
    ddb_service.put_items(table=train_table, entries=train_job.__dict__)

    return {
        "id": train_job.id,
        "status": train_job.job_status.value,
        "trainType": train_job.train_type,
        "params": train_job.params,
        "input_location": train_input_s3_location,
    }


def handler(raw_event, context):
    try:
        training_job = _create_training_job(raw_event, context)

        return _start_training_job(training_job.id)
    except Exception as e:
        logger.error(f"Error when creating a training job: {e}")

        return internal_server_error(message=str(e))
