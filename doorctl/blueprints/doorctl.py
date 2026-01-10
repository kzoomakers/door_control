# Filename    : makersweb.py
# Author      : Jon Kelley <jon.kelley@kzoomakers.org>
# Description : Kzoomakers Door Controller
import requests
from flask import Flask, render_template, request, flash, Blueprint, redirect, url_for, current_app, jsonify, send_file
import json
import datetime  # Import the datetime module
from doorctl.sharedlib.get_config import parse_uhppoted_config
import time
from dateutil import tz
import subprocess
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import not_
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from passlib.apache import HtpasswdFile
from ..db import db, GlobalEventLog, CardMemberMapping, init_db
import pytz
import io

HEADERS = {'accept': 'application/json'}

doorctl = Blueprint('doorctl', __name__)



@doorctl.before_request
def run_on_all_routes():
    """
    Used to block requests that aren't from a specific server with the known values
    """
    # Require x-forwarded-for header to serve requests
    if current_app.config['ENABLE_PROXY_DETECTION'] == 'true':
        if 'X-Forwarded-For' not in request.headers:
            return 'Must be behind a proxy'
    # Require x-doorcontrol-security-key header with proper value
    if current_app.config['ENABLE_PROXIED_SECURIY_KEY']:
        header = request.headers.get('x-doorcontrol-security-key', None)
        if header:
            if not header == current_app.config['ENABLE_PROXIED_SECURIY_KEY']:
                return 'Invalid key for header x-doorcontrol-security-key'
        else:
            return 'Missing header x-doorcontrol-security-key'



@doorctl.route('/accesscontrol/global/cards')
def globalcards():
    # Query the REST endpoint to get a list of cards

    url = f"{current_app.config['REST_ENDPOINT']}/device"
    response = requests.get(url, headers=HEADERS)

    all_cards = []
    api_config = parse_uhppoted_config('/etc/uhppoted/uhppoted.conf')
    device = {}
    for device_id, deviceproperty in api_config['devices'].items():
        url = f"{current_app.config['REST_ENDPOINT']}/device/{device_id}/cards"
        response = requests.get(url, headers=HEADERS)
        device[device_id] = deviceproperty
        if response.status_code == 200:
            thecardslist = response.json().get("cards")
            device[device_id]['cards'] = thecardslist
            all_cards.append(thecardslist)
        else:
            device[device_id]['cards'] = []
    all_cards_collapsed = []
    for sublist in all_cards:
        all_cards_collapsed.extend(sublist)

    current_app.logger.debug(f'all_cards_collapsed={all_cards_collapsed}')
    # Initialize an empty dictionary to store assigned devices for each card
    assigned_devices = {}

    # Iterate over the keys and values of your_dict and place the devices assigned to each card
    for device_id, device_data in device.items():
        for card_number in device_data['cards']:
            if card_number not in assigned_devices:
                assigned_devices[card_number] = []
            assigned_devices[card_number].append(f"{device_data['name']} ({device_id})")

    current_app.logger.debug(f'assigned_devices={assigned_devices}')
    db_allcards = CardMemberMapping.query.all()
    card_data = {card.card_number: (card.name, card.email, card.membership_type) for card in db_allcards}
    current_app.logger.debug(f'card_data={card_data}')
    # Combine REST and database data to display in the table
    # Use set() to get unique card numbers to prevent duplicates when a card is on multiple controllers
    cards = []
    for card_number in set(all_cards_collapsed):
        assigned_device_list = assigned_devices.get(card_number, [])
        name, email, membership_type = card_data.get(card_number, ("Undefined", "Undefined", "Undefined"))
        cards.append({
            "card_number": card_number,
            "name": name,
            "email": email,
            "membership_type": membership_type,
            "assigned_devices": assigned_device_list
        })


    # find orphan card numbers
    #db_allcards = CardMemberMapping.query.all()
    orphan_cards = []
    db_allcards = CardMemberMapping.query.filter(not_(CardMemberMapping.card_number.in_(all_cards_collapsed)))
    card_data = {card.card_number: (card.card_number, card.name, card.note) for card in db_allcards}
    for entry in db_allcards:
        card_number, name, note = card_data.get(entry, ("Undefined", "Undefined", "Undefined"))
        if card_number not in all_cards_collapsed:
            orphan_cards.append({
                "card_number": entry.card_number,
                "name": entry.name,
                "note": entry.note,
            })

    return render_template('globalcardusers.html', cards=cards, orphan_cards=orphan_cards)


@doorctl.route('/accesscontrol/global/cards/delete/<int:card_number>', methods=['GET', 'POST'])
def globalcards_delete(card_number):
    db.session.query(CardMemberMapping).filter(CardMemberMapping.card_number == card_number).delete()
    db.session.commit()
    return redirect(url_for('doorctl.globalcards'))


@doorctl.route('/accesscontrol/global/cards/delete-all-abandoned', methods=['GET', 'POST'])
def globalcards_delete_all_abandoned():
    """Delete all abandoned cards (cards not assigned to any controller)"""
    try:
        # Get all cards from all controllers
        api_config = parse_uhppoted_config('/etc/uhppoted/uhppoted.conf')
        all_cards_collapsed = []
        
        for device_id, deviceproperty in api_config['devices'].items():
            url = f"{current_app.config['REST_ENDPOINT']}/device/{device_id}/cards"
            response = requests.get(url, headers=HEADERS)
            if response.status_code == 200:
                thecardslist = response.json().get("cards")
                all_cards_collapsed.extend(thecardslist)
        
        # Find and delete orphan cards (cards not in any controller)
        orphan_cards = CardMemberMapping.query.filter(not_(CardMemberMapping.card_number.in_(all_cards_collapsed)))
        deleted_count = orphan_cards.count()
        orphan_cards.delete(synchronize_session=False)
        db.session.commit()
        
        flash(f'Successfully deleted {deleted_count} abandoned card(s)', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting abandoned cards: {str(e)}', 'danger')
    
    return redirect(url_for('doorctl.globalcards') + '#abandoned')






@doorctl.route('/accesscontrol/global/cards/edit/<int:card_id>', methods=['GET', 'POST'])
def globalcards_edit(card_id):
    try:
        card = CardMemberMapping.query.filter_by(card_number=card_id).one()
    except NoResultFound:
        card = CardMemberMapping(card_number=card_id)
    if request.method == 'POST':
        if card is None:
            try:
                # Attempt to retrieve an existing card by card_number
                card = CardMemberMapping.query.filter_by(card_number=card_id).one()
            except NoResultFound:
                # If not found, create a new card
                card = CardMemberMapping(card_number=card_id)

        card.name = request.form['name']
        card.email = request.form['email']
        card.phone = request.form['phone']
        card.note = request.form['note']
        
        # Handle membership_type with "Other" option
        membership_type = request.form.get('membership_type', '')
        if membership_type == 'Other':
            membership_type = request.form.get('membership_type_other', '')
        card.membership_type = membership_type

        try:
            # Merge the card into the session to update or insert
            db.session.merge(card)
            db.session.commit()

            return redirect(url_for('doorctl.globalcards'))

        except Exception as e:
            # Handle other exceptions if necessary
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')

    return render_template('globaleditcardusers.html', card=card)


# @doorctl.route('/accesscontrol/global/cards/edit/<int:card_id>', methods=['GET', 'POST'])
# def globalcards_edit(card_id):
#     card = Card.query.get(card_id)

#     if request.method == 'POST':
#         if card is None:
#             # If the card doesn't exist, create a new one
#             card = Card()

#         card.name = request.form['name']
#         card.email = request.form['email']
#         card.card_number = card_id
#         card.membership_type = request.form['membership_type']

#         # Add or update the card in the database
#         db.session.add(card)
#         db.session.commit()

#         return redirect(url_for('doorctl.globalcards'))

#     return render_template('editcardusers.html', card=card)


@doorctl.route('/accesscontrol/edit/<int:card_id>', methods=['GET', 'POST'])
def edit_card(card_id):
    card = CardMemberMapping.query.get(card_id)
    if request.method == 'POST':
        card.name = request.form['name']
        card.email = request.form['email']
        card.membership_type = request.form['membership_type']
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('editcardusers.html', card=card)


@doorctl.route('/robots.txt')
@doorctl.route('/<path:subpath>/robots.txt')
def generate_robots_txt():
    robots_txt_content = "User-agent: *\nDisallow: /"
    return Response(robots_txt_content, content_type="text/plain")


@doorctl.route('/', methods=['GET'])
def index():
    return 'It works!'

### config editor ###
@doorctl.route('/accesscontrol/configedit')
def config_edit():
    with open('/etc/uhppoted/uhppoted.conf', 'r') as file:
        content = file.read()
    return render_template('configedit.html', content=content)

@doorctl.route('/accesscontrol/configedit/save', methods=['POST'])
def config_save():
    content = request.form.get('content')
    with open('/etc/uhppoted/uhppoted.conf', 'w') as file:
        file.write(content)
    #flash("File saved successfully!")
    return redirect('/accesscontrol/configedit')

##### controller routes #####

@doorctl.route('/accesscontrol', methods=['GET'])
@doorctl.route('/accesscontrol/', methods=['GET'])
def accesscontrol():
    return render_template('splash.html')


@doorctl.route('/accesscontrol/controller', methods=['GET'])
@doorctl.route('/accesscontrol/controller/', methods=['GET'])
def controllers_list():
    # Fetch the device time from the API
    url = f"{current_app.config['REST_ENDPOINT']}/device"
    response = requests.get(url, headers=HEADERS)

    api_config = parse_uhppoted_config('/etc/uhppoted/uhppoted.conf')
    print(api_config)
    if response.status_code == 200:
        data = response.json()
        for device in data['devices']:
            device_id = device['device-id']

            # Check if the device_id exists in 'api_config'
            if str(device_id) in api_config['devices']:
                # If it exists, update the device information in 'data'
                device_info = api_config['devices'][str(device_id)]
                device.update(device_info)
        print(data)
        return render_template('controllers.html', devices=data.get('devices', []))


##### door stuff #####

@doorctl.route('/accesscontrol/controller/<int:controller_id>/door/<int:door>/swipe', methods=['POST'])
def swipe_card(controller_id, door):
    card_number = request.json.get('card-number')
    try:
        url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/door/{door}/swipes"
        response = requests.post(url, json={"card-number": int(card_number)})
        if response.status_code in [401, 404, 405, 500]:
            error_data = response.json()
            # Flashing the error for the JS to pick up
            #flash(error_data.get('message'), 'error')
            return json.dumps({"error": "API error", "message": error_data.get('message')}), 500
        return json.dumps(response.json())
    except requests.RequestException as e:
            return json.dumps({"error": "API error"}), 500
    except Exception as e:
            return json.dumps({"error": "Unknown error", "message": f"{e}"}), 500

@doorctl.route('/accesscontrol/controller/<int:controller_id>/door/<int:door>/delay', methods=['PUT'])
def set_door_delay(controller_id, door):
    delay_time = request.json.get('delay')
    try:
        payload = {"delay": int(delay_time)}

        url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/door/{door}/delay"
        response = requests.put(url, json=payload)
        #response = requests.put(REMOTE_API_DELAY_URL.format(device_id, door), json={"delay": delay_time})
        response.raise_for_status()
        return json.dumps(response.json())
    except requests.RequestException as e:
        # Flashing the error for the JS to pick up
        #flash(str(e), 'error')
        return json.dumps({"error": f"API error, {e}"}), 500

@doorctl.route('/accesscontrol/controller/<int:controller_id>/door/<int:door>/state', methods=['PUT'])
def set_door_control(controller_id, door):
    control_state = request.json.get('control')
    try:
        url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/door/{door}/control"
        response = requests.put(url, json={"control": control_state})
        response.raise_for_status()
        return json.dumps(response.json())
    except requests.RequestException as e:
        # Flashing the error for the JS to pick up
        #flash(str(e), 'error')
        return json.dumps({"error": f"API error, {e}"}), 500


@doorctl.route('/accesscontrol/controller/<int:controller_id>/doors')
def manage_doors(controller_id):

    # Fetch device status
    url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/status"
    response = requests.get(url)
    if response.status_code == 200:
        device_status = response.json()
    else:
        device_status = {}
        flash(f"Failed to retrieve device status. Status code: {response.status_code}", "danger")

    # Fetch door details for each door
    door_info = {}
    for door_id in device_status.get('status', {}).get('door-states', {}):
        url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/door/{door_id}"
        response = requests.get(url)
        if response.status_code == 200:
            door_info[door_id] = response.json().get('door', {})
        else:
            flash(f"Failed to retrieve door {door_id} details. Status code: {response.status_code}", "danger")

    return render_template('doors.html', controller_id=controller_id, device_status=device_status, door_info=door_info)

##### device info #####
@doorctl.route('/accesscontrol/controller/<int:controller_id>/info')
def display_device_info(controller_id):
    url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/status"
    response = requests.get(url)
    if response.status_code == 200:
        device_status = response.json()
    else:
        device_status = {}
        flash(f"Failed to retrieve device status. Status code: {response.status_code}", "danger")
    url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}"
    response = requests.get(url)
    if response.status_code == 200:
        device_info = response.json()
    else:
        device_info = {}
        flash(f"Failed to retrieve device status. Status code: {response.status_code}", "danger")
    return render_template('controller_info.html', controller_id=controller_id, device_status=device_status, device_info=device_info)



##### events #####

##### events #####

def get_events(device_id, page=1, per_page=50):
    """
    Get events with pagination support
    
    Args:
        device_id: The device ID to get events for
        page: Page number (1-based)
        per_page: Number of events per page
    """
    # Get range of events
    url = f"{current_app.config['REST_ENDPOINT']}/device/{device_id}/events/1000"
    print(f'getting events list {url}')
    response = requests.get(url, headers={'accept': 'application/json'})
    response_data = response.json()

    first_event = response_data['events']['first']
    last_event = response_data['events']['last']
    total_events = last_event - first_event + 1

    # Calculate pagination
    total_pages = (total_events + per_page - 1) // per_page  # Ceiling division
    
    # Calculate which events to fetch for this page
    start_index = (page - 1) * per_page
    end_index = min(start_index + per_page, total_events)
    
    # Convert to actual event IDs (counting backwards from last_event)
    start_event_id = last_event - start_index
    end_event_id = last_event - end_index + 1

    events = []
    db_cards = CardMemberMapping.query.all()
    card_data = {card.card_number: (card.name, card.email, card.membership_type) for card in db_cards}
    
    # Fetch only the events for this page
    for i in range(start_event_id, end_event_id - 1, -1):
        url = f"{current_app.config['REST_ENDPOINT']}/device/{device_id}/event/{i}"
        response = requests.get(url, headers={'accept': 'application/json'})
        event_data = response.json()

        name, email, membership_type = card_data.get(event_data["event"]["card-number"], ("Undefined", "Undefined", "Undefined"))
        event_dict = {
            "device-id": event_data["event"]["device-id"],
            "name": name,
            "email": email,
            "membership-type": membership_type,
            "event-id": event_data["event"]["event-id"],
            "event-type": event_data["event"]["event-type"],
            "event-type-text": event_data["event"]["event-type-text"],
            "access-granted": event_data["event"]["access-granted"],
            "door-id": event_data["event"]["door-id"],
            "direction": event_data["event"]["direction"],
            "direction-text": event_data["event"]["direction-text"],
            "card-number": event_data["event"]["card-number"],
            "timestamp": event_data["event"]["timestamp"],
            "event-reason": event_data["event"]["event-reason"],
            "event-reason-text": event_data["event"]["event-reason-text"]
        }
        events.append(event_dict)

    return {
        "events": events,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total_events,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "prev_page": page - 1 if page > 1 else None,
            "next_page": page + 1 if page < total_pages else None
        }
    }

@doorctl.route('/accesscontrol/get_events_in_log_by_doors/controller/<int:controller_id>/doors/<string:door_ids>', methods=['GET'])
def get_events_in_log_by_doors(controller_id, door_ids):
    door_ids = door_ids.split(',')
    door_ids = [int(door_id) for door_id in door_ids]
    try:
        events = GlobalEventLog.query.all()
        events_data = []

        for event in events:
            if (event.controller_id == controller_id) and (event.door_id in door_ids):
                event_dict = {
                    "controller_id": event.controller_id,
                    "insert_timestamp_utc": event.insert_timestamp_utc,
                    "event_id": event.event_id,
                    "timestamp_utc": event.timestamp_utc,
                    "timestamp": event.timestamp,
                    "card_number": event.card_number,
                    "event_type": event.event_type,
                    "event_type_text": event.event_type_text,
                    "access_granted": event.access_granted,
                    "door_id": event.door_id,
                    "direction": event.direction,
                    "direction_text": event.direction_text,
                    "event_reason": event.event_reason,
                    "event_reason_text": event.event_reason_text,
                    "name": event.name,
                    "email": event.email,
                    "membership_type": event.membership_type,
                }
                events_data.append(event_dict)


        return jsonify(events=events_data)
    except Exception as e:
        return jsonify(message=f'Error: {str(e)}'), 500



@doorctl.route('/accesscontrol/store_events_in_log', methods=['GET'])
def store_events_in_log():
    api_config = parse_uhppoted_config('/etc/uhppoted/uhppoted.conf')
    device = {}
    db_cards = CardMemberMapping.query.all()
    card_data = {card.card_number: (card.name, card.email, card.membership_type) for card in db_cards}
    for controller_id, deviceproperty in api_config['devices'].items():
        try:
            events_data = get_events(controller_id)

            event_count=0
            event_dupe_count=0
            for event_dict in events_data['events']:
                name, email, membership_type = card_data.get(event_dict.get("card-number"), ("Undefined", "Undefined", "Undefined"))
                event_count += 1
                print(event_dict)
                # Check if an identical entry already exists in the database
                existing_entry = GlobalEventLog.query.filter_by(
                    controller_id=controller_id,
                    event_id=event_dict.get("event-id"),
                    timestamp=event_dict.get("timestamp"),
                    card_number=event_dict.get("card-number"),
                    event_type=event_dict.get("event-type"),
                    event_type_text=event_dict.get("event-type-text"),
                    access_granted=event_dict.get("access-granted"),
                    door_id=event_dict.get("door-id"),
                    direction=event_dict.get("direction"),
                    direction_text=event_dict.get("direction-text"),
                    event_reason=event_dict.get("event-reason"),
                    event_reason_text=event_dict.get("event-reason-text")
                ).first()
                print(f'entry={existing_entry}')

                if not existing_entry and (name != "Undefined"):
                    source_timestamp = event_dict.get("timestamp", "")
                    current_app.logger.warning(f'source_timestamp={source_timestamp}')
                    source_datetime = datetime.datetime.strptime(source_timestamp, "%Y-%m-%d %H:%M:%S %Z")
                    current_app.logger.warning(f'source_datetime={source_datetime}')
                    source_datetime_utc = source_datetime.astimezone(pytz.utc)
                    current_app.logger.warning(f'source_datetime_utc={source_datetime_utc}')

                    new_event = GlobalEventLog(
                        controller_id=controller_id,
                        event_id=event_dict.get("event-id", 0),
                        timestamp=event_dict.get("timestamp", ""),
                        timestamp_utc=source_datetime_utc,
                        card_number=event_dict.get("card-number", 0),
                        event_type=event_dict.get("event-type", 0),
                        event_type_text=event_dict.get("event-type-text", ""),
                        access_granted=event_dict.get("access-granted", False),
                        door_id=event_dict.get("door-id", 0),
                        direction=event_dict.get("direction", 1),
                        direction_text=event_dict.get("direction-text", ""),
                        event_reason=event_dict.get("event-reason", 0),
                        event_reason_text=event_dict.get("event-reason-text", ""),
                        name=event_dict.get("name", ""),
                        email=event_dict.get("email", ""),
                        membership_type=event_dict.get("membership_type", "")
                    )

                    db.session.add(new_event)
                else:
                    event_dupe_count += 1
                    current_app.logger.warning(f'store_events_in_log : ignoring existing entry from controller: {controller_id} event-id: {event_dict["event-id"]} timestamp: {event_dict["timestamp"]}')

            db.session.commit()
            return jsonify(message=f'Events stored successfully, {event_dupe_count} out of {event_count} events were ignored duplicates.'), 201
        except Exception as e:
            return jsonify(message=f'Error: {str(e)}'), 500


@doorctl.route('/accesscontrol/get_events_in_log', methods=['GET'])
def get_events_in_log():
    try:
        events = GlobalEventLog.query.all()
        events_data = []

        for event in events:
            event_dict = {
                "controller_id": event.controller_id,
                "insert_timestamp_utc": event.insert_timestamp_utc,
                "event_id": event.event_id,
                "timestamp_utc": event.timestamp_utc,
                "timestamp": event.timestamp,
                "card_number": event.card_number,
                "event_type": event.event_type,
                "event_type_text": event.event_type_text,
                "access_granted": event.access_granted,
                "door_id": event.door_id,
                "direction": event.direction,
                "direction_text": event.direction_text,
                "event_reason": event.event_reason,
                "event_reason_text": event.event_reason_text,
                "name": event.name,
                "email": event.email,
                "membership_type": event.membership_type,
            }
            events_data.append(event_dict)

        return jsonify(events=events_data)
    except Exception as e:
        return jsonify(message=f'Error: {str(e)}'), 500



@doorctl.route('/accesscontrol/controller/<int:controller_id>/events')
def device_events(controller_id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Limit per_page to prevent abuse
    per_page = min(per_page, 10000)
    
    event_data = get_events(device_id=controller_id, page=page, per_page=per_page)
    return render_template('events.html', events=event_data, controller_id=controller_id)


##### time profiles #####
@doorctl.route("/accesscontrol/controller//<int:controller_id>/add_time_profile", methods=["GET", "POST"])
def add_time_profile(controller_id):
    if request.method == "GET":
        # Get all controllers from config
        api_config = parse_uhppoted_config('/etc/uhppoted/uhppoted.conf')
        controllers = []
        for ctrl_id, ctrl_info in api_config['devices'].items():
            controllers.append({
                'id': ctrl_id,
                'name': ctrl_info.get('name', f'Controller {ctrl_id}')
            })
        
        # Get existing time profiles to find the next available ID
        url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/time-profiles"
        response = requests.get(url)
        
        next_profile_id = 2  # Start from 2 (1 is reserved)
        if response.status_code == 200:
            time_profiles_data = response.json()
            existing_ids = set()
            
            # Collect all existing profile IDs that are actually in use
            # (not expired or with empty time segments)
            for profile in time_profiles_data.get('profiles', []):
                # Check if profile is actually in use (not a "deleted" one)
                if profile.get('weekdays') and profile.get('weekdays') != '':
                    # Check if it's not expired
                    end_date_str = profile.get('end-date', '')
                    if end_date_str:
                        try:
                            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
                            if end_date >= datetime.date.today():
                                existing_ids.add(profile['id'])
                        except:
                            existing_ids.add(profile['id'])
            
            # Find the next available ID
            for i in range(2, 255):  # Profile IDs are 2-254
                if i not in existing_ids:
                    next_profile_id = i
                    break
            else:
                # All IDs are taken
                flash("Maximum number of time profiles reached (254). Please delete an existing profile first.", "danger")
                return redirect(url_for("doorctl.get_time_profiles", controller_id=controller_id))
        
        return render_template("add_time_profile.html", controller_id=controller_id, next_profile_id=next_profile_id, controllers=controllers)
    
    if request.method == "POST":
        day_mapping = {
            "Mon": "Monday",
            "Tue": "Tuesday",
            "Tues": "Tuesday",
            "Wed": "Wednesday",
            "Weds": "Wednesday",
            "Thur": "Thursday",
            "Thurs": "Thursday",
            "Fri": "Friday",
            "Sat": "Saturday",
            "Sun": "Sunday"
        }

        # Split the input string into a list of day names while removing spaces
        weekdays = request.form.get("weekdays").replace(" ", "").split(",")

        # Use the dictionary to expand abbreviated day names to full day names
        finalized_days = []
        for day in weekdays:
            finalized_days.append(day_mapping.get(day.strip(), day.strip()))

        finalized_days = ",".join(finalized_days)
        # Handle form submission for creating a new time profile
        time_profile_id = request.form.get("time_profile_id")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        segment_start = request.form.get("segment_start")
        segment_end = request.form.get("segment_end")

        # Get selected controllers
        selected_controllers = request.form.getlist("controllers")
        if not selected_controllers:
            flash("Please select at least one controller.", "warning")
            return redirect(url_for("doorctl.add_time_profile", controller_id=controller_id))

        # Create a dictionary with the time profile data
        time_profile_data = {
            "id": int(time_profile_id),
            "start-date": start_date,
            "end-date": end_date,
            "weekdays": finalized_days,
        }
        time_profile_data['segments'] = [{"start": segment_start, "end": segment_end}, {'start': '00:00', 'end': '00:00'}, {'start': '00:00', 'end': '00:00'}]

        # Apply to all selected controllers
        success_count = 0
        failed_controllers = []
        
        for ctrl_id in selected_controllers:
            url = f"{current_app.config['REST_ENDPOINT']}/device/{ctrl_id}/time-profile/{time_profile_id}"
            response = requests.put(url, json=time_profile_data)
            
            if response.status_code == 200:
                success_count += 1
            else:
                failed_controllers.append(ctrl_id)
        
        # Show results
        if success_count > 0:
            flash(f"Time profile created successfully on {success_count} controller(s).", "success")
        if failed_controllers:
            flash(f"Failed to create time profile on controller(s): {', '.join(failed_controllers)}", "danger")
        
        return redirect(url_for("doorctl.get_time_profiles", controller_id=controller_id))

    return render_template("add_time_profile.html", controller_id=controller_id)


# @doorctl.route("/accesscontrol/controller//<int:controller_id>/add_time_profile", methods=["GET", "POST"])
# def add_time_profile(controller_id):
#     if request.method == "POST":
#         # Handle form submission for creating a new time profile
#         time_profile_id = request.form.get("time_profile_id")
#         start_date = request.form.get("start_date")
#         end_date = request.form.get("end_date")
#         weekdays = request.form.get("weekdays")
#         segment_start = request.form.get("segment_start")
#         segment_end = request.form.get("segment_end")

#         # Create a dictionary with the time profile data
#         time_profile_data = {
#             "id": int(time_profile_id),  # Include the time profile ID
#             "start-date": start_date,
#             "end-date": end_date,
#             "weekdays": weekdays,
#         }
#         time_profile_data['segments'] = [{"start": segment_start, "end": segment_end}]
#         # additional_segments = [
#         #     {"start": "00:00", "end": "00:00"},
#         #     {"start": "00:00", "end": "00:00"}
#         # ]
#         # time_profile_data['segments'].extend(additional_segments)
#         import json
#         print(json.dumps(time_profile_data, indent=3))
#         # Make a POST request to create the time profile

#         url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/time-profile/{time_profile_id}"
#         response = requests.put(
#             url, json=time_profile_data
#         )
#         if response.status_code == 200:
#             flash("Time profile created successfully.", "success")
#             return redirect(url_for("doorctl.get_time_profiles", controller_id=controller_id))
#         else:
#             flash("Failed to create time profile. Please check your input and try again.", "danger")

#     return render_template("add_time_profile.html", controller_id=controller_id)

@doorctl.route("/accesscontrol/controller/<int:controller_id>/time_profiles", methods=["GET"])
def get_time_profiles(controller_id):
    # Make a GET request to retrieve the list of time profiles for the device
    url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/time-profiles"
    response = requests.get(url)

    if response.status_code == 200:
        time_profiles_data = response.json()
        print(time_profiles_data)
        return render_template("get_time_profiles.html", controller_id=controller_id, time_profiles=time_profiles_data)
    else:
        flash(f"Failed to retrieve time profiles. Status code: {response.status_code}", "danger")

    return render_template("get_time_profiles.html", controller_id=controller_id)


@doorctl.route("/accesscontrol/controller/<int:controller_id>/time_profile/<int:profile_id>/edit", methods=["GET", "POST"])
def edit_time_profile(controller_id, profile_id):
    # Protect profile 1 from being edited
    if profile_id == 1:
        flash("Profile 1 is hardcoded and cannot be edited.", "warning")
        return redirect(url_for("doorctl.get_time_profiles", controller_id=controller_id))
    
    # GET request - fetch existing profile data and controller list
    if request.method == "GET":
        # Get all controllers from config
        api_config = parse_uhppoted_config('/etc/uhppoted/uhppoted.conf')
        controllers = []
        for ctrl_id, ctrl_info in api_config['devices'].items():
            controllers.append({
                'id': ctrl_id,
                'name': ctrl_info.get('name', f'Controller {ctrl_id}')
            })
        
        url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/time-profile/{profile_id}"
        response = requests.get(url)
        
        if response.status_code == 200:
            profile_data = response.json().get('time-profile', {})
            return render_template("edit_time_profile.html", controller_id=controller_id, profile_id=profile_id, profile=profile_data, controllers=controllers)
        else:
            flash(f"Failed to retrieve time profile. Status code: {response.status_code}", "danger")
            return redirect(url_for("doorctl.get_time_profiles", controller_id=controller_id))
    
    if request.method == "POST":
        day_mapping = {
            "Mon": "Monday",
            "Tue": "Tuesday",
            "Tues": "Tuesday",
            "Wed": "Wednesday",
            "Weds": "Wednesday",
            "Thur": "Thursday",
            "Thurs": "Thursday",
            "Fri": "Friday",
            "Sat": "Saturday",
            "Sun": "Sunday"
        }

        # Process weekdays
        weekdays = request.form.get("weekdays").replace(" ", "").split(",")
        finalized_days = []
        for day in weekdays:
            finalized_days.append(day_mapping.get(day.strip(), day.strip()))
        finalized_days = ",".join(finalized_days)

        # Get form data
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        segment_start = request.form.get("segment_start")
        segment_end = request.form.get("segment_end")

        # Get selected controllers
        selected_controllers = request.form.getlist("controllers")
        if not selected_controllers:
            flash("Please select at least one controller.", "warning")
            return redirect(url_for("doorctl.edit_time_profile", controller_id=controller_id, profile_id=profile_id))

        # Create time profile data
        time_profile_data = {
            "id": profile_id,
            "start-date": start_date,
            "end-date": end_date,
            "weekdays": finalized_days,
        }
        time_profile_data['segments'] = [
            {"start": segment_start, "end": segment_end},
            {'start': '00:00', 'end': '00:00'},
            {'start': '00:00', 'end': '00:00'}
        ]

        # Apply to all selected controllers
        success_count = 0
        failed_controllers = []
        
        for ctrl_id in selected_controllers:
            url = f"{current_app.config['REST_ENDPOINT']}/device/{ctrl_id}/time-profile/{profile_id}"
            response = requests.put(url, json=time_profile_data)
            
            if response.status_code == 200:
                success_count += 1
            else:
                failed_controllers.append(ctrl_id)
        
        # Show results
        if success_count > 0:
            flash(f"Time profile updated successfully on {success_count} controller(s).", "success")
        if failed_controllers:
            flash(f"Failed to update time profile on controller(s): {', '.join(failed_controllers)}", "danger")
        
        return redirect(url_for("doorctl.get_time_profiles", controller_id=controller_id))


@doorctl.route("/accesscontrol/controller/<int:controller_id>/time_profile/<int:profile_id>/delete", methods=["POST"])
def delete_time_profile(controller_id, profile_id):
    # Protect profile 1 from being deleted
    if profile_id == 1:
        flash("Profile 1 is hardcoded and cannot be deleted.", "warning")
        return redirect(url_for("doorctl.get_time_profiles", controller_id=controller_id))
    
    try:
        # Clear the time profile by setting it to an expired/inactive state
        # We use a past date range and minimal weekdays to effectively disable it
        time_profile_data = {
            "id": profile_id,
            "start-date": "2000-01-01",
            "end-date": "2000-01-02",
            "weekdays": "Monday",  # Required field, cannot be empty
            "segments": [
                {'start': '00:00', 'end': '00:00'}
            ]
        }
        
        url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/time-profile/{profile_id}"
        response = requests.put(url, json=time_profile_data)
        
        if response.status_code == 200:
            flash(f"Time profile {profile_id} deleted successfully.", "success")
        else:
            error_msg = response.json().get('message', 'Unknown error') if response.headers.get('content-type') == 'application/json' else response.text
            flash(f"Failed to delete time profile {profile_id}: {error_msg}", "danger")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    
    return redirect(url_for("doorctl.get_time_profiles", controller_id=controller_id))


##### cards #####

def get_door_states(controller_id):
    # Query door states
    url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/status"
    status_response = requests.get(url)

    if status_response.status_code == 200:
        status_data = status_response.json()
        door_states = status_data['status']['door-states']
    else:
        door_states = {}
    return door_states

def get_time_profiles(controller_id):
    # Make a GET request to retrieve the list of time profiles for the device
    url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/time-profiles"
    response_timeprofile = requests.get(url)

    if response_timeprofile.status_code == 200:
        time_profiles_data = response_timeprofile.json()
    return time_profiles_data

@doorctl.route('/accesscontrol/controller/<int:controller_id>/cards', methods=['GET'])
@doorctl.route('/accesscontrol/controller/<int:controller_id>/card', methods=['GET'])
def show_cards(controller_id):
    door_states = get_door_states(controller_id)


    db_cards = CardMemberMapping.query.all()
    card_data = {card.card_number: (card.name, card.email, card.membership_type, card.note) for card in db_cards}

    # Fetch the list of cards from the API
    url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/cards"
    response = requests.get(url)
    data = {}
    deactivated_data = {}
    
    if response.status_code == 200:
        for card_number in response.json()['cards']:
            if card_number in card_data:
                name, email, membership_type, note = card_data[card_number]
            else:
                name, email, membership_type, note = ("Undefined", "Undefined", "Undefined", None)
            
            # Check if card is deactivated by fetching its door permissions
            card_url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/card/{card_number}"
            card_response = requests.get(card_url)
            is_deactivated = False
            
            if card_response.status_code == 200:
                card_details = card_response.json()['card']
                doors = card_details.get('doors', {})
                # Check if all doors are set to 0 (deny) - API uses 0=deny, 1=allow
                if doors and all(value == 0 for value in doors.values()):
                    is_deactivated = True
            
            card_info = {"name": name, "email": email, "membership_type": membership_type, "note": note}
            
            if is_deactivated:
                deactivated_data[card_number] = card_info
            else:
                data[card_number] = card_info

    time_profile_data = get_time_profiles(controller_id)

    return render_template('cards.html', time_profiles_data=time_profile_data, door_states=door_states, card_data=data, deactivated_data=deactivated_data, controller_id=controller_id)


@doorctl.route('/accesscontrol/controller/<int:controller_id>/card/<int:card_number>/show', methods=['GET'])
def get_card(controller_id, card_number):
    url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/card/{card_number}"
    response = requests.get(url)
    
    # Fetch user data from database
    try:
        card_user = CardMemberMapping.query.filter_by(card_number=card_number).first()
        user_data = {
            'name': card_user.name if card_user else 'Undefined',
            'email': card_user.email if card_user else 'Undefined',
            'membership_type': card_user.membership_type if card_user else 'Undefined',
            'note': card_user.note if card_user else None
        }
    except Exception as e:
        user_data = {
            'name': 'Undefined',
            'email': 'Undefined',
            'membership_type': 'Undefined',
            'note': None
        }
    
    return render_template('get_card.html', controller_id=controller_id, card_data=response.json()['card'], user_data=user_data)


@doorctl.route('/accesscontrol/controller/<int:controller_id>/card/<int:card_number>/edit', methods=['GET', 'POST'])
def edit_card_on_controller(controller_id, card_number):
    if request.method == 'POST':
        # Update controller-specific card data
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        doors = request.form.getlist('doors')
        pin = request.form['pin']

        # Create card data for controller
        card_data = {
            'card-number': int(card_number),
            'start-date': start_date,
            'end-date': end_date,
            'pin': int(pin) if pin != '' else None
        }
        card_data['doors'] = {}

        for i, value in enumerate(doors, start=1):
            if value == '0':
                card_data['doors'][str(i)] = 1
            elif value == '1':
                card_data['doors'][str(i)] = 0
            else:
                card_data['doors'][str(i)] = int(value)

        # Update card on controller
        url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/card/{card_number}"
        response = requests.put(url, json=card_data)
        
        if response.status_code == 200:
            flash(f'Card {card_number} updated successfully on controller', 'success')
        else:
            error_message = response.json().get('message', 'Error updating card')
            flash(f'Card {card_number} failed to update: {error_message}', 'danger')

        # Update global metadata
        try:
            card_user = CardMemberMapping.query.filter_by(card_number=card_number).one_or_none()
            if card_user is None:
                card_user = CardMemberMapping(card_number=card_number)
            
            card_user.name = request.form['name']
            card_user.email = request.form['email']
            card_user.phone = request.form.get('phone', '')
            card_user.note = request.form.get('note', '')
            
            # Handle membership_type with "Other" option
            membership_type = request.form.get('membership_type', '')
            if membership_type == 'Other':
                membership_type = request.form.get('membership_type_other', '')
            card_user.membership_type = membership_type
            
            db.session.merge(card_user)
            db.session.commit()
            flash('Card metadata updated successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating card metadata: {str(e)}', 'danger')

        return redirect(url_for('doorctl.show_cards', controller_id=controller_id))

    # GET request - fetch card data
    url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/card/{card_number}"
    response = requests.get(url)
    
    if response.status_code != 200:
        flash(f'Failed to retrieve card {card_number} from controller', 'danger')
        return redirect(url_for('doorctl.show_cards', controller_id=controller_id))
    
    card_data = response.json()['card']
    
    # Fetch user data from database
    try:
        card_user = CardMemberMapping.query.filter_by(card_number=card_number).first()
        user_data = {
            'name': card_user.name if card_user else '',
            'email': card_user.email if card_user else '',
            'phone': card_user.phone if card_user else '',
            'note': card_user.note if card_user else '',
            'membership_type': card_user.membership_type if card_user else ''
        }
    except Exception as e:
        user_data = {
            'name': '',
            'email': '',
            'phone': '',
            'note': '',
            'membership_type': ''
        }
    
    # Get door states and time profiles
    door_states = get_door_states(controller_id)
    time_profile_data = get_time_profiles(controller_id)
    
    return render_template('edit_card.html',
                         controller_id=controller_id,
                         card_data=card_data,
                         user_data=user_data,
                         door_states=door_states,
                         time_profiles_data=time_profile_data)


@doorctl.route('/accesscontrol/controller/<int:controller_id>/add_card', methods=['POST'])
def add_card(controller_id):
    door_states = get_door_states(controller_id)
    # Extract card details from the form data
    card_number = request.form['card_number']
    start_date = request.form['start_date']
    end_date = request.form['end_date']
    #doors = request.form['doors']
    doors = request.form.getlist('doors')
    pin = request.form['pin']

    # Create a card object to send to the API
    card_data = {
        'card-number': int(card_number),
        'start-date': start_date,
        'end-date': end_date,
        # 'doors': {"1":True,"2":False,"3":False,"4":True},
        'pin': int(pin) if pin != '' else None
    }
    card_data['doors'] = {}

    for i, value in enumerate(doors, start=1):
        if value == '0':
            card_data['doors'][str(i)] = 1
        elif value == '1':
            card_data['doors'][str(i)] = 0
        else:
            card_data['doors'][str(i)] = int(value)

    # Send a PUT request to add the card
    url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/card/{card_number}"
    response = requests.put(url, json=card_data)
    if response.status_code == 200:
        flash(f'Card {card_number} added successfully to controller', 'success')
        
        # Save global metadata to database
        try:
            card_user = CardMemberMapping.query.filter_by(card_number=int(card_number)).one_or_none()
            if card_user is None:
                card_user = CardMemberMapping(card_number=int(card_number))
            
            card_user.name = request.form.get('name', '')
            card_user.email = request.form.get('email', '')
            card_user.phone = request.form.get('phone', '')
            card_user.note = request.form.get('note', '')
            
            # Handle membership_type with "Other" option
            membership_type = request.form.get('membership_type', '')
            if membership_type == 'Other':
                membership_type = request.form.get('membership_type_other', '')
            card_user.membership_type = membership_type
            
            db.session.merge(card_user)
            db.session.commit()
            flash('Card metadata saved successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving card metadata: {str(e)}', 'warning')
    else:
        error_message = response.json().get('message', 'Error adding card')
        response = response.json()['message']
        flash(
            f'Card {card_number} failed to add, server response: {response}', 'danger')

    url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/cards"
    response = requests.get(url)
    db_cards = CardMemberMapping.query.all()
    card_data = {card.card_number: (card.name, card.email, card.membership_type) for card in db_cards}

    data = {}
    if response.status_code == 200:
        for card_number in response.json()['cards']:
            if card_number in card_data:
                name, email, membership_type = card_data[card_number]
            else:
                name, email, membership_type = ("", "", "")
            data[card_number] = {"name": name, "email": email, "membership-type": membership_type}

    time_profile_data = get_time_profiles(controller_id)
    return render_template('cards.html', time_profiles_data=time_profile_data, door_states=door_states, controller_id=controller_id, card_data=data)


@doorctl.route('/accesscontrol/controller/<int:controller_id>/delete_card', methods=['POST'])
def delete_card(controller_id):
    card_number = request.form['card_number']
    print(card_number)
    try:
        # Send a DELETE request to delete the card from the controller only
        # Do NOT delete from database - card metadata should persist across controllers
        url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/card/{card_number}"
        response = requests.delete(url)
        if response.status_code == 200:
            flash('Card deleted successfully from controller', 'success')
        else:
            flash('Failed to delete card from controller', 'danger')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('doorctl.show_cards', controller_id=controller_id))


@doorctl.route('/accesscontrol/controller/<int:controller_id>/card/<int:card_number>/delete', methods=['GET', 'POST'])
def delete_card_user(controller_id, card_number):
    """Delete a specific card from a controller (does not delete global metadata)"""
    try:
        # Send a DELETE request to delete the card from the controller only
        # Do NOT delete from database - card metadata should persist across controllers
        url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/card/{card_number}"
        response = requests.delete(url)
        if response.status_code == 200:
            flash(f'Card {card_number} deleted successfully from controller', 'success')
        else:
            flash(f'Failed to delete card {card_number} from controller', 'danger')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('doorctl.show_cards', controller_id=controller_id))


@doorctl.route('/accesscontrol/controller/<int:controller_id>/deactivate_card', methods=['POST'])
def deactivate_card(controller_id):
    card_number = request.form['card_number']
    try:
        # First, get the current card data
        url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/card/{card_number}"
        response = requests.get(url)
        
        if response.status_code == 200:
            card_data = response.json()['card']
            
            # Update the card with all relays set to deny (API uses 0=deny, 1=allow)
            # Set all door permissions to 0 (deny)
            card_data['doors'] = {
                '1': 0,  # Relay 1 - Deny
                '2': 0,  # Relay 2 - Deny
                '3': 0,  # Relay 3 - Deny
                '4': 0   # Relay 4 - Deny
            }
            
            # Send a PUT request to update the card
            url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/card/{card_number}"
            response = requests.put(url, json=card_data)
            
            if response.status_code == 200:
                flash(f'Card {card_number} deactivated successfully (all relays set to DENY)', 'success')
            else:
                flash(f'Failed to deactivate card {card_number}', 'danger')
        else:
            flash(f'Failed to retrieve card {card_number} data', 'danger')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('doorctl.show_cards', controller_id=controller_id))


@doorctl.route('/accesscontrol/controller/<int:controller_id>', methods=['GET'])
@doorctl.route('/accesscontrol/controller/<int:controller_id>/', methods=['GET'])
def controller_manage(controller_id):
    # Fetch the device time from the API
    event = None
    try:
        url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/event/last"
        response = requests.get(url, headers={'accept': 'application/json'})
        event = response.json().get('event')
    except ValueError:
        # There's an issue with the response format (e.g., not a valid JSON)
        pass
    return render_template('controller_manage.html', event=event, controller_id=controller_id)


##### time routes #####
@doorctl.route('/accesscontrol/controller/<int:controller_id>/get_time', methods=['GET'])
def get_device_time(controller_id):
    # Fetch the device time from the API
    url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/time"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        device_time = response.json()
        return f"Device current time: {device_time['datetime']}"
    elif response.status_code == 500:
        error = response.json()['message']
        error_message = f'Error getting time: {error}'
        return error_message

@doorctl.route('/accesscontrol/ajax/get_server_time')
# def get_server_time():
#     server_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     return json.dumps({"server_time": server_time})
def get_server_local_time():
    # Get the current local time that's timezone-aware
    local_time = datetime.datetime.now(tz=tz.tzlocal())

    # Return the formatted local time
    return json.dumps({"server_time": local_time.strftime("%Y-%m-%d %H:%M:%S")})

@doorctl.route('/accesscontrol/controller/<int:controller_id>/set_time', methods=['POST', 'GET'])
def set_device_time(controller_id):
    # Get the current date and time as a string
    server_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/time"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        current_device_time = response.json()['datetime']

    if request.method == 'POST':
        set_to_server_time = request.form.get('setToServerTime')  # Check if checkbox is checked

        if set_to_server_time:
            device_datetime = datetime.datetime.strptime(
                server_datetime, '%Y-%m-%d %H:%M:%S')  # Convert server_datetime to a datetime object
        else:
            # Get the datetime input from the form
            datetime_str = request.form.get('datetime')

            # Convert the input string to a datetime object
            try:
                device_datetime = datetime.datetime.strptime(
                    datetime_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                flash("Invalid datetime format. Please use 'YYYY-MM-DD HH:MM:SS'", 'danger')
                return render_template('set_device_time.html', controller_id=controller_id)

        # Prepare the request data
        request_data = {
            "datetime": device_datetime.strftime('%Y-%m-%d %H:%M:%S')
        }

        # Set the device time using the API

        url = f"{current_app.config['REST_ENDPOINT']}/device/{controller_id}/time"
        response = requests.put(url, json=request_data, headers=HEADERS)

        if response.status_code == 200:
            device_time = response.json()
            flash(
                f"Device current time set to: {device_time['datetime']}", 'success')
        elif response.status_code == 500:
            error_message = response.json().get(
                'message', 'Error setting device date/time')
            flash(error_message, 'danger')
        else:
            flash("Failed to set device time", 'danger')
    return render_template('set_device_time.html', webserver_time=server_datetime, controller_id=controller_id, current_device_time=current_device_time)


##### Data Export/Import Routes #####

@doorctl.route('/accesscontrol/data/export-import', methods=['GET'])
def data_export_import():
    """Display the export/import page"""
    return render_template('data_export_import.html')


@doorctl.route('/accesscontrol/data/export', methods=['GET', 'POST'])
def export_data_ui():
    """Export database data to JSON file"""
    try:
        include_events = request.args.get('include_events', 'true').lower() == 'true'
        
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
        
        # Create filename with timestamp
        filename = f"door_control_export_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        json_str = json.dumps(export_data, indent=2)
        
        return send_file(
            io.BytesIO(json_str.encode('utf-8')),
            mimetype='application/json',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        flash(f'Error exporting data: {str(e)}', 'danger')
        return redirect(url_for('doorctl.data_export_import'))


@doorctl.route('/accesscontrol/data/import', methods=['POST'])
def import_data_ui():
    """Import database data from JSON file"""
    try:
        # Check if file was uploaded
        if 'import_file' not in request.files:
            flash('No file uploaded', 'danger')
            return redirect(url_for('doorctl.data_export_import'))
        
        file = request.files['import_file']
        
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(url_for('doorctl.data_export_import'))
        
        # Get import options
        mode = request.form.get('import_mode', 'merge')
        skip_duplicates = request.form.get('skip_duplicates', 'true').lower() == 'true'
        
        # Read and parse JSON file
        try:
            import_data = json.load(file)
        except json.JSONDecodeError as e:
            flash(f'Invalid JSON file: {str(e)}', 'danger')
            return redirect(url_for('doorctl.data_export_import'))
        
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
                flash('Existing data cleared', 'info')
            except Exception as e:
                db.session.rollback()
                flash(f'Failed to clear existing data: {str(e)}', 'danger')
                return redirect(url_for('doorctl.data_export_import'))
        
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
            
            # Build success message
            message_parts = []
            if results['users']['added'] > 0:
                message_parts.append(f"{results['users']['added']} users imported")
            if results['users']['skipped'] > 0:
                message_parts.append(f"{results['users']['skipped']} users skipped")
            if results['events']['added'] > 0:
                message_parts.append(f"{results['events']['added']} events imported")
            if results['events']['skipped'] > 0:
                message_parts.append(f"{results['events']['skipped']} events skipped")
            
            if message_parts:
                flash(f"Import completed: {', '.join(message_parts)}", 'success')
            else:
                flash('No data imported', 'info')
            
            # Show errors if any
            if results['users']['errors']:
                flash(f"{len(results['users']['errors'])} user import errors occurred", 'warning')
            if results['events']['errors']:
                flash(f"{len(results['events']['errors'])} event import errors occurred", 'warning')
                
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to commit changes: {str(e)}', 'danger')
        
        return redirect(url_for('doorctl.data_export_import'))

    except Exception as e:
        db.session.rollback()
        flash(f'Error importing data: {str(e)}', 'danger')
        return redirect(url_for('doorctl.data_export_import'))




