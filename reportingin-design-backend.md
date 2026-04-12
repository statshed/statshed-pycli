# Reporting In Backend Design Document

A Flask-based backend providing REST API and WebSocket services for the Reporting In status dashboard.

## Overview

The backend is the central service that:
- Stores job status data in SQLite via SQLAlchemy
- Provides REST API endpoints consumed by the frontend and CLI
- Pushes real-time updates via WebSocket (Socket.IO)
- Runs background tasks for timeout/staleness detection

```
backend/
├── app.py              # Flask application factory and routes
├── models.py           # SQLAlchemy models (Group, Job, Config)
├── config.py           # Application configuration
├── background.py       # Background task for timeout checking
└── requirements.txt    # Python dependencies
```

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Web Framework | Flask | REST API and request handling |
| ORM | SQLAlchemy | Database abstraction |
| Database | SQLite | Persistent storage |
| WebSocket | Flask-SocketIO | Real-time push updates |
| Background Tasks | APScheduler or threading | Periodic timeout checks |
| Linting | Ruff | Code formatting and linting |

## Database Schema

### Groups Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Auto-increment ID |
| name | TEXT | UNIQUE, NOT NULL | Group identifier (max 255 chars) |
| progress_timeout_minutes | INTEGER | NULLABLE | Override for progress timeout |
| staleness_timeout_hours | INTEGER | NULLABLE | Override for staleness timeout |
| created_at | DATETIME | NOT NULL | Timestamp when group was created |

### Jobs Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Auto-increment ID |
| group_id | INTEGER | FOREIGN KEY (groups.id) | Parent group reference |
| name | TEXT | NOT NULL | Job name (unique within group) |
| status | TEXT | NOT NULL | success, error, progress, timeout, stale |
| message | TEXT | NULLABLE | Optional status message (max 4096 chars) |
| updated_at | DATETIME | NOT NULL | Last status update time |
| created_at | DATETIME | NOT NULL | Timestamp when job was first created |

**Composite Unique Constraint:** (group_id, name)

### Config Table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| key | TEXT | PRIMARY KEY | Configuration key name |
| value | TEXT | NOT NULL | JSON-encoded configuration value |

**Default Config Values:**
- `progress_timeout_minutes`: 5
- `staleness_timeout_hours`: 24

## REST API Endpoints

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Overall health summary across all jobs |

### Status Submission

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/status` | Submit or update a job status (creates group/job if needed) |

### Groups

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/groups` | List all groups with health summary |
| GET | `/groups/<name>/jobs` | Get all jobs in a specific group |

### Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/config` | Get global configuration |
| PUT | `/config` | Update global configuration |
| GET | `/groups/<name>/config` | Get group-specific config overrides |
| PUT | `/groups/<name>/config` | Update group-specific config overrides |

## WebSocket Events

| Event | Direction | Trigger | Payload |
|-------|-----------|---------|---------|
| `status_update` | Server → Client | Job status changes | `{ "job": Job }` |
| `group_created` | Server → Client | New group created | `{ "group": Group }` |
| `health_update` | Server → Client | Background task updates jobs | `{}` |

## Background Task: Timeout Checker

Runs every 60 seconds to:

1. **Progress Timeout**: Jobs with `progress` status exceeding `progress_timeout_minutes` are marked as `timeout`
2. **Staleness Timeout**: Jobs with `success` status exceeding `staleness_timeout_hours` are marked as `stale`

Group-specific overrides take precedence over global settings.

## Input Validation

| Field | Validation |
|-------|------------|
| Group name | Required, max 255 characters |
| Job name | Required, max 255 characters |
| Status | Required, one of: success, error, progress, timeout, stale |
| Message | Optional, max 4096 characters |
| Timeout values | Must be positive integers |

---

## Implementation Phases

### Phase 1: Project Setup

- [ ] Create `backend/` directory structure
- [ ] Initialize Python project with `uv`
- [ ] Add dependencies (Flask, SQLAlchemy, Flask-SocketIO, etc.)
- [ ] Create `config.py` with environment variable handling
- [ ] Set up Ruff for linting and formatting
- [ ] Create Flask application factory in `app.py`

### Phase 2: Database Layer

- [ ] Define SQLAlchemy `Group` model
- [ ] Define SQLAlchemy `Job` model with foreign key to Group
- [ ] Define SQLAlchemy `Config` model for key-value storage
- [ ] Implement `to_dict()` methods on all models for JSON serialization
- [ ] Create database initialization function
- [ ] Implement helper functions for config get/set with defaults

### Phase 3: Core REST API - Health & Status

- [ ] Implement `GET /health` endpoint
  - [ ] Query all jobs and calculate status counts
  - [ ] Return overall health status (healthy/unhealthy/in_progress/empty)
- [ ] Implement `POST /status` endpoint
  - [ ] Validate request body (group, job, status required)
  - [ ] Validate field lengths and status values
  - [ ] Create group if it doesn't exist
  - [ ] Create or update job record
  - [ ] Return created/updated job data

### Phase 4: Core REST API - Groups

- [ ] Implement `GET /groups` endpoint
  - [ ] Return all groups with job counts
  - [ ] Include per-group health status
  - [ ] Include per-group status counts
- [ ] Implement `GET /groups/<name>/jobs` endpoint
  - [ ] Validate group exists (404 if not)
  - [ ] Return group details and all jobs

### Phase 5: Core REST API - Configuration

- [ ] Implement `GET /config` endpoint
  - [ ] Return global timeout settings with defaults
- [ ] Implement `PUT /config` endpoint
  - [ ] Validate values are positive integers
  - [ ] Update config values in database
- [ ] Implement `GET /groups/<name>/config` endpoint
  - [ ] Return group-specific overrides
  - [ ] Calculate effective values (group override or global fallback)
- [ ] Implement `PUT /groups/<name>/config` endpoint
  - [ ] Allow setting overrides to null to revert to global
  - [ ] Validate values when provided

### Phase 6: WebSocket Integration

- [ ] Initialize Flask-SocketIO with the Flask app
- [ ] Emit `status_update` event when job status changes via POST /status
- [ ] Emit `group_created` event when new group is created
- [ ] Configure CORS for WebSocket connections
- [ ] Test WebSocket connection and event delivery

### Phase 7: Background Timeout Checker

- [ ] Create background task function for timeout checking
- [ ] Query jobs with `progress` status exceeding timeout threshold
- [ ] Mark expired progress jobs as `timeout`
- [ ] Query jobs with `success` status exceeding staleness threshold
- [ ] Mark stale jobs as `stale`
- [ ] Respect group-specific timeout overrides
- [ ] Emit `health_update` WebSocket event when jobs are updated
- [ ] Schedule task to run every 60 seconds
- [ ] Ensure thread safety with database sessions

### Phase 8: Error Handling & Edge Cases

- [ ] Add consistent error response format
- [ ] Handle database connection errors gracefully
- [ ] Add request size limit (1 MB)
- [ ] Handle URL-encoded group names in path parameters
- [ ] Log errors appropriately

### Phase 9: Testing

- [ ] Set up pytest with test fixtures
- [ ] Create test database configuration
- [ ] Write tests for `POST /status` endpoint
- [ ] Write tests for `GET /health` endpoint
- [ ] Write tests for `GET /groups` endpoint
- [ ] Write tests for `GET /groups/<name>/jobs` endpoint
- [ ] Write tests for `GET /config` and `PUT /config` endpoints
- [ ] Write tests for group config endpoints
- [ ] Write tests for input validation and error cases
- [ ] Write tests for timeout checker background task
- [ ] Verify WebSocket events are emitted correctly

### Phase 10: Integration & Documentation

- [ ] Verify CLI can connect and submit statuses
- [ ] Verify frontend can connect and receive updates
- [ ] Test concurrent status submissions
- [ ] Add inline code comments for complex logic
- [ ] Document environment variables in README

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///reportingin.db` | SQLAlchemy database connection URL |
| `SECRET_KEY` | (generated) | Flask secret key for sessions |
| `DEBUG` | `false` | Enable Flask debug mode |
| `HOST` | `127.0.0.1` | Server bind address |
| `PORT` | `7828` | Server port |

## HTTP Status Codes

| Code | Usage |
|------|-------|
| 200 | Successful GET or PUT |
| 201 | Successful POST (resource created) |
| 400 | Validation error (missing fields, invalid values) |
| 404 | Resource not found (group doesn't exist) |
| 500 | Internal server error |

## Status Value Definitions

| Status | Description | Auto-Transition |
|--------|-------------|-----------------|
| `success` | Job completed successfully | → `stale` after staleness timeout |
| `error` | Job failed with error | None |
| `progress` | Job currently running | → `timeout` after progress timeout |
| `timeout` | Progress job exceeded timeout | None |
| `stale` | No update within staleness period | None |

## Health Status Logic

The overall health status is determined by:

1. `empty` - No jobs exist in the system
2. `unhealthy` - Any job has status: error, timeout, or stale
3. `in_progress` - Any job has status: progress (and no unhealthy jobs)
4. `healthy` - All jobs have status: success
