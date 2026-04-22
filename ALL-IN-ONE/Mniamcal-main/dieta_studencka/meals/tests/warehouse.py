"""Warehouse tests."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase


User = get_user_model()


class WarehouseApiTests(APITestCase):
	meal_coverage_url = '/api/warehouse/meal-coverage/'
	possible_meals_url = '/api/warehouse/possible-meals/'
	update_product_url = '/api/warehouse/update-product/'

	def setUp(self):
		self.user = User.objects.create_user(username='warehouse-user', password='testpass123')

	def test_meal_coverage_requires_authentication(self):
		response = self.client.get(self.meal_coverage_url)
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_possible_meals_requires_authentication(self):
		response = self.client.get(self.possible_meals_url)
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_update_product_requires_authentication(self):
		response = self.client.post(
			self.update_product_url,
			{'produkt_id': 1, 'ilosc_produktu': 300},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	@patch('meals.api_views.warehouse.ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects.select_related')
	@patch('meals.api_views.warehouse._ensure_family_membership_for_shopping')
	def test_update_product_amount_success(self, mocked_resolve_context, mocked_select_related):
		self.client.force_authenticate(user=self.user)
		mocked_resolve_context.return_value = (SimpleNamespace(id=7), SimpleNamespace(id=12), None)

		warehouse_product = SimpleNamespace(
			nazwa_produktu_uproszczonego=SimpleNamespace(nazwa_produktu_uproszczonego='Chleb'),
			ilosc_produktu=300.0,
			save=Mock(),
		)
		mocked_select_related.return_value.filter.return_value.first.return_value = warehouse_product

		response = self.client.post(
			self.update_product_url,
			{'produkt_id': 44, 'ilosc_produktu': 500},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['CODE'], 'WAREHOUSE_PRODUCT_UPDATED')
		self.assertEqual(response.data['produkt_id'], 44)
		self.assertEqual(response.data['nazwa_produktu'], 'Chleb')
		self.assertEqual(response.data['ilosc_produktu'], 500.0)
		self.assertEqual(warehouse_product.ilosc_produktu, 500.0)
		warehouse_product.save.assert_called_once_with(update_fields=['ilosc_produktu'])

	@patch('meals.api_views.warehouse.ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects.select_related')
	@patch('meals.api_views.warehouse._ensure_family_membership_for_shopping')
	def test_update_product_removes_item_when_amount_is_zero(self, mocked_resolve_context, mocked_select_related):
		self.client.force_authenticate(user=self.user)
		mocked_resolve_context.return_value = (SimpleNamespace(id=7), SimpleNamespace(id=12), None)

		warehouse_product = SimpleNamespace(
			nazwa_produktu_uproszczonego=SimpleNamespace(nazwa_produktu_uproszczonego='Mleko'),
			delete=Mock(),
		)
		mocked_select_related.return_value.filter.return_value.first.return_value = warehouse_product

		response = self.client.post(
			self.update_product_url,
			{'produkt_id': 55, 'ilosc_produktu': 0},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['CODE'], 'WAREHOUSE_PRODUCT_REMOVED')
		self.assertEqual(response.data['produkt_id'], 55)
		self.assertEqual(response.data['nazwa_produktu'], 'Mleko')
		self.assertEqual(response.data['ilosc_produktu'], 0.0)
		warehouse_product.delete.assert_called_once_with()

	@patch('meals.api_views.warehouse.ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects.select_related')
	@patch('meals.api_views.warehouse._ensure_family_membership_for_shopping')
	def test_update_product_returns_404_when_missing(self, mocked_resolve_context, mocked_select_related):
		self.client.force_authenticate(user=self.user)
		mocked_resolve_context.return_value = (SimpleNamespace(id=7), SimpleNamespace(id=12), None)
		mocked_select_related.return_value.filter.return_value.first.return_value = None

		response = self.client.post(
			self.update_product_url,
			{'produkt_id': 99, 'ilosc_produktu': 100},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
		self.assertEqual(response.data['CODE'], 'WAREHOUSE_PRODUCT_NOT_FOUND')

	@patch('meals.api_views.warehouse.timezone.localdate')
	@patch('meals.api_views.warehouse.ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.select_related')
	@patch('meals.api_views.warehouse._ensure_family_membership_for_shopping')
	def test_meal_coverage_filters_planned_meals_from_current_day(
		self,
		mocked_resolve_context,
		mocked_planned_select_related,
		mocked_localdate,
	):
		self.client.force_authenticate(user=self.user)
		mocked_resolve_context.return_value = (SimpleNamespace(id=7), SimpleNamespace(id=12), None)
		mocked_localdate.return_value = date(2026, 4, 6)
		mocked_planned_select_related.return_value.filter.return_value.order_by.return_value = []

		response = self.client.get(self.meal_coverage_url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		mocked_planned_select_related.return_value.filter.assert_called_once_with(
			rodzina_id=12,
			czy_zjedzone=False,
			data__gte=date(2026, 4, 6),
		)

	@patch('meals.api_views.warehouse.ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects.filter')
	@patch('meals.api_views.warehouse.ProjektInflacjaMobileProduktywposilku.objects.select_related')
	@patch('meals.api_views.warehouse.ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.select_related')
	@patch('meals.api_views.warehouse._ensure_family_membership_for_shopping')
	def test_meal_coverage_returns_zero_for_empty_planned_meals(
		self,
		mocked_resolve_context,
		mocked_planned_select_related,
		_mocked_ingredients_select_related,
		_mocked_warehouse_filter,
	):
		self.client.force_authenticate(user=self.user)
		mocked_resolve_context.return_value = (SimpleNamespace(id=7), SimpleNamespace(id=12), None)
		mocked_planned_select_related.return_value.filter.return_value.order_by.return_value = []

		response = self.client.get(self.meal_coverage_url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['rodzina_id'], 12)
		self.assertEqual(response.data['total_planned_meals'], 0)
		self.assertEqual(response.data['covered_meals'], 0)
		self.assertEqual(response.data['uncovered_meals'], 0)
		self.assertEqual(response.data['coverage_percent'], 0.0)

	@patch('meals.api_views.warehouse.ProjektInflacjaMobileProduktywposilku.objects.select_related')
	@patch('meals.api_views.warehouse.ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects.filter')
	@patch('meals.api_views.warehouse._ensure_family_membership_for_shopping')
	def test_possible_meals_returns_only_meals_covered_by_stock(
		self,
		mocked_resolve_context,
		mocked_warehouse_filter,
		mocked_ingredients_select_related,
	):
		self.client.force_authenticate(user=self.user)
		mocked_resolve_context.return_value = (SimpleNamespace(id=7), SimpleNamespace(id=12), None)
		mocked_warehouse_filter.return_value = [
			SimpleNamespace(nazwa_produktu_uproszczonego_id=1, ilosc_produktu=100),
			SimpleNamespace(nazwa_produktu_uproszczonego_id=2, ilosc_produktu=10),
		]

		meal_ok = SimpleNamespace(
			id=10,
			nazwa_posilku=SimpleNamespace(nazwa_posilku='Owsianka'),
			pora_posilku=SimpleNamespace(pora_posilku='Sniadanie'),
			czas_przygotowania='15 min',
		)
		meal_missing = SimpleNamespace(
			id=11,
			nazwa_posilku=SimpleNamespace(nazwa_posilku='Kurczak z ryzem'),
			pora_posilku=SimpleNamespace(pora_posilku='Obiad'),
			czas_przygotowania='35 min',
		)

		mocked_ingredients_select_related.return_value.all.return_value = [
			SimpleNamespace(
				nazwa_posilku=meal_ok,
				nazwa_produktu=SimpleNamespace(nazwa_produktu_uproszczonego_id=1),
				czysta_ilosc_produktu=80,
			),
			SimpleNamespace(
				nazwa_posilku=meal_missing,
				nazwa_produktu=SimpleNamespace(nazwa_produktu_uproszczonego_id=2),
				czysta_ilosc_produktu=50,
			),
		]

		response = self.client.get(self.possible_meals_url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['rodzina_id'], 12)
		self.assertEqual(response.data['liczba_mozliwych_posilkow'], 1)
		self.assertEqual(len(response.data['mozliwe_posilki']), 2)
		self.assertEqual(response.data['mozliwe_posilki'][0]['posilek_w_diecie_id'], 10)
		self.assertEqual(response.data['mozliwe_posilki'][0]['nazwa_posilku'], 'Owsianka')
		self.assertEqual(response.data['mozliwe_posilki'][0]['coverage_percent'], 100.0)
		self.assertTrue(response.data['mozliwe_posilki'][0]['can_prepare'])
		self.assertEqual(response.data['mozliwe_posilki'][1]['posilek_w_diecie_id'], 11)
		self.assertEqual(response.data['mozliwe_posilki'][1]['coverage_percent'], 20.0)
		self.assertFalse(response.data['mozliwe_posilki'][1]['can_prepare'])
