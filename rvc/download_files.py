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

# asset 폴더 다운로드
s3_folder = 'assets/'  # 다운로드할 S3 폴더 경로
local_folder = '/local-directory/'  # 로컬에 저장할 폴더 경로

# S3 폴더 내 객체 목록 가져오기
objects = s3.list_objects_v2(Bucket=bucket_name, Prefix=s3_folder)

# 폴더 생성
if not os.path.exists(local_folder):
    os.makedirs(local_folder)

# S3 폴더 내 객체들 다운로드
for obj in objects.get('Contents', []):
    s3_object_key = obj['Key']
    local_file_path = os.path.join(local_folder, os.path.basename(s3_object_key))

    s3.download_file(bucket_name, s3_object_key, local_file_path)
    print(f"Downloaded: {s3_object_key} to {local_file_path}")