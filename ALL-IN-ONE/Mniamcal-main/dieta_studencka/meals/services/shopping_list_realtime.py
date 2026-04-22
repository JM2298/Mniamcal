from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.utils import OperationalError, ProgrammingError

from meals.models import ProjektInflacjaMobileListazakupowrodziny


def shopping_list_group_name(shopping_list_id):
    return f'shopping_list_live_{shopping_list_id}'


def emit_live_shopping_list_update(family_id, shopping_list_id, reason='shopping_list.updated'):
    """Broadcast refreshed live shopping list payload to websocket subscribers."""
    try:
        from meals.api_views.shoping_list import _build_live_shopping_list_output

        payload, live_error = _build_live_shopping_list_output(family_id, shopping_list_id)
    except (ProgrammingError, OperationalError):
        return False

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return False

    async_to_sync(channel_layer.group_send)(
        shopping_list_group_name(shopping_list_id),
        {
            'type': 'shopping_list_event',
            'event': reason,
            'shopping_list_id': shopping_list_id,
            'payload': payload,
            'error': live_error,
        },
    )
    return True


def emit_live_shopping_list_updates_for_date(family_id, target_date, reason='calendar.updated'):
    """Broadcast updates for all family shopping lists whose date range includes target_date."""
    try:
        shopping_list_ids = list(
            ProjektInflacjaMobileListazakupowrodziny.objects
            .filter(rodzina_id=family_id, data_od__lte=target_date, data_do__gte=target_date)
            .values_list('id', flat=True)
        )
    except (ProgrammingError, OperationalError):
        return 0

    sent = 0
    for shopping_list_id in shopping_list_ids:
        if emit_live_shopping_list_update(family_id, shopping_list_id, reason=reason):
            sent += 1
    return sent


def emit_live_shopping_list_updates_for_family(family_id, reason='family.updated'):
    """Broadcast updates for all shopping lists in the family."""
    try:
        shopping_list_ids = list(
            ProjektInflacjaMobileListazakupowrodziny.objects
            .filter(rodzina_id=family_id)
            .values_list('id', flat=True)
        )
    except (ProgrammingError, OperationalError):
        return 0

    sent = 0
    for shopping_list_id in shopping_list_ids:
        if emit_live_shopping_list_update(family_id, shopping_list_id, reason=reason):
            sent += 1
    return sent
