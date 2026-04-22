"""Warehouse API views category."""

from collections import defaultdict

from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from meals.api_views.shoping_list import _ensure_family_membership_for_shopping
from meals.models import ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny, ProjektInflacjaMobileProduktywposilku, ProjektInflacjaMobileZaplanowaneposilkirodziny
from meals.serializers import ApiErrorSerializer
from meals.serializers.warehouse import FamilyWarehouseClearResponseSerializer, FamilyWarehouseListResponseSerializer, FamilyWarehouseMealCoverageResponseSerializer, FamilyWarehousePossibleMealsResponseSerializer, FamilyWarehouseUpdateProductResponseSerializer, FamilyWarehouseUpdateProductSerializer


def _is_lunch_meal(meal):
	meal_time_name = getattr(getattr(meal, 'pora_posilku', None), 'pora_posilku', '')
	return (meal_time_name or '').strip().lower() == 'obiad'


def _resolve_numeric_calorie(diet_calorie):
	if diet_calorie is None:
		return None
	calorie_obj = getattr(diet_calorie, 'kalorycznosc', None)
	if calorie_obj is None:
		return None
	if isinstance(calorie_obj, (int, float)):
		return calorie_obj
	return getattr(calorie_obj, 'czysta_kalorycznosc', None)


def _resolve_ingredient_ratio_for_planned_meal(meal, member):
	if not _is_lunch_meal(meal):
		return 1.0

	meal_calorie = _resolve_numeric_calorie(meal.kalorycznosc_diety)
	member_calorie = _resolve_numeric_calorie(member.kalorycznosc_diety)
	if meal_calorie and member_calorie and meal_calorie > 0:
		return member_calorie / meal_calorie

	return 1.0


def _meal_time_order(meal_time_name):
	normalized = (meal_time_name or '').strip().lower()
	if 'sniad' in normalized or 'śniad' in normalized:
		return 1
	if 'drugie sniad' in normalized or 'drugie śniad' in normalized:
		return 2
	if 'obiad' in normalized:
		return 3
	if 'podwiecz' in normalized:
		return 4
	if 'kolac' in normalized:
		return 5
	return 99


@extend_schema_view(
	list=extend_schema(
		tags=['magazyn'],
		summary='Produkty w magazynie rodziny',
		description='Zwraca produkty zapisane w magazynie wszystkich uzytkownikow rodziny.',
		responses={
			200: FamilyWarehouseListResponseSerializer,
			401: ApiErrorSerializer,
			404: ApiErrorSerializer,
			503: ApiErrorSerializer,
		},
	),
)
class FamilyWarehouseReadViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
	permission_classes = [IsAuthenticated]
	serializer_class = FamilyWarehouseListResponseSerializer
	http_method_names = ['get', 'post']
	pagination_class = None

	def list(self, request, *args, **kwargs):
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

		warehouse_products = list(
			ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects
			.select_related('nazwa_produktu_uproszczonego')
			.filter(rodzina_id=family.id)
		)

		output_products = [
			{
				'produkt_id': product.nazwa_produktu_uproszczonego_id,
				'nazwa_produktu': getattr(product.nazwa_produktu_uproszczonego, 'nazwa_produktu_uproszczonego', 'Produkt'),
				'ilosc_produktu': round(float(product.ilosc_produktu or 0.0), 2),
			}
			for product in sorted(
				warehouse_products,
				key=lambda item: getattr(item.nazwa_produktu_uproszczonego, 'nazwa_produktu_uproszczonego', ''),
			)
		]

		return Response(
			{
				'rodzina_id': family.id,
				'liczba_pozycji': len(output_products),
				'produkty': output_products,
			},
			status=status.HTTP_200_OK,
		)

	@extend_schema(
		tags=['magazyn'],
		summary='Procent pokrycia posilkow skladnikami z lodowki',
		description='Oblicza procent zaplanowanych i niezjedzonych posilkow rodziny od biezacego dnia wzwyz, dla ktorych magazyn ma komplet skladnikow.',
		responses={
			200: FamilyWarehouseMealCoverageResponseSerializer,
			401: ApiErrorSerializer,
			404: ApiErrorSerializer,
			503: ApiErrorSerializer,
		},
	)
	@action(detail=False, methods=['get'], url_path='meal-coverage')
	def meal_coverage(self, request, *args, **kwargs):
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

		today = timezone.localdate()

		planned_meals = list(
			ProjektInflacjaMobileZaplanowaneposilkirodziny.objects
			.select_related(
				'posilki_w_diecie__pora_posilku',
				'posilki_w_diecie__kalorycznosc_diety__kalorycznosc',
				'uzytkownik_w_rodzinie__kalorycznosc_diety__kalorycznosc',
			)
			.filter(rodzina_id=family.id, czy_zjedzone=False, data__gte=today)
			.order_by('data', 'id')
		)

		total_planned_meals = len(planned_meals)
		if total_planned_meals == 0:
			return Response(
				{
					'rodzina_id': family.id,
					'total_planned_meals': 0,
					'covered_meals': 0,
					'uncovered_meals': 0,
					'coverage_percent': 0.0,
				},
				status=status.HTTP_200_OK,
			)

		meal_ids = {planned_meal.posilki_w_diecie_id for planned_meal in planned_meals}
		ingredients_by_meal_id = defaultdict(list)
		all_ingredients = (
			ProjektInflacjaMobileProduktywposilku.objects
			.select_related('nazwa_produktu')
			.filter(nazwa_posilku_id__in=meal_ids)
		)
		for ingredient in all_ingredients:
			ingredients_by_meal_id[ingredient.nazwa_posilku_id].append(ingredient)

		stock_by_simplified_product_id = defaultdict(float)
		for warehouse_product in ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects.filter(rodzina_id=family.id):
			stock_by_simplified_product_id[warehouse_product.nazwa_produktu_uproszczonego_id] += float(warehouse_product.ilosc_produktu or 0.0)

		covered_meals = 0
		for planned_meal in planned_meals:
			requirements = defaultdict(float)
			meal = planned_meal.posilki_w_diecie
			member = planned_meal.uzytkownik_w_rodzinie
			ratio = _resolve_ingredient_ratio_for_planned_meal(meal, member)

			for ingredient in ingredients_by_meal_id.get(planned_meal.posilki_w_diecie_id, []):
				simplified_product_id = getattr(ingredient.nazwa_produktu, 'nazwa_produktu_uproszczonego_id', None)
				if simplified_product_id is None:
					continue
				requirements[simplified_product_id] += float(getattr(ingredient, 'czysta_ilosc_produktu', 0) or 0) * ratio

			can_cover = True
			for simplified_product_id, required_amount in requirements.items():
				if stock_by_simplified_product_id.get(simplified_product_id, 0.0) < required_amount:
					can_cover = False
					break

			if not can_cover:
				continue

			for simplified_product_id, required_amount in requirements.items():
				stock_by_simplified_product_id[simplified_product_id] -= required_amount
			covered_meals += 1

		coverage_percent = round((covered_meals / total_planned_meals) * 100, 2)
		return Response(
			{
				'rodzina_id': family.id,
				'total_planned_meals': total_planned_meals,
				'covered_meals': covered_meals,
				'uncovered_meals': total_planned_meals - covered_meals,
				'coverage_percent': coverage_percent,
			},
			status=status.HTTP_200_OK,
		)

	@extend_schema(
		tags=['magazyn'],
		summary='Mozliwe inne posilki na podstawie lodowki',
		description='Zwraca liste posilkow, ktore mozna przygotowac na podstawie aktualnych skladnikow w lodowce rodziny.',
		responses={
			200: FamilyWarehousePossibleMealsResponseSerializer,
			401: ApiErrorSerializer,
			404: ApiErrorSerializer,
			503: ApiErrorSerializer,
		},
	)
	@action(detail=False, methods=['get'], url_path='possible-meals')
	def possible_meals(self, request, *args, **kwargs):
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

		stock_by_simplified_product_id = defaultdict(float)
		for warehouse_product in ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects.filter(rodzina_id=family.id):
			stock_by_simplified_product_id[warehouse_product.nazwa_produktu_uproszczonego_id] += float(warehouse_product.ilosc_produktu or 0.0)

		ingredients = list(
			ProjektInflacjaMobileProduktywposilku.objects
			.select_related('nazwa_produktu', 'nazwa_posilku__nazwa_posilku', 'nazwa_posilku__pora_posilku')
			.all()
		)

		requirements_by_meal_id = defaultdict(lambda: defaultdict(float))
		meal_meta_by_id = {}
		for ingredient in ingredients:
			meal = ingredient.nazwa_posilku
			simplified_product_id = getattr(ingredient.nazwa_produktu, 'nazwa_produktu_uproszczonego_id', None)
			if simplified_product_id is None:
				continue
			requirements_by_meal_id[meal.id][simplified_product_id] += float(getattr(ingredient, 'czysta_ilosc_produktu', 0) or 0)
			meal_meta_by_id[meal.id] = {
				'posilek_w_diecie_id': meal.id,
				'nazwa_posilku': getattr(getattr(meal, 'nazwa_posilku', None), 'nazwa_posilku', 'Posilek'),
				'pora_posilku': getattr(getattr(meal, 'pora_posilku', None), 'pora_posilku', ''),
				'czas_przygotowania': getattr(meal, 'czas_przygotowania', ''),
			}

		possible_meals = []
		preparable_meals_count = 0
		for meal_id, requirements in requirements_by_meal_id.items():
			total_required_amount = sum(requirements.values())
			if total_required_amount <= 0:
				continue

			available_amount = 0.0
			can_prepare = True
			for simplified_product_id, required_amount in requirements.items():
				available_for_ingredient = stock_by_simplified_product_id.get(simplified_product_id, 0.0)
				available_amount += min(available_for_ingredient, required_amount)
				if available_for_ingredient < required_amount:
					can_prepare = False

			coverage_percent = round((available_amount / total_required_amount) * 100, 2)
			if coverage_percent <= 0:
				continue
			if can_prepare:
				preparable_meals_count += 1

			meal_meta = meal_meta_by_id.get(meal_id)
			if meal_meta is None:
				continue
			possible_meals.append(
				{
					'posilek_w_diecie_id': meal_meta['posilek_w_diecie_id'],
					'nazwa_posilku': meal_meta['nazwa_posilku'],
					'pora_posilku': meal_meta['pora_posilku'],
					'czas_przygotowania': meal_meta['czas_przygotowania'],
					'liczba_skladnikow': len(requirements),
					'coverage_percent': coverage_percent,
					'can_prepare': can_prepare,
				}
			)

		possible_meals.sort(
			key=lambda meal: (
				0 if meal.get('can_prepare') else 1,
				-(meal.get('coverage_percent') or 0.0),
				_meal_time_order(meal.get('pora_posilku')),
				(meal.get('nazwa_posilku') or '').lower(),
			),
		)

		return Response(
			{
				'rodzina_id': family.id,
				'liczba_mozliwych_posilkow': preparable_meals_count,
				'mozliwe_posilki': possible_meals[:20],
			},
			status=status.HTTP_200_OK,
		)

	@extend_schema(
		tags=['magazyn'],
		summary='Wyzerowanie lodówki rodziny',
		description='Usuwa wszystkie pozycje z magazynu (lodówki) rodziny zalogowanego użytkownika.',
		responses={
			200: FamilyWarehouseClearResponseSerializer,
			401: ApiErrorSerializer,
			404: ApiErrorSerializer,
			503: ApiErrorSerializer,
		},
	)
	@action(detail=False, methods=['post'], url_path='clear')
	def clear(self, request, *args, **kwargs):
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

		deleted_entries, _ = (
			ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects
			.filter(rodzina_id=family.id)
			.delete()
		)

		return Response(
			{
				'CODE': 'WAREHOUSE_CLEARED',
				'detail': 'Lodówka rodziny została wyzerowana.',
				'deleted_entries': deleted_entries,
			},
			status=status.HTTP_200_OK,
		)

	@extend_schema(
		tags=['magazyn'],
		summary='Aktualizacja ilosci produktu w lodowce',
		description=(
			'Ustawia nowa ilosc wskazanego produktu w lodowce rodziny. '
			'Podanie ilosc_produktu = 0 usuwa produkt z lodowki.'
		),
		request=FamilyWarehouseUpdateProductSerializer,
		responses={
			200: FamilyWarehouseUpdateProductResponseSerializer,
			400: ApiErrorSerializer,
			401: ApiErrorSerializer,
			404: ApiErrorSerializer,
			503: ApiErrorSerializer,
		},
	)
	@action(detail=False, methods=['post'], url_path='update-product')
	def update_product(self, request, *args, **kwargs):
		serializer = FamilyWarehouseUpdateProductSerializer(data=request.data)
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

		product_id = serializer.validated_data['produkt_id']
		target_amount = float(serializer.validated_data['ilosc_produktu'])

		warehouse_product = (
			ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects
			.select_related('nazwa_produktu_uproszczonego')
			.filter(
				rodzina_id=family.id,
				nazwa_produktu_uproszczonego_id=product_id,
			)
			.first()
		)

		if warehouse_product is None:
			return Response(
				{
					'CODE': 'WAREHOUSE_PRODUCT_NOT_FOUND',
					'detail': 'Nie znaleziono produktu w lodowce rodziny.',
				},
				status=status.HTTP_404_NOT_FOUND,
			)

		product_name = getattr(warehouse_product.nazwa_produktu_uproszczonego, 'nazwa_produktu_uproszczonego', '')

		if target_amount <= 0:
			warehouse_product.delete()
			return Response(
				{
					'CODE': 'WAREHOUSE_PRODUCT_REMOVED',
					'detail': 'Produkt zostal usuniety z lodowki (ilosc ustawiona na 0).',
					'produkt_id': product_id,
					'nazwa_produktu': product_name,
					'ilosc_produktu': 0.0,
				},
				status=status.HTTP_200_OK,
			)

		warehouse_product.ilosc_produktu = target_amount
		warehouse_product.save(update_fields=['ilosc_produktu'])

		return Response(
			{
				'CODE': 'WAREHOUSE_PRODUCT_UPDATED',
				'detail': 'Zaktualizowano ilosc produktu w lodowce.',
				'produkt_id': product_id,
				'nazwa_produktu': product_name,
				'ilosc_produktu': round(target_amount, 2),
			},
			status=status.HTTP_200_OK,
		)
