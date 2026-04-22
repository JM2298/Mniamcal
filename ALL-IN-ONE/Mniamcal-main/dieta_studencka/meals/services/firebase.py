import json

import firebase_admin
from django.conf import settings
from firebase_admin import credentials


def ensure_firebase_initialized():
    if firebase_admin._apps:
        return

    if settings.FIREBASE_CREDENTIALS_FILE:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_FILE)
    elif settings.FIREBASE_CREDENTIALS_JSON:
        cred = credentials.Certificate(json.loads(settings.FIREBASE_CREDENTIALS_JSON))
    else:
        raise RuntimeError('Brak konfiguracji Firebase. Ustaw FIREBASE_CREDENTIALS_FILE lub FIREBASE_CREDENTIALS_JSON.')

    firebase_admin.initialize_app(cred)
