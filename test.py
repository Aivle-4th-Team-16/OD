import boto3
from dotenv import load_dotenv
import os

load_dotenv()

# AWS 계정 및 인증 정보 설정
s3 = boto3.client('s3',
                  aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                  aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                  region_name=os.getenv("AWS_REGION"))

# S3에서 모델 파일 다운로드
bucket_name = 'bigproject-bucket'
response = s3.list_objects_v2(Bucket=bucket_name)
print(response)
