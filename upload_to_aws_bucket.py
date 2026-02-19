import boto3
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize the S3 client
s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)

def upload_to_s3(file_name, bucket, object_name=None):
    if object_name is None:
        object_name = file_name
    
    try:
        s3.upload_file(file_name, bucket, object_name)
        print(f"✅ {file_name} uploaded to {bucket}")
    except Exception as e:
        print(f"❌ Error: {e}")

# Usage
upload_to_s3('sample_centroids.csv', os.getenv('AWS_S3_BUCKET'))