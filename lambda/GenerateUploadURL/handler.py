"""
GenerateUploadURLLambda
------------------------
Triggered by: API Gateway (HTTP API) - POST /upload-url
Returns:      a presigned S3 POST (url + fields) that the client uses to upload
              a file directly to the Upload Bucket. No AWS credentials are ever
              exposed to the frontend.

Environment variables required:
    UPLOAD_BUCKET_NAME -> e.g. kareem-image-upload-xxxx-us-east-1
    URL_EXPIRATION      (optional, default 300 seconds)
"""

import json
import os
import uuid
import boto3

s3_client = boto3.client('s3')

UPLOAD_BUCKET = os.environ['UPLOAD_BUCKET_NAME']
URL_EXPIRATION = int(os.environ.get('URL_EXPIRATION', '300'))
ALLOWED_CONTENT_TYPES = ('image/jpeg', 'image/png', 'image/webp')
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB cap to prevent abuse/cost surprises


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body)
    }


def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body') or '{}')
        content_type = body.get('contentType', 'image/jpeg')
        original_filename = body.get('filename', 'upload.jpg')

        if content_type not in ALLOWED_CONTENT_TYPES:
            return _response(400, {"error": f"Unsupported contentType. Allowed: {ALLOWED_CONTENT_TYPES}"})

        ext = os.path.splitext(original_filename)[1].lower() or '.jpg'
        object_key = f"uploads/{uuid.uuid4()}{ext}"

        presigned = s3_client.generate_presigned_post(
            Bucket=UPLOAD_BUCKET,
            Key=object_key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1, MAX_UPLOAD_BYTES]
            ],
            ExpiresIn=URL_EXPIRATION
        )

        return _response(200, {
            "uploadUrl": presigned['url'],
            "fields": presigned['fields'],
            "objectKey": object_key,
            "expiresIn": URL_EXPIRATION
        })

    except Exception as e:
        print(f"Error generating presigned URL: {e}")
        return _response(500, {"error": "Failed to generate upload URL"})
