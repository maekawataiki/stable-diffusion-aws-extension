import json
import os
import tarfile

import boto3
import execution
import server
from aiohttp import web

global bucket_name_using
global sqs_url_using
global region_using
global need_sync
global prompt_id


async def prepare_environment(json_data):
    print("prepare_environment start")
    global bucket_name_using, sqs_url_using, region_using
    bucket_name_using = json_data['bucket_name']
    sqs_url_using = json_data['sqs_url']
    region_using = json_data['region']
    sync_s3_models_or_inputs_to_local(bucket_name_using, 'models', '/opt/ml/code/models', False)
    sync_s3_models_or_inputs_to_local(bucket_name_using, 'input', '/opt/ml/code/input', False)
    sync_s3_models_or_inputs_to_local(bucket_name_using, 'nodes', '/opt/ml/code/custom_nodes', True)
    print("prepare_environment end")


# def create_tar_gz(source_file, target_tar_gz):
#     # Example usage:
#     # source_file_path = "/path/to/your/source/file.txt"
#     # target_tar_gz_path = "/path/to/your/target/file.tar.gz"
#     with tarfile.open(target_tar_gz, "w:gz") as tar:
#         tar.add(source_file, arcname=os.path.basename(source_file))


def sync_s3_models_or_inputs_to_local(bucket_name, s3_path, local_path, need_un_tar):
    print("sync_s3_models_or_inputs_to_local start")
    s5cmd_command = f'/opt/ml/code/tools/s5cmd cp "s3://{bucket_name}/{s3_path}/*" "{local_path}/"'
    try:
        # TODO 注意添加去重逻辑
        print(s5cmd_command)
        os.system(s5cmd_command)
        print(f'Files copied from "s3://{bucket_name}/{s3_path}/*" to "{local_path}/"')
        if need_un_tar:
            for filename in os.listdir(local_path):
                if filename.endswith(".tar.gz"):
                    tar_filepath = os.path.join(local_path, filename)
                    with tarfile.open(tar_filepath, "r:gz") as tar:
                        tar.extractall(path=local_path)
                    os.remove(tar_filepath)
                    print(f'File {tar_filepath} extracted and removed')
    except Exception as e:
        print(f"Error executing s5cmd command: {e}")


def sync_local_outputs_to_s3(bucket_name, s3_path, local_path):
    print("sync_local_outputs_to_s3 start")
    s5cmd_command = f'/opt/ml/code/tools/s5cmd cp "{local_path}/*" "s3://{bucket_name}/{s3_path}/" '
    try:
        print(s5cmd_command)
        os.system(s5cmd_command)
        print(f'Files copied local to "s3://{bucket_name}/{s3_path}/" to "{local_path}/"')
    except Exception as e:
        print(f"Error executing s5cmd command: {e}")


@server.PromptServer.instance.routes.post("/invocations")
async def invocations(request):
    global bucket_name_using
    global region_using
    global need_sync
    global prompt_id
    json_data = await request.json()
    try:
        print(f"invocations start json_data:{json_data}")

        need_sync = json_data['need_sync']

        if bool(json_data['need_prepare']):
            # TODO 待优化记录 是否初始化过 或者拆分单独方法处理准备工作
            await prepare_environment(json_data)

        if not bucket_name_using:
            print("No sqs url or bucket name")
            return web.Response(status=500)

        print(
            f'bucket_name_using: {bucket_name_using}, region_using: {region_using}, need_sync: {need_sync}')

        server_instance = server.PromptServer.instance
        if "number" in json_data:
            number = float(json_data['number'])
            server_instance.number = number
        else:
            number = server_instance.number
            if "front" in json_data:
                if json_data['front']:
                    number = -number
            server_instance.number += 1

        valid = execution.validate_prompt(json_data['prompt'])

        if not valid[0]:
            await prepare_environment(json_data)

        extra_data = {}
        if "extra_data" in json_data:
            extra_data = json_data["extra_data"]
        if "client_id" in json_data:
            extra_data["client_id"] = json_data["client_id"]
        if valid[0]:
            # prompt_id = str(uuid.uuid4())
            prompt_id = json_data['prompt_id']
            e = execution.PromptExecutor(server_instance)
            outputs_to_execute = valid[2]
            e.execute(json_data['prompt'], prompt_id, extra_data, outputs_to_execute)
            sync_local_outputs_to_s3(bucket_name_using, f'output/{prompt_id}', '/opt/ml/code/output')
            clean_cmd = 'rm -rf /opt/ml/code/output'
            os.system(clean_cmd)
        return web.Response(status=200)
    except Exception as e:
        print("exception occurred", e)
        await prepare_environment(json_data)
        return web.Response(status=500)


def validate_prompt_proxy(func):
    def wrapper(*args, **kwargs):
        # 在这里添加您的代理逻辑
        print("validate_prompt_proxy start...")
        # 调用原始函数
        result = func(*args, **kwargs)
        # 在这里添加执行后的操作
        print("validate_prompt_proxy end...")
        return result

    return wrapper


execution.validate_prompt = validate_prompt_proxy(execution.validate_prompt)


def send_sync_proxy(func):
    def wrapper(*args, **kwargs):
        global sqs_url_using
        global region_using
        global need_sync
        global prompt_id
        print(f"send_sync_proxy start... {need_sync},{prompt_id}")
        if not need_sync:
            func(*args, **kwargs)
        elif sqs_url_using and region_using:
            print(f"send_sync_proxy params... {sqs_url_using},{region_using},{need_sync},{prompt_id}")
            event = args[1]
            data = args[2]
            sid = args[3] if len(args) == 4 else None
            queue_url = sqs_url_using
            sqs_client = boto3.client('sqs', region_name=region_using)
            message_body = {'prompt_id': prompt_id, 'event': event, 'data': data, 'sid': sid}
            response = sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message_body),
                MessageGroupId=prompt_id
            )
            message_id = response['MessageId']
            print(f'send_sync_proxy message_id :{message_id} message_body: {message_body}')
        print(f"send_sync_proxy end...")

    return wrapper


server.PromptServer.send_sync = send_sync_proxy(server.PromptServer.send_sync)
