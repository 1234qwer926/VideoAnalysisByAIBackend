import boto3
from app.core.config import settings

def get_s3_client():
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )

def generate_presigned_upload_url(key: str, content_type: str = "video/webm", expires: int = 3600) -> str:
    """Pre-signed PUT URL — browser uploads video directly to S3."""
    s3 = get_s3_client()
    return s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.S3_BUCKET_NAME,
            "Key": key,
            "ContentType": content_type
        },
        ExpiresIn=expires,
    )

def generate_presigned_view_url(key: str, expires: int = 3600) -> str:
    """Pre-signed GET URL — admin plays back video in browser."""
    s3 = get_s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.S3_BUCKET_NAME,
            "Key": key
        },
        ExpiresIn=expires,
    )

def download_file(key: str, dest_path: str):
    """Download file from S3 to local path."""
    s3 = get_s3_client()
    s3.download_file(settings.S3_BUCKET_NAME, key, dest_path)