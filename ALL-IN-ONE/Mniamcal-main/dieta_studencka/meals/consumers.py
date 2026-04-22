import json
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db.utils import OperationalError, ProgrammingError
from rest_framework import status


class FamilyUpdatesConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = 'family_updates'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send(
            text_data=json.dumps(
                {
                    'type': 'connection_established',
                    'message': 'Polaczono z websocket rodziny.',
                }
            )
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        payload = json.loads(text_data or '{}')
        event_type = payload.get('type')

        if event_type == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))
            return

        await self.send(
            text_data=json.dumps(
                {
                    'type': 'echo',
                    'payload': payload,
                }
            )
        )

    async def family_event(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    'type': 'family_event',
                    'payload': event.get('payload', {}),
                }
            )
        )


class ShoppingListLiveFromCalendarConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.subscribed_group = None
        self.subscribed_shopping_list_id = None
        self.user = self.scope.get('user')
        if not getattr(self.user, 'is_authenticated', False):
            self.user = await self._authenticate_from_query_token()

        if not self.user:
            await self.close(code=4401)
            return

        await self.accept()
        await self.send(
            text_data=json.dumps(
                {
                    'type': 'connection_established',
                    'message': 'Polaczono z websocket live listy zakupow. Wyslij shopping_list_id aby subskrybowac aktualizacje.',
                }
            )
        )

    async def disconnect(self, close_code):
        if self.subscribed_group:
            await self.channel_layer.group_discard(self.subscribed_group, self.channel_name)

    @database_sync_to_async
    def _authenticate_from_query_token(self):
        from rest_framework_simplejwt.authentication import JWTAuthentication
        from rest_framework_simplejwt.exceptions import InvalidToken

        raw_query = self.scope.get('query_string', b'').decode('utf-8')
        token = parse_qs(raw_query).get('token', [None])[0]
        if not token:
            return None

        try:
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token)
            return jwt_auth.get_user(validated_token)
        except (InvalidToken, Exception):
            return None

    @database_sync_to_async
    def _resolve_family_context(self):
        from meals.api_views.shoping_list import _ensure_family_membership_for_shopping

        try:
            _, family, context_error = _ensure_family_membership_for_shopping(self.user)
        except (ProgrammingError, OperationalError):
            return None, {
                'CODE': 'FAMILY_CONTEXT_UNAVAILABLE',
                'detail': 'Kontekst rodziny jest chwilowo niedostepny.',
                'status': status.HTTP_503_SERVICE_UNAVAILABLE,
            }

        if context_error is not None:
            return None, context_error

        return family, None

    @database_sync_to_async
    def _build_live_payload(self, family_id, shopping_list_id):
        from meals.api_views.shoping_list import _build_live_shopping_list_output

        return _build_live_shopping_list_output(family_id, shopping_list_id)

    @staticmethod
    def _shopping_list_group_name(shopping_list_id):
        from meals.services.shopping_list_realtime import shopping_list_group_name

        return shopping_list_group_name(shopping_list_id)

    async def receive(self, text_data):
        if not hasattr(self, 'subscribed_group'):
            self.subscribed_group = None
            self.subscribed_shopping_list_id = None

        try:
            payload = json.loads(text_data or '{}')
        except json.JSONDecodeError:
            await self.send(
                text_data=json.dumps(
                    {
                        'type': 'error',
                        'CODE': 'VALIDATION_ERROR',
                        'detail': 'Niepoprawny format JSON wiadomosci websocket.',
                    }
                )
            )
            return

        event_type = payload.get('type')
        if event_type == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))
            return

        shopping_list_id = payload.get('shopping_list_id')
        if not isinstance(shopping_list_id, int) or shopping_list_id <= 0:
            await self.send(
                text_data=json.dumps(
                    {
                        'type': 'error',
                        'CODE': 'VALIDATION_ERROR',
                        'detail': 'Pole shopping_list_id jest wymagane i musi byc dodatnia liczba calkowita.',
                    }
                )
            )
            return

        family, context_error = await self._resolve_family_context()
        if context_error is not None:
            await self.send(
                text_data=json.dumps(
                    {
                        'type': 'error',
                        'CODE': context_error.get('CODE', 'UNKNOWN_ERROR'),
                        'detail': context_error.get('detail', 'Nieznany blad.'),
                    }
                )
            )
            return

        next_group = self._shopping_list_group_name(shopping_list_id)
        if self.subscribed_group and self.subscribed_group != next_group:
            await self.channel_layer.group_discard(self.subscribed_group, self.channel_name)

        if self.subscribed_group != next_group:
            await self.channel_layer.group_add(next_group, self.channel_name)
            self.subscribed_group = next_group
            self.subscribed_shopping_list_id = shopping_list_id
            await self.send(
                text_data=json.dumps(
                    {
                        'type': 'subscribed',
                        'shopping_list_id': shopping_list_id,
                    }
                )
            )

        output, live_error = await self._build_live_payload(family.id, shopping_list_id)
        if live_error is not None:
            await self.send(
                text_data=json.dumps(
                    {
                        'type': 'error',
                        'CODE': live_error.get('CODE', 'UNKNOWN_ERROR'),
                        'detail': live_error.get('detail', 'Nieznany blad.'),
                    }
                )
            )
            return

        await self.send(
            text_data=json.dumps(
                {
                    'type': 'live_shopping_list',
                    'data': output,
                    'shopping_list_id': shopping_list_id,
                    'event': 'snapshot',
                },
                default=str,
            )
        )

    async def shopping_list_event(self, event):
        error = event.get('error')
        if error is not None:
            await self.send(
                text_data=json.dumps(
                    {
                        'type': 'error',
                        'CODE': error.get('CODE', 'UNKNOWN_ERROR'),
                        'detail': error.get('detail', 'Nieznany blad.'),
                        'shopping_list_id': event.get('shopping_list_id'),
                        'event': event.get('event', 'shopping_list.updated'),
                    },
                    default=str,
                )
            )
            return

        await self.send(
            text_data=json.dumps(
                {
                    'type': 'live_shopping_list',
                    'shopping_list_id': event.get('shopping_list_id'),
                    'event': event.get('event', 'shopping_list.updated'),
                    'data': event.get('payload'),
                },
                default=str,
            )
        )
