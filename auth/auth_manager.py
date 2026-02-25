"""
Auth Manager — salted password hashing, login verification, session helpers.
Never stores plain-text passwords.
"""
import hashlib
import secrets
from typing import Tuple, Optional


class AuthManager:
    """
    Handles password hashing (SHA-256 + 32-byte random salt) and
    verification for Staff and Admin accounts.
    """

    HASH_ITERATIONS = 260_000   # OWASP 2024 recommended for SHA-256 PBKDF2

    # ------------------------------------------------------------------ #
    # Core crypto
    # ------------------------------------------------------------------ #

    def hash_password(self, password: str,
                      salt: Optional[str] = None) -> Tuple[str, str]:
        """
        Returns (hex_hash, hex_salt).
        If salt is None a fresh random salt is generated.
        """
        if salt is None:
            salt = secrets.token_hex(32)          # 256-bit salt
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            self.HASH_ITERATIONS,
        )
        return dk.hex(), salt

    def verify_password(self, password: str,
                        stored_hash: str, salt: str) -> bool:
        """Constant-time comparison to prevent timing attacks."""
        candidate_hash, _ = self.hash_password(password, salt)
        return secrets.compare_digest(candidate_hash, stored_hash)

    # ------------------------------------------------------------------ #
    # Staff login
    # ------------------------------------------------------------------ #

    def staff_login(self, emp_id: str, password: str) -> bool:
        """
        Verifies staff credentials against main.db.
        Returns True on success.
        """
        from database.db_manager import DatabaseManager
        db = DatabaseManager()
        creds = db.get_staff_credentials(emp_id)
        if not creds:
            return False
        return self.verify_password(password, creds["password_hash"], creds["salt"])

    # ------------------------------------------------------------------ #
    # Admin login
    # ------------------------------------------------------------------ #

    def admin_login(self, username: str,
                    password: str) -> Tuple[bool, bool]:
        """
        Returns (authenticated: bool, must_change_password: bool).
        """
        from database.db_manager import DatabaseManager
        db = DatabaseManager()
        admin = db.get_admin(username)
        if not admin:
            return False, False
        ok = self.verify_password(password, admin["password_hash"], admin["salt"])
        must_change = bool(admin["must_change_password"])
        return ok, must_change

    def change_admin_password(self, username: str,
                              new_password: str) -> bool:
        from database.db_manager import DatabaseManager
        db = DatabaseManager()
        h, s = self.hash_password(new_password)
        return db.update_admin_password(username, h, s)

    def change_staff_password(self, emp_id: str,
                              new_password: str) -> bool:
        from database.db_manager import DatabaseManager
        db = DatabaseManager()
        h, s = self.hash_password(new_password)
        return db.set_staff_credentials(emp_id, h, s)

    # ------------------------------------------------------------------ #
    # Password strength
    # ------------------------------------------------------------------ #

    @staticmethod
    def is_strong_password(password: str) -> Tuple[bool, str]:
        """
        Returns (is_strong, reason).
        Minimum: 8 chars, 1 uppercase, 1 digit, 1 special char.
        """
        if len(password) < 8:
            return False, "Password must be at least 8 characters."
        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter."
        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one digit."
        specials = set("!@#$%^&*()_+-=[]{}|;':\",./<>?")
        if not any(c in specials for c in password):
            return False, "Password must contain at least one special character."
        return True, "OK"
