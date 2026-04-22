"""Shoping list websocket tests."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from meals.consumers import ShoppingListLiveFromCalendarConsumer


User = get_user_model()


class ShopingListWebsocketTests(APITestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='shop-list-ws-user', password='testpass123')

	def test_live_shopping_list_consumer_returns_payload_for_shopping_list_id(self):
		consumer = ShoppingListLiveFromCalendarConsumer()
		consumer.user = self.user
		consumer.channel_name = 'test-channel'
		consumer.channel_layer = SimpleNamespace(
			group_add=AsyncMock(),
			group_discard=AsyncMock(),
		)
		sent_messages = []

		async def fake_send(*, text_data=None, bytes_data=None, close=False):
			sent_messages.append(json.loads(text_data))

		consumer.send = fake_send
		consumer._resolve_family_context = AsyncMock(return_value=(SimpleNamespace(id=12), None))
		consumer._build_live_payload = AsyncMock(
			return_value=(
				{
					'rodzina_id': 12,
					'data_od': '2026-03-28',
					'data_do': '2026-03-28',
					'liczba_zaplanowanych_posilkow': 2,
					'liczba_pozycji_na_liscie': 1,
					'produkty': [
						{
							'produkt_id': 501,
							'nazwa_produktu': 'Ryż',
							'ilosc_produktu_do_kupienia': '280.0 g',
							'kolejnosc_kategorii': None,
						}
					],
				},
				None,
			)
		)

		async_to_sync(consumer.receive)(json.dumps({'shopping_list_id': 77}))

		self.assertEqual(sent_messages[0]['type'], 'subscribed')
		self.assertEqual(sent_messages[0]['shopping_list_id'], 77)
		self.assertEqual(sent_messages[1]['type'], 'live_shopping_list')
		self.assertEqual(sent_messages[1]['data']['liczba_pozycji_na_liscie'], 1)
		self.assertEqual(sent_messages[1]['data']['produkty'][0]['nazwa_produktu'], 'Ryż')
		consumer._build_live_payload.assert_awaited_once_with(12, 77)
		consumer.channel_layer.group_add.assert_awaited_once()

	def test_live_shopping_list_consumer_validates_shopping_list_id(self):
		consumer = ShoppingListLiveFromCalendarConsumer()
		consumer.user = self.user
		sent_messages = []

		async def fake_send(*, text_data=None, bytes_data=None, close=False):
			sent_messages.append(json.loads(text_data))

		consumer.send = fake_send
		consumer._resolve_family_context = AsyncMock(return_value=(SimpleNamespace(id=12), None))
		consumer._build_live_payload = AsyncMock()

		async_to_sync(consumer.receive)(json.dumps({'nazwa_listy_zakupow': 'Lista A'}))

		self.assertEqual(sent_messages[0]['type'], 'error')
		self.assertEqual(sent_messages[0]['CODE'], 'VALIDATION_ERROR')
		consumer._resolve_family_context.assert_not_called()
		consumer._build_live_payload.assert_not_called()

	def test_live_shopping_list_consumer_returns_not_found_error(self):
		consumer = ShoppingListLiveFromCalendarConsumer()
		consumer.user = self.user
		consumer.channel_name = 'test-channel'
		consumer.channel_layer = SimpleNamespace(
			group_add=AsyncMock(),
			group_discard=AsyncMock(),
		)
		sent_messages = []

		async def fake_send(*, text_data=None, bytes_data=None, close=False):
			sent_messages.append(json.loads(text_data))

		consumer.send = fake_send
		consumer._resolve_family_context = AsyncMock(return_value=(SimpleNamespace(id=12), None))
		consumer._build_live_payload = AsyncMock(
			return_value=(
				None,
				{
					'CODE': 'SHOPPING_LIST_NOT_FOUND',
					'detail': 'Nie znaleziono listy zakupow o podanym id dla rodziny.',
				},
			)
		)

		async_to_sync(consumer.receive)(json.dumps({'shopping_list_id': 999}))

		self.assertEqual(sent_messages[0]['type'], 'subscribed')
		self.assertEqual(sent_messages[1]['type'], 'error')
		self.assertEqual(sent_messages[1]['CODE'], 'SHOPPING_LIST_NOT_FOUND')
