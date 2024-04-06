#!/usr/bin/env bash

# Build inference image and push it to private ECR repository
dockerfile=$1
image=$2
mode=$3
region=$4
tag=$5
commit_id=$6

if [ "$image" = "" ] || [ "$dockerfile" = "" ]
then
    echo "Usage: $0 <docker-file> <image-name>"
    exit 1
fi

if [ "$tag" = "" ]
then
    tag=latest
fi

# Get the account number associated with the current IAM credentials
account=$(aws sts get-caller-identity --region "$region" --query Account --output text)

if [ $? -ne 0 ]
then
    exit 255
fi

# Get the region defined in the current configuration (default to us-west-2 if none defined)
region="${region}"

if [[ $region == cn* ]]; then
    AWS_DOMAIN="amazonaws.com.cn"
else
    AWS_DOMAIN="amazonaws.com"
fi

image_name="${image}"

# If the repository doesn't exist in ECR, create it.

desc_output=$(aws ecr describe-repositories --region "$region" --repository-names ${image_name} 2>&1)

if [ $? -ne 0 ]
then
    if echo ${desc_output} | grep -q RepositoryNotFoundException
    then
        aws ecr create-repository --region "$region" --repository-name "${image_name}" > /dev/null
    else
        >&2 echo ${desc_output}
    fi
fi

#aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 763104351884.dkr.ecr.us-east-1.$AWS_DOMAIN
aws ecr get-login-password --region "$region" | docker login --username AWS --password-stdin "$account.dkr.ecr.$region.$AWS_DOMAIN"

cp ${dockerfile} .

# Build the docker image locally with the image name and then push it to ECR
# with the full name.
fullname="${account}.dkr.ecr.$region.$AWS_DOMAIN/${image_name}:${tag}"
echo "$fullname"

docker build -t ${image_name}:${tag} -f ${dockerfile} .
docker tag ${image_name}:${tag} ${fullname}
docker push ${fullname}
echo "docker push ${account}.dkr.ecr.${region}.$AWS_DOMAIN/${image_name}:${tag}"
echo "Completed"
