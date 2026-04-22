"""Kalendar tests."""

from types import SimpleNamespace
from unittest.mock import patch
from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from meals.api_views.kalendar import FamilyPlannedMealCreateViewSet


User = get_user_model()


class KalendarApiTests(APITestCase):
	planned_meals_url = '/api/calendar/family-planned-meals/'

	def setUp(self):
		self.user = User.objects.create_user(username='calendar-user', password='testpass123')

	def test_create_planned_meal_requires_authentication(self):
		response = self.client.post(
			self.planned_meals_url,
			{
				'data': '2026-03-28',
				'posilek_w_diecie_id': 10,
			},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_possible_ratings_requires_authentication(self):
		response = self.client.get('/api/calendar/family-planned-meals/possible-ratings/')
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	@patch('meals.api_views.kalendar.ProjektInflacjaMobileMozliweocenyposilku.objects.order_by')
	def test_possible_ratings_returns_values_from_table(self, mocked_order_by):
		self.client.force_authenticate(user=self.user)
		mocked_order_by.return_value.values.return_value = [
			{'id': 1, 'ocena': 'Slabe'},
			{'id': 2, 'ocena': 'Dobre'},
			{'id': 3, 'ocena': 'Bardzo dobre'},
		]

		response = self.client.get('/api/calendar/family-planned-meals/possible-ratings/')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data.get('count'), 3)
		self.assertEqual(len(response.data.get('oceny', [])), 3)
		self.assertEqual(response.data['oceny'][1]['ocena'], 'Dobre')
		mocked_order_by.assert_called_once_with('id')

	@patch('meals.api_views.kalendar.ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.filter')
	@patch('meals.api_views.kalendar.ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.create')
	@patch('meals.api_views.kalendar.ProjektInflacjaMobileUzytkownicywrodzinach.objects.select_related')
	@patch('meals.api_views.kalendar.ProjektInflacjaMobilePosilkiwdiecie.objects.filter')
	@patch('meals.api_views.kalendar.ProjektInflacjaMobilePosilkiwdiecie.objects.select_related')
	@patch('meals.api_views.kalendar._ensure_family_membership_for_planning')
	def test_create_planned_lunch_for_family_with_scaled_ingredients(
		self,
		mocked_resolve_membership,
		mocked_select_related_meal,
		mocked_member_meal_filter,
		mocked_family_members_select_related,
		mocked_create,
		mocked_existing_lunch_filter,
	):
		self.client.force_authenticate(user=self.user)

		membership = SimpleNamespace(id=7, uzytkownik_id=101)
		family = SimpleNamespace(id=12)
		mocked_resolve_membership.return_value = (membership, family, None)

		requested_meal = SimpleNamespace(
			id=10,
			nazwa_posilku_id=111,
			pora_posilku_id=3,
			pora_posilku=SimpleNamespace(pora_posilku='Obiad'),
			kalorycznosc_diety=SimpleNamespace(kalorycznosc=1500),
		)
		mocked_select_related_meal.return_value.filter.return_value.first.return_value = requested_meal

		member_one = SimpleNamespace(
			id=7,
			uzytkownik_id=101,
			kalorycznosc_diety_id=1,
			kalorycznosc_diety=SimpleNamespace(kalorycznosc=1500),
		)
		member_two = SimpleNamespace(
			id=8,
			uzytkownik_id=102,
			kalorycznosc_diety_id=2,
			kalorycznosc_diety=SimpleNamespace(kalorycznosc=2000),
		)
		mocked_family_members_select_related.return_value.filter.return_value = [member_one, member_two]

		member_one_meal_qs = SimpleNamespace(first=lambda: SimpleNamespace(id=10))
		member_two_meal_qs = SimpleNamespace(first=lambda: SimpleNamespace(id=20))
		mocked_member_meal_filter.side_effect = [member_one_meal_qs, member_two_meal_qs]

		mocked_existing_lunch_filter.return_value.exists.return_value = False

		mocked_create.side_effect = [SimpleNamespace(id=99), SimpleNamespace(id=100)]

		response = self.client.post(
			self.planned_meals_url,
			{
				'data': '2026-03-28',
				'posilek_w_diecie_id': 10,
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data['pora_posilku'], 'Obiad')
		self.assertEqual(response.data['rodzina_id'], 12)
		self.assertEqual(response.data['liczba_czlonkow_rodziny'], 2)
		self.assertEqual(response.data['liczba_osob_przy_posilku'], 2)
		self.assertEqual(len(response.data['zaplanowane_posilki']), 2)
		self.assertEqual(response.data['zaplanowane_posilki'][1]['posilek_w_diecie_id'], 20)
		self.assertEqual(response.data['zaplanowane_posilki'][1]['proporcja_kaloryczna'], 1.3333)
		self.assertNotIn('skladniki', response.data)

		self.assertEqual(mocked_create.call_count, 2)

	@patch('meals.api_views.kalendar.ProjektInflacjaMobileUzytkownicywrodzinach.objects.select_related')
	@patch('meals.api_views.kalendar.ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.filter')
	@patch('meals.api_views.kalendar.ProjektInflacjaMobilePosilkiwdiecie.objects.select_related')
	@patch('meals.api_views.kalendar._ensure_family_membership_for_planning')
	def test_create_planned_lunch_returns_400_when_lunch_exists(
		self,
		mocked_resolve_membership,
		mocked_select_related_meal,
		mocked_existing_lunch_filter,
		mocked_family_members_select_related,
	):
		self.client.force_authenticate(user=self.user)

		membership = SimpleNamespace(id=7, uzytkownik_id=101)
		family = SimpleNamespace(id=12)
		mocked_resolve_membership.return_value = (membership, family, None)
		mocked_select_related_meal.return_value.filter.return_value.first.return_value = SimpleNamespace(
			id=10,
			nazwa_posilku_id=111,
			pora_posilku_id=3,
			pora_posilku=SimpleNamespace(pora_posilku='Obiad'),
			kalorycznosc_diety=SimpleNamespace(kalorycznosc=1500),
		)
		mocked_family_members_select_related.return_value.filter.return_value = [membership]
		mocked_existing_lunch_filter.return_value.exists.return_value = True

		response = self.client.post(
			self.planned_meals_url,
			{
				'data': '2026-03-28',
				'posilek_w_diecie_id': 10,
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(response.data.get('CODE'), 'LUNCH_ALREADY_PLANNED')

	@patch('meals.api_views.kalendar.ProjektInflacjaMobilePosilkiwdiecie.objects.select_related')
	@patch('meals.api_views.kalendar._ensure_family_membership_for_planning')
	def test_create_planned_meal_returns_404_when_meal_not_found(self, mocked_resolve_membership, mocked_select_related_meal):
		self.client.force_authenticate(user=self.user)

		membership = SimpleNamespace(id=7)
		family = SimpleNamespace(id=12)
		mocked_resolve_membership.return_value = (membership, family, None)
		mocked_select_related_meal.return_value.filter.return_value.first.return_value = None

		response = self.client.post(
			self.planned_meals_url,
			{
				'data': '2026-03-28',
				'posilek_w_diecie_id': 999,
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
		self.assertEqual(response.data.get('CODE'), 'MEAL_NOT_FOUND')

	@patch('meals.api_views.kalendar.emit_live_shopping_list_updates_for_date')
	@patch('meals.api_views.kalendar.FamilyPlannedMealCreateViewSet._subtract_planned_meal_ingredients_from_warehouse')
	@patch('meals.api_views.kalendar.ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.select_related')
	@patch('meals.api_views.kalendar._ensure_family_membership_for_planning')
	def test_mark_eaten_non_lunch_succeeds_when_warehouse_empty(
		self,
		mocked_resolve_membership,
		mocked_planned_meals_select_related,
		mocked_subtract_ingredients,
		mocked_emit_live_updates,
	):
		self.client.force_authenticate(user=self.user)

		membership = SimpleNamespace(id=7, uzytkownik_id=101)
		family = SimpleNamespace(id=12)
		mocked_resolve_membership.return_value = (membership, family, None)
		mocked_subtract_ingredients.return_value = 0

		planned_meal = SimpleNamespace(
			id=99,
			data='2026-04-01',
			posilki_w_diecie_id=321,
			uzytkownik_w_rodzinie_id=membership.id,
			posilki_w_diecie=SimpleNamespace(
				pora_posilku=SimpleNamespace(pora_posilku='Sniadanie'),
				pora_posilku_id=1,
			),
		)

		entry = SimpleNamespace(
			id=99,
			czy_zjedzone=False,
			posilki_w_diecie_id=321,
			save=MagicMock(),
		)

		lookup_qs = MagicMock()
		lookup_qs.filter.return_value.first.return_value = planned_meal

		target_base_qs = MagicMock()
		target_filtered_qs = MagicMock()
		target_base_qs.filter.return_value = target_filtered_qs
		target_filtered_qs.filter.return_value = [entry]

		mocked_planned_meals_select_related.side_effect = [lookup_qs, target_base_qs]

		response = self.client.post(
			'/api/calendar/family-planned-meals/mark-eaten/',
			{'planned_meal_id': planned_meal.id},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data.get('CODE'), 'PLANNED_MEAL_MARKED_EATEN')
		self.assertEqual(response.data.get('marked_entries'), 1)
		self.assertEqual(response.data.get('consumed_products'), 0)
		self.assertFalse(response.data.get('meal_rating_saved'))
		self.assertTrue(entry.czy_zjedzone)
		entry.save.assert_called_once_with(update_fields=['czy_zjedzone'])
		mocked_subtract_ingredients.assert_called_once_with(family.id, [entry.posilki_w_diecie_id])
		mocked_emit_live_updates.assert_called_once_with(
			family.id,
			planned_meal.data,
			reason='calendar.meal_eaten',
		)

	@patch('meals.api_views.kalendar.ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects.filter')
	@patch('meals.api_views.kalendar.ProjektInflacjaMobileProduktywposilku.objects.select_related')
	def test_subtract_planned_lunch_ingredients_scales_by_member_calories(
		self,
		mocked_ingredients_select_related,
		mocked_warehouse_filter,
	):
		ingredient = SimpleNamespace(
			nazwa_posilku_id=10,
			czysta_ilosc_produktu=100,
			nazwa_produktu=SimpleNamespace(nazwa_produktu_uproszczonego_id=5),
		)
		mocked_ingredients_select_related.return_value.filter.return_value = [ingredient]

		warehouse_product = SimpleNamespace(
			ilosc_produktu=500.0,
			save=MagicMock(),
		)
		mocked_warehouse_filter.return_value.first.return_value = warehouse_product

		planned_entry_base = SimpleNamespace(
			posilki_w_diecie_id=10,
			posilki_w_diecie=SimpleNamespace(
				pora_posilku=SimpleNamespace(pora_posilku='Obiad'),
				kalorycznosc_diety=SimpleNamespace(kalorycznosc=1500),
			),
			uzytkownik_w_rodzinie=SimpleNamespace(
				kalorycznosc_diety=SimpleNamespace(kalorycznosc=1500),
			),
		)
		planned_entry_scaled = SimpleNamespace(
			posilki_w_diecie_id=10,
			posilki_w_diecie=SimpleNamespace(
				pora_posilku=SimpleNamespace(pora_posilku='Obiad'),
				kalorycznosc_diety=SimpleNamespace(kalorycznosc=1500),
			),
			uzytkownik_w_rodzinie=SimpleNamespace(
				kalorycznosc_diety=SimpleNamespace(kalorycznosc=1800),
			),
		)

		consumed_products = FamilyPlannedMealCreateViewSet._subtract_planned_meal_ingredients_from_warehouse(
			family_id=12,
			meal_ids=[10, 10],
			planned_entries=[planned_entry_base, planned_entry_scaled],
		)

		self.assertEqual(consumed_products, 1)
		self.assertAlmostEqual(warehouse_product.ilosc_produktu, 280.0)
		warehouse_product.save.assert_called_once_with(update_fields=['ilosc_produktu'])

	@patch('meals.api_views.kalendar.emit_live_shopping_list_updates_for_date')
	@patch('meals.api_views.kalendar.ProjektInflacjaMobileOcenaposilkuprzezuzytkownika.objects.update_or_create')
	@patch('meals.api_views.kalendar.ProjektInflacjaMobileMozliweocenyposilku.objects.filter')
	@patch('meals.api_views.kalendar.FamilyPlannedMealCreateViewSet._subtract_planned_meal_ingredients_from_warehouse')
	@patch('meals.api_views.kalendar.ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.select_related')
	@patch('meals.api_views.kalendar._ensure_family_membership_for_planning')
	def test_mark_eaten_saves_rating_when_rating_id_provided(
		self,
		mocked_resolve_membership,
		mocked_planned_meals_select_related,
		mocked_subtract_ingredients,
		mocked_possible_ratings_filter,
		mocked_rating_update_or_create,
		mocked_emit_live_updates,
	):
		self.client.force_authenticate(user=self.user)

		membership = SimpleNamespace(id=7, uzytkownik_id=101)
		family = SimpleNamespace(id=12)
		mocked_resolve_membership.return_value = (membership, family, None)
		mocked_subtract_ingredients.return_value = 0
		mocked_possible_ratings_filter.return_value.first.return_value = SimpleNamespace(
			id=4,
			ocena='Dobre',
		)

		planned_meal = SimpleNamespace(
			id=99,
			data='2026-04-01',
			posilki_w_diecie_id=321,
			uzytkownik_w_rodzinie_id=membership.id,
			posilki_w_diecie=SimpleNamespace(
				pora_posilku=SimpleNamespace(pora_posilku='Sniadanie'),
				pora_posilku_id=1,
			),
		)

		entry = SimpleNamespace(
			id=99,
			uzytkownik_w_rodzinie_id=membership.id,
			czy_zjedzone=False,
			posilki_w_diecie_id=321,
			save=MagicMock(),
		)

		lookup_qs = MagicMock()
		lookup_qs.filter.return_value.first.return_value = planned_meal

		target_base_qs = MagicMock()
		target_filtered_qs = MagicMock()
		target_base_qs.filter.return_value = target_filtered_qs
		target_filtered_qs.filter.return_value = [entry]

		mocked_planned_meals_select_related.side_effect = [lookup_qs, target_base_qs]

		response = self.client.post(
			'/api/calendar/family-planned-meals/mark-eaten/',
			{'planned_meal_id': planned_meal.id, 'ocena_id': 4},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertTrue(response.data.get('meal_rating_saved'))
		mocked_possible_ratings_filter.assert_called_once_with(id=4)
		mocked_rating_update_or_create.assert_called_once_with(
			uzytkownik_id=self.user.id,
			posilek_id=entry.posilki_w_diecie_id,
			data_oceny=planned_meal.data,
			defaults={'ocena_id': 4},
		)
		mocked_emit_live_updates.assert_called_once_with(
			family.id,
			planned_meal.data,
			reason='calendar.meal_eaten',
		)

	@patch('meals.api_views.kalendar.ProjektInflacjaMobileMozliweocenyposilku.objects.filter')
	@patch('meals.api_views.kalendar.ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.select_related')
	@patch('meals.api_views.kalendar._ensure_family_membership_for_planning')
	def test_mark_eaten_returns_400_when_rating_not_found(
		self,
		mocked_resolve_membership,
		mocked_planned_meals_select_related,
		mocked_possible_ratings_filter,
	):
		self.client.force_authenticate(user=self.user)

		membership = SimpleNamespace(id=7, uzytkownik_id=101)
		family = SimpleNamespace(id=12)
		mocked_resolve_membership.return_value = (membership, family, None)
		mocked_possible_ratings_filter.return_value.first.return_value = None

		planned_meal = SimpleNamespace(
			id=99,
			data='2026-04-01',
			posilki_w_diecie_id=321,
			uzytkownik_w_rodzinie_id=membership.id,
			posilki_w_diecie=SimpleNamespace(
				pora_posilku=SimpleNamespace(pora_posilku='Sniadanie'),
				pora_posilku_id=1,
			),
		)

		mocked_planned_meals_select_related.return_value.filter.return_value.first.return_value = planned_meal

		response = self.client.post(
			'/api/calendar/family-planned-meals/mark-eaten/',
			{'planned_meal_id': planned_meal.id, 'ocena_id': 999},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(response.data.get('CODE'), 'MEAL_RATING_NOT_FOUND')

	@patch('meals.api_views.kalendar.emit_live_shopping_list_updates_for_date')
	@patch('meals.api_views.kalendar.ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.filter')
	@patch('meals.api_views.kalendar.ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.select_related')
	@patch('meals.api_views.kalendar._ensure_family_membership_for_planning')
	def test_remove_non_lunch_planned_meal_succeeds(
		self,
		mocked_resolve_membership,
		mocked_select_related,
		mocked_filter,
		mocked_emit_live_updates,
	):
		self.client.force_authenticate(user=self.user)

		membership = SimpleNamespace(id=7, uzytkownik_id=101)
		family = SimpleNamespace(id=12)
		mocked_resolve_membership.return_value = (membership, family, None)

		planned_meal = SimpleNamespace(
			id=99,
			data='2026-04-02',
			uzytkownik_w_rodzinie_id=membership.id,
			posilki_w_diecie=SimpleNamespace(
				pora_posilku=SimpleNamespace(pora_posilku='Sniadanie'),
				pora_posilku_id=1,
			),
		)
		mocked_select_related.return_value.filter.return_value.first.return_value = planned_meal

		target_entries_qs = MagicMock()
		target_entries_qs.filter.return_value = target_entries_qs
		target_entries_qs.__iter__.return_value = iter([SimpleNamespace(id=99)])
		mocked_filter.return_value = target_entries_qs

		response = self.client.post(
			'/api/calendar/family-planned-meals/remove/',
			{'planned_meal_id': planned_meal.id},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data.get('CODE'), 'PLANNED_MEAL_REMOVED')
		self.assertEqual(response.data.get('deleted_entries'), 1)
		target_entries_qs.delete.assert_called_once()
		mocked_emit_live_updates.assert_called_once_with(
			family.id,
			planned_meal.data,
			reason='calendar.meal_removed',
		)

	@patch('meals.api_views.kalendar.ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.select_related')
	@patch('meals.api_views.kalendar._ensure_family_membership_for_planning')
	def test_remove_non_lunch_planned_meal_forbidden_for_other_member(
		self,
		mocked_resolve_membership,
		mocked_select_related,
	):
		self.client.force_authenticate(user=self.user)

		membership = SimpleNamespace(id=7, uzytkownik_id=101)
		family = SimpleNamespace(id=12)
		mocked_resolve_membership.return_value = (membership, family, None)

		planned_meal = SimpleNamespace(
			id=99,
			data='2026-04-02',
			uzytkownik_w_rodzinie_id=999,
			posilki_w_diecie=SimpleNamespace(
				pora_posilku=SimpleNamespace(pora_posilku='Sniadanie'),
				pora_posilku_id=1,
			),
		)
		mocked_select_related.return_value.filter.return_value.first.return_value = planned_meal

		response = self.client.post(
			'/api/calendar/family-planned-meals/remove/',
			{'planned_meal_id': planned_meal.id},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
		self.assertEqual(response.data.get('CODE'), 'FORBIDDEN_MEAL_REMOVE')
