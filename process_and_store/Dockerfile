FROM python:3.12-slim

WORKDIR /app

COPY process_data.py mock_snowflake.sqlite /app/

RUN pip install boto3 duckdb fsspec fastapi uvicorn

CMD ["uvicorn", "process_data:app", "--host", "0.0.0.0", "--port", "7000"]
