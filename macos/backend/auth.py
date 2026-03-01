"""
auth.py — Authentication logic for the Facial Attendance System.

Session tokens, password hashing, role-based access.
No classes. All def-based functions.
"""

import hashlib
import hmac
import json
import os
import time
import secrets
from functools import wraps

from flask import request, jsonify

from config import SECRET_KEY, SESSION_LIFETIME_HOURS


# ---------------------------------------------------------------------------
# Password Hashing (hashlib-based, no bcrypt dependency needed)
# ---------------------------------------------------------------------------

def hash_password(password):
    """
    Create a salted SHA-256 hash of the password.
    Returns 'salt:hash' string.
    """
    salt = secrets.token_hex(16)
    pw_hash = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{pw_hash}"


def verify_password(password, stored_hash):
    """
    Verify a password against a stored 'salt:hash' string.
    Returns True if match.
    """
    if ":" not in stored_hash:
        return False

    salt, expected_hash = stored_hash.split(":", 1)
    actual_hash = hashlib.sha256((salt + password).encode()).hexdigest()
    return hmac.compare_digest(actual_hash, expected_hash)


# ---------------------------------------------------------------------------
# Session Tokens (HMAC-based, no JWT dependency)
# ---------------------------------------------------------------------------

def create_session_token(user_id, role):
    """
    Create a signed session token containing user_id, role, and expiry.
    Format: base64(json_payload):signature
    """
    import base64

    expiry = int(time.time()) + (SESSION_LIFETIME_HOURS * 3600)
    payload = json.dumps({
        "user_id": user_id,
        "role": role,
        "exp": expiry,
    })

    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode()
    signature = hmac.new(
        SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256
    ).hexdigest()

    return f"{payload_b64}.{signature}"


def validate_session(token):
    """
    Validate a session token. Returns payload dict or None.
    Checks signature and expiry.
    """
    import base64

    if not token or "." not in token:
        return None

    try:
        payload_b64, signature = token.rsplit(".", 1)

        # Verify signature
        expected_sig = hmac.new(
            SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            return None

        # Decode payload
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))

        # Check expiry
        if payload.get("exp", 0) < int(time.time()):
            return None

        return payload

    except (ValueError, json.JSONDecodeError, Exception):
        return None


def get_current_user():
    """
    Extract and validate the session from the Authorization header.
    Returns payload dict or None.
    Header format: 'Bearer <token>'
    """
    auth_header = request.headers.get("Authorization", "")

    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        return validate_session(token)

    return None


# ---------------------------------------------------------------------------
# Route Protection Decorators
# ---------------------------------------------------------------------------

def require_auth(f):
    """Decorator: require a valid session token for the route."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Authentication required"}), 401
        request.current_user = user
        return f(*args, **kwargs)
    return decorated


def require_role(*roles):
    """
    Decorator factory: require the user to have one of the specified roles.
    Usage: @require_role('admin', 'staff')
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"error": "Authentication required"}), 401
            if user.get("role") not in roles:
                return jsonify({"error": "Insufficient permissions"}), 403
            request.current_user = user
            return f(*args, **kwargs)
        return decorated
    return decorator
