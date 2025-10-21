import os
import boto3
from dotenv import load_dotenv
from io import StringIO

load_dotenv()

def get_s3_client():
    """Initializes and returns an S3 client."""
    endpoint_url = 'http://localhost:9000'
    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION")

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=aws_region,
    )

def upload_to_s3(df, bucket_name, file_name):
    """
    Uploads a pandas DataFrame to an S3 bucket as a CSV file.
    """
    s3_client = get_s3_client()
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)

    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=file_name,
            Body=csv_buffer.getvalue(),
            ContentType="text/csv",
        )
        print(f"Successfully uploaded {file_name} to {bucket_name}")
        return True
    except Exception as e:
        print(f"Error uploading file to S3: {e}")
        return False

if __name__ == "__main__":
    # Example usage:
    import pandas as pd
    from datetime import datetime

    # Create a dummy dataframe
    dummy_data = {
        'played_at': [datetime.now().isoformat()],
        'track_name': ['Test Track'],
        'artists': ['Test Artist'],
        'album_name': ['Test Album'],
        'track_id': ['12345'],
        'album_id': ['67890'],
        'duration_ms': [200000],
        'popularity': [80]
    }
    dummy_df = pd.DataFrame(dummy_data)
    
    bucket_name = os.getenv("S3_BUCKET_NAME")
    if bucket_name:
        file_name = f"spotify-history/test-upload-{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
        upload_to_s3(dummy_df, bucket_name, file_name)
    else:
        print("S3_BUCKET_NAME environment variable not set.")
