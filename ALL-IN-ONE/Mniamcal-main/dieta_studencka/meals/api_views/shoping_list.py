"""Shoping list API views category."""

from collections import defaultdict
import re

from django.db.utils import OperationalError, ProgrammingError
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from meals.models import (
	AuthUser,
	ShoppingPackagePreference,
	ProjektInflacjaMobileKalorycznoscdiety,
	ProjektInflacjaMobileKolejnosckategoriiwsklepie,
	ProjektInflacjaMobileListazakupowrodziny,
	ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny,
	ProjektInflacjaMobileProdukty,
	ProjektInflacjaMobileProduktynalisciezakupowrodziny,
	ProjektInflacjaMobileProduktywposilku,
	ProjektInflacjaMobileRodziny,
	ProjektInflacjaMobileUzytkownicywrodzinach,
	ProjektInflacjaMobileZaplanowaneposilkirodziny,
)
from meals.serializers import ApiErrorSerializer
from meals.serializers.shoping_list import (
	FamilyShoppingListCreateFromCalendarResponseSerializer,
	FamilyShoppingListCreateFromCalendarSerializer,
	FamilyShoppingListDeleteResponseSerializer,
	FamilyShoppingListMarkBoughtResponseSerializer,
	FamilyShoppingListMarkBoughtSerializer,
	FamilyShoppingListReadDetailSerializer,
	FamilyShoppingListSummarySerializer,
)
from meals.services.shopping_list_realtime import emit_live_shopping_list_update


def _ensure_family_membership_for_shopping(user):
	membership = (
		ProjektInflacjaMobileUzytkownicywrodzinach.objects
		.filter(uzytkownik_id=user.id)
		.select_related('rodzina')
		.first()
	)
	if membership is not None:
		return membership, membership.rodzina, None

	family = ProjektInflacjaMobileRodziny.objects.filter(zalozyciel_rodziny_id=user.id).first()
	if family is None:
		return None, None, {
			'CODE': 'FAMILY_NOT_FOUND',
			'detail': 'Uzytkownik nie nalezy do zadnej rodziny.',
			'status': status.HTTP_404_NOT_FOUND,
		}

	auth_user = AuthUser.objects.filter(id=user.id).first()
	if auth_user is None:
		return None, None, {
			'CODE': 'USER_MAPPING_NOT_FOUND',
			'detail': 'Nie znaleziono mapowania uzytkownika w tabeli auth_user.',
			'status': status.HTTP_404_NOT_FOUND,
		}

	default_diet_calorie = ProjektInflacjaMobileKalorycznoscdiety.objects.order_by('id').first()
	if default_diet_calorie is None:
		return None, None, {
			'CODE': 'DIET_OPTION_NOT_FOUND',
			'detail': 'Brak skonfigurowanej opcji kalorycznosci diety.',
			'status': status.HTTP_404_NOT_FOUND,
		}

	membership = ProjektInflacjaMobileUzytkownicywrodzinach.objects.create(
		rodzina=family,
		uzytkownik=auth_user,
		kalorycznosc_diety=default_diet_calorie,
	)
	return membership, family, None


def _subtract_warehouse_stock(aggregated_products, family_id):
	if not aggregated_products:
		return aggregated_products

	simplified_product_ids = {
		product_data.get('nazwa_produktu_uproszczonego_id')
		for product_data in aggregated_products.values()
		if product_data.get('nazwa_produktu_uproszczonego_id') is not None
	}
	if not simplified_product_ids:
		return aggregated_products

	warehouse_products = list(
		ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects
		.filter(
			rodzina_id=family_id,
			nazwa_produktu_uproszczonego_id__in=simplified_product_ids,
		)
	)

	stock_by_simplified_product_id = defaultdict(float)
	for warehouse_product in warehouse_products:
		stock_by_simplified_product_id[warehouse_product.nazwa_produktu_uproszczonego_id] += float(warehouse_product.ilosc_produktu or 0.0)

	adjusted_products = {}
	for product_id, product_data in sorted(aggregated_products.items(), key=lambda pair: pair[1]['nazwa_produktu']):
		remaining_amount = float(product_data['ilosc'])
		simplified_product_id = product_data.get('nazwa_produktu_uproszczonego_id')
		available_stock = stock_by_simplified_product_id.get(simplified_product_id, 0.0)
		if available_stock > 0:
			consumed = min(remaining_amount, available_stock)
			remaining_amount -= consumed
			stock_by_simplified_product_id[simplified_product_id] = available_stock - consumed

		if remaining_amount <= 0:
			continue

		adjusted_product = dict(product_data)
		adjusted_product['ilosc'] = remaining_amount
		adjusted_products[product_id] = adjusted_product

	return adjusted_products


def _get_last_package_preferences_by_product(family_id, simplified_product_ids):
	if not simplified_product_ids:
		return {}

	preferences = list(
		ShoppingPackagePreference.objects
		.filter(
			rodzina_id=family_id,
			nazwa_produktu_uproszczonego_id__in=simplified_product_ids,
		)
	)

	return {
		preference.nazwa_produktu_uproszczonego_id: preference
		for preference in preferences
	}


def _is_lunch_meal(meal):
	meal_time_name = getattr(getattr(meal, 'pora_posilku', None), 'pora_posilku', '')
	return (meal_time_name or '').strip().lower() == 'obiad'


def _resolve_ingredient_ratio_for_planned_meal(meal, member):
	if not _is_lunch_meal(meal):
		return 1.0

	meal_calorie = FamilyShoppingListFromCalendarCreateViewSet._resolve_numeric_calorie(meal.kalorycznosc_diety)
	member_calorie = FamilyShoppingListFromCalendarCreateViewSet._resolve_numeric_calorie(member.kalorycznosc_diety)
	if meal_calorie and member_calorie and meal_calorie > 0:
		return member_calorie / meal_calorie

	return 1.0


def _build_live_shopping_list_output(family_id, shopping_list_id):
	shopping_list = (
		ProjektInflacjaMobileListazakupowrodziny.objects
		.filter(rodzina_id=family_id, id=shopping_list_id)
		.first()
	)
	if shopping_list is None:
		return None, {
			'CODE': 'SHOPPING_LIST_NOT_FOUND',
			'detail': 'Nie znaleziono listy zakupow o podanym id dla rodziny.',
			'status': status.HTTP_404_NOT_FOUND,
		}

	data_od = shopping_list.data_od
	data_do = shopping_list.data_do

	planned_meals = list(
		ProjektInflacjaMobileZaplanowaneposilkirodziny.objects
		.select_related(
			'posilki_w_diecie__pora_posilku',
			'posilki_w_diecie__kalorycznosc_diety__kalorycznosc',
			'uzytkownik_w_rodzinie__kalorycznosc_diety__kalorycznosc',
		)
		.filter(
			rodzina_id=family_id,
			data__gte=data_od,
			data__lte=data_do,
			czy_zjedzone=False,
		)
	)

	if not planned_meals:
		return None, {
			'CODE': 'CALENDAR_EMPTY',
			'detail': 'Brak zaplanowanych posilkow w kalendarzu dla zakresu dat zapisanej listy zakupow.',
			'status': status.HTTP_404_NOT_FOUND,
		}

	meal_ids = {planned_meal.posilki_w_diecie_id for planned_meal in planned_meals}
	ingredients_by_meal_id = defaultdict(list)
	all_ingredients = (
		ProjektInflacjaMobileProduktywposilku.objects
		.select_related('nazwa_produktu__nazwa_produktu_uproszczonego', 'miarka')
		.filter(nazwa_posilku_id__in=meal_ids)
	)
	for ingredient in all_ingredients:
		ingredients_by_meal_id[ingredient.nazwa_posilku_id].append(ingredient)

	aggregated_products = {}
	for planned_meal in planned_meals:
		meal = planned_meal.posilki_w_diecie
		member = planned_meal.uzytkownik_w_rodzinie
		ratio = _resolve_ingredient_ratio_for_planned_meal(meal, member)

		for ingredient in ingredients_by_meal_id.get(planned_meal.posilki_w_diecie_id, []):
			product_id = ingredient.nazwa_produktu_id
			product_category = getattr(
				getattr(ingredient.nazwa_produktu, 'nazwa_produktu_uproszczonego', None),
				'kategoria_produktu',
				None,
			)
			category_id = getattr(product_category, 'id', None)
			category_name = getattr(product_category, 'nazwa_kategorii', None)
			if product_id not in aggregated_products:
				simplified_product_id = getattr(ingredient.nazwa_produktu, 'nazwa_produktu_uproszczonego_id', None)
				if simplified_product_id is None:
					simplified_product_id = getattr(
						getattr(ingredient.nazwa_produktu, 'nazwa_produktu_uproszczonego', None),
						'id',
						None,
					)
				aggregated_products[product_id] = {
					'nazwa_produktu': ingredient.nazwa_produktu.nazwa_produktu,
					'miarka': FamilyShoppingListFromCalendarCreateViewSet._normalize_measure_unit(
						getattr(getattr(ingredient, 'miarka', None), 'nazwa_miarki', ''),
						product_name=getattr(getattr(ingredient, 'nazwa_produktu', None), 'nazwa_produktu', ''),
					),
					'kategoria_id': category_id,
					'kategoria_nazwa': category_name,
					'nazwa_produktu_uproszczonego_id': simplified_product_id,
					'ilosc': 0.0,
				}
			aggregated_products[product_id]['ilosc'] += float(ingredient.czysta_ilosc_produktu) * ratio

	store_category_order_by_id = {}
	for category_order in ProjektInflacjaMobileKolejnosckategoriiwsklepie.objects.filter(sklep_id=shopping_list.rodzina.sklep_id).select_related('kategoria_produktu'):
		store_category_order_by_id[category_order.kategoria_produktu_id] = {
			'kolejnosc': category_order.kolejnosc,
			'kategoria_nazwa': getattr(category_order.kategoria_produktu, 'nazwa_kategorii', None),
		}

	aggregated_products = _subtract_warehouse_stock(aggregated_products, family_id)
	last_package_preferences_by_simplified_product_id = _get_last_package_preferences_by_product(
		family_id,
		{
			product_data.get('nazwa_produktu_uproszczonego_id')
			for product_data in aggregated_products.values()
			if product_data.get('nazwa_produktu_uproszczonego_id') is not None
		},
	)

	if not aggregated_products:
		return {
			'rodzina_id': family_id,
			'data_od': data_od,
			'data_do': data_do,
			'liczba_zaplanowanych_posilkow': len(planned_meals),
			'liczba_pozycji_na_liscie': 0,
			'produkty': [],
		}, None

	products = []
	for product_id, product_data in sorted(aggregated_products.items(), key=lambda pair: pair[1]['nazwa_produktu']):
		amount_value = round(product_data['ilosc'], 2)
		amount_text = f"{amount_value} {product_data['miarka']}".strip()
		category_order_data = store_category_order_by_id.get(product_data.get('kategoria_id'))
		last_package_preference = last_package_preferences_by_simplified_product_id.get(
			product_data.get('nazwa_produktu_uproszczonego_id')
		)
		products.append(
			{
				'produkt_id': product_id,
				'nazwa_produktu': product_data['nazwa_produktu'],
				'ilosc_produktu_do_kupienia': amount_text,
				'kolejnosc_kategorii': category_order_data.get('kolejnosc') if category_order_data else None,
				'kategoria_nazwa': (
					category_order_data.get('kategoria_nazwa')
					if category_order_data and category_order_data.get('kategoria_nazwa')
					else product_data.get('kategoria_nazwa')
				),
				'ostatnia_wielkosc_opakowania': (
					round(float(last_package_preference.wielkosc_opakowania), 2)
					if last_package_preference is not None
					else None
				),
				'jednostka_ostatniego_opakowania': (
					last_package_preference.jednostka_opakowania
					if last_package_preference is not None
					else None
				),
			}
		)

	return {
		'rodzina_id': family_id,
		'data_od': data_od,
		'data_do': data_do,
		'liczba_zaplanowanych_posilkow': len(planned_meals),
		'liczba_pozycji_na_liscie': len(products),
		'produkty': products,
	}, None


def _extract_amount_value(raw_amount_text):
	if not raw_amount_text:
		return None

	match = re.search(r'([-+]?\d+(?:[\.,]\d+)?)', str(raw_amount_text))
	if match is None:
		return None

	try:
		return float(match.group(1).replace(',', '.'))
	except (TypeError, ValueError):
		return None


def _extract_amount_unit(raw_amount_text):
	if not raw_amount_text:
		return 'g'

	match = re.search(r'([a-zA-Z]+)$', str(raw_amount_text).strip().lower())
	if match is None:
		return 'g'

	unit = match.group(1)
	if (
		unit in {'ml', 'l', 'ltr'}
		or 'ml' in unit
		or 'litr' in unit
		or 'liter' in unit
	):
		return 'ml'
	return 'g'


@extend_schema_view(
	create=extend_schema(
		tags=['lista-zakupow'],
		summary='Tworzenie listy zakupow rodziny na podstawie kalendarza',
		description=(
			'Tworzy liste zakupow na podstawie zaplanowanych posilkow rodziny z zakresu dat. '
			'Skladniki sa sumowane proporcjonalnie do kalorycznosci czlonkow rodziny. '
			'Endpoint zwraca tylko metadane utworzonej listy i liczbe pozycji; szczegoly produktow sa dostepne '
			'w endpointach odczytu i live.'
		),
		request=FamilyShoppingListCreateFromCalendarSerializer,
		responses={
			201: FamilyShoppingListCreateFromCalendarResponseSerializer,
			400: ApiErrorSerializer,
			401: ApiErrorSerializer,
			404: ApiErrorSerializer,
			503: ApiErrorSerializer,
		},
	),
)
class FamilyShoppingListFromCalendarCreateViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
	permission_classes = [IsAuthenticated]
	serializer_class = FamilyShoppingListCreateFromCalendarSerializer
	http_method_names = ['post', 'get']

	@staticmethod
	def _normalize_measure_unit(raw_unit, product_name=''):
		unit = (raw_unit or '').strip().lower()
		normalized = re.sub(r'[^a-z0-9\u0105\u0107\u0119\u0142\u0144\u00f3\u015b\u017a\u017c]', '', unit)
		product = (product_name or '').strip().lower()
		product_normalized = re.sub(r'[^a-z0-9\u0105\u0107\u0119\u0142\u0144\u00f3\u015b\u017a\u017c]', '', product)

		liquid_product_keywords = (
			'sok',
			'woda',
			'mleko',
			'napoj',
			'kefir',
			'jogurtpitny',
		)
		if any(keyword in product_normalized for keyword in liquid_product_keywords):
			return 'ml'

		if not normalized:
			return 'g'

		ml_like_units = {
			'ml',
			'mililitr',
			'mililitry',
			'mililitrow',
			'mililitrow',
			'milliliter',
			'milliliters',
		}
		liter_like_units = {
			'l',
			'ltr',
			'litr',
			'litra',
			'litry',
			'litrow',
			'liter',
			'liters',
		}

		if (
			normalized in ml_like_units
			or normalized in liter_like_units
			or normalized.startswith('ml')
			or 'mililitr' in normalized
			or 'milliliter' in normalized
			or normalized.startswith('litr')
			or normalized.startswith('liter')
		):
			return 'ml'
		return 'g'

	@staticmethod
	def _resolve_numeric_calorie(diet_calorie):
		if diet_calorie is None:
			return None
		calorie_obj = getattr(diet_calorie, 'kalorycznosc', None)
		if calorie_obj is None:
			return None
		if isinstance(calorie_obj, (int, float)):
			return calorie_obj
		return getattr(calorie_obj, 'czysta_kalorycznosc', None)

	@staticmethod
	def _build_list_name(base_name, data_od, data_do, family_id):
		name = (base_name or '').strip() or f'Lista zakupow {data_od} - {data_do}'
		if not ProjektInflacjaMobileListazakupowrodziny.objects.filter(nazwa_listy_zakupow=name).exists():
			return name
		suffix = 2
		while True:
			candidate = f'{name} ({family_id}-{suffix})'
			if not ProjektInflacjaMobileListazakupowrodziny.objects.filter(nazwa_listy_zakupow=candidate).exists():
				return candidate
			suffix += 1

	def create(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		try:
			_, family, context_error = _ensure_family_membership_for_shopping(request.user)
		except (ProgrammingError, OperationalError):
			return Response(
				{'CODE': 'FAMILY_CONTEXT_UNAVAILABLE', 'detail': 'Kontekst rodziny jest chwilowo niedostepny.'},
				status=status.HTTP_503_SERVICE_UNAVAILABLE,
			)

		if context_error is not None:
			return Response(
				{'CODE': context_error['CODE'], 'detail': context_error['detail']},
				status=context_error['status'],
			)

		data_od = serializer.validated_data['data_od']
		data_do = serializer.validated_data['data_do']

		planned_meals = list(
			ProjektInflacjaMobileZaplanowaneposilkirodziny.objects
			.select_related(
				'posilki_w_diecie__pora_posilku',
				'posilki_w_diecie__kalorycznosc_diety__kalorycznosc',
				'uzytkownik_w_rodzinie__kalorycznosc_diety__kalorycznosc',
			)
			.filter(
				rodzina_id=family.id,
				data__gte=data_od,
				data__lte=data_do,
				czy_zjedzone=False,
			)
		)

		if not planned_meals:
			return Response(
				{'CODE': 'CALENDAR_EMPTY', 'detail': 'Brak zaplanowanych posilkow w kalendarzu dla podanego zakresu dat.'},
				status=status.HTTP_404_NOT_FOUND,
			)

		meal_ids = {planned_meal.posilki_w_diecie_id for planned_meal in planned_meals}
		ingredients_by_meal_id = defaultdict(list)
		all_ingredients = (
			ProjektInflacjaMobileProduktywposilku.objects
			.select_related(
				'nazwa_produktu__nazwa_produktu_uproszczonego__kategoria_produktu',
				'miarka',
			)
			.filter(nazwa_posilku_id__in=meal_ids)
		)
		for ingredient in all_ingredients:
			ingredients_by_meal_id[ingredient.nazwa_posilku_id].append(ingredient)

		aggregated_products = {}
		for planned_meal in planned_meals:
			meal = planned_meal.posilki_w_diecie
			member = planned_meal.uzytkownik_w_rodzinie
			ratio = _resolve_ingredient_ratio_for_planned_meal(meal, member)

			for ingredient in ingredients_by_meal_id.get(planned_meal.posilki_w_diecie_id, []):
				product_id = ingredient.nazwa_produktu_id
				normalized_unit = self._normalize_measure_unit(
					getattr(getattr(ingredient, 'miarka', None), 'nazwa_miarki', ''),
					product_name=getattr(getattr(ingredient, 'nazwa_produktu', None), 'nazwa_produktu', ''),
				)
				category_id = getattr(
					getattr(getattr(ingredient.nazwa_produktu, 'nazwa_produktu_uproszczonego', None), 'kategoria_produktu', None),
					'id',
					None,
				)
				if product_id not in aggregated_products:
					simplified_product_id = getattr(ingredient.nazwa_produktu, 'nazwa_produktu_uproszczonego_id', None)
					if simplified_product_id is None:
						simplified_product_id = getattr(
							getattr(ingredient.nazwa_produktu, 'nazwa_produktu_uproszczonego', None),
							'id',
							None,
						)
					aggregated_products[product_id] = {
						'nazwa_produktu': ingredient.nazwa_produktu.nazwa_produktu,
						'miarka': normalized_unit,
						'kategoria_id': category_id,
						'nazwa_produktu_uproszczonego_id': simplified_product_id,
						'ilosc': 0.0,
					}
				aggregated_products[product_id]['ilosc'] += float(ingredient.czysta_ilosc_produktu) * ratio

		aggregated_products = _subtract_warehouse_stock(aggregated_products, family.id)

		if not aggregated_products:
			return Response(
				{'CODE': 'SHOPPING_LIST_COVERED_BY_WAREHOUSE', 'detail': 'Wszystkie potrzebne skladniki sa juz dostepne w magazynie rodziny.'},
				status=status.HTTP_404_NOT_FOUND,
			)

		list_name = self._build_list_name(
			serializer.validated_data.get('nazwa_listy_zakupow', ''),
			data_od,
			data_do,
			family.id,
		)
		shopping_list = ProjektInflacjaMobileListazakupowrodziny.objects.create(
			nazwa_listy_zakupow=list_name,
			data_od=data_od,
			data_do=data_do,
			rodzina_id=family.id,
		)

		store_order_fallback = (
			ProjektInflacjaMobileKolejnosckategoriiwsklepie.objects
			.filter(sklep_id=family.sklep_id)
			.order_by('kolejnosc')
			.first()
		)

		created_positions_count = 0
		for product_id, product_data in sorted(aggregated_products.items(), key=lambda pair: pair[1]['nazwa_produktu']):
			order_qs = ProjektInflacjaMobileKolejnosckategoriiwsklepie.objects.filter(sklep_id=family.sklep_id)
			if product_data['kategoria_id'] is not None:
				order_qs = order_qs.filter(kategoria_produktu_id=product_data['kategoria_id'])
			category_order = order_qs.order_by('kolejnosc').first() or store_order_fallback

			amount_value = round(product_data['ilosc'], 2)
			amount_text = f"{amount_value} {product_data['miarka']}".strip()
			ProjektInflacjaMobileProduktynalisciezakupowrodziny.objects.create(
				ilosc_produktu_do_kupienia=amount_text,
				kolejnosc_kategorii_w_sklepie_id=category_order.id if category_order else 1,
				lista_zakupow_id=shopping_list.id,
				nazwa_produktu_id=product_id,
			)
			created_positions_count += 1

		output = {
			'lista_zakupow_id': shopping_list.id,
			'nazwa_listy_zakupow': shopping_list.nazwa_listy_zakupow,
			'rodzina_id': family.id,
			'data_od': data_od,
			'data_do': data_do,
			'liczba_zaplanowanych_posilkow': len(planned_meals),
			'liczba_pozycji_na_liscie': created_positions_count,
		}
		emit_live_shopping_list_update(family.id, shopping_list.id, reason='shopping_list.created')
		return Response(output, status=status.HTTP_201_CREATED)


@extend_schema_view(
	list=extend_schema(
		tags=['lista-zakupow'],
		summary='Lista list zakupow rodziny',
		description='Zwraca wszystkie listy zakupow aktualnej rodziny zalogowanego uzytkownika.',
		responses={
			200: FamilyShoppingListSummarySerializer(many=True),
			401: ApiErrorSerializer,
			404: ApiErrorSerializer,
			503: ApiErrorSerializer,
		},
	),
	retrieve=extend_schema(
		tags=['lista-zakupow'],
		summary='Szczegoly listy zakupow',
		description='Zwraca wskazana liste zakupow rodziny wraz z wymaganymi produktami.',
		responses={
			200: FamilyShoppingListReadDetailSerializer,
			401: ApiErrorSerializer,
			404: ApiErrorSerializer,
			503: ApiErrorSerializer,
		},
	),
	destroy=extend_schema(
		tags=['lista-zakupow'],
		summary='Usuniecie listy zakupow',
		description='Usuwa wskazana liste zakupow rodziny wraz z jej pozycjami.',
		responses={
			200: FamilyShoppingListDeleteResponseSerializer,
			401: ApiErrorSerializer,
			404: ApiErrorSerializer,
			503: ApiErrorSerializer,
		},
	),
)
class FamilyShoppingListReadViewSet(
	mixins.ListModelMixin,
	mixins.RetrieveModelMixin,
	mixins.DestroyModelMixin,
	viewsets.GenericViewSet,
):
	permission_classes = [IsAuthenticated]
	serializer_class = FamilyShoppingListSummarySerializer
	http_method_names = ['get', 'delete']
	pagination_class = None

	def _resolve_family_or_error(self, user):
		try:
			_, family, context_error = _ensure_family_membership_for_shopping(user)
		except (ProgrammingError, OperationalError):
			return None, Response(
				{'CODE': 'FAMILY_CONTEXT_UNAVAILABLE', 'detail': 'Kontekst rodziny jest chwilowo niedostepny.'},
				status=status.HTTP_503_SERVICE_UNAVAILABLE,
			)

		if context_error is not None:
			return None, Response(
				{'CODE': context_error['CODE'], 'detail': context_error['detail']},
				status=context_error['status'],
			)

		return family, None

	def list(self, request, *args, **kwargs):
		family, error_response = self._resolve_family_or_error(request.user)
		if error_response is not None:
			return error_response

		shopping_lists = list(
			ProjektInflacjaMobileListazakupowrodziny.objects
			.filter(rodzina_id=family.id)
			.order_by('-data_od', '-id')
		)

		list_ids = [item.id for item in shopping_lists]
		products = []
		if list_ids:
			products = list(
				ProjektInflacjaMobileProduktynalisciezakupowrodziny.objects
				.filter(lista_zakupow_id__in=list_ids)
			)

		product_count_by_list_id = defaultdict(int)
		for product in products:
			product_count_by_list_id[product.lista_zakupow_id] += 1

		output = [
			{
				'id': shopping_list.id,
				'nazwa_listy_zakupow': shopping_list.nazwa_listy_zakupow,
				'data_od': shopping_list.data_od,
				'data_do': shopping_list.data_do,
				'liczba_pozycji_na_liscie': product_count_by_list_id.get(shopping_list.id, 0),
			}
			for shopping_list in shopping_lists
		]
		return Response(output, status=status.HTTP_200_OK)

	def destroy(self, request, *args, **kwargs):
		family, error_response = self._resolve_family_or_error(request.user)
		if error_response is not None:
			return error_response

		shopping_list = (
			ProjektInflacjaMobileListazakupowrodziny.objects
			.filter(id=kwargs.get('pk'), rodzina_id=family.id)
			.first()
		)
		if shopping_list is None:
			return Response(
				{'CODE': 'SHOPPING_LIST_NOT_FOUND', 'detail': 'Nie znaleziono wskazanej listy zakupow.'},
				status=status.HTTP_404_NOT_FOUND,
			)

		deleted_products, _ = (
			ProjektInflacjaMobileProduktynalisciezakupowrodziny.objects
			.filter(lista_zakupow_id=shopping_list.id)
			.delete()
		)
		deleted_list_id = shopping_list.id
		shopping_list.delete()

		return Response(
			{
				'CODE': 'SHOPPING_LIST_DELETED',
				'detail': 'Lista zakupow zostala usunieta.',
				'shopping_list_id': deleted_list_id,
				'deleted_products': deleted_products,
			},
			status=status.HTTP_200_OK,
		)

	def retrieve(self, request, *args, **kwargs):
		family, error_response = self._resolve_family_or_error(request.user)
		if error_response is not None:
			return error_response

		shopping_list = (
			ProjektInflacjaMobileListazakupowrodziny.objects
			.select_related('rodzina')
			.filter(id=kwargs.get('pk'), rodzina_id=family.id)
			.first()
		)
		if shopping_list is None:
			return Response(
				{'CODE': 'SHOPPING_LIST_NOT_FOUND', 'detail': 'Nie znaleziono wskazanej listy zakupow.'},
				status=status.HTTP_404_NOT_FOUND,
			)

		list_products = list(
			ProjektInflacjaMobileProduktynalisciezakupowrodziny.objects
			.select_related('nazwa_produktu', 'kolejnosc_kategorii_w_sklepie__kategoria_produktu')
			.filter(lista_zakupow_id=shopping_list.id)
			.order_by('kolejnosc_kategorii_w_sklepie__kolejnosc', 'nazwa_produktu__nazwa_produktu')
		)

		output_products = []
		for product in list_products:
			category = getattr(product.kolejnosc_kategorii_w_sklepie, 'kategoria_produktu', None)
			output_products.append(
				{
					'produkt_id': product.nazwa_produktu_id,
					'nazwa_produktu': getattr(product.nazwa_produktu, 'nazwa_produktu', ''),
					'ilosc_produktu_do_kupienia': product.ilosc_produktu_do_kupienia,
					'kolejnosc_kategorii': getattr(product.kolejnosc_kategorii_w_sklepie, 'kolejnosc', None),
					'kategoria_nazwa': getattr(category, 'nazwa_kategorii', None),
					'ostatnia_wielkosc_opakowania': None,
					'jednostka_ostatniego_opakowania': None,
				}
			)

		output = {
			'id': shopping_list.id,
			'nazwa_listy_zakupow': shopping_list.nazwa_listy_zakupow,
			'rodzina_id': family.id,
			'data_od': shopping_list.data_od,
			'data_do': shopping_list.data_do,
			'liczba_pozycji_na_liscie': len(output_products),
			'produkty': output_products,
		}
		return Response(output, status=status.HTTP_200_OK)


@extend_schema_view(
	create=extend_schema(
		tags=['lista-zakupow'],
		summary='Oznaczenie produktu jako kupionego',
		description=(
			'Usuwa produkt z listy zakupow i dodaje jego ilosc do magazynu rodziny. '
			'Po zapisaniu wysyla aktualizacje live przez websocket. '
			'Opcjonalnie mozna podac wielkosc_opakowania i jednostka_opakowania (g/ml), '
			'wtedy do magazynu trafi wielkosc opakowania zamiast ilosci wymaganej na liscie. '
			'Przeslana wielkosc opakowania jest zapamietywana jako ostatnio wybrana dla produktu w rodzinie.'
		),
		request=FamilyShoppingListMarkBoughtSerializer,
		responses={
			200: FamilyShoppingListMarkBoughtResponseSerializer,
			400: ApiErrorSerializer,
			401: ApiErrorSerializer,
			404: ApiErrorSerializer,
			503: ApiErrorSerializer,
		},
	),
)
class FamilyShoppingListMarkBoughtViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
	permission_classes = [IsAuthenticated]
	serializer_class = FamilyShoppingListMarkBoughtSerializer
	http_method_names = ['post']

	def create(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		try:
			_, family, context_error = _ensure_family_membership_for_shopping(request.user)
		except (ProgrammingError, OperationalError):
			return Response(
				{'CODE': 'FAMILY_CONTEXT_UNAVAILABLE', 'detail': 'Kontekst rodziny jest chwilowo niedostepny.'},
				status=status.HTTP_503_SERVICE_UNAVAILABLE,
			)

		if context_error is not None:
			return Response(
				{'CODE': context_error['CODE'], 'detail': context_error['detail']},
				status=context_error['status'],
			)

		shopping_list_id = serializer.validated_data['shopping_list_id']
		product_id = serializer.validated_data['produkt_id']
		package_size = serializer.validated_data.get('wielkosc_opakowania')
		package_unit = serializer.validated_data.get('jednostka_opakowania')

		list_product = (
			ProjektInflacjaMobileProduktynalisciezakupowrodziny.objects
			.select_related('nazwa_produktu')
			.filter(
				lista_zakupow_id=shopping_list_id,
				lista_zakupow__rodzina_id=family.id,
				nazwa_produktu_id=product_id,
			)
			.first()
		)
		added_amount = None
		amount_unit = 'g'
		simplified_product_id = None
		should_delete_list_product = False

		if list_product is not None:
			added_amount = _extract_amount_value(list_product.ilosc_produktu_do_kupienia)
			amount_unit = _extract_amount_unit(list_product.ilosc_produktu_do_kupienia)
			simplified_product_id = getattr(list_product.nazwa_produktu, 'nazwa_produktu_uproszczonego_id', None)
			should_delete_list_product = True
		else:
			live_output, live_error = _build_live_shopping_list_output(family.id, shopping_list_id)
			if live_error is not None:
				return Response(
					{
						'CODE': 'SHOPPING_LIST_PRODUCT_NOT_FOUND',
						'detail': 'Nie znaleziono produktu na tej liscie zakupow.',
					},
					status=status.HTTP_404_NOT_FOUND,
				)

			live_product = None
			for product in (live_output or {}).get('produkty', []):
				raw_product_id = product.get('produkt_id')
				try:
					resolved_product_id = raw_product_id if isinstance(raw_product_id, int) else int(raw_product_id)
				except (TypeError, ValueError):
					continue

				if resolved_product_id == product_id:
					live_product = product
					break

			if live_product is None:
				return Response(
					{
						'CODE': 'SHOPPING_LIST_PRODUCT_NOT_FOUND',
						'detail': 'Nie znaleziono produktu na tej liscie zakupow.',
					},
					status=status.HTTP_404_NOT_FOUND,
				)

			added_amount = _extract_amount_value(live_product.get('ilosc_produktu_do_kupienia'))
			amount_unit = _extract_amount_unit(live_product.get('ilosc_produktu_do_kupienia'))
			product_obj = ProjektInflacjaMobileProdukty.objects.filter(id=product_id).first()
			simplified_product_id = getattr(product_obj, 'nazwa_produktu_uproszczonego_id', None)

		if added_amount is None or added_amount <= 0:
			return Response(
				{
					'CODE': 'INVALID_PRODUCT_AMOUNT',
					'detail': 'Nie mozna odczytac poprawnej ilosci produktu do dodania do magazynu.',
				},
				status=status.HTTP_400_BAD_REQUEST,
			)

		if package_size is not None:
			if package_unit != amount_unit:
				return Response(
					{
						'CODE': 'INVALID_PACKAGE_UNIT',
						'detail': 'Jednostka opakowania musi byc zgodna z jednostka produktu z listy zakupow.',
					},
					status=status.HTTP_400_BAD_REQUEST,
				)
			added_amount = float(package_size)

		if simplified_product_id is None:
			return Response(
				{
					'CODE': 'SIMPLIFIED_PRODUCT_NOT_FOUND',
					'detail': 'Brak mapowania produktu na produkt uproszczony.',
				},
				status=status.HTTP_400_BAD_REQUEST,
			)

		if package_size is not None:
			ShoppingPackagePreference.objects.update_or_create(
				rodzina_id=family.id,
				nazwa_produktu_uproszczonego_id=simplified_product_id,
				defaults={
					'wielkosc_opakowania': float(package_size),
					'jednostka_opakowania': amount_unit,
				},
			)

		warehouse_product = (
			ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects
			.filter(
				rodzina_id=family.id,
				nazwa_produktu_uproszczonego_id=simplified_product_id,
			)
			.first()
		)

		if warehouse_product is None:
			warehouse_product = ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects.create(
				rodzina_id=family.id,
				nazwa_produktu_uproszczonego_id=simplified_product_id,
				ilosc_produktu=added_amount,
			)
		else:
			warehouse_product.ilosc_produktu = float(warehouse_product.ilosc_produktu or 0.0) + added_amount
			warehouse_product.save(update_fields=['ilosc_produktu'])

		if should_delete_list_product:
			list_product.delete()
		emit_live_shopping_list_update(family.id, shopping_list_id, reason='shopping_list.product_marked_bought')

		return Response(
			{
				'shopping_list_id': shopping_list_id,
				'produkt_id': product_id,
				'ilosc_dodana_do_magazynu': round(added_amount, 2),
				'jednostka_dodanej_ilosci': amount_unit,
			},
			status=status.HTTP_200_OK,
		)

