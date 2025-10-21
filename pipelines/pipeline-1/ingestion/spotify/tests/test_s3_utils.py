import pytest
from unittest.mock import MagicMock
import pandas as pd
from s3_utils import upload_to_s3

@pytest.fixture
def mock_s3_client(mocker):
    """Fixture to create a mock S3 client."""
    mock_client = MagicMock()
    mocker.patch("s3_utils.get_s3_client", return_value=mock_client)
    return mock_client

def test_upload_to_s3(mock_s3_client):
    """Test uploading a DataFrame to S3."""
    dummy_df = pd.DataFrame({"col1": [1, 2], "col2": ["A", "B"]})
    bucket_name = "test-bucket"
    file_name = "test-file.csv"

    result = upload_to_s3(dummy_df, bucket_name, file_name)

    assert result is True
    mock_s3_client.put_object.assert_called_once()
    call_args = mock_s3_client.put_object.call_args[1]
    assert call_args["Bucket"] == bucket_name
    assert call_args["Key"] == file_name
    assert "col1,col2" in call_args["Body"]
