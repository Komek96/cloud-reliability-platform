import os

import boto3
from botocore.config import Config


def get_table():
    """Return the configured DynamoDB events table."""
    endpoint = os.getenv("DYNAMODB_ENDPOINT_URL")

    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url=endpoint,
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        config=Config(
            connect_timeout=3,
            read_timeout=5,
            retries={"max_attempts": 1},
        ),
    )

    return dynamodb.Table(
        os.getenv(
            "DYNAMODB_TABLE",
            "cloud_reliability_events",
        )
    )
