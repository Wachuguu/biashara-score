"""
S3 Storage Client Wrapper
Provides local filesystem fallback when MOCK_AWS=true.
"""
import os
from typing import Optional

MOCK_MODE = os.getenv("MOCK_AWS", "true").lower() == "true"


class S3Client:
    def __init__(self):
        self.mock = MOCK_MODE
        if not self.mock:
            import boto3
            self.s3 = boto3.client("s3")
            self.bucket_name = os.getenv("S3_STATEMENTS_BUCKET", "biashara-statements-dev")

    def get_statement_content(self, s3_key: str) -> str:
        if self.mock:
            # Fall back to local sample file
            sample_path = os.getenv("LOCAL_SAMPLE_DATA_PATH", "sample-data/mpesa_statement.csv")
            if os.path.exists(sample_path):
                with open(sample_path, "r", encoding="utf-8") as f:
                    return f.read()
            return ""
        
        response = self.s3.get_object(Bucket=self.bucket_name, Key=s3_key)
        return response["Body"].read().decode("utf-8")


s3_client = S3Client()
