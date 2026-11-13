import os
import time
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import (
    ConnectTimeoutError,
    ConnectionClosedError,
    EndpointConnectionError,
    ReadTimeoutError,
)


def main():
    endpoint = os.environ["DYNAMODB_ENDPOINT_URL"]
    parsed = urlparse(endpoint)

    # This initializer is for local Compose only.
    # Prevent accidentally creating resources in AWS.
    if (
        parsed.scheme != "http"
        or parsed.hostname not in ("dynamodb", "127.0.0.1")
        or parsed.port != 8000
    ):
        raise RuntimeError(
            "Database initializer requires local "
            "DynamoDB at http://dynamodb:8000"
        )

    client = boto3.client(
        "dynamodb",
        endpoint_url=endpoint,
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        config=Config(
            connect_timeout=3,
            read_timeout=5,
            retries={"max_attempts": 1},
        ),
    )

    table_name = os.getenv(
        "DYNAMODB_TABLE",
        "cloud_reliability_events",
    )

    print("Waiting for DynamoDB Local...", flush=True)

    transient_errors = (
        ConnectTimeoutError,
        ConnectionClosedError,
        EndpointConnectionError,
        ReadTimeoutError,
    )

    for attempt in range(1, 31):
        try:
            client.list_tables()
            print("PASS: DynamoDB is ready.", flush=True)
            break
        except transient_errors as error:
            print(
                f"Attempt {attempt}/30: "
                f"{type(error).__name__}",
                flush=True,
            )

            if attempt == 30:
                raise

            time.sleep(1)

    try:
        client.describe_table(TableName=table_name)
        print("Events table already exists.", flush=True)

    except client.exceptions.ResourceNotFoundException:
        print("Creating events table...", flush=True)

        client.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    "AttributeName": "event_id",
                    "KeyType": "HASH",
                }
            ],
            AttributeDefinitions=[
                {
                    "AttributeName": "event_id",
                    "AttributeType": "S",
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )

    client.get_waiter("table_exists").wait(
        TableName=table_name,
        WaiterConfig={
            "Delay": 1,
            "MaxAttempts": 30,
        },
    )

    print(
        "PASS: Events table initialized.",
        flush=True,
    )


if __name__ == "__main__":
    main()
