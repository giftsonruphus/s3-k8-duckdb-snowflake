import os
import requests
import boto3
from botocore.exceptions import NoCredentialsError
import json


def download_data(url, params):
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()['data']


def upload_to_s3(data, bucket_name, object_name, aws_access_key_id, aws_secret_access_key, region):
    s3 = boto3.client('s3',
                      aws_access_key_id=aws_access_key_id,
                      aws_secret_access_key=aws_secret_access_key,
                      region_name=region)
    try:
        s3.put_object(Bucket=bucket_name,
                      Key=object_name,
                      Body=data,
                      ContentType='application/json')
        print("Upload successful")
        return True
    except NoCredentialsError as exc:
        print("Credentials not available")
        return False


if __name__ == "__main__":
    url = os.getenv("DATA_URL")
    api_key = os.getenv("API_KEY")

    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    region = os.getenv("AWS_REGION", "us-east-1")
    bucket_name = os.getenv("S3_BUCKET_NAME")
    prefix = os.getenv("S3_OBJECT_PREFIX")
    ticker = os.getenv("TICKER")
    object_name = f"{prefix}/{ticker}.json"

    data = download_data(url, params={'access_key': api_key, 'symbols': ticker})
    upload_to_s3(json.dumps(data), bucket_name, object_name, aws_access_key_id, aws_secret_access_key, region)