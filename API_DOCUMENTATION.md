# Door Control REST API Documentation

## Overview

This document describes the REST API endpoints for the Door Control system. The API provides programmatic access to user management, access control, and event logging functionality.

## Authentication

All API endpoints (except `/health` and `/docs`) require authentication using an API key.

### API Key Setup

1. Generate a secure API key:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. Add the API key to your `.env` file:
   ```
   API_KEY=your_generated_api_key_here
   ```

3. Include the API key in all requests using the `X-API-Key` header:
   ```bash
   curl -H "X-API-Key: your_api_key_here" http://localhost:5001/api/v1/users
   ```

## Base URL

All API endpoints are prefixed with `/api/v1`

Example: `http://localhost:5001/api/v1/users`

## Endpoints

### System Endpoints

#### Health Check
```
GET /api/v1/health
```

Check if the API is running (no authentication required).

**Response:**
```json
{
  "success": true,
  "status": "healthy",
  "timestamp": "2026-01-09T21:30:00.000000"
}
```

#### API Documentation
```
GET /api/v1/docs
```

Get API documentation (no authentication required).

---

### User Management Endpoints

#### List All Users
```
GET /api/v1/users
```

Get a list of all users in the system.

**Headers:**
- `X-API-Key`: Your API key (required)

**Response:**
```json
{
  "success": true,
  "count": 2,
  "users": [
    {
      "id": 1,
      "card_number": 12345678,
      "name": "John Doe",
      "email": "john@example.com",
      "phone": "555-1234",
      "login": "jdoe",
      "uid": 1001,
      "note": "Regular member",
      "membership_type": "full"
    }
  ]
}
```

#### Get Specific User
```
GET /api/v1/users/<user_id>
```

Get details for a specific user by their database ID.

**Parameters:**
- `user_id` (path): The database ID of the user

**Headers:**
- `X-API-Key`: Your API key (required)

**Response:**
```json
{
  "success": true,
  "user": {
    "id": 1,
    "card_number": 12345678,
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "555-1234",
    "login": "jdoe",
    "uid": 1001,
    "note": "Regular member",
    "membership_type": "full"
  }
}
```

#### Create New User
```
POST /api/v1/users
```

Create a new user in the system.

**Headers:**
- `X-API-Key`: Your API key (required)
- `Content-Type`: application/json

**Request Body:**
```json
{
  "card_number": 12345678,
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "555-1234",
  "login": "jdoe",
  "uid": 1001,
  "note": "Regular member",
  "membership_type": "full"
}
```

**Required Fields:**
- `card_number` (integer)
- `name` (string)

**Optional Fields:**
- `email` (string)
- `phone` (string)
- `login` (string)
- `uid` (integer)
- `note` (string)
- `membership_type` (string)

**Response:**
```json
{
  "success": true,
  "message": "User created successfully",
  "user": {
    "id": 1,
    "card_number": 12345678,
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "555-1234",
    "login": "jdoe",
    "uid": 1001,
    "note": "Regular member",
    "membership_type": "full"
  }
}
```

#### Update User
```
PUT /api/v1/users/<user_id>
PATCH /api/v1/users/<user_id>
```

Update an existing user's information.

**Parameters:**
- `user_id` (path): The database ID of the user

**Headers:**
- `X-API-Key`: Your API key (required)
- `Content-Type`: application/json

**Request Body:**
```json
{
  "name": "John Smith",
  "email": "john.smith@example.com",
  "phone": "555-5678",
  "membership_type": "premium"
}
```

All fields are optional. Only include fields you want to update.

**Response:**
```json
{
  "success": true,
  "message": "User updated successfully",
  "user": {
    "id": 1,
    "card_number": 12345678,
    "name": "John Smith",
    "email": "john.smith@example.com",
    "phone": "555-5678",
    "login": "jdoe",
    "uid": 1001,
    "note": "Regular member",
    "membership_type": "premium"
  }
}
```

#### Delete User
```
DELETE /api/v1/users/<user_id>
```

Delete a user from the system.

**Parameters:**
- `user_id` (path): The database ID of the user

**Headers:**
- `X-API-Key`: Your API key (required)

**Response:**
```json
{
  "success": true,
  "message": "User John Doe (card 12345678) deleted successfully"
}
```

---

### Access Control Endpoints

#### Activate User Access
```
POST /api/v1/users/<user_id>/access/activate
```

Activate a user's access on all controllers in the system.

**Parameters:**
- `user_id` (path): The database ID of the user

**Headers:**
- `X-API-Key`: Your API key (required)
- `Content-Type`: application/json

**Request Body (all fields optional):**
```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-12-31",
  "doors": [1, 2, 3, 4],
  "pin": 1234
}
```

**Fields:**
- `start_date` (string, optional): Start date in YYYY-MM-DD format (defaults to today)
- `end_date` (string, optional): End date in YYYY-MM-DD format (defaults to 1 year from start)
- `doors` (array, optional): List of door IDs to grant access to (defaults to [1, 2, 3, 4])
- `pin` (integer, optional): PIN code for the user

**Response:**
```json
{
  "success": true,
  "message": "Access activated on 2 of 2 controllers",
  "user": {
    "id": 1,
    "card_number": 12345678,
    "name": "John Doe"
  },
  "results": [
    {
      "controller_id": "405419896",
      "success": true,
      "message": "Access activated"
    },
    {
      "controller_id": "303986753",
      "success": true,
      "message": "Access activated"
    }
  ]
}
```

#### Deactivate User Access
```
POST /api/v1/users/<user_id>/access/deactivate
```

Deactivate a user's access on all controllers in the system.

**Parameters:**
- `user_id` (path): The database ID of the user

**Headers:**
- `X-API-Key`: Your API key (required)

**Response:**
```json
{
  "success": true,
  "message": "Access deactivated on 2 of 2 controllers",
  "user": {
    "id": 1,
    "card_number": 12345678,
    "name": "John Doe"
  },
  "results": [
    {
      "controller_id": "405419896",
      "success": true,
      "message": "Access deactivated"
    },
    {
      "controller_id": "303986753",
      "success": true,
      "message": "Access deactivated"
    }
  ]
}
```

#### Get Card Access Status
```
GET /api/v1/users/card/<card_number>/access/status
```

Get the access status of a card across all controllers.

**Parameters:**
- `card_number` (path): The card number to check

**Headers:**
- `X-API-Key`: Your API key (required)

**Response:**
```json
{
  "success": true,
  "card_number": 12345678,
  "controllers": [
    {
      "controller_id": "405419896",
      "controller_name": "Main Entrance",
      "has_access": true,
      "card_info": {
        "card-number": 12345678,
        "start-date": "2026-01-01",
        "end-date": "2026-12-31",
        "doors": {
          "1": 1,
          "2": 1,
          "3": 0,
          "4": 0
        },
        "pin": 0
      }
    },
    {
      "controller_id": "303986753",
      "controller_name": "Back Door",
      "has_access": false,
      "card_info": null
    }
  ]
}
```

---

### Event Log Endpoints

#### Get Events
```
GET /api/v1/events
```

Get event logs with optional filtering and pagination.

**Headers:**
- `X-API-Key`: Your API key (required)

**Query Parameters (all optional):**
- `controller_id` (integer): Filter by controller ID
- `card_number` (integer): Filter by card number
- `door_id` (integer): Filter by door ID
- `limit` (integer): Maximum number of events to return (default: 100, max: 1000)
- `offset` (integer): Number of events to skip (default: 0)

**Example:**
```
GET /api/v1/events?controller_id=405419896&limit=50&offset=0
```

**Response:**
```json
{
  "success": true,
  "count": 50,
  "total": 1234,
  "limit": 50,
  "offset": 0,
  "events": [
    {
      "id": 1,
      "controller_id": 405419896,
      "event_id": 100,
      "timestamp": "2026-01-09 16:30:00 EST",
      "timestamp_utc": "2026-01-09T21:30:00.000000",
      "card_number": 12345678,
      "event_type": 2,
      "event_type_text": "door",
      "access_granted": true,
      "door_id": 1,
      "direction": 1,
      "direction_text": "in",
      "event_reason": 0,
      "event_reason_text": "swipe",
      "name": "John Doe",
      "email": "john@example.com",
      "membership_type": "full"
    }
  ]
}
```

---

### Data Management Endpoints

#### Export Database
```
GET /api/v1/export
```

Export all database data to JSON format for backup or migration purposes.

**Headers:**
- `X-API-Key`: Your API key (required)

**Query Parameters (all optional):**
- `include_events` (boolean): Include event logs in export (default: true)
- `download` (boolean): Return as downloadable file attachment (default: false)

**Example:**
```
GET /api/v1/export?include_events=true&download=true
```

**Response (when download=false):**
```json
{
  "success": true,
  "data": {
    "export_metadata": {
      "timestamp": "2026-01-09T21:30:00.000000",
      "version": "1.0",
      "include_events": true
    },
    "users": [
      {
        "id": 1,
        "card_number": 12345678,
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "555-1234",
        "login": "jdoe",
        "uid": 1001,
        "note": "Regular member",
        "membership_type": "full"
      }
    ],
    "events": [
      {
        "id": 1,
        "controller_id": 405419896,
        "event_id": 100,
        "timestamp": "2026-01-09 16:30:00 EST",
        "timestamp_utc": "2026-01-09T21:30:00.000000",
        "card_number": 12345678,
        "event_type": 2,
        "event_type_text": "door",
        "access_granted": true,
        "door_id": 1,
        "direction": 1,
        "direction_text": "in",
        "event_reason": 0,
        "event_reason_text": "swipe",
        "insert_timestamp_utc": "2026-01-09T21:30:05.000000",
        "name": "John Doe",
        "email": "john@example.com",
        "membership_type": "full"
      }
    ]
  }
}
```

**Response (when download=true):**
Returns a JSON file as an attachment with filename `door_control_export_YYYYMMDD_HHMMSS.json`

#### Import Database
```
POST /api/v1/import
```

Import database data from JSON format (previously exported from this system).

**Headers:**
- `X-API-Key`: Your API key (required)
- `Content-Type`: application/json

**Request Body:**
```json
{
  "data": {
    "users": [
      {
        "card_number": 12345678,
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "555-1234",
        "login": "jdoe",
        "uid": 1001,
        "note": "Regular member",
        "membership_type": "full"
      }
    ],
    "events": [
      {
        "controller_id": 405419896,
        "event_id": 100,
        "timestamp": "2026-01-09 16:30:00 EST",
        "timestamp_utc": "2026-01-09T21:30:00.000000",
        "card_number": 12345678,
        "event_type": 2,
        "event_type_text": "door",
        "access_granted": true,
        "door_id": 1,
        "direction": 1,
        "direction_text": "in",
        "event_reason": 0,
        "event_reason_text": "swipe",
        "name": "John Doe",
        "email": "john@example.com",
        "membership_type": "full"
      }
    ]
  },
  "mode": "merge",
  "skip_duplicates": true
}
```

**Fields:**
- `data` (object, required): The data to import
  - `users` (array, required): Array of user objects
  - `events` (array, optional): Array of event objects
- `mode` (string, optional): Import mode - "merge" or "replace" (default: "merge")
  - `merge`: Add new records, keep existing data
  - `replace`: **DANGEROUS** - Delete all existing data before importing
- `skip_duplicates` (boolean, optional): Skip duplicate records (default: true)

**Response:**
```json
{
  "success": true,
  "message": "Import completed",
  "mode": "merge",
  "results": {
    "users": {
      "added": 5,
      "skipped": 2,
      "errors": []
    },
    "events": {
      "added": 150,
      "skipped": 10,
      "errors": []
    }
  }
}
```

**Important Notes:**
- The `replace` mode will **permanently delete all existing data** before importing
- Database IDs are auto-generated during import and may differ from the original export
- Duplicate detection for users is based on `card_number`
- Duplicate detection for events is based on `controller_id`, `event_id`, and `timestamp`
- Always backup your data before performing an import with `replace` mode

---

## Error Responses

All endpoints return consistent error responses:

### 401 Unauthorized
```json
{
  "error": "Missing API key",
  "message": "X-API-Key header is required"
}
```

### 403 Forbidden
```json
{
  "error": "Invalid API key",
  "message": "The provided API key is not valid"
}
```

### 404 Not Found
```json
{
  "success": false,
  "error": "User not found",
  "message": "No user found with ID 123"
}
```

### 409 Conflict
```json
{
  "success": false,
  "error": "Duplicate card number",
  "message": "A user with card number 12345678 already exists"
}
```

### 500 Internal Server Error
```json
{
  "success": false,
  "error": "Database error",
  "message": "Error details here"
}
```

---

## Example Usage

### Python Example

```python
import requests

API_KEY = "your_api_key_here"
BASE_URL = "http://localhost:5001/api/v1"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# Create a new user
new_user = {
    "card_number": 12345678,
    "name": "John Doe",
    "email": "john@example.com",
    "membership_type": "full"
}

response = requests.post(
    f"{BASE_URL}/users",
    json=new_user,
    headers=headers
)

if response.status_code == 201:
    user = response.json()["user"]
    user_id = user["id"]
    print(f"User created with ID: {user_id}")
    
    # Activate access for the user
    access_config = {
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "doors": [1, 2, 3, 4]
    }
    
    response = requests.post(
        f"{BASE_URL}/users/{user_id}/access/activate",
        json=access_config,
        headers=headers
    )
    
    if response.status_code == 200:
        print("Access activated successfully")
        print(response.json())
```

### cURL Examples

```bash
# List all users
curl -H "X-API-Key: your_api_key_here" \
  http://localhost:5001/api/v1/users

# Create a new user
curl -X POST \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"card_number": 12345678, "name": "John Doe", "email": "john@example.com"}' \
  http://localhost:5001/api/v1/users

# Activate user access
curl -X POST \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"start_date": "2026-01-01", "end_date": "2026-12-31", "doors": [1,2,3,4]}' \
  http://localhost:5001/api/v1/users/1/access/activate

# Deactivate user access
curl -X POST \
  -H "X-API-Key: your_api_key_here" \
  http://localhost:5001/api/v1/users/1/access/deactivate

# Get events with filtering
curl -H "X-API-Key: your_api_key_here" \
  "http://localhost:5001/api/v1/events?controller_id=405419896&limit=50"

# Update user
curl -X PUT \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"name": "John Smith", "email": "john.smith@example.com"}' \
  http://localhost:5001/api/v1/users/1

# Delete user
curl -X DELETE \
  -H "X-API-Key: your_api_key_here" \
  http://localhost:5001/api/v1/users/1

# Check card access status
curl -H "X-API-Key: your_api_key_here" \
  http://localhost:5001/api/v1/users/card/12345678/access/status

# Export database (as JSON response)
curl -H "X-API-Key: your_api_key_here" \
  "http://localhost:5001/api/v1/export?include_events=true&download=false"

# Export database (as downloadable file)
curl -H "X-API-Key: your_api_key_here" \
  "http://localhost:5001/api/v1/export?include_events=true&download=true" \
  -o backup.json

# Import database (merge mode)
curl -X POST \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d @backup.json \
  http://localhost:5001/api/v1/import

# Import database with specific options
curl -X POST \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"data": {"users": [...], "events": [...]}, "mode": "merge", "skip_duplicates": true}' \
  http://localhost:5001/api/v1/import
```

---

## Security Best Practices

1. **Keep your API key secure**: Never commit your API key to version control
2. **Use HTTPS in production**: Always use HTTPS to encrypt API communications
3. **Rotate API keys regularly**: Generate new API keys periodically
4. **Limit API key access**: Use different API keys for different applications
5. **Monitor API usage**: Keep logs of API access for security auditing

---

## Rate Limiting

Currently, there is no rate limiting implemented. Consider implementing rate limiting in production environments to prevent abuse.

---

## Support

For issues or questions about the API, please contact the system administrator or refer to the main project documentation.
