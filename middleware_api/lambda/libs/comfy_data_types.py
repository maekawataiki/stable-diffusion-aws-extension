import datetime
from dataclasses import dataclass
from typing import Optional, List, Any

from libs.enums import ComfyEnvPrepareType, ComfySyncStatus


@dataclass
class ComfyTemplateTable:
    template_name: str
    tag: Optional[str]
    s3_path: str
    create_time: datetime.datetime
    modify_time: datetime.datetime


@dataclass
class ComfyConfigTable:
    config_name: str
    tag: Optional[str]
    config_value: str
    create_time: datetime.datetime
    modify_time: datetime.datetime


@dataclass
class ComfyExecuteTable:
    prompt_id: str
    endpoint_name: str
    inference_type: str
    need_sync: bool
    status: str
    # prompt: str number: Optional[int] front: Optional[str] extra_data: Optional[str] client_id: Optional[str]
    prompt_params: dict[str, Any]
    instance_id: Optional[str]
    prompt_path: Optional[str]
    output_path: Optional[str]
    output_files: Optional[List[str]] = None
    create_time: Optional[Any] = None
    start_time: Optional[Any] = None
    complete_time: Optional[Any] = None


@dataclass
class ComfySyncTable:
    request_id: str
    endpoint_name: str
    endpoint_id: str
    instance_count: int
    sync_instance_count: int
    prepare_type: ComfyEnvPrepareType
    need_reboot: bool
    s3_source_path: Optional[str]
    local_target_path: Optional[str]
    sync_script: Optional[str]
    endpoint_snapshot: Optional[Any]
    sync_status: ComfySyncStatus
    request_time: datetime.datetime


@dataclass
class ComfyInstanceMonitorTable:
    endpoint_id: str
    endpoint_name: str
    gen_instance_id: str
    sync_status: ComfySyncStatus
    last_sync_request_id: str
    last_sync_time: str
    # period_config: str  move to config table
    sync_list: Optional[List[str]]
    create_time: datetime.datetime
    last_heartbeat_time: Optional[Any] = None


@dataclass
class ComfyMessageTable:
    prompt_id: str
    msg_list: Optional[List[str]] = None

