# Filename    : api.py
# Author      : Jon Kelley <jon.kelley@kzoomakers.org>
# Description : REST API endpoints for door control system
import requests
from flask import Blueprint, request, jsonify, current_app, send_file
from functools import wraps
from doorctl.db import db, CardMemberMapping, GlobalEventLog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound
import datetime
import json
import io

api = Blueprint('api', __name__, url_prefix='/api/v1')

def require_api_key(f):
    """Decorator to require API key authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            return jsonify({
                'error': 'Missing API key',
                'message': 'X-API-Key header is required'
            }), 401
        
        if api_key != current_app.config.get('API_KEY'):
            return jsonify({
                'error': 'Invalid API key',
                'message': 'The provided API key is not valid'
            }), 403
        
        return f(*args, **kwargs)
    return decorated_function


# ===== User Management Endpoints =====

@api.route('/users', methods=['GET'])
@require_api_key
def list_users():
    """
    List all users in the system
    
    Returns:
        JSON array of all users with their details
    """
    try:
        users = CardMemberMapping.query.all()
        users_list = []
        
        for user in users:
            users_list.append({
                'id': user.id,
                'card_number': user.card_number,
                'name': user.name,
                'email': user.email,
                'phone': user.phone,
                'login': user.login,
                'uid': user.uid,
                'note': user.note,
                'membership_type': user.membership_type
            })
        
        return jsonify({
            'success': True,
            'count': len(users_list),
            'users': users_list
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Database error',
            'message': str(e)
        }), 500


@api.route('/users/<int:user_id>', methods=['GET'])
@require_api_key
def get_user(user_id):
    """
    Get a specific user by ID
    
    Args:
        user_id: The database ID of the user
    
    Returns:
        JSON object with user details
    """
    try:
        user = CardMemberMapping.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found',
                'message': f'No user found with ID {user_id}'
            }), 404
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'card_number': user.card_number,
                'name': user.name,
                'email': user.email,
                'phone': user.phone,
                'login': user.login,
                'uid': user.uid,
                'note': user.note,
                'membership_type': user.membership_type
            }
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Database error',
            'message': str(e)
        }), 500


@api.route('/users', methods=['POST'])
@require_api_key
def create_user():
    """
    Create a new user in the system
    
    Request Body:
        {
            "card_number": int (required),
            "name": str (required),
            "email": str (optional),
            "phone": str (optional),
            "login": str (optional),
            "uid": int (optional),
            "note": str (optional),
            "membership_type": str (optional)
        }
    
    Returns:
        JSON object with created user details
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Invalid request',
                'message': 'Request body must be JSON'
            }), 400
        
        # Validate required fields
        if 'card_number' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field',
                'message': 'card_number is required'
            }), 400
        
        if 'name' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field',
                'message': 'name is required'
            }), 400
        
        # Check if card number already exists
        existing_user = CardMemberMapping.query.filter_by(card_number=data['card_number']).first()
        if existing_user:
            return jsonify({
                'success': False,
                'error': 'Duplicate card number',
                'message': f'A user with card number {data["card_number"]} already exists'
            }), 409
        
        # Create new user
        new_user = CardMemberMapping(
            card_number=data['card_number'],
            name=data['name'],
            email=data.get('email'),
            phone=data.get('phone'),
            login=data.get('login'),
            uid=data.get('uid'),
            note=data.get('note'),
            membership_type=data.get('membership_type')
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'User created successfully',
            'user': {
                'id': new_user.id,
                'card_number': new_user.card_number,
                'name': new_user.name,
                'email': new_user.email,
                'phone': new_user.phone,
                'login': new_user.login,
                'uid': new_user.uid,
                'note': new_user.note,
                'membership_type': new_user.membership_type
            }
        }), 201
    
    except IntegrityError as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Database integrity error',
            'message': 'Card number must be unique'
        }), 409
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Database error',
            'message': str(e)
        }), 500


@api.route('/users/<int:user_id>', methods=['PUT', 'PATCH'])
@require_api_key
def update_user(user_id):
    """
    Update an existing user
    
    Args:
        user_id: The database ID of the user
    
    Request Body:
        {
            "name": str (optional),
            "email": str (optional),
            "phone": str (optional),
            "login": str (optional),
            "uid": int (optional),
            "note": str (optional),
            "membership_type": str (optional)
        }
    
    Returns:
        JSON object with updated user details
    """
    try:
        user = CardMemberMapping.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found',
                'message': f'No user found with ID {user_id}'
            }), 404
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Invalid request',
                'message': 'Request body must be JSON'
            }), 400
        
        # Update fields if provided
        if 'name' in data:
            user.name = data['name']
        if 'email' in data:
            user.email = data['email']
        if 'phone' in data:
            user.phone = data['phone']
        if 'login' in data:
            user.login = data['login']
        if 'uid' in data:
            user.uid = data['uid']
        if 'note' in data:
            user.note = data['note']
        if 'membership_type' in data:
            user.membership_type = data['membership_type']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'User updated successfully',
            'user': {
                'id': user.id,
                'card_number': user.card_number,
                'name': user.name,
                'email': user.email,
                'phone': user.phone,
                'login': user.login,
                'uid': user.uid,
                'note': user.note,
                'membership_type': user.membership_type
            }
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Database error',
            'message': str(e)
        }), 500


@api.route('/users/<int:user_id>', methods=['DELETE'])
@require_api_key
def delete_user(user_id):
    """
    Delete a user from the system
    
    Args:
        user_id: The database ID of the user
    
    Returns:
        JSON confirmation message
    """
    try:
        user = CardMemberMapping.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found',
                'message': f'No user found with ID {user_id}'
            }), 404
        
        card_number = user.card_number
        name = user.name
        
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'User {name} (card {card_number}) deleted successfully'
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Database error',
            'message': str(e)
        }), 500


# ===== Card Access Control Endpoints =====

@api.route('/users/<int:user_id>/access/activate', methods=['POST'])
@require_api_key
def activate_user_access(user_id):
    """
    Activate a user's access on all controllers
    
    Args:
        user_id: The database ID of the user
    
    Request Body:
        {
            "start_date": "YYYY-MM-DD" (optional, defaults to today),
            "end_date": "YYYY-MM-DD" (optional, defaults to 1 year from start),
            "doors": [1, 2, 3, 4] (optional, defaults to all doors),
            "pin": int (optional)
        }
    
    Returns:
        JSON object with activation results for each controller
    """
    try:
        user = CardMemberMapping.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found',
                'message': f'No user found with ID {user_id}'
            }), 404
        
        data = request.get_json() or {}
        
        # Set default dates
        start_date = data.get('start_date', datetime.date.today().strftime('%Y-%m-%d'))
        end_date = data.get('end_date', (datetime.date.today() + datetime.timedelta(days=365)).strftime('%Y-%m-%d'))
        
        # Get door configuration
        doors_list = data.get('doors', [1, 2, 3, 4])
        pin = data.get('pin')
        
        # Get all controllers from config
        from doorctl.sharedlib.get_config import parse_uhppoted_config
        api_config = parse_uhppoted_config('/etc/uhppoted/uhppoted.conf')
        
        results = []
        success_count = 0
        
        for controller_id in api_config['devices'].keys():
            # Build card data
            card_data = {
                'card-number': user.card_number,
                'start-date': start_date,
                'end-date': end_date,
                'doors': {}
            }
            
            # Set door permissions
            for i in range(1, 5):
                card_data['doors'][str(i)] = 1 if i in doors_list else 0
            
            if pin:
                card_data['pin'] = int(pin)
            
            # Send request to controller
            url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/card/{user.card_number}"
            response = requests.put(url, json=card_data)
            
            if response.status_code == 200:
                success_count += 1
                results.append({
                    'controller_id': controller_id,
                    'success': True,
                    'message': 'Access activated'
                })
            else:
                results.append({
                    'controller_id': controller_id,
                    'success': False,
                    'message': response.json().get('message', 'Failed to activate access')
                })
        
        return jsonify({
            'success': success_count > 0,
            'message': f'Access activated on {success_count} of {len(api_config["devices"])} controllers',
            'user': {
                'id': user.id,
                'card_number': user.card_number,
                'name': user.name
            },
            'results': results
        }), 200 if success_count > 0 else 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Error activating access',
            'message': str(e)
        }), 500


@api.route('/users/<int:user_id>/access/deactivate', methods=['POST'])
@require_api_key
def deactivate_user_access(user_id):
    """
    Deactivate a user's access on all controllers
    
    Args:
        user_id: The database ID of the user
    
    Returns:
        JSON object with deactivation results for each controller
    """
    try:
        user = CardMemberMapping.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found',
                'message': f'No user found with ID {user_id}'
            }), 404
        
        # Get all controllers from config
        from doorctl.sharedlib.get_config import parse_uhppoted_config
        api_config = parse_uhppoted_config('/etc/uhppoted/uhppoted.conf')
        
        results = []
        success_count = 0
        
        for controller_id in api_config['devices'].keys():
            # Send DELETE request to remove card from controller
            url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/card/{user.card_number}"
            response = requests.delete(url)
            
            if response.status_code == 200:
                success_count += 1
                results.append({
                    'controller_id': controller_id,
                    'success': True,
                    'message': 'Access deactivated'
                })
            else:
                results.append({
                    'controller_id': controller_id,
                    'success': False,
                    'message': response.json().get('message', 'Failed to deactivate access')
                })
        
        return jsonify({
            'success': success_count > 0,
            'message': f'Access deactivated on {success_count} of {len(api_config["devices"])} controllers',
            'user': {
                'id': user.id,
                'card_number': user.card_number,
                'name': user.name
            },
            'results': results
        }), 200 if success_count > 0 else 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Error deactivating access',
            'message': str(e)
        }), 500


@api.route('/users/card/<int:card_number>/access/status', methods=['GET'])
@require_api_key
def get_card_access_status(card_number):
    """
    Get the access status of a card across all controllers
    
    Args:
        card_number: The card number to check
    
    Returns:
        JSON object with access status for each controller
    """
    try:
        # Get all controllers from config
        from doorctl.sharedlib.get_config import parse_uhppoted_config
        api_config = parse_uhppoted_config('/etc/uhppoted/uhppoted.conf')
        
        results = []
        
        for controller_id in api_config['devices'].keys():
            url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/card/{card_number}"
            response = requests.get(url)
            
            if response.status_code == 200:
                card_info = response.json().get('card', {})
                results.append({
                    'controller_id': controller_id,
                    'controller_name': api_config['devices'][controller_id].get('name', 'Unknown'),
                    'has_access': True,
                    'card_info': card_info
                })
            else:
                results.append({
                    'controller_id': controller_id,
                    'controller_name': api_config['devices'][controller_id].get('name', 'Unknown'),
                    'has_access': False,
                    'card_info': None
                })
        
        return jsonify({
            'success': True,
            'card_number': card_number,
            'controllers': results
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Error checking access status',
            'message': str(e)
        }), 500


# ===== Event Log Endpoints =====

@api.route('/events', methods=['GET'])
@require_api_key
def get_events():
    """
    Get event logs with optional filtering
    
    Query Parameters:
        controller_id: Filter by controller ID
        card_number: Filter by card number
        door_id: Filter by door ID
        limit: Maximum number of events to return (default: 100)
        offset: Number of events to skip (default: 0)
    
    Returns:
        JSON array of events
    """
    try:
        query = GlobalEventLog.query
        
        # Apply filters
        controller_id = request.args.get('controller_id', type=int)
        if controller_id:
            query = query.filter_by(controller_id=controller_id)
        
        card_number = request.args.get('card_number', type=int)
        if card_number:
            query = query.filter_by(card_number=card_number)
        
        door_id = request.args.get('door_id', type=int)
        if door_id:
            query = query.filter_by(door_id=door_id)
        
        # Apply pagination
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Limit maximum results
        limit = min(limit, 1000)
        
        # Order by most recent first
        query = query.order_by(GlobalEventLog.timestamp_utc.desc())
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination
        events = query.limit(limit).offset(offset).all()
        
        events_list = []
        for event in events:
            events_list.append({
                'id': event.id,
                'controller_id': event.controller_id,
                'event_id': event.event_id,
                'timestamp': event.timestamp,
                'timestamp_utc': event.timestamp_utc.isoformat() if event.timestamp_utc else None,
                'card_number': event.card_number,
                'event_type': event.event_type,
                'event_type_text': event.event_type_text,
                'access_granted': event.access_granted,
                'door_id': event.door_id,
                'direction': event.direction,
                'direction_text': event.direction_text,
                'event_reason': event.event_reason,
                'event_reason_text': event.event_reason_text,
                'name': event.name,
                'email': event.email,
                'membership_type': event.membership_type
            })
        
        return jsonify({
            'success': True,
            'count': len(events_list),
            'total': total_count,
            'limit': limit,
            'offset': offset,
            'events': events_list
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Database error',
            'message': str(e)
        }), 500


# ===== System Health Endpoint =====

@api.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint (no authentication required)
    
    Returns:
        JSON object with system health status
    """
    return jsonify({
        'success': True,
        'status': 'healthy',
        'timestamp': datetime.datetime.utcnow().isoformat()
    }), 200


# ===== API Documentation Endpoint =====

@api.route('/docs', methods=['GET'])
def api_docs():
    """
    API documentation endpoint
    
    Returns:
        JSON object with API documentation
    """
    return jsonify({
        'api_version': 'v1',
        'endpoints': {
            'users': {
                'GET /api/v1/users': 'List all users',
                'GET /api/v1/users/<user_id>': 'Get specific user',
                'POST /api/v1/users': 'Create new user',
                'PUT /api/v1/users/<user_id>': 'Update user',
                'DELETE /api/v1/users/<user_id>': 'Delete user'
            },
            'access_control': {
                'POST /api/v1/users/<user_id>/access/activate': 'Activate user access on all controllers',
                'POST /api/v1/users/<user_id>/access/deactivate': 'Deactivate user access on all controllers',
                'GET /api/v1/users/card/<card_number>/access/status': 'Get card access status'
            },
            'events': {
                'GET /api/v1/events': 'Get event logs with optional filtering'
            },
            'data_management': {
                'GET /api/v1/export': 'Export all database data to JSON',
                'POST /api/v1/import': 'Import database data from JSON'
            },
            'system': {
                'GET /api/v1/health': 'Health check (no auth required)',
                'GET /api/v1/docs': 'API documentation (no auth required)'
            }
        },
        'authentication': {
            'method': 'API Key',
            'header': 'X-API-Key',
            'description': 'Include your API key in the X-API-Key header for all authenticated endpoints'
        }
    }), 200


# ===== Data Export/Import Endpoints =====

@api.route('/export', methods=['GET'])
@require_api_key
def export_data():
    """
    Export all database data to JSON format
    
    Query Parameters:
        download: If 'true', returns file as attachment (default: false)
        include_events: If 'false', excludes event logs (default: true)
    
    Returns:
        JSON file with all database data
    """
    try:
        include_events = request.args.get('include_events', 'true').lower() == 'true'
        download = request.args.get('download', 'false').lower() == 'true'
        
        # Export users
        users = CardMemberMapping.query.all()
        users_data = []
        for user in users:
            users_data.append({
                'id': user.id,
                'card_number': user.card_number,
                'name': user.name,
                'email': user.email,
                'phone': user.phone,
                'login': user.login,
                'uid': user.uid,
                'note': user.note,
                'membership_type': user.membership_type
            })
        
        export_data = {
            'export_metadata': {
                'timestamp': datetime.datetime.utcnow().isoformat(),
                'version': '1.0',
                'include_events': include_events
            },
            'users': users_data
        }
        
        # Export events if requested
        if include_events:
            events = GlobalEventLog.query.all()
            events_data = []
            for event in events:
                events_data.append({
                    'id': event.id,
                    'controller_id': event.controller_id,
                    'event_id': event.event_id,
                    'timestamp': event.timestamp,
                    'timestamp_utc': event.timestamp_utc.isoformat() if event.timestamp_utc else None,
                    'card_number': event.card_number,
                    'event_type': event.event_type,
                    'event_type_text': event.event_type_text,
                    'access_granted': event.access_granted,
                    'door_id': event.door_id,
                    'direction': event.direction,
                    'direction_text': event.direction_text,
                    'event_reason': event.event_reason,
                    'event_reason_text': event.event_reason_text,
                    'insert_timestamp_utc': event.insert_timestamp_utc.isoformat() if event.insert_timestamp_utc else None,
                    'name': event.name,
                    'email': event.email,
                    'membership_type': event.membership_type
                })
            export_data['events'] = events_data
        
        # Return as downloadable file or JSON response
        if download:
            filename = f"door_control_export_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            json_str = json.dumps(export_data, indent=2)
            return send_file(
                io.BytesIO(json_str.encode('utf-8')),
                mimetype='application/json',
                as_attachment=True,
                download_name=filename
            )
        else:
            return jsonify({
                'success': True,
                'data': export_data
            }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Export error',
            'message': str(e)
        }), 500


@api.route('/import', methods=['POST'])
@require_api_key
def import_data():
    """
    Import database data from JSON format
    
    Request Body:
        {
            "data": {
                "users": [...],
                "events": [...]  (optional)
            },
            "mode": "merge" or "replace" (default: "merge"),
            "skip_duplicates": true/false (default: true)
        }
    
    Mode options:
        - merge: Add new records, skip existing ones (based on card_number for users)
        - replace: Clear existing data and import new data
    
    Returns:
        JSON object with import results
    """
    try:
        request_data = request.get_json()
        
        if not request_data:
            return jsonify({
                'success': False,
                'error': 'Invalid request',
                'message': 'Request body must be JSON'
            }), 400
        
        import_data = request_data.get('data')
        if not import_data:
            return jsonify({
                'success': False,
                'error': 'Missing data',
                'message': 'Request must include "data" field'
            }), 400
        
        mode = request_data.get('mode', 'merge')
        skip_duplicates = request_data.get('skip_duplicates', True)
        
        if mode not in ['merge', 'replace']:
            return jsonify({
                'success': False,
                'error': 'Invalid mode',
                'message': 'Mode must be "merge" or "replace"'
            }), 400
        
        results = {
            'users': {'added': 0, 'skipped': 0, 'errors': []},
            'events': {'added': 0, 'skipped': 0, 'errors': []}
        }
        
        # Replace mode: clear existing data
        if mode == 'replace':
            try:
                GlobalEventLog.query.delete()
                CardMemberMapping.query.delete()
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                return jsonify({
                    'success': False,
                    'error': 'Failed to clear existing data',
                    'message': str(e)
                }), 500
        
        # Import users
        users_data = import_data.get('users', [])
        for user_data in users_data:
            try:
                # Check if user exists (by card_number)
                existing_user = CardMemberMapping.query.filter_by(
                    card_number=user_data.get('card_number')
                ).first()
                
                if existing_user and skip_duplicates and mode == 'merge':
                    results['users']['skipped'] += 1
                    continue
                
                # Create new user (id will be auto-generated)
                new_user = CardMemberMapping(
                    card_number=user_data.get('card_number'),
                    name=user_data.get('name'),
                    email=user_data.get('email'),
                    phone=user_data.get('phone'),
                    login=user_data.get('login'),
                    uid=user_data.get('uid'),
                    note=user_data.get('note'),
                    membership_type=user_data.get('membership_type')
                )
                
                db.session.add(new_user)
                results['users']['added'] += 1
                
            except Exception as e:
                results['users']['errors'].append({
                    'card_number': user_data.get('card_number'),
                    'error': str(e)
                })
        
        # Import events if provided
        events_data = import_data.get('events', [])
        for event_data in events_data:
            try:
                # Parse timestamp_utc if it's a string
                timestamp_utc = None
                if event_data.get('timestamp_utc'):
                    timestamp_utc = datetime.datetime.fromisoformat(
                        event_data['timestamp_utc'].replace('Z', '+00:00')
                    )
                
                insert_timestamp_utc = None
                if event_data.get('insert_timestamp_utc'):
                    insert_timestamp_utc = datetime.datetime.fromisoformat(
                        event_data['insert_timestamp_utc'].replace('Z', '+00:00')
                    )
                
                # Check for duplicate events
                if skip_duplicates and mode == 'merge':
                    existing_event = GlobalEventLog.query.filter_by(
                        controller_id=event_data.get('controller_id'),
                        event_id=event_data.get('event_id'),
                        timestamp=event_data.get('timestamp')
                    ).first()
                    
                    if existing_event:
                        results['events']['skipped'] += 1
                        continue
                
                # Create new event (id will be auto-generated)
                new_event = GlobalEventLog(
                    controller_id=event_data.get('controller_id'),
                    event_id=event_data.get('event_id'),
                    timestamp=event_data.get('timestamp'),
                    timestamp_utc=timestamp_utc,
                    card_number=event_data.get('card_number'),
                    event_type=event_data.get('event_type'),
                    event_type_text=event_data.get('event_type_text'),
                    access_granted=event_data.get('access_granted'),
                    door_id=event_data.get('door_id'),
                    direction=event_data.get('direction'),
                    direction_text=event_data.get('direction_text'),
                    event_reason=event_data.get('event_reason'),
                    event_reason_text=event_data.get('event_reason_text'),
                    insert_timestamp_utc=insert_timestamp_utc,
                    name=event_data.get('name'),
                    email=event_data.get('email'),
                    membership_type=event_data.get('membership_type')
                )
                
                db.session.add(new_event)
                results['events']['added'] += 1
                
            except Exception as e:
                results['events']['errors'].append({
                    'event_id': event_data.get('event_id'),
                    'error': str(e)
                })
        
        # Commit all changes
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': 'Failed to commit changes',
                'message': str(e)
            }), 500
        
        return jsonify({
            'success': True,
            'message': 'Import completed',
            'mode': mode,
            'results': results
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Import error',
            'message': str(e)
        }), 500
