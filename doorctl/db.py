from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

db = SQLAlchemy()


def init_db(app):
    db.init_app(app)


class CardMemberMapping(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    card_number = db.Column(db.Integer, unique=True)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(100))
    email = db.Column(db.String(512))
    login = db.Column(db.String(64))
    uid = db.Column(db.Integer)
    note = db.Column(db.String(1024))
    membership_type = db.Column(db.String(20))

class GlobalEventLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    controller_id = db.Column(db.Integer)
    event_id = db.Column(db.Integer)
    timestamp = db.Column(db.String(25))
    card_number = db.Column(db.Integer)
    event_type = db.Column(db.Integer)
    event_type_text = db.Column(db.String(128))
    access_granted = db.Column(db.Boolean)
    door_id = db.Column(db.Integer)
    direction = db.Column(db.Boolean)
    direction_text = db.Column(db.String(10))
    event_reason = db.Column(db.Integer)
    event_reason_text = db.Column(db.String(128))
    insert_timestamp_utc = db.Column(db.DateTime, default=func.now())
    timestamp_utc = db.Column(db.DateTime)
    name = db.Column(db.String(100))
    email = db.Column(db.String(512))
    membership_type = db.Column(db.String(20))


