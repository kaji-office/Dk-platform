#!/bin/bash
# LocalStack S3 initialization — runs on container ready
echo "Initializing LocalStack S3 buckets..."
awslocal s3 mb s3://workflow-platform-dev --region us-east-1
awslocal s3api put-bucket-versioning \
  --bucket workflow-platform-dev \
  --versioning-configuration Status=Enabled
echo "S3 bucket 'workflow-platform-dev' created."
