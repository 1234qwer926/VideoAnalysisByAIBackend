import os
import mimetypes
import boto3
from datetime import datetime
from fastapi import UploadFile, HTTPException


class S3Service:
    # Manual overrides/fallback for reliable mimetypes regardless of OS environment
    MIME_MAP = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".mp4": "video/mp4",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp"
    }

    def __init__(self):
        self.bucket = os.getenv("S3_BUCKET_NAME")
        if not self.bucket:
            raise Exception("S3_BUCKET_NAME not set in .env")

        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        )

    # ---------------------------------------------------------
    # 1️⃣ Upload File to S3 (PRIVATE)
    # ---------------------------------------------------------
    async def upload_file(self, file: UploadFile) -> dict:
        allowed_types = [
            ".pdf", ".doc", ".docx",
            ".mp4", ".avi", ".mov", ".webm",
            ".jpg", ".jpeg", ".png", ".webp"
        ]

        if not any(file.filename.lower().endswith(ext) for ext in allowed_types):
            raise HTTPException(status_code=400, detail="Unsupported file type")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_filename = "".join(
            c if c.isalnum() or c in "._-" else "_" for c in file.filename
        )
        key = f"uploads/{timestamp}_{safe_filename}"
        ext = os.path.splitext(file.filename)[1].lower()

        try:
            file_content = await file.read()

            # Detect content-type safely
            guessed_type, _ = mimetypes.guess_type(file.filename)
            content_type = S3Service.MIME_MAP.get(ext) or file.content_type or guessed_type or "application/octet-stream"

            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=file_content,
                ContentType=content_type
            )

            return {"key": key, "filename": file.filename}

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"S3 Upload Failed: {str(e)}")

    # ---------------------------------------------------------
    # 2️⃣ Generate Pre-Signed URL (INLINE VIEW ENABLED)
    # ---------------------------------------------------------
    def get_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        try:
            # Try to guess file content type based on extension
            content_type, _ = mimetypes.guess_type(key)
            ext = os.path.splitext(key)[1].lower()
            content_type = S3Service.MIME_MAP.get(ext) or content_type or "application/octet-stream"

            # Force inline view for browsers
            params = {
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentDisposition": "inline",
                "ResponseContentType": content_type
            }

            url = self.s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params=params,
                ExpiresIn=expires_in
            )

            return url

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"URL generation failed: {str(e)}")

    # ---------------------------------------------------------
    # 3️⃣ Verify Object Exists in S3
    # ---------------------------------------------------------
    def verify_object_exists(self, key: str) -> bool:
        """
        Verify that an object exists in S3 bucket.
        Returns True if object exists, False otherwise.
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as e:
            print(f"  ⚠ S3 verification failed for key {key}: {e}")
            return False

    # ---------------------------------------------------------
    # 4️⃣ Upload File with Verification and Retry
    # ---------------------------------------------------------
    async def upload_file_with_verification(
        self,
        file: UploadFile,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> dict:
        """
        Upload file to S3 with automatic verification and retry logic.
        
        Args:
            file: The UploadFile to upload
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            dict with 'key', 'filename', and 'verified' status
            
        Raises:
            HTTPException: If upload fails after all retries
        """
        import asyncio
        
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            try:
                print(f"  [S3 Upload] Attempt {attempt}/{max_retries}...")
                
                # Perform the upload
                result = await self.upload_file(file)
                
                # Verify the upload
                if self.verify_object_exists(result["key"]):
                    print(f"  ✓ S3 upload verified (Key: {result['key']})")
                    result["verified"] = True
                    return result
                else:
                    raise Exception("Upload verification failed - object not found in S3")
                    
            except Exception as e:
                last_error = e
                print(f"  ✗ S3 upload attempt {attempt} failed: {e}")
                
                if attempt < max_retries:
                    print(f"  → Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                continue
        
        # All retries exhausted
        raise HTTPException(
            status_code=500,
            detail=f"S3 upload failed after {max_retries} attempts: {str(last_error)}"
        )
        
    # ---------------------------------------------------------
    # 5️⃣ Download File
    # ---------------------------------------------------------
    def download_file(self, key: str, dest_path: str):
        try:
            self.s3_client.download_file(self.bucket, key, dest_path)
        except Exception as e:
            print(f"  ⚠ S3 download failed for key {key}: {e}")
            raise
