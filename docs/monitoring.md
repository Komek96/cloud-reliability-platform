# Local Prometheus Monitoring

## Overview

The Cloud Reliability Platform exposes Prometheus metrics
through the FastAPI `/metrics` endpoint.

Prometheus runs locally in Docker Compose and scrapes the API
every 15 seconds. This setup uses no AWS infrastructure.

The monitoring deployment is defined in:

- `compose.monitoring.yaml`
- `monitoring/prometheus.yml`

The application instrumentation is implemented in:

- `app/metrics.py`
- `app/main.py`

## Architecture

FastAPI exposes HTTP request counters and duration histograms.

Prometheus periodically fetches:

`http://127.0.0.1:8080/metrics`

In the Codespaces environment, FastAPI and DynamoDB share a
Docker network namespace due to prior connectivity problems.

Prometheus joins that same namespace to access the API over
loopback. Its web interface listens on `127.0.0.1:9090` inside
the shared namespace and is not published to the Codespace host.

Prometheus uses a separate Docker named volume:

`cloud-reliability-platform_prometheus-data`

DynamoDB retains its own persistent named volume:

`cloud-reliability-platform_dynamodb-data`

Never remove the DynamoDB data volume.

## Metrics

### Request counter

`http_requests_total`

Labels:

- `method`
- `route`
- `status_code`

### Request duration histogram

`http_request_duration_seconds`

Labels:

- `method`
- `route`

Duration is measured in seconds.

Route labels use templates such as `/events/{event_id}`,
rather than actual event IDs. This prevents unbounded
metric-cardinality growth from unique identifiers.

Requests to `/metrics` are excluded from the application's
HTTP request counters and histograms.

### Metric lifecycle

Application metrics are held in process memory and reset
when the FastAPI process restarts.

Prometheus stores scraped samples in its persistent volume.
Historical samples can survive container replacement while
the current API counters begin again from zero.

## Starting Prometheus

Use all three Compose files:

```bash
docker compose \
  -f compose.yaml \
  -f compose.codespaces.yaml \
  -f compose.monitoring.yaml \
  up -d --no-build --no-deps prometheus
```

The Prometheus container depends on the existing shared
network namespace. Start the API and DynamoDB stack first.

Do not use `docker compose down -v` or Docker-wide pruning.

## Inspecting Services

```bash
docker compose \
  -f compose.yaml \
  -f compose.codespaces.yaml \
  -f compose.monitoring.yaml \
  ps -a
```

Prometheus logs can be inspected with:

```bash
docker compose \
  -f compose.yaml \
  -f compose.codespaces.yaml \
  -f compose.monitoring.yaml \
  logs --tail 100 prometheus
```

## PromQL Queries

### Scrape target availability

```promql
up{job="cloud-reliability-api"}
```

A value of `1` indicates a successful latest scrape.
A value of `0` indicates a failed latest scrape.

### Request rate by status code

```promql
sum by (status_code) (
  rate(http_requests_total{job="cloud-reliability-api"}[5m])
)
```

### 95th percentile request latency

```promql
histogram_quantile(
  0.95,
  sum by (le) (
    rate(http_request_duration_seconds_bucket{
      job="cloud-reliability-api"
    }[5m])
  )
)
```

These rate-based queries require enough scraped samples
within the selected time window.

## Live Verification — November 19, 2026

The local Prometheus container was started without recreating
the existing FastAPI or DynamoDB containers.

Verified observations:

- Prometheus version: `v3.13.5`
- Scrape interval: 15 seconds
- Scrape target: `http://127.0.0.1:8080/metrics`
- Scrape target health: `up`
- Scrape error: empty
- `up{job="cloud-reliability-api"}` returned `1`
- HTTP 200 `/health` counter observed at `60`
- Separate persistent monitoring volume mounted
- Original application container preserved
- Original DynamoDB container preserved
- Existing DynamoDB named volume preserved

The observed counter includes earlier API requests and
health-check traffic, not just requests generated during
the Prometheus startup verification.

## Operational Limitations

This is a local development monitoring environment,
not a production monitoring deployment.

Current limitations include:

- Monitoring runs only while the Codespace is available.
- Prometheus shares the database's network namespace.
- The Prometheus UI is not exposed to the host.
- No Grafana dashboard is configured yet.
- No alert rules or alert delivery are configured yet.
- API metric counters reset when the API process restarts.

Future improvements include Grafana dashboards, local
alerting, and investigation of shorter DynamoDB timeouts.
