# DynamoDB Fault-Injection and Recovery Test

## Objective

Demonstrate graceful API degradation during a real database
outage, followed by database recovery and verification of
persistent event data.

## Environment

- Application: FastAPI running in Docker Compose
- Database: DynamoDB Local
- Storage: Persistent Docker named volume
- Execution environment: GitHub Codespaces
- Cloud infrastructure: None
- AWS credentials: Not required

## Fault-Injection Method

The running DynamoDB container was temporarily paused using
`docker pause`, then restored using `docker unpause`.

The FastAPI application remained running throughout the test.

The database container was paused rather than stopped because
the Codespaces Compose configuration uses a shared network
namespace for application and database communication.

## Observed Results

| Test | Expected | Observed | Result |
|---|---|---|---|
| API health before outage | HTTP 200 | HTTP 200 | PASS |
| Historical event before outage | HTTP 200 | HTTP 200 | PASS |
| API health during outage | HTTP 200 | HTTP 200 | PASS |
| Event lookup during outage | HTTP 503 | HTTP 503 | PASS |
| Safe error message | No internal details | No internal details | PASS |
| Event lookup after recovery | HTTP 200 | HTTP 200 | PASS |
| Persistent data after recovery | Event preserved | Event preserved | PASS |

During the outage, the database-dependent request returned:

```json
{
  "detail": "Event storage temporarily unavailable"
}
```

## Persistence Verification

The following event was retrieved successfully before the
outage and after recovery:

- Event ID: `181d7d10-a58b-4e3a-a88c-9ca754aebf01`
- Event type: `full_stack_test`
- Message: `Docker Compose integration verified`

The persistent Docker volume remained present:

`cloud-reliability-platform_dynamodb-data`

## Engineering Findings

1. Database-related failures can be translated into HTTP 503
   responses without exposing internal error information.
2. The `/health` endpoint continues responding during a database
   outage because it represents application liveness.
3. Persistent event records remain accessible after the database
   process resumes.
4. Separating liveness from database readiness would provide
   more useful operational monitoring.

## Live Readiness Fault-Injection Verification

### Objective

Verify that application liveness and database readiness provide
different operational signals when DynamoDB becomes unavailable.

### Procedure

1. Confirm that both endpoints return HTTP 200 with DynamoDB running.
2. Verify the historical event is retrievable.
3. Temporarily pause the DynamoDB Local container.
4. Request `/health` and `/ready` while the database is paused.
5. Resume DynamoDB using `docker unpause`.
6. Verify both endpoints recover and the event remains available.

### Observed Results

| Database state | `/health` | `/ready` | Result |
|---|---|---|---|
| Operational | HTTP 200 | HTTP 200 | PASS |
| Paused | HTTP 200 | HTTP 503 | PASS |
| Restored | HTTP 200 | HTTP 200 | PASS |

The readiness endpoint returned the following response during
the database outage:

```json
{
  "detail": "Event storage temporarily unavailable"
}
```

The API remained alive throughout the simulated outage.

After restoring DynamoDB, the existing event with ID
`181d7d10-a58b-4e3a-a88c-9ca754aebf01`
was successfully retrieved.

### Operational Interpretation

- `/health` represents application liveness.
- `/ready` checks whether DynamoDB can serve a read request.
- HTTP 503 indicates that database-dependent functionality
  is temporarily unavailable.
- The API can remain running while its readiness check fails.
- The persistent event record survived the database interruption.

### Limitations

This was a manually executed local experiment.

The readiness probe tests DynamoDB read connectivity but does
not independently verify write capability.

The experiment does not establish automatic failover,
production availability, or AWS deployment.

## Scope and Limitations

This was a manually executed local fault-injection experiment.

It does not demonstrate automatic failover, zero downtime,
production high availability, or an AWS deployment.

The experiment validated a database-dependent GET request.
It did not independently exercise every API operation during
the live outage.

## Next Improvements

- Add structured operational logging and request metrics.
- Introduce monitoring dashboards and alerting.
- Automate repeatable container-level fault-injection tests.
- Refine database error classification and recovery behavior.

## Structured Logging and Correlated Outage (2026-11-19)

### Objective

Verify that structured JSON application logs correlate an
HTTP failure with the underlying database dependency failure
during a real local Docker Compose outage.

### Environment

- FastAPI application running inside Docker Compose.
- DynamoDB Local with an existing persistent named volume.
- Structured JSON logging introduced in commit `fd8b2ad`.
- All infrastructure remained local; no AWS resources used.

### Fault injection

The running DynamoDB Local container was paused using
`docker pause`, making database requests time out while
leaving the API process running.

An EXIT trap was installed to attempt automatic database
restoration if the test failed.

### Observed results

| Check | Observation |
| --- | --- |
| Healthy baseline `/health` | HTTP 200 |
| Healthy baseline `/ready` | HTTP 200 |
| `/health` during outage | HTTP 200 |
| `/ready` during outage | HTTP 503 |
| Client error response | `Event storage temporarily unavailable` |
| Database exception type | `ReadTimeoutError` |
| Failed request duration | 10,034.74 ms |
| Correlated structured log events | 2 |
| `/ready` after restoration | HTTP 200 |
| Historical DynamoDB event | Successfully retrieved |

### Request correlation

The HTTP 503 response included this `X-Request-ID`:

`53b0135a65774d15bb69b611c9722575`

Two structured JSON log records carried that same ID:

1. `database_failure`: ERROR, `/ready`, HTTP 503,
   `ReadTimeoutError`.
2. `http_request`: INFO, `/ready`, HTTP 503,
   duration 10,034.74 ms.

Both log records were observed in the application's
Docker logs on 2026-11-19 at approximately 23:53:28 UTC.

The inspected structured records did not expose the
internal DynamoDB endpoint.

### Recovery and persistence

After `docker unpause`, `/health` and `/ready` both
returned HTTP 200. The previously stored event
`181d7d10-a58b-4e3a-a88c-9ca754aebf01`
was successfully retrieved.

The database's persistent named volume was preserved.
No AWS infrastructure was provisioned.

### Operational interpretation

Liveness remained healthy while readiness failed,
demonstrating that the application process was running
but its database dependency was unavailable.

The correlated JSON events made it possible to connect
the failed HTTP request to a specific database error.

The approximately 10-second failed-request duration
also identifies an area for future improvement:
reviewing database-client timeout settings to reduce
the time needed to detect dependency failures.

This experiment validates local failure logging and
manual recovery. It does not establish automatic
application recovery, production alerting, or
production-grade availability.
