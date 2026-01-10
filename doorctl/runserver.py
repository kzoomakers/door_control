# Filename    : runserver.py
# Author      : Jon Kelley <jon.kelley@kzoomakers.org>
# Description : Kzoomakers Door Controller

from flask import Blueprint, Flask, request, session, g, redirect, url_for, abort, render_template, flash, Response, json, make_response, send_file
from doorctl.blueprints.doorctl import doorctl
from doorctl.blueprints.lastevent import lastevent
from doorctl.blueprints.api import api
from doorctl.sharedlib.jinja2 import split_list_one, split_list_two, reverse_string, resume_date, calculate_age, make_slug
import base64
import os
from datetime import datetime
import time
from dateutil import tz
from flask_sqlalchemy import SQLAlchemy
from .db import db, init_db
import logging

os.environ['TZ'] = os.environ.get('TIMEZONE')
time.tzset()


app = Flask(__name__, static_url_path='/accesscontrol/static')

app.logger.setLevel(logging.DEBUG)
stream_handler = logging.StreamHandler()
app.logger.addHandler(stream_handler)

# Define a custom Jinja2 filter for strftime
def format_datetime(value, format='%B %d'):
    return datetime.strptime(value, '%Y-%m-%d %H:%M:%S').strftime(format)

# Add the custom filter to the Jinja2 environment
app.jinja_env.filters['strftime'] = format_datetime

print('startup')
# key for cookie safety. Shal be overridden using ENV var SECRET_KEY
app.secret_key = os.getenv(
    "SECRET_KEY", "kalamazoo03h0f03h0f3h03hf830dboqboqow2")

app.instance_path = '/door'
ENV_REST_ENDPOINT = os.environ.get('REST_ENDPOINT', 'http://127.0.0.1:8080')
app.config['REST_ENDPOINT'] = f"{ENV_REST_ENDPOINT}/uhppote"
app.config['ENABLE_PROXY_DETECTION'] = os.environ.get('ENABLE_PROXY_DETECTION', False)
app.config['ENABLE_PROXIED_SECURIY_KEY'] = os.environ.get('ENABLE_PROXIED_SECURIY_KEY', False)
app.config['API_KEY'] = os.environ.get('API_KEY', '')
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///door/flask_database.db'  # Replace with your database URI
db_path = os.path.abspath(os.path.join(app.instance_path, 'flask_database.db'))

# Configure the database URI with the absolute path
#app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:////door/flask_database.db'


app.register_blueprint(doorctl)
app.register_blueprint(lastevent)
app.register_blueprint(api)

@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    # note that we set the 500 status explicitly
    return render_template('500.html'), 500


def main():
    init_db(app)
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', debug=True, port=5001, threaded=True)

if __name__ == '__main__':
    main()

