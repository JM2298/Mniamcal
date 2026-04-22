from firebase_admin import messaging

from .firebase import ensure_firebase_initialized


def send_push_notification(token, title, body, data=None):
    ensure_firebase_initialized()

    payload = {str(k): str(v) for k, v in (data or {}).items()}
    message = messaging.Message(
        token=token,
        notification=messaging.Notification(title=title, body=body),
        data=payload,
    )
    return messaging.send(message)
