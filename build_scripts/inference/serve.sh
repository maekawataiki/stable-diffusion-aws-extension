#!/bin/bash

export ESD_CODE_BRANCH=main
export INSTALL_SCRIPT=https://raw.githubusercontent.com/awslabs/stable-diffusion-aws-extension/main/install.sh

if [[ $ECR_IMAGE_TAG == *"dev"* ]]; then
  export ESD_CODE_BRANCH=dev
  export INSTALL_SCRIPT=https://raw.githubusercontent.com/awslabs/stable-diffusion-aws-extension/dev/install.sh
  trap 'echo "error_lock" > /error_lock; exit 1' ERR
  if [ -f "/error_lock" ]; then
      echo "start failed, please check the log"
      sleep 30
      exit 1
  fi
fi

echo "*********************************************************************************"
cat $0

echo "---------------------------------------------------------------------------------"
echo "Current shell: $SHELL"
echo "Running in $(bash --version)"

echo "---------------------------------------------------------------------------------"
nvidia-smi

echo "---------------------------------------------------------------------------------"
printenv

export ESD_VERSION='1.5.0'

echo "---------------------------------------------------------------------------------"
echo "INSTANCE_TYPE: $INSTANCE_TYPE"
echo "ECR_IMAGE_TAG: $ECR_IMAGE_TAG"
echo "IMAGE_URL: $IMAGE_URL"
echo "ENDPOINT_NAME: $ENDPOINT_NAME"
echo "ENDPOINT_ID: $ENDPOINT_ID"
echo "ESD_VERSION: $ESD_VERSION"
echo "CREATED_AT: $CREATED_AT"
created_time_seconds=$(date -d "$CREATED_AT" +%s)
current_time=$(date "+%Y-%m-%dT%H:%M:%S.%6N")
current_time_seconds=$(date -d "$current_time" +%s)
init_seconds=$(( current_time_seconds - created_time_seconds ))
echo "NOW_AT: $current_time"
echo "Init from Create: $init_seconds seconds"

echo "---------------------------------------------------------------------------------"
export S3_LOCATION="esd-$ESD_VERSION-$INSTANCE_TYPE"

if [ -n "$EXTENSIONS" ]; then
    export S3_LOCATION="$ENDPOINT_NAME"
fi

tar_file="webui.tar"

echo "Check s3://$BUCKET_NAME/$S3_LOCATION files..."
output=$(s5cmd ls "s3://$BUCKET_NAME/")
if echo "$output" | grep -q "$S3_LOCATION"; then

  start_at=$(date +%s)
  s5cmd --log=error sync "s3://$BUCKET_NAME/$S3_LOCATION/*" /home/ubuntu/
  end_at=$(date +%s)
  cost=$((end_at-start_at))
  echo "download file: $cost seconds"

  echo "set conda environment..."
  export LD_LIBRARY_PATH=/home/ubuntu/conda/lib:$LD_LIBRARY_PATH

  start_at=$(date +%s)
  tar --overwrite -xf "webui.tar" -C /home/ubuntu/stable-diffusion-webui/
  rm -rf $tar_file
  end_at=$(date +%s)
  cost=$((end_at-start_at))
  echo "decompress file: $cost seconds"

  cd /home/ubuntu/stable-diffusion-webui/

  # remove soft link
  rm -rf /home/ubuntu/stable-diffusion-webui/models
  s5cmd --log=error sync "s3://$BUCKET_NAME/$S3_LOCATION/insightface/*" "/home/ubuntu/stable-diffusion-webui/models/insightface/"

  mkdir -p /home/ubuntu/stable-diffusion-webui/models/VAE
  mkdir -p /home/ubuntu/stable-diffusion-webui/models/Stable-diffusion
  mkdir -p /home/ubuntu/stable-diffusion-webui/models/Lora
  mkdir -p /home/ubuntu/stable-diffusion-webui/models/hypernetworks

  source /home/ubuntu/stable-diffusion-webui/venv/bin/activate

  echo "---------------------------------------------------------------------------------"
  echo "accelerate launch..."

  accelerate launch --num_cpu_threads_per_process=6 launch.py --api --listen --port 8080 --xformers --no-half-vae --no-download-sd-model --no-hashing --nowebui --skip-torch-cuda-test --skip-load-model-at-start --disable-safe-unpickle --skip-prepare-environment --skip-python-version-check --skip-install --skip-version-check
fi

cd /home/ubuntu
curl -sSL "$INSTALL_SCRIPT" | bash;

echo "---------------------------------------------------------------------------------"
echo "Set conda"
export AWS_REGION="us-west-2"
s5cmd --log=error cp "s3://aws-gcr-solutions-us-west-2/extension-for-stable-diffusion-on-aws/1.5.0-g5/conda/libcufft.so.10" /home/ubuntu/conda/lib/
s5cmd --log=error cp "s3://aws-gcr-solutions-us-west-2/extension-for-stable-diffusion-on-aws/1.5.0-g5/conda/libcurand.so.10" /home/ubuntu/conda/lib/
export LD_LIBRARY_PATH=/home/ubuntu/conda/lib:$LD_LIBRARY_PATH
export AWS_REGION=$AWS_DEFAULT_REGION
echo "---------------------------------------------------------------------------------"

cd stable-diffusion-webui
python3 -m venv venv

# chmod +x /home/ubuntu/stable-diffusion-webui/venv/bin/*

source venv/bin/activate

python -m pip install --upgrade pip
python -m pip install accelerate
python -m pip install markdown

python -m pip install onnxruntime-gpu
python -m pip install insightface==0.7.3

export TORCH_INDEX_URL="https://download.pytorch.org/whl/cu118"
export TORCH_COMMAND="pip install torch==2.0.1 torchvision==0.15.2 --extra-index-url $TORCH_INDEX_URL"
export XFORMERS_PACKAGE="xformers==0.0.20"

# if $EXTENSIONS is not empty, it will be executed
if [ -n "$EXTENSIONS" ]; then
    echo "---------------------------------------------------------------------------------"
    cd /home/ubuntu/stable-diffusion-webui/extensions/ || exit 1

    read -ra array <<< "$(echo "$EXTENSIONS" | tr "," " ")"

    for git_repo in "${array[@]}"; do
      start_at=$(date +%s)
      echo "git clone $git_repo"
      git clone "$git_repo"
      end_at=$(date +%s)
      cost=$((end_at-start_at))
      echo "git clone $git_repo: $cost seconds"
    done
fi

check_ready() {
  while true; do
    PID=$(lsof -i :8080 | awk 'NR!=1 {print $2}' | head -1)

    if [ -n "$PID" ]; then
      echo "Port 8080 is in use by PID: $PID. tar files and upload to S3"

      rm -rf /home/ubuntu/stable-diffusion-webui/extensions/stable-diffusion-aws-extension/docs
      rm -rf /home/ubuntu/stable-diffusion-webui/extensions/stable-diffusion-aws-extension/infrastructure
      rm -rf /home/ubuntu/stable-diffusion-webui/extensions/stable-diffusion-aws-extension/middleware_api
      rm -rf /home/ubuntu/stable-diffusion-webui/extensions/stable-diffusion-aws-extension/test
      rm -rf /home/ubuntu/stable-diffusion-webui/repositories/BLIP/BLIP.gif
      rm -rf /home/ubuntu/stable-diffusion-webui/repositories/generative-models/assets/
      rm -rf /home/ubuntu/stable-diffusion-webui/repositories/stable-diffusion-stability-ai/assets/

      echo "delete git..."
      find "/home/ubuntu/stable-diffusion-webui" -type d -name '.git' -exec rm -rf {} +
      find "/home/ubuntu/stable-diffusion-webui" -type d -name '.github' -exec rm -rf {} +
      find "/home/ubuntu/stable-diffusion-webui" -type f -name '.gitignore' -exec rm -rf {} +
      find "/home/ubuntu/stable-diffusion-webui" -type f -name 'README.md' -exec rm -rf {} +
      find "/home/ubuntu/stable-diffusion-webui" -type f -name 'CHANGELOG.md' -exec rm -rf {} +
      find "/home/ubuntu/stable-diffusion-webui" -type f -name 'CODE_OF_CONDUCT.md' -exec rm -rf {} +
      find "/home/ubuntu/stable-diffusion-webui" -type f -name 'LICENSE.md' -exec rm -rf {} +
      find "/home/ubuntu/stable-diffusion-webui" -type f -name 'NOTICE.md' -exec rm -rf {} +

      echo "collection big files..."
      upload_files=$(mktemp)
      big_files=$(find "/home/ubuntu/stable-diffusion-webui" -type f -size +2520k)
      for file in $big_files; do
         key=$(echo "$file" | cut -d'/' -f4-)
         echo "sync $file s3://$BUCKET_NAME/$S3_LOCATION/$key" >> "$upload_files"
      done

      echo "tar files..."
      filelist=$(mktemp)
      # shellcheck disable=SC2164
      cd /home/ubuntu/stable-diffusion-webui
      find "./" \( -type f -o -type l \) -size -2530k > "$filelist"
      tar -cf $tar_file -T "$filelist"

      echo "sync $tar_file s3://$BUCKET_NAME/$S3_LOCATION/" >> "$upload_files"
      echo "sync /home/ubuntu/conda/* s3://$BUCKET_NAME/$S3_LOCATION/conda/" >> "$upload_files"
      echo "sync /home/ubuntu/stable-diffusion-webui/models/insightface/* s3://$BUCKET_NAME/$S3_LOCATION/insightface/" >> "$upload_files"

      echo "upload files..."
      s5cmd run "$upload_files"

      break
    fi

    echo "Port 8080 is not in use, waiting for 10 seconds..."
    sleep 10
  done
}

check_ready &

echo "---------------------------------------------------------------------------------"
cd /home/ubuntu/stable-diffusion-webui
accelerate launch --num_cpu_threads_per_process=6 launch.py --api --listen --port 8080 --xformers --no-half-vae --no-download-sd-model --no-hashing --nowebui --skip-torch-cuda-test --skip-load-model-at-start --disable-safe-unpickle