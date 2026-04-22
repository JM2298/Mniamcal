import datetime as dt
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from meals.tasks import recalculate_meal_prices_for_store, recalculate_meal_prices_for_store_task


class MealsTaskTests(SimpleTestCase):
	@patch('meals.tasks.ProjektInflacjaMobileCenacalegoposilku.objects.update_or_create')
	@patch('meals.tasks.ProjektInflacjaMobileProduktywposilku.objects.select_related')
	@patch('meals.tasks.ProjektInflacjaMobileAktualnecenyproduktowwdanymsklepie.objects.filter')
	def test_zero_price_product_is_saved_as_missing(self, mock_prices_filter, mock_ingredients_select_related, mock_update_or_create):
		mock_prices_filter.return_value.order_by.return_value = [
			SimpleNamespace(
				nazwa_produktu_uproszczonego_id=11,
				cena_produktu_za_kg=Decimal('0.00'),
			),
		]

		ingredient = SimpleNamespace(
			nazwa_posilku_id=77,
			nazwa_produktu=SimpleNamespace(
				nazwa_produktu_uproszczonego_id=11,
				nazwa_produktu='Papryka',
				nazwa_produktu_uproszczonego=SimpleNamespace(
					nazwa_produktu_uproszczonego='Papryka',
				),
			),
			czysta_ilosc_produktu=100,
		)
		mock_ingredients_select_related.return_value.order_by.return_value = [ingredient]

		stats = recalculate_meal_prices_for_store(
			sklep_id=1,
			data_wyliczenia=dt.date(2026, 4, 2),
		)

		self.assertEqual(stats['updated_meal_prices'], 1)
		self.assertEqual(stats['meals_with_missing_products'], 1)

		defaults = mock_update_or_create.call_args.kwargs['defaults']
		self.assertEqual(defaults['cena_calego_posilku'], Decimal('0.00'))
		self.assertEqual(defaults['brakujace_ceny_produktu'], '["Papryka"]')

	@patch('meals.tasks.ProjektInflacjaMobileCenacalegoposilku.objects.update_or_create')
	@patch('meals.tasks.ProjektInflacjaMobileProduktywposilku.objects.select_related')
	@patch('meals.tasks.ProjektInflacjaMobileAktualnecenyproduktowwdanymsklepie.objects.filter')
	def test_no_missing_products_are_saved_as_empty_json_list(self, mock_prices_filter, mock_ingredients_select_related, mock_update_or_create):
		mock_prices_filter.return_value.order_by.return_value = [
			SimpleNamespace(
				nazwa_produktu_uproszczonego_id=22,
				cena_produktu_za_kg=Decimal('12.00'),
			),
		]

		ingredient = SimpleNamespace(
			nazwa_posilku_id=99,
			nazwa_produktu=SimpleNamespace(
				nazwa_produktu_uproszczonego_id=22,
				nazwa_produktu='Marchew',
				nazwa_produktu_uproszczonego=SimpleNamespace(
					nazwa_produktu_uproszczonego='Marchew',
				),
			),
			czysta_ilosc_produktu=100,
		)
		mock_ingredients_select_related.return_value.order_by.return_value = [ingredient]

		stats = recalculate_meal_prices_for_store(
			sklep_id=1,
			data_wyliczenia=dt.date(2026, 4, 2),
		)

		self.assertEqual(stats['updated_meal_prices'], 1)
		self.assertEqual(stats['meals_with_missing_products'], 0)

		defaults = mock_update_or_create.call_args.kwargs['defaults']
		self.assertEqual(defaults['cena_calego_posilku'], Decimal('1.20'))
		self.assertEqual(defaults['brakujace_ceny_produktu'], '[]')

	@patch('meals.tasks.send_push_notification')
	@patch('meals.tasks.FcmDeviceToken.objects.filter')
	@patch('meals.tasks.recalculate_meal_prices_for_store')
	def test_recalculate_task_sends_push_to_all_active_tokens(self, mock_recalculate, mock_filter, mock_send_push):
		mock_recalculate.return_value = {
			'updated_meal_prices': 10,
			'meals_with_missing_products': 2,
		}
		mock_filter.return_value.values_list.return_value = ['token-1', 'token-2']
		mock_send_push.side_effect = ['msg-1', 'msg-2']

		result = recalculate_meal_prices_for_store_task(sklep_id=1, data_wyliczenia='2026-04-02')

		self.assertEqual(result['updated_meal_prices'], 10)
		self.assertEqual(result['meals_with_missing_products'], 2)
		self.assertEqual(result['push_tokens_total'], 2)
		self.assertEqual(result['push_sent'], 2)
		self.assertEqual(result['push_failed'], 0)
		self.assertEqual(mock_send_push.call_count, 2)

	@patch('meals.tasks.send_push_notification')
	@patch('meals.tasks.FcmDeviceToken.objects.filter')
	@patch('meals.tasks.recalculate_meal_prices_for_store')
	def test_recalculate_task_counts_push_failures(self, mock_recalculate, mock_filter, mock_send_push):
		mock_recalculate.return_value = {
			'updated_meal_prices': 8,
			'meals_with_missing_products': 1,
		}
		mock_filter.return_value.values_list.return_value = ['token-1', 'token-2']
		mock_send_push.side_effect = [Exception('send failed'), 'msg-2']

		result = recalculate_meal_prices_for_store_task(sklep_id=3, data_wyliczenia='2026-04-02')

		self.assertEqual(result['push_tokens_total'], 2)
		self.assertEqual(result['push_sent'], 1)
		self.assertEqual(result['push_failed'], 1)
