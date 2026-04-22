from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase


User = get_user_model()


class SettingsStoreCurrentPricesApiTests(APITestCase):
	update_url = '/api/settings/stores/current-prices/update/'

	def setUp(self):
		super().setUp()
		self.user = User.objects.create_user(
			username='settings_user',
			email='settings@example.com',
			password='SilneHaslo123',
		)

	def _payload(self):
		return {
			'sklep_id': 1,
			'produkty': [
				{
					'nazwa_produktu_uproszczonego_id': 101,
					'dokladna_nazwa_produktu': 'Mleko 3.2% 1L',
					'cena_produktu': '4.79',
					'cena_produktu_za_kg': '4.79',
					'producent': 'Mlekpol',
					'opakowanie': '1 l',
					'data_dodania': '2026-04-01',
				},
			],
		}

	def test_store_current_prices_requires_authentication(self):
		response = self.client.post(self.update_url, self._payload(), format='json')
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	@patch('meals.api_views.settings.ProjektInflacjaMobileHistoriacenproduktow.objects.create')
	@patch('meals.api_views.settings.ProjektInflacjaMobileAktualnecenyproduktowwdanymsklepie.objects.create')
	@patch('meals.api_views.settings.ProjektInflacjaMobileAktualnecenyproduktowwdanymsklepie.objects.filter')
	@patch('meals.api_views.settings.recalculate_meal_prices_for_store_task.delay')
	def test_store_current_prices_post_creates_rows(self, mock_delay, mock_filter, mock_current_create, mock_history_create):
		self.client.force_authenticate(user=self.user)
		mock_filter.return_value.first.return_value = None
		mock_delay.return_value = SimpleNamespace(id='task-post-123')

		response = self.client.post(self.update_url, self._payload(), format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data.get('CODE'), 'STORE_CURRENT_PRICES_UPDATED')
		self.assertEqual(response.data.get('processed_products'), 1)
		self.assertEqual(response.data.get('created_current_prices'), 1)
		self.assertEqual(response.data.get('updated_current_prices'), 0)
		self.assertEqual(response.data.get('created_history_rows'), 1)
		self.assertEqual(response.data.get('meal_price_recalculation_status'), 'queued')
		self.assertEqual(response.data.get('meal_price_recalculation_task_id'), 'task-post-123')
		mock_current_create.assert_called_once()
		mock_history_create.assert_called_once()
		mock_delay.assert_called_once_with(
			sklep_id=1,
			data_wyliczenia='2026-04-01',
		)

	@patch('meals.api_views.settings.ProjektInflacjaMobileHistoriacenproduktow.objects.create')
	@patch('meals.api_views.settings.ProjektInflacjaMobileAktualnecenyproduktowwdanymsklepie.objects.filter')
	@patch('meals.api_views.settings.recalculate_meal_prices_for_store_task.delay')
	def test_store_current_prices_put_updates_existing_row(self, mock_delay, mock_filter, mock_history_create):
		self.client.force_authenticate(user=self.user)
		mock_delay.return_value = SimpleNamespace(id='task-put-246')

		existing = SimpleNamespace(
			save=Mock(),
			dokladna_nazwa_produktu='Stara nazwa',
			cena_produktu='0.00',
			cena_produktu_za_kg='0.00',
			producent='',
			opakowanie='',
			data_dodania='2025-01-01',
		)
		mock_filter.return_value.first.return_value = existing

		response = self.client.put(self.update_url, self._payload(), format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data.get('processed_products'), 1)
		self.assertEqual(response.data.get('created_current_prices'), 0)
		self.assertEqual(response.data.get('updated_current_prices'), 1)
		self.assertEqual(response.data.get('created_history_rows'), 1)
		self.assertEqual(response.data.get('meal_price_recalculation_status'), 'queued')
		self.assertEqual(response.data.get('meal_price_recalculation_task_id'), 'task-put-246')
		existing.save.assert_called_once()
		mock_history_create.assert_called_once()
		mock_delay.assert_called_once_with(
			sklep_id=1,
			data_wyliczenia='2026-04-01',
		)

	@patch('meals.api_views.settings.ProjektInflacjaMobileHistoriacenproduktow.objects.create')
	@patch('meals.api_views.settings.ProjektInflacjaMobileAktualnecenyproduktowwdanymsklepie.objects.create')
	@patch('meals.api_views.settings.ProjektInflacjaMobileAktualnecenyproduktowwdanymsklepie.objects.filter')
	@patch('meals.api_views.settings.recalculate_meal_prices_for_store_task.delay', side_effect=Exception('broker down'))
	def test_store_current_prices_returns_503_when_task_cannot_be_queued(self, mock_delay, mock_filter, mock_current_create, mock_history_create):
		self.client.force_authenticate(user=self.user)
		mock_filter.return_value.first.return_value = None

		response = self.client.post(self.update_url, self._payload(), format='json')

		self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
		self.assertEqual(response.data.get('CODE'), 'MEAL_PRICE_TASK_QUEUE_UNAVAILABLE')
		mock_current_create.assert_called_once()
		mock_history_create.assert_called_once()
		mock_delay.assert_called_once()

	def test_store_current_prices_validates_payload(self):
		self.client.force_authenticate(user=self.user)

		response = self.client.post(
			self.update_url,
			{'sklep_id': 1, 'produkty': []},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
