import requests
from flask import Blueprint, jsonify, current_app, request, abort
from ..db import CardMemberMapping

lastevent = Blueprint('lastevent', __name__, url_prefix="/kiosk")

REQUEST_TIMEOUT = 3

def _rest_get(path):
    base = current_app.config['REST_ENDPOINT'].rstrip('/')
    url = f"{base}{path}"
    r = requests.get(url, headers={'accept': 'application/json'}, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json()

@lastevent.get('/controller/<int:controller_id>/events/last')
def get_last_event(controller_id: int):
    """
    Returns the latest event for a controller (device) as JSON.
    Caching: uses ETag = event-id to allow the kiosk to poll cheaply.
    """

    try:

        meta = _rest_get(f"/device/{controller_id}/events/1000")
    except requests.RequestException as e:
        abort(502, description=f"upstream error getting event range: {e}")

    try:
        first_idx = meta["events"]["first"]
        last_idx = meta["events"]["last"]
    except (TypeError, KeyError):
        abort(502, description="upstream returned unexpected payload (missing events.first/last)")

    if last_idx is None or first_idx is None or last_idx < first_idx:
        abort(404, description="no events available")

    etag= f'W/"{last_idx}"'
    if request.headers.get("If-None-Match") == etag:
        return ("", 304, {"ETAG": etag})
 
    try:
        ev = _rest_get(f"/device/{controller_id}/event/{last_idx}")
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404 and last_idx > first_idx:
            try:
                ev = _rest_get(f"/device/{controller_id}/event/{last_idx-1}")
                etag = f'W/"{last_idx-1}"'
            except Exception as e2:
                abort(502, description=f"upstream error on fallback event fetch: {e2}")
        else:
            abort(502, description=f"upstream error getting last event: {e}")

    event = ev.get("event", {})
    card_number = event.get("card-number")
    enriched = {}
    try:
    
        card = 	CardMemberMapping.query.filter_by(card_number=card_number).first() if card_number else None
        if card:
            enriched = {
                "name": card.name,
                "email": card.email,
                "membership-type": card.membership_type
            }
    except Exception:
        enriched = {}

    payload = {
        "device-id": event.get("device-id"),
        "event-id": event.get("event-id"),
        "card-number": card_number,
        "door-id": event.get("door-id"),
        "direction": event.get("direction"),
        "direction-text": event.get("direction-text"),
        "event-type": event.get("event-type"),
        "event-type-text": event.get("event-type-text"),
        "access-granted": event.get("access-granted"),
        "timestamp": event.get("timestamp"),
        "event-reason": event.get("event-reason"),
        "event-reason-text": event.get("event-reason-text"),
        **enriched
    }
    return jsonify(payload), 200, {"ETag": etag}



          

     






