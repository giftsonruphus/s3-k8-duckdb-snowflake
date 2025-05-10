import boto3
import tempfile
import duckdb
import sqlite3
import os
import json
import asyncio
from fastapi import FastAPI
from concurrent.futures import ThreadPoolExecutor


app = FastAPI()

executor = ThreadPoolExecutor(max_workers=1)

def download_from_s3(bucket_name, object_name, aws_access_key_id, aws_secret_access_key, region) -> str:
    s3 = boto3.client("s3",
                      aws_access_key_id=aws_access_key_id,
                      aws_secret_access_key=aws_secret_access_key,
                      region_name=region)
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    s3.download_file(bucket_name, object_name, temp_file.name)
    temp_file.close()
    return temp_file.name

def process_and_store_to_snowflake(duckdb_con, sqlite_con, filename):

    offset = 0
    chunk_size = 10

    while True:
        chunk_df = duckdb_con.execute(
            f"select diff, date from read_json('{filename}') LIMIT {chunk_size} OFFSET {offset}"
        ).fetchdf()

        if chunk_df.empty:
            break

        chunk_df.to_sql('processed_data', sqlite_con, if_exists='append', index=False)

        offset += chunk_size
    
    sqlite_con.commit()
    sqlite_con.close()
    duckdb_con.close()

def sqs_polling_loop(queue_url, aws_access_key_id, aws_secret_access_key, region, duckdb_con, sqlite_con):
    sqs = boto3.client("sqs",
                      aws_access_key_id=aws_access_key_id,
                      aws_secret_access_key=aws_secret_access_key,
                      region_name=region)
    sqs_queue_url = queue_url
    while True:
        response = sqs.receive_message(
            QueueUrl = sqs_queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            VisibilityTimeout=60
        )
        messages = response.get("Messages", [])

        if not messages:
            continue

        for message in messages:
            body = json.loads(message['Body'])
            record = body["Records"][0]
            bucket = record['s3']['bucket']['name']
            object = record['s3']['object']['key']

            downloaded_file_from_s3 = download_from_s3(bucket, object, aws_access_key_id, aws_secret_access_key)

            process_and_store_to_snowflake(duckdb_con, sqlite_con, downloaded_file_from_s3)

            os.remove(downloaded_file_from_s3)

            sqs.delete_message(
                QueueUrl = sqs_queue_url,
                ReceiptHandle=message['ReceiptHandle']
            )

def get_diff_date_data(limit, offset):
    connection = sqlite3.connect("mock_snowflake.sqlite")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    query = """
        SELECT diff, date
        FROM processed_data
        LIMIT ? OFFSET ?
    """
    cursor.execute(query, (limit, offset))
    rows = cursor.fetchall()
    connection.close()

    # Convert rows to list of dictionaries
    result = [dict(row) for row in rows]
    return result

@app.on_event("startup")
async def poll_sqs_queue():

    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    region = os.getenv("AWS_REGION", "us-east-1")
    sqs_queue = os.getenv("SQS_QUEUE_URL")
    
    duckdb_con = duckdb.connect()
    sqlite_con = sqlite3.connect("mock_snowflake.sqlite")

    loop = asyncio.get_event_loop()
    loop.run_in_executor(executor, lambda: sqs_polling_loop(sqs_queue, aws_access_key_id, aws_secret_access_key, region, duckdb_con, sqlite_con))


@app.get("/health")
def health():
    return {"message": "Processor microservice running"}

@app.get("/diff/{ticker}")
def diff_high_low():
    data = get_diff_date_data(limit=50, offset=0)
    return {"data": data}

