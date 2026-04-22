"""Shoping list tests."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from meals.api_views.shoping_list import (
	FamilyShoppingListFromCalendarCreateViewSet,
	_build_live_shopping_list_output,
)


User = get_user_model()


class ShopingListApiTests(APITestCase):
	shopping_list_from_calendar_url = '/api/shopping-lists/from-calendar/'
	shopping_lists_url = '/api/shopping-lists/'
	shopping_list_mark_bought_url = '/api/shopping-lists/products/mark-bought/'
	shopping_list_detail_url = '/api/shopping-lists/1/'

	def setUp(self):
		self.user = User.objects.create_user(username='shop-list-user', password='testpass123')

	def test_create_shopping_list_from_calendar_requires_authentication(self):
		response = self.client.post(
			self.shopping_list_from_calendar_url,
			{
				'data_od': '2026-03-28',
				'data_do': '2026-03-28',
			},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_read_shopping_lists_requires_authentication(self):
		response = self.client.get(self.shopping_lists_url)
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_mark_bought_requires_authentication(self):
		response = self.client.post(
			self.shopping_list_mark_bought_url,
			{'shopping_list_id': 1, 'produkt_id': 2},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_delete_shopping_list_requires_authentication(self):
		response = self.client.delete(self.shopping_list_detail_url)
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_normalize_measure_unit_maps_liquids_to_ml(self):
		self.assertEqual(FamilyShoppingListFromCalendarCreateViewSet._normalize_measure_unit('ml'), 'ml')
		self.assertEqual(FamilyShoppingListFromCalendarCreateViewSet._normalize_measure_unit('mililitry'), 'ml')
		self.assertEqual(FamilyShoppingListFromCalendarCreateViewSet._normalize_measure_unit('l'), 'ml')
		self.assertEqual(FamilyShoppingListFromCalendarCreateViewSet._normalize_measure_unit('ltr'), 'ml')
		self.assertEqual(
			FamilyShoppingListFromCalendarCreateViewSet._normalize_measure_unit('g', product_name='Sok marchwiowy'),
			'ml',
		)
		self.assertEqual(FamilyShoppingListFromCalendarCreateViewSet._normalize_measure_unit('g'), 'g')

	@patch('meals.api_views.shoping_list.ShoppingPackagePreference.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileKolejnosckategoriiwsklepie.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileProduktywposilku.objects.select_related')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.select_related')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileListazakupowrodziny.objects.filter')
	def test_build_live_output_includes_last_package_size_for_product(
		self,
		mocked_lists_filter,
		mocked_planned_select_related,
		mocked_ingredients_select_related,
		mocked_warehouse_filter,
		mocked_store_order_filter,
		mocked_package_preference_filter,
	):
		shopping_list = SimpleNamespace(
			id=77,
			data_od=date(2026, 3, 28),
			data_do=date(2026, 3, 28),
			rodzina=SimpleNamespace(sklep_id=2),
		)
		mocked_lists_filter.return_value.first.return_value = shopping_list

		meal = SimpleNamespace(pora_posilku=SimpleNamespace(pora_posilku='Sniadanie'))
		member = SimpleNamespace(kalorycznosc_diety=SimpleNamespace(kalorycznosc=2000))
		planned_meal = SimpleNamespace(
			posilki_w_diecie_id=10,
			posilki_w_diecie=meal,
			uzytkownik_w_rodzinie=member,
		)
		mocked_planned_select_related.return_value.filter.return_value = [planned_meal]

		ingredient = SimpleNamespace(
			nazwa_posilku_id=10,
			czysta_ilosc_produktu=120,
			nazwa_produktu_id=501,
			nazwa_produktu=SimpleNamespace(
				nazwa_produktu='Ryż',
				nazwa_produktu_uproszczonego_id=44,
				nazwa_produktu_uproszczonego=SimpleNamespace(
					kategoria_produktu=SimpleNamespace(id=33, nazwa_kategorii='Warzywa i przetwory warzywne')
				),
			),
			miarka=SimpleNamespace(nazwa_miarki='g'),
		)
		mocked_ingredients_select_related.return_value.filter.return_value = [ingredient]
		mocked_warehouse_filter.return_value = []
		mocked_store_order_filter.return_value.select_related.return_value = []
		mocked_package_preference_filter.return_value = [
			SimpleNamespace(
				nazwa_produktu_uproszczonego_id=44,
				wielkosc_opakowania=200.0,
				jednostka_opakowania='g',
			)
		]

		output, live_error = _build_live_shopping_list_output(12, 77)

		self.assertIsNone(live_error)
		self.assertEqual(output['liczba_pozycji_na_liscie'], 1)
		self.assertEqual(output['produkty'][0]['produkt_id'], 501)
		self.assertEqual(output['produkty'][0]['ostatnia_wielkosc_opakowania'], 200.0)
		self.assertEqual(output['produkty'][0]['jednostka_ostatniego_opakowania'], 'g')

	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.select_related')
	@patch('meals.api_views.shoping_list._ensure_family_membership_for_shopping')
	def test_create_shopping_list_from_calendar_returns_404_when_calendar_empty(self, mocked_resolve_context, mocked_select_related_planned):
		self.client.force_authenticate(user=self.user)

		mocked_resolve_context.return_value = (
			SimpleNamespace(id=7, uzytkownik_id=101),
			SimpleNamespace(id=12, sklep_id=2),
			None,
		)
		mocked_select_related_planned.return_value.filter.return_value = []

		response = self.client.post(
			self.shopping_list_from_calendar_url,
			{
				'data_od': '2026-03-28',
				'data_do': '2026-03-28',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
		self.assertEqual(response.data.get('CODE'), 'CALENDAR_EMPTY')
		mocked_select_related_planned.return_value.filter.assert_called_once_with(
			rodzina_id=12,
			data__gte=date(2026, 3, 28),
			data__lte=date(2026, 3, 28),
			czy_zjedzone=False,
		)

	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileProduktynalisciezakupowrodziny.objects.create')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileKolejnosckategoriiwsklepie.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileListazakupowrodziny.objects.create')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileListazakupowrodziny.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileProduktywposilku.objects.select_related')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.select_related')
	@patch('meals.api_views.shoping_list._ensure_family_membership_for_shopping')
	def test_create_shopping_list_from_calendar_success_with_kcal_scaling(
		self,
		mocked_resolve_context,
		mocked_planned_select_related,
		mocked_ingredients_select_related,
		mocked_warehouse_filter,
		mocked_list_name_filter,
		mocked_list_create,
		mocked_store_order_filter,
		_mocked_products_create,
	):
		self.client.force_authenticate(user=self.user)

		membership = SimpleNamespace(id=7, uzytkownik_id=101)
		family = SimpleNamespace(id=12, sklep_id=2)
		mocked_resolve_context.return_value = (membership, family, None)

		meal = SimpleNamespace(
			id=10,
			kalorycznosc_diety=SimpleNamespace(kalorycznosc=1500),
			pora_posilku=SimpleNamespace(pora_posilku='Obiad'),
		)
		member_one = SimpleNamespace(kalorycznosc_diety=SimpleNamespace(kalorycznosc=1500))
		member_two = SimpleNamespace(kalorycznosc_diety=SimpleNamespace(kalorycznosc=2000))
		planned_one = SimpleNamespace(posilki_w_diecie_id=10, posilki_w_diecie=meal, uzytkownik_w_rodzinie=member_one)
		planned_two = SimpleNamespace(posilki_w_diecie_id=10, posilki_w_diecie=meal, uzytkownik_w_rodzinie=member_two)
		mocked_planned_select_related.return_value.filter.return_value = [planned_one, planned_two]

		ingredient = SimpleNamespace(
			nazwa_posilku_id=10,
			czysta_ilosc_produktu=120,
			nazwa_produktu_id=501,
			nazwa_produktu=SimpleNamespace(
				nazwa_produktu='Ryż',
				nazwa_produktu_uproszczonego=SimpleNamespace(
					kategoria_produktu=SimpleNamespace(id=33)
				),
			),
			miarka=SimpleNamespace(nazwa_miarki='g'),
		)
		mocked_ingredients_select_related.return_value.filter.return_value = [ingredient]
		mocked_warehouse_filter.return_value = []

		mocked_list_name_filter.return_value.exists.return_value = False
		mocked_list_create.return_value = SimpleNamespace(id=77, nazwa_listy_zakupow='Lista zakupow 2026-03-28 - 2026-03-28')

		order_qs = SimpleNamespace(
			filter=lambda **kwargs: SimpleNamespace(order_by=lambda *args, **inner_kwargs: SimpleNamespace(first=lambda: SimpleNamespace(id=9, kolejnosc=1))),
			order_by=lambda *args, **kwargs: SimpleNamespace(first=lambda: SimpleNamespace(id=9, kolejnosc=1)),
		)
		mocked_store_order_filter.return_value = order_qs

		response = self.client.post(
			self.shopping_list_from_calendar_url,
			{
				'data_od': '2026-03-28',
				'data_do': '2026-03-28',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data['lista_zakupow_id'], 77)
		self.assertEqual(response.data['rodzina_id'], 12)
		self.assertEqual(response.data['liczba_zaplanowanych_posilkow'], 2)
		self.assertEqual(response.data['liczba_pozycji_na_liscie'], 1)
		self.assertNotIn('produkty', response.data)

	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileProduktynalisciezakupowrodziny.objects.create')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileKolejnosckategoriiwsklepie.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileListazakupowrodziny.objects.create')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileListazakupowrodziny.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileProduktywposilku.objects.select_related')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.select_related')
	@patch('meals.api_views.shoping_list._ensure_family_membership_for_shopping')
	def test_create_shopping_list_from_calendar_does_not_scale_non_lunch_meals(
		self,
		mocked_resolve_context,
		mocked_planned_select_related,
		mocked_ingredients_select_related,
		mocked_warehouse_filter,
		mocked_list_name_filter,
		mocked_list_create,
		mocked_store_order_filter,
		mocked_products_create,
	):
		self.client.force_authenticate(user=self.user)

		membership = SimpleNamespace(id=7, uzytkownik_id=101)
		family = SimpleNamespace(id=12, sklep_id=2)
		mocked_resolve_context.return_value = (membership, family, None)

		meal = SimpleNamespace(
			id=10,
			kalorycznosc_diety=SimpleNamespace(kalorycznosc=1500),
			pora_posilku=SimpleNamespace(pora_posilku='Sniadanie'),
		)
		member = SimpleNamespace(kalorycznosc_diety=SimpleNamespace(kalorycznosc=1000))
		planned = SimpleNamespace(posilki_w_diecie_id=10, posilki_w_diecie=meal, uzytkownik_w_rodzinie=member)
		mocked_planned_select_related.return_value.filter.return_value = [planned]

		ingredient = SimpleNamespace(
			nazwa_posilku_id=10,
			czysta_ilosc_produktu=120,
			nazwa_produktu_id=501,
			nazwa_produktu=SimpleNamespace(
				nazwa_produktu='Ryż',
				nazwa_produktu_uproszczonego=SimpleNamespace(
					kategoria_produktu=SimpleNamespace(id=33)
				),
			),
			miarka=SimpleNamespace(nazwa_miarki='g'),
		)
		mocked_ingredients_select_related.return_value.filter.return_value = [ingredient]
		mocked_warehouse_filter.return_value = []

		mocked_list_name_filter.return_value.exists.return_value = False
		mocked_list_create.return_value = SimpleNamespace(id=79, nazwa_listy_zakupow='Lista zakupow 2026-03-28 - 2026-03-28')

		order_qs = SimpleNamespace(
			filter=lambda **kwargs: SimpleNamespace(order_by=lambda *args, **inner_kwargs: SimpleNamespace(first=lambda: SimpleNamespace(id=9, kolejnosc=1))),
			order_by=lambda *args, **kwargs: SimpleNamespace(first=lambda: SimpleNamespace(id=9, kolejnosc=1)),
		)
		mocked_store_order_filter.return_value = order_qs

		response = self.client.post(
			self.shopping_list_from_calendar_url,
			{
				'data_od': '2026-03-28',
				'data_do': '2026-03-28',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		created_kwargs = mocked_products_create.call_args.kwargs
		self.assertEqual(created_kwargs['ilosc_produktu_do_kupienia'], '120.0 g')

	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileProduktynalisciezakupowrodziny.objects.create')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileKolejnosckategoriiwsklepie.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileListazakupowrodziny.objects.create')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileListazakupowrodziny.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileProduktywposilku.objects.select_related')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.select_related')
	@patch('meals.api_views.shoping_list._ensure_family_membership_for_shopping')
	def test_create_shopping_list_from_calendar_subtracts_family_warehouse_stock(
		self,
		mocked_resolve_context,
		mocked_planned_select_related,
		mocked_ingredients_select_related,
		mocked_warehouse_filter,
		mocked_list_name_filter,
		mocked_list_create,
		mocked_store_order_filter,
		_mocked_products_create,
	):
		self.client.force_authenticate(user=self.user)

		membership = SimpleNamespace(id=7, uzytkownik_id=101)
		family = SimpleNamespace(id=12, sklep_id=2)
		mocked_resolve_context.return_value = (membership, family, None)

		meal = SimpleNamespace(id=10, kalorycznosc_diety=SimpleNamespace(kalorycznosc=1500))
		member = SimpleNamespace(kalorycznosc_diety=SimpleNamespace(kalorycznosc=1500))
		planned = SimpleNamespace(posilki_w_diecie_id=10, posilki_w_diecie=meal, uzytkownik_w_rodzinie=member)
		mocked_planned_select_related.return_value.filter.return_value = [planned]

		ingredient = SimpleNamespace(
			nazwa_posilku_id=10,
			czysta_ilosc_produktu=200,
			nazwa_produktu_id=501,
			nazwa_produktu=SimpleNamespace(
				nazwa_produktu='Ryż',
				nazwa_produktu_uproszczonego_id=44,
				nazwa_produktu_uproszczonego=SimpleNamespace(
					kategoria_produktu=SimpleNamespace(id=33)
				),
			),
			miarka=SimpleNamespace(nazwa_miarki='g'),
		)
		mocked_ingredients_select_related.return_value.filter.return_value = [ingredient]
		mocked_warehouse_filter.return_value = [
			SimpleNamespace(nazwa_produktu_uproszczonego_id=44, ilosc_produktu=80),
		]

		mocked_list_name_filter.return_value.exists.return_value = False
		mocked_list_create.return_value = SimpleNamespace(id=78, nazwa_listy_zakupow='Lista zakupow 2026-03-28 - 2026-03-28')

		order_qs = SimpleNamespace(
			filter=lambda **kwargs: SimpleNamespace(order_by=lambda *args, **inner_kwargs: SimpleNamespace(first=lambda: SimpleNamespace(id=9, kolejnosc=1))),
			order_by=lambda *args, **kwargs: SimpleNamespace(first=lambda: SimpleNamespace(id=9, kolejnosc=1)),
		)
		mocked_store_order_filter.return_value = order_qs

		response = self.client.post(
			self.shopping_list_from_calendar_url,
			{
				'data_od': '2026-03-28',
				'data_do': '2026-03-28',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data['liczba_pozycji_na_liscie'], 1)
		self.assertNotIn('produkty', response.data)

	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileProduktynalisciezakupowrodziny.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileListazakupowrodziny.objects.filter')
	@patch('meals.api_views.shoping_list._ensure_family_membership_for_shopping')
	def test_read_shopping_lists_success(self, mocked_resolve_context, mocked_lists_filter, mocked_products_filter):
		self.client.force_authenticate(user=self.user)

		mocked_resolve_context.return_value = (SimpleNamespace(id=7), SimpleNamespace(id=12), None)
		shopping_lists = [
			SimpleNamespace(id=101, nazwa_listy_zakupow='Lista A', data_od='2026-03-28', data_do='2026-03-28'),
			SimpleNamespace(id=102, nazwa_listy_zakupow='Lista B', data_od='2026-03-29', data_do='2026-03-29'),
		]
		mocked_lists_filter.return_value.order_by.return_value = shopping_lists
		mocked_products_filter.return_value = [
			SimpleNamespace(lista_zakupow_id=101),
			SimpleNamespace(lista_zakupow_id=101),
			SimpleNamespace(lista_zakupow_id=102),
		]

		response = self.client.get(self.shopping_lists_url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data), 2)

	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileProduktynalisciezakupowrodziny.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileListazakupowrodziny.objects.filter')
	@patch('meals.api_views.shoping_list._ensure_family_membership_for_shopping')
	def test_delete_shopping_list_success(self, mocked_resolve_context, mocked_lists_filter, mocked_products_filter):
		self.client.force_authenticate(user=self.user)

		mocked_resolve_context.return_value = (SimpleNamespace(id=7), SimpleNamespace(id=12), None)
		shopping_list = SimpleNamespace(id=1, nazwa_listy_zakupow='Lista A', delete=Mock())
		mocked_lists_filter.return_value.first.return_value = shopping_list
		mocked_products_filter.return_value.delete.return_value = (3, {})

		response = self.client.delete(self.shopping_list_detail_url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data.get('CODE'), 'SHOPPING_LIST_DELETED')
		self.assertEqual(response.data.get('shopping_list_id'), 1)
		self.assertEqual(response.data.get('deleted_products'), 3)
		shopping_list.delete.assert_called_once_with()

	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileListazakupowrodziny.objects.filter')
	@patch('meals.api_views.shoping_list._ensure_family_membership_for_shopping')
	def test_delete_shopping_list_returns_404_when_missing(self, mocked_resolve_context, mocked_lists_filter):
		self.client.force_authenticate(user=self.user)

		mocked_resolve_context.return_value = (SimpleNamespace(id=7), SimpleNamespace(id=12), None)
		mocked_lists_filter.return_value.first.return_value = None

		response = self.client.delete(self.shopping_list_detail_url)

		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
		self.assertEqual(response.data.get('CODE'), 'SHOPPING_LIST_NOT_FOUND')

	@patch('meals.api_views.shoping_list.emit_live_shopping_list_update')
	@patch('meals.api_views.shoping_list._build_live_shopping_list_output')
	@patch('meals.api_views.shoping_list.ShoppingPackagePreference.objects.update_or_create')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileProdukty.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects.create')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileProduktynalisciezakupowrodziny.objects.select_related')
	@patch('meals.api_views.shoping_list._ensure_family_membership_for_shopping')
	def test_mark_bought_moves_product_amount_to_warehouse(
		self,
		mocked_resolve_context,
		mocked_list_products_select_related,
		mocked_warehouse_filter,
		mocked_warehouse_create,
		mocked_products_filter,
		mocked_package_preference_update,
		mocked_build_live_output,
		mocked_emit_live_update,
	):
		self.client.force_authenticate(user=self.user)
		mocked_resolve_context.return_value = (SimpleNamespace(id=7), SimpleNamespace(id=12), None)
		mocked_build_live_output.return_value = (None, {'CODE': 'NOT_USED'})
		mocked_products_filter.return_value.first.return_value = None

		list_product = SimpleNamespace(
			ilosc_produktu_do_kupienia='25.5 g',
			nazwa_produktu=SimpleNamespace(nazwa_produktu_uproszczonego_id=44),
			delete=Mock(),
		)
		mocked_list_products_select_related.return_value.filter.return_value.first.return_value = list_product

		existing_warehouse_product = SimpleNamespace(ilosc_produktu=10.0, save=Mock())
		mocked_warehouse_filter.return_value.first.return_value = existing_warehouse_product

		response = self.client.post(
			self.shopping_list_mark_bought_url,
			{'shopping_list_id': 77, 'produkt_id': 501},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['shopping_list_id'], 77)
		self.assertEqual(response.data['produkt_id'], 501)
		self.assertEqual(response.data['ilosc_dodana_do_magazynu'], 25.5)
		self.assertEqual(response.data['jednostka_dodanej_ilosci'], 'g')
		self.assertEqual(existing_warehouse_product.ilosc_produktu, 35.5)
		existing_warehouse_product.save.assert_called_once_with(update_fields=['ilosc_produktu'])
		list_product.delete.assert_called_once()
		mocked_warehouse_create.assert_not_called()
		mocked_package_preference_update.assert_not_called()
		mocked_emit_live_update.assert_called_once_with(12, 77, reason='shopping_list.product_marked_bought')

	@patch('meals.api_views.shoping_list.emit_live_shopping_list_update')
	@patch('meals.api_views.shoping_list._build_live_shopping_list_output')
	@patch('meals.api_views.shoping_list.ShoppingPackagePreference.objects.update_or_create')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileProdukty.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects.create')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileProduktynalisciezakupowrodziny.objects.select_related')
	@patch('meals.api_views.shoping_list._ensure_family_membership_for_shopping')
	def test_mark_bought_uses_live_payload_when_product_not_persisted(
		self,
		mocked_resolve_context,
		mocked_list_products_select_related,
		mocked_warehouse_filter,
		mocked_warehouse_create,
		mocked_products_filter,
		mocked_package_preference_update,
		mocked_build_live_output,
		mocked_emit_live_update,
	):
		self.client.force_authenticate(user=self.user)
		mocked_resolve_context.return_value = (SimpleNamespace(id=7), SimpleNamespace(id=12), None)

		mocked_list_products_select_related.return_value.filter.return_value.first.return_value = None
		mocked_build_live_output.return_value = (
			{
				'produkty': [
					{
						'produkt_id': 501,
						'ilosc_produktu_do_kupienia': '25.5 g',
					}
				]
			},
			None,
		)
		mocked_products_filter.return_value.first.return_value = SimpleNamespace(
			nazwa_produktu_uproszczonego_id=44,
		)

		existing_warehouse_product = SimpleNamespace(ilosc_produktu=10.0, save=Mock())
		mocked_warehouse_filter.return_value.first.return_value = existing_warehouse_product

		response = self.client.post(
			self.shopping_list_mark_bought_url,
			{'shopping_list_id': 77, 'produkt_id': 501},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['shopping_list_id'], 77)
		self.assertEqual(response.data['produkt_id'], 501)
		self.assertEqual(response.data['ilosc_dodana_do_magazynu'], 25.5)
		self.assertEqual(response.data['jednostka_dodanej_ilosci'], 'g')
		self.assertEqual(existing_warehouse_product.ilosc_produktu, 35.5)
		existing_warehouse_product.save.assert_called_once_with(update_fields=['ilosc_produktu'])
		mocked_warehouse_create.assert_not_called()
		mocked_package_preference_update.assert_not_called()
		mocked_emit_live_update.assert_called_once_with(12, 77, reason='shopping_list.product_marked_bought')

	@patch('meals.api_views.shoping_list.emit_live_shopping_list_update')
	@patch('meals.api_views.shoping_list._build_live_shopping_list_output')
	@patch('meals.api_views.shoping_list.ShoppingPackagePreference.objects.update_or_create')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileProdukty.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects.create')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileProduktynalisciezakupowrodziny.objects.select_related')
	@patch('meals.api_views.shoping_list._ensure_family_membership_for_shopping')
	def test_mark_bought_uses_package_size_when_provided(
		self,
		mocked_resolve_context,
		mocked_list_products_select_related,
		mocked_warehouse_filter,
		mocked_warehouse_create,
		mocked_products_filter,
		mocked_package_preference_update,
		mocked_build_live_output,
		mocked_emit_live_update,
	):
		self.client.force_authenticate(user=self.user)
		mocked_resolve_context.return_value = (SimpleNamespace(id=7), SimpleNamespace(id=12), None)
		mocked_build_live_output.return_value = (None, {'CODE': 'NOT_USED'})
		mocked_products_filter.return_value.first.return_value = None

		list_product = SimpleNamespace(
			ilosc_produktu_do_kupienia='40 g',
			nazwa_produktu=SimpleNamespace(nazwa_produktu_uproszczonego_id=44),
			delete=Mock(),
		)
		mocked_list_products_select_related.return_value.filter.return_value.first.return_value = list_product

		existing_warehouse_product = SimpleNamespace(ilosc_produktu=10.0, save=Mock())
		mocked_warehouse_filter.return_value.first.return_value = existing_warehouse_product

		response = self.client.post(
			self.shopping_list_mark_bought_url,
			{
				'shopping_list_id': 77,
				'produkt_id': 501,
				'wielkosc_opakowania': 200,
				'jednostka_opakowania': 'g',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['shopping_list_id'], 77)
		self.assertEqual(response.data['produkt_id'], 501)
		self.assertEqual(response.data['ilosc_dodana_do_magazynu'], 200.0)
		self.assertEqual(response.data['jednostka_dodanej_ilosci'], 'g')
		self.assertEqual(existing_warehouse_product.ilosc_produktu, 210.0)
		existing_warehouse_product.save.assert_called_once_with(update_fields=['ilosc_produktu'])
		list_product.delete.assert_called_once()
		mocked_warehouse_create.assert_not_called()
		mocked_package_preference_update.assert_called_once_with(
			rodzina_id=12,
			nazwa_produktu_uproszczonego_id=44,
			defaults={
				'wielkosc_opakowania': 200.0,
				'jednostka_opakowania': 'g',
			},
		)
		mocked_emit_live_update.assert_called_once_with(12, 77, reason='shopping_list.product_marked_bought')

	@patch('meals.api_views.shoping_list._build_live_shopping_list_output')
	@patch('meals.api_views.shoping_list.ShoppingPackagePreference.objects.update_or_create')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileProdukty.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects.filter')
	@patch('meals.api_views.shoping_list.ProjektInflacjaMobileProduktynalisciezakupowrodziny.objects.select_related')
	@patch('meals.api_views.shoping_list._ensure_family_membership_for_shopping')
	def test_mark_bought_rejects_package_unit_mismatch(
		self,
		mocked_resolve_context,
		mocked_list_products_select_related,
		mocked_warehouse_filter,
		mocked_package_preference_update,
		mocked_products_filter,
		mocked_build_live_output,
	):
		self.client.force_authenticate(user=self.user)
		mocked_resolve_context.return_value = (SimpleNamespace(id=7), SimpleNamespace(id=12), None)
		mocked_build_live_output.return_value = (None, {'CODE': 'NOT_USED'})
		mocked_products_filter.return_value.first.return_value = None
		mocked_warehouse_filter.return_value.first.return_value = None

		list_product = SimpleNamespace(
			ilosc_produktu_do_kupienia='40 g',
			nazwa_produktu=SimpleNamespace(nazwa_produktu_uproszczonego_id=44),
			delete=Mock(),
		)
		mocked_list_products_select_related.return_value.filter.return_value.first.return_value = list_product

		response = self.client.post(
			self.shopping_list_mark_bought_url,
			{
				'shopping_list_id': 77,
				'produkt_id': 501,
				'wielkosc_opakowania': 200,
				'jednostka_opakowania': 'ml',
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(response.data.get('CODE'), 'INVALID_PACKAGE_UNIT')
		mocked_package_preference_update.assert_not_called()
		list_product.delete.assert_not_called()
