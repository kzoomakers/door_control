# Door Control API Quick Reference

## Setup

1. Generate API key:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. Add to `.env`:
   ```
   API_KEY=your_generated_key
   ```

3. Use in requests:
   ```bash
   curl -H "X-API-Key: your_key" http://localhost:5001/api/v1/users
   ```

## Quick Command Reference

### User Management

```bash
# List all users
curl -H "X-API-Key: KEY" http://localhost:5001/api/v1/users

# Get specific user
curl -H "X-API-Key: KEY" http://localhost:5001/api/v1/users/1

# Create user
curl -X POST -H "X-API-Key: KEY" -H "Content-Type: application/json" \
  -d '{"card_number": 12345678, "name": "John Doe", "email": "john@example.com"}' \
  http://localhost:5001/api/v1/users

# Update user
curl -X PUT -H "X-API-Key: KEY" -H "Content-Type: application/json" \
  -d '{"name": "Jane Doe", "email": "jane@example.com"}' \
  http://localhost:5001/api/v1/users/1

# Delete user
curl -X DELETE -H "X-API-Key: KEY" http://localhost:5001/api/v1/users/1
```

### Access Control

```bash
# Activate access (all controllers)
curl -X POST -H "X-API-Key: KEY" -H "Content-Type: application/json" \
  -d '{"start_date": "2026-01-01", "end_date": "2026-12-31", "doors": [1,2,3,4]}' \
  http://localhost:5001/api/v1/users/1/access/activate

# Deactivate access (all controllers)
curl -X POST -H "X-API-Key: KEY" \
  http://localhost:5001/api/v1/users/1/access/deactivate

# Check card status
curl -H "X-API-Key: KEY" \
  http://localhost:5001/api/v1/users/card/12345678/access/status
```

### Events

```bash
# Get all events
curl -H "X-API-Key: KEY" http://localhost:5001/api/v1/events

# Get events with filters
curl -H "X-API-Key: KEY" \
  "http://localhost:5001/api/v1/events?controller_id=405419896&limit=50&offset=0"

# Get events for specific card
curl -H "X-API-Key: KEY" \
  "http://localhost:5001/api/v1/events?card_number=12345678"
```

### Data Management

```bash
# Export database (as JSON response)
curl -H "X-API-Key: KEY" \
  "http://localhost:5001/api/v1/export?include_events=true"

# Export database (download file)
curl -H "X-API-Key: KEY" \
  "http://localhost:5001/api/v1/export?include_events=true&download=true" \
  -o backup.json

# Import database
curl -X POST -H "X-API-Key: KEY" -H "Content-Type: application/json" \
  -d @backup.json \
  http://localhost:5001/api/v1/import
```

### System

```bash
# Health check (no auth)
curl http://localhost:5001/api/v1/health

# API docs (no auth)
curl http://localhost:5001/api/v1/docs
```

## Common Workflows

### Add New Member with Access

```bash
# 1. Create user
USER_ID=$(curl -s -X POST -H "X-API-Key: KEY" -H "Content-Type: application/json" \
  -d '{"card_number": 12345678, "name": "John Doe", "email": "john@example.com", "membership_type": "full"}' \
  http://localhost:5001/api/v1/users | jq -r '.user.id')

# 2. Activate access
curl -X POST -H "X-API-Key: KEY" -H "Content-Type: application/json" \
  -d '{"start_date": "2026-01-01", "end_date": "2026-12-31", "doors": [1,2,3,4]}' \
  http://localhost:5001/api/v1/users/$USER_ID/access/activate
```

### Remove Member Access

```bash
# 1. Deactivate access
curl -X POST -H "X-API-Key: KEY" \
  http://localhost:5001/api/v1/users/1/access/deactivate

# 2. Optionally delete user record
curl -X DELETE -H "X-API-Key: KEY" \
  http://localhost:5001/api/v1/users/1
```

### Update Member Information

```bash
curl -X PUT -H "X-API-Key: KEY" -H "Content-Type: application/json" \
  -d '{"email": "newemail@example.com", "phone": "555-9999", "membership_type": "premium"}' \
  http://localhost:5001/api/v1/users/1
```

## Python Quick Start

```python
import requests

API_KEY = "your_api_key"
BASE_URL = "http://localhost:5001/api/v1"
headers = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

# Create user
user = requests.post(f"{BASE_URL}/users", 
    json={"card_number": 12345678, "name": "John Doe"}, 
    headers=headers).json()

# Activate access
requests.post(f"{BASE_URL}/users/{user['user']['id']}/access/activate",
    json={"doors": [1,2,3,4]}, headers=headers)

# Get events
events = requests.get(f"{BASE_URL}/events?limit=10", headers=headers).json()
```

## Response Codes

- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized (missing API key)
- `403` - Forbidden (invalid API key)
- `404` - Not Found
- `409` - Conflict (duplicate)
- `500` - Server Error

## All Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check (no auth) |
| GET | `/api/v1/docs` | API documentation (no auth) |
| GET | `/api/v1/users` | List all users |
| GET | `/api/v1/users/<id>` | Get specific user |
| POST | `/api/v1/users` | Create new user |
| PUT | `/api/v1/users/<id>` | Update user |
| DELETE | `/api/v1/users/<id>` | Delete user |
| POST | `/api/v1/users/<id>/access/activate` | Activate access |
| POST | `/api/v1/users/<id>/access/deactivate` | Deactivate access |
| GET | `/api/v1/users/card/<card>/access/status` | Check card status |
| GET | `/api/v1/events` | Get event logs |
| GET | `/api/v1/export` | Export database to JSON |
| POST | `/api/v1/import` | Import database from JSON |
