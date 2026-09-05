#!/usr/bin/env python3
"""Idempotently create the OtterWiki admin user.

Runs inside the OtterWiki virtualenv using OtterWiki's own app and models
(importing otterwiki.server creates the database tables if missing).
Configuration via environment variables: OTTERWIKI_SETTINGS,
OTTERWIKI_ADMIN_NAME, OTTERWIKI_ADMIN_EMAIL, OTTERWIKI_ADMIN_PASSWORD.

Prints "created" or "exists" — an existing user is never modified, so a
password changed in the UI survives re-runs.
"""

import os
import sys
from datetime import datetime

from werkzeug.security import generate_password_hash

from otterwiki.server import app, db
from otterwiki.models import User

name = os.environ["OTTERWIKI_ADMIN_NAME"]
email = os.environ["OTTERWIKI_ADMIN_EMAIL"]
password = os.environ["OTTERWIKI_ADMIN_PASSWORD"]

with app.app_context():
    if User.query.filter_by(email=email).first() is not None:
        print("exists")
        sys.exit(0)
    now = datetime.now()
    user = User(
        name=name,
        email=email,
        # same hash method OtterWiki's own registration uses
        password_hash=generate_password_hash(password, method="scrypt"),
        first_seen=now,
        last_seen=now,
        is_admin=True,
        is_approved=True,
        email_confirmed=True,
        allow_read=True,
        allow_write=True,
        allow_upload=True,
    )
    db.session.add(user)
    db.session.commit()
    print("created")
