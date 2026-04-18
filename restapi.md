# Reporting In REST API Reference

Reporting In is a status dashboard application for tracking job statuses across groups. This document describes the REST API provided by the Reporting In backend server.

## Base URL

By default, the server runs at `http://127.0.0.1:7828`. Configure via `HOST` and `PORT` environment variables.

## Content Type

- **Requests:** `application/json`
- **Responses:** `application/json`

## Authentication

No authentication is currently required for API endpoints.

---

## Endpoints

### Health

#### GET /health

Returns an overall health summary across all groups.

**Response:**

```json
{
  "status": "healthy",
  "total_jobs": 10,
  "healthy": 8,
  "unhealthy": 1,
  "in_progress": 1,
  "by_status": {
    "success": 8,
    "error": 1,
    "progress": 1,
    "timeout": 0,
    "stale": 0
  }
}
```

**Status Values:**
- `healthy` - All jobs are successful
- `unhealthy` - Any jobs have error, timeout, or stale status
- `in_progress` - Jobs are running (no errors)
- `empty` - No jobs exist

---

### Status Submission

#### POST /status

Submit or update a job status. Creates the group and job if they don't exist.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `group` | string | Yes | Group name (max 255 chars) |
| `job` | string | Yes | Job name (max 255 chars) |
| `status` | string | Yes | One of: `success`, `error`, `progress`, `timeout`, `stale` |
| `message` | string | No | Optional message (max 4096 chars) |

**Example Request:**

```json
{
  "group": "nightly-builds",
  "job": "backend-tests",
  "status": "success",
  "message": "All 42 tests passed"
}
```

**Response (201 Created):**

```json
{
  "success": true,
  "job": {
    "id": 1,
    "group_id": 1,
    "group_name": "nightly-builds",
    "name": "backend-tests",
    "status": "success",
    "message": "All 42 tests passed",
    "updated_at": "2025-01-17T12:00:00Z",
    "created_at": "2025-01-17T10:00:00Z"
  }
}
```

**Errors:**
- `400 Bad Request` - Missing required fields, invalid status, or length exceeded
- `500 Internal Server Error` - Database error

---

### Groups

#### GET /groups

List all groups with health summary information.

**Response:**

```json
{
  "groups": [
    {
      "id": 1,
      "name": "nightly-builds",
      "progress_timeout_minutes": null,
      "staleness_timeout_hours": null,
      "created_at": "2025-01-17T10:00:00Z",
      "job_count": 5,
      "health": "healthy",
      "status_counts": {
        "success": 5,
        "error": 0,
        "progress": 0,
        "timeout": 0,
        "stale": 0
      }
    }
  ]
}
```

---

#### GET /groups/{name}/jobs

Get all jobs within a specific group.

**Path Parameters:**
- `name` - Group name

**Response:**

```json
{
  "group": {
    "id": 1,
    "name": "nightly-builds",
    "progress_timeout_minutes": null,
    "staleness_timeout_hours": null,
    "created_at": "2025-01-17T10:00:00Z"
  },
  "jobs": [
    {
      "id": 1,
      "group_id": 1,
      "group_name": "nightly-builds",
      "name": "backend-tests",
      "status": "success",
      "message": "All 42 tests passed",
      "updated_at": "2025-01-17T12:00:00Z",
      "created_at": "2025-01-17T10:00:00Z"
    }
  ]
}
```

**Errors:**
- `404 Not Found` - Group does not exist

---

### Configuration

#### GET /config

Retrieve global configuration settings.

**Response:**

```json
{
  "progress_timeout_minutes": 5,
  "staleness_timeout_hours": 24
}
```

---

#### PUT /config

Update global configuration settings.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `progress_timeout_minutes` | integer | No | Minutes before a "progress" job becomes "timeout" |
| `staleness_timeout_hours` | integer | No | Hours before a "success" job becomes "stale" |

**Example Request:**

```json
{
  "progress_timeout_minutes": 10,
  "staleness_timeout_hours": 48
}
```

**Response:**

```json
{
  "progress_timeout_minutes": 10,
  "staleness_timeout_hours": 48
}
```

**Errors:**
- `400 Bad Request` - Invalid values (must be positive integers)

---

#### GET /groups/{name}/config

Get group-specific configuration overrides.

**Path Parameters:**
- `name` - Group name

**Response:**

```json
{
  "group": "nightly-builds",
  "progress_timeout_minutes": null,
  "staleness_timeout_hours": 48,
  "effective_progress_timeout_minutes": 5,
  "effective_staleness_timeout_hours": 48
}
```

- `null` values indicate the group uses global defaults
- `effective_*` fields show the actual timeout values in use

**Errors:**
- `404 Not Found` - Group does not exist

---

#### PUT /groups/{name}/config

Update group-specific configuration overrides.

**Path Parameters:**
- `name` - Group name

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `progress_timeout_minutes` | integer or null | No | Override for progress timeout, or null to use global |
| `staleness_timeout_hours` | integer or null | No | Override for staleness timeout, or null to use global |

**Example Request:**

```json
{
  "staleness_timeout_hours": 72
}
```

**Response:**

```json
{
  "group": "nightly-builds",
  "progress_timeout_minutes": null,
  "staleness_timeout_hours": 72,
  "effective_progress_timeout_minutes": 5,
  "effective_staleness_timeout_hours": 72
}
```

**Errors:**
- `400 Bad Request` - Invalid values
- `404 Not Found` - Group does not exist

---

## Job Status Values

| Status | Description |
|--------|-------------|
| `success` | Job completed successfully |
| `error` | Job failed with an error |
| `progress` | Job is currently running |
| `timeout` | Progress job exceeded the progress timeout (automatic) |
| `stale` | Success job exceeded the staleness timeout (automatic) |

---

## Background Timeout Checker

A background process runs every 60 seconds to automatically update job statuses:

- Jobs with `progress` status are marked as `timeout` if they exceed `progress_timeout_minutes`
- Jobs with `success` status are marked as `stale` if they exceed `staleness_timeout_hours`

Group-specific timeout overrides take precedence over global settings.

---

## WebSocket Events

The server uses Socket.IO for real-time updates. Connect to the same host/port.

| Event | Description | Payload |
|-------|-------------|---------|
| `group_created` | New group was created | `{ "group": { ... } }` |
| `status_update` | Job status was updated | `{ "job": { ... } }` |
| `health_update` | Signal to refresh health data | `{}` |

---

## Input Limits

| Field | Maximum Length |
|-------|----------------|
| Group name | 255 characters |
| Job name | 255 characters |
| Message | 4096 characters |
| Request body | 1 MB |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///reportingin.db` | SQLAlchemy database connection URL |
| `SECRET_KEY` | (dev key) | Flask secret key for sessions |
| `DEBUG` | `false` | Enable Flask debug mode |
| `HOST` | `127.0.0.1` | Server bind address |
| `PORT` | `5000` | Server port |

---

## CLI Client

The `reportingin` command-line tool provides convenient access to this API:

```bash
# Submit a status
reportingin submit --group nightly-builds --job backend-tests --status success --message "All tests passed"

# Check health
reportingin health

# List groups
reportingin groups

# Get group jobs
reportingin jobs nightly-builds

# Get or update global configuration
reportingin config                          # View current config
reportingin config --progress-timeout 10    # Update progress timeout
reportingin config --staleness-timeout 48   # Update staleness timeout

# Use JSON output
reportingin health --json
reportingin groups --json
reportingin jobs nightly-builds --json

# Connect to a different server
reportingin --url http://myserver:7828 health
```

See `reportingin --help` for full usage information.
