FROM python:3.12-slim

WORKDIR /app

COPY download_upload.py /app/

RUN pip install requests boto3

CMD ["python", "download_upload.py"]
