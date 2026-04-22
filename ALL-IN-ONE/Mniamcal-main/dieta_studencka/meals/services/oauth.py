from firebase_admin import auth

from .firebase import ensure_firebase_initialized


class FirebaseConfigurationError(RuntimeError):
    pass


class FirebaseTokenValidationError(ValueError):
    pass

def verify_firebase_id_token(id_token_value):
    try:
        ensure_firebase_initialized()
    except RuntimeError as exc:
        raise FirebaseConfigurationError(str(exc)) from exc

    try:
        # Allow minor client/server clock drift to prevent false negatives.
        return auth.verify_id_token(id_token_value, clock_skew_seconds=60)
    except Exception as exc:
        raise FirebaseTokenValidationError(str(exc)) from exc
