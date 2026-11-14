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

## Scope and Limitations

This was a manually executed local fault-injection experiment.

It does not demonstrate automatic failover, zero downtime,
production high availability, or an AWS deployment.

The experiment validated a database-dependent GET request.
It did not independently exercise every API operation during
the live outage.

## Next Improvements

- Add a database-aware `/ready` endpoint.
- Test readiness responses under healthy and failed conditions.
- Add automated reliability checks to continuous integration.
