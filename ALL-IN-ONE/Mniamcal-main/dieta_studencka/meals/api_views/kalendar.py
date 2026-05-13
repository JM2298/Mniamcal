"""Kalendar API views category."""

from django.db.utils import OperationalError, ProgrammingError
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema, extend_schema_view
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from meals.models import (
	AuthUser,
	ProjektInflacjaMobileKalorycznoscdiety,
	ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny,
	ProjektInflacjaMobileMozliweocenyposilku,
	ProjektInflacjaMobileOcenaposilkuprzezuzytkownika,
	ProjektInflacjaMobilePosilkiwdiecie,
	ProjektInflacjaMobileProduktywposilku,
	ProjektInflacjaMobileRodziny,
	ProjektInflacjaMobileUzytkownicywrodzinach,
	ProjektInflacjaMobileZaplanowaneposilkirodziny,
)
from meals.serializers import ApiErrorSerializer, FamilyMealPossibleRatingsResponseSerializer, FamilyPlannedMealCreateSerializer, FamilyPlannedMealListResponseSerializer, FamilyPlannedMealMarkEatenResponseSerializer, FamilyPlannedMealMarkEatenSerializer, FamilyPlannedMealRemoveResponseSerializer, FamilyPlannedMealRemoveSerializer, FamilyPlannedMealResponseSerializer
from rest_framework.decorators import action
from meals.services.shopping_list_realtime import emit_live_shopping_list_updates_for_date


def _ensure_family_membership_for_planning(user):
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


@extend_schema_view(
	list=extend_schema(
		tags=['kalendarz'],
		summary='Lista zaplanowanych posilkow rodziny',
		description=(
			'Zwraca zaplanowane posilki rodziny aktualnie zalogowanego uzytkownika. '
			'Parametry data_od i data_do pozwalaja ograniczyc zakres dat.'
		),
		parameters=[
			OpenApiParameter(
				name='data_od',
				type=OpenApiTypes.DATE,
				required=False,
				description='Data poczatkowa (YYYY-MM-DD). Domyslnie dzisiejsza data.',
			),
			OpenApiParameter(
				name='data_do',
				type=OpenApiTypes.DATE,
				required=False,
				description='Data koncowa (YYYY-MM-DD).',
			),
		],
		responses={
			200: FamilyPlannedMealListResponseSerializer,
			400: ApiErrorSerializer,
			401: ApiErrorSerializer,
			404: ApiErrorSerializer,
			503: ApiErrorSerializer,
		},
	),
	create=extend_schema(
		tags=['kalendarz'],
		summary='Dodanie posilku do zaplanowanych posilkow rodziny',
		description=(
			'Tworzy wpis zaplanowanego posilku dla rodziny aktualnie zalogowanego uzytkownika. '
			'Endpoint automatycznie ustala rodzine i przypisanie uzytkownika w rodzinie.'
		),
		request=FamilyPlannedMealCreateSerializer,
		responses={
			201: FamilyPlannedMealResponseSerializer,
			400: ApiErrorSerializer,
			401: ApiErrorSerializer,
			404: ApiErrorSerializer,
			503: ApiErrorSerializer,
		},
	),
)
class FamilyPlannedMealCreateViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
	permission_classes = [IsAuthenticated]
	serializer_class = FamilyPlannedMealCreateSerializer
	http_method_names = ['post', 'get']

	def list(self, request, *args, **kwargs):
		try:
			_membership, family, context_error = _ensure_family_membership_for_planning(request.user)
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

		data_od_param = request.query_params.get('data_od')
		data_do_param = request.query_params.get('data_do')
		data_od = parse_date(data_od_param) if data_od_param else None
		data_do = parse_date(data_do_param) if data_do_param else None

		if data_od_param and data_od is None:
			return Response(
				{'CODE': 'INVALID_DATE', 'detail': 'Niepoprawny format parametru data_od.'},
				status=status.HTTP_400_BAD_REQUEST,
			)
		if data_do_param and data_do is None:
			return Response(
				{'CODE': 'INVALID_DATE', 'detail': 'Niepoprawny format parametru data_do.'},
				status=status.HTTP_400_BAD_REQUEST,
			)

		if data_od is None:
			data_od = timezone.localdate()

		if data_do and data_do < data_od:
			return Response(
				{'CODE': 'INVALID_DATE_RANGE', 'detail': 'Parametr data_do nie moze byc wczesniejszy niz data_od.'},
				status=status.HTTP_400_BAD_REQUEST,
			)

		planned_meals_qs = (
			ProjektInflacjaMobileZaplanowaneposilkirodziny.objects
			.filter(rodzina_id=family.id, data__gte=data_od)
			.select_related(
				'uzytkownik_w_rodzinie',
				'posilki_w_diecie__nazwa_posilku',
				'posilki_w_diecie__pora_posilku',
			)
		)
		if data_do is not None:
			planned_meals_qs = planned_meals_qs.filter(data__lte=data_do)

		planned_meals = list(
			planned_meals_qs.order_by('data', 'posilki_w_diecie__pora_posilku_id', 'id')
		)

		payload = []
		for planned_meal in planned_meals:
			payload.append(
				{
					'planned_meal_id': planned_meal.id,
					'posilek_w_diecie_id': getattr(planned_meal, 'posilki_w_diecie_id', None),
					'data': planned_meal.data,
					'posilek': getattr(planned_meal.posilki_w_diecie.nazwa_posilku, 'nazwa_posilku', ''),
					'pora_posilku': getattr(planned_meal.posilki_w_diecie.pora_posilku, 'pora_posilku', ''),
					'czy_zjedzone': bool(planned_meal.czy_zjedzone),
					'uzytkownik_id': getattr(planned_meal.uzytkownik_w_rodzinie, 'uzytkownik_id', None),
					'uzytkownik_w_rodzinie_id': getattr(planned_meal.uzytkownik_w_rodzinie, 'id', None),
				}
			)

		return Response(
			{
				'rodzina_id': family.id,
				'data_od': data_od,
				'data_do': data_do,
				'count': len(payload),
				'zaplanowane_posilki': payload,
			},
			status=status.HTTP_200_OK,
		)

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
	def _resolve_ingredient_ratio_for_planned_entry(planned_entry):
		meal = getattr(planned_entry, 'posilki_w_diecie', None)
		member = getattr(planned_entry, 'uzytkownik_w_rodzinie', None)
		meal_time_name = getattr(getattr(meal, 'pora_posilku', None), 'pora_posilku', '')
		is_lunch = 'obiad' in (meal_time_name or '').strip().lower()
		if not is_lunch:
			return 1.0

		meal_calorie = FamilyPlannedMealCreateViewSet._resolve_numeric_calorie(
			getattr(meal, 'kalorycznosc_diety', None),
		)
		member_calorie = FamilyPlannedMealCreateViewSet._resolve_numeric_calorie(
			getattr(member, 'kalorycznosc_diety', None),
		)
		if meal_calorie and member_calorie and meal_calorie > 0:
			return member_calorie / meal_calorie

		return 1.0

	@staticmethod
	def _subtract_planned_meal_ingredients_from_warehouse(family_id, meal_ids, planned_entries=None):
		meal_counts = {}
		for planned_entry in planned_entries or []:
			meal_id = getattr(planned_entry, 'posilki_w_diecie_id', None)
			if meal_id is None:
				continue
			ratio = FamilyPlannedMealCreateViewSet._resolve_ingredient_ratio_for_planned_entry(
				planned_entry,
			)
			meal_counts[meal_id] = meal_counts.get(meal_id, 0.0) + ratio

		if not meal_counts:
			for meal_id in meal_ids:
				meal_counts[meal_id] = meal_counts.get(meal_id, 0.0) + 1.0

		consumed_by_simplified_product_id = {}
		ingredients = list(
			ProjektInflacjaMobileProduktywposilku.objects
			.select_related('nazwa_produktu')
			.filter(nazwa_posilku_id__in=list(meal_counts.keys()))
		)
		meal_ids_with_direct_ingredients = set()

		for ingredient in ingredients:
			meal_ids_with_direct_ingredients.add(ingredient.nazwa_posilku_id)
			simplified_product_id = getattr(ingredient.nazwa_produktu, 'nazwa_produktu_uproszczonego_id', None)
			if simplified_product_id is None:
				continue
			multiplier = meal_counts.get(ingredient.nazwa_posilku_id, 1)
			consumed_by_simplified_product_id[simplified_product_id] = (
				consumed_by_simplified_product_id.get(simplified_product_id, 0.0)
				+ float(getattr(ingredient, 'czysta_ilosc_produktu', 0) or 0)
				* multiplier
			)

		missing_meal_ids = [meal_id for meal_id in meal_counts if meal_id not in meal_ids_with_direct_ingredients]
		if missing_meal_ids:
			missing_meals = list(
				ProjektInflacjaMobilePosilkiwdiecie.objects
				.filter(id__in=missing_meal_ids)
			)
			for missing_meal in missing_meals:
				fallback_recipe_meal_id = (
					ProjektInflacjaMobileProduktywposilku.objects
					.filter(
						nazwa_posilku__nazwa_posilku_id=missing_meal.nazwa_posilku_id,
						nazwa_posilku__pora_posilku_id=missing_meal.pora_posilku_id,
					)
					.order_by('nazwa_posilku_id')
					.values_list('nazwa_posilku_id', flat=True)
					.first()
				)
				if fallback_recipe_meal_id is None:
					continue

				fallback_ingredients = (
					ProjektInflacjaMobileProduktywposilku.objects
					.select_related('nazwa_produktu')
					.filter(nazwa_posilku_id=fallback_recipe_meal_id)
				)
				multiplier = meal_counts.get(missing_meal.id, 1)
				for ingredient in fallback_ingredients:
					simplified_product_id = getattr(ingredient.nazwa_produktu, 'nazwa_produktu_uproszczonego_id', None)
					if simplified_product_id is None:
						continue
					consumed_by_simplified_product_id[simplified_product_id] = (
						consumed_by_simplified_product_id.get(simplified_product_id, 0.0)
						+ float(getattr(ingredient, 'czysta_ilosc_produktu', 0) or 0)
						* multiplier
					)

		for simplified_product_id, consumed_amount in consumed_by_simplified_product_id.items():
			warehouse_product = (
				ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects
				.filter(
					rodzina_id=family_id,
					nazwa_produktu_uproszczonego_id=simplified_product_id,
				)
				.first()
			)
			if warehouse_product is None:
				continue

			current_amount = float(warehouse_product.ilosc_produktu or 0.0)
			warehouse_product.ilosc_produktu = max(0.0, current_amount - consumed_amount)
			warehouse_product.save(update_fields=['ilosc_produktu'])

		return len(consumed_by_simplified_product_id)

	def create(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		try:
			membership, family, context_error = _ensure_family_membership_for_planning(request.user)
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

		meal_id = serializer.validated_data['posilek_w_diecie_id']
		requested_meal = (
			ProjektInflacjaMobilePosilkiwdiecie.objects
			.select_related('pora_posilku', 'kalorycznosc_diety', 'nazwa_posilku')
			.filter(id=meal_id)
			.first()
		)
		if requested_meal is None:
			return Response(
				{'CODE': 'MEAL_NOT_FOUND', 'detail': 'Wskazany posilek w diecie nie istnieje.'},
				status=status.HTTP_404_NOT_FOUND,
			)

		meal_date = serializer.validated_data['data']
		meal_time_name = requested_meal.pora_posilku.pora_posilku.strip().lower()
		is_lunch = 'obiad' in meal_time_name

		family_members = list(
			ProjektInflacjaMobileUzytkownicywrodzinach.objects
			.select_related('kalorycznosc_diety')
			.filter(rodzina_id=family.id)
		)

		if not family_members:
			return Response(
				{'CODE': 'FAMILY_MEMBERS_NOT_FOUND', 'detail': 'Brak czlonkow rodziny do zaplanowania posilku.'},
				status=status.HTTP_404_NOT_FOUND,
			)

		if is_lunch:
			already_planned_lunch = ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.filter(
				rodzina_id=family.id,
				data=meal_date,
				posilki_w_diecie__pora_posilku_id=requested_meal.pora_posilku_id,
			).exists()
			if already_planned_lunch:
				return Response(
					{
						'CODE': 'LUNCH_ALREADY_PLANNED',
						'detail': 'Dla tej rodziny obiad w podanym dniu jest juz zaplanowany.',
					},
					status=status.HTTP_400_BAD_REQUEST,
				)

		def _meal_for_member(member):
			if not is_lunch:
				return requested_meal
			member_meal = (
				ProjektInflacjaMobilePosilkiwdiecie.objects
				.filter(
					nazwa_posilku_id=requested_meal.nazwa_posilku_id,
					pora_posilku_id=requested_meal.pora_posilku_id,
					kalorycznosc_diety_id=member.kalorycznosc_diety_id,
				)
				.first()
			)
			return member_meal or requested_meal

		participants = family_members if is_lunch else [membership]
		created_entries = []
		for participant in participants:
			member_meal = _meal_for_member(participant)
			planned_meal = ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.create(
				data=meal_date,
				czy_zjedzone=serializer.validated_data.get('czy_zjedzone', False),
				posilki_w_diecie_id=member_meal.id,
				rodzina_id=family.id,
				uzytkownik_w_rodzinie_id=participant.id,
			)
			created_entries.append((participant, member_meal, planned_meal))

		base_calorie = self._resolve_numeric_calorie(requested_meal.kalorycznosc_diety) or 0
		planned_members_payload = []
		for participant, member_meal, _ in created_entries:
			member_calorie = self._resolve_numeric_calorie(participant.kalorycznosc_diety)
			if is_lunch and base_calorie > 0 and member_calorie is not None:
				ratio = round(member_calorie / base_calorie, 4)
			else:
				ratio = 1.0
			planned_members_payload.append(
				{
					'uzytkownik_id': participant.uzytkownik_id,
					'uzytkownik_w_rodzinie_id': participant.id,
					'posilek_w_diecie_id': member_meal.id,
					'kalorycznosc_diety': member_calorie,
					'proporcja_kaloryczna': ratio,
				}
			)

		output = {
			'data': meal_date,
			'czy_zjedzone': serializer.validated_data.get('czy_zjedzone', False),
			'pora_posilku': requested_meal.pora_posilku.pora_posilku,
			'rodzina_id': family.id,
			'liczba_czlonkow_rodziny': len(family_members),
			'liczba_osob_przy_posilku': len(planned_members_payload),
			'zaplanowane_posilki': planned_members_payload,
		}
		emit_live_shopping_list_updates_for_date(family.id, meal_date, reason='calendar.updated')
		return Response(output, status=status.HTTP_201_CREATED)

	@extend_schema(
		tags=['kalendarz'],
		summary='Lista mozliwych ocen posilku',
		description='Zwraca mozliwe oceny posilku z tabeli projekt_inflacja_mobile_mozliweocenyposilku.',
		responses={
			200: FamilyMealPossibleRatingsResponseSerializer,
			401: ApiErrorSerializer,
			503: ApiErrorSerializer,
		},
	)
	@action(detail=False, methods=['get'], url_path='possible-ratings')
	def possible_ratings(self, request, *args, **kwargs):
		try:
			possible_ratings = list(
				ProjektInflacjaMobileMozliweocenyposilku.objects
				.order_by('id')
				.values('id', 'ocena')
			)
		except (ProgrammingError, OperationalError):
			return Response(
				{
					'CODE': 'MEAL_RATINGS_UNAVAILABLE',
					'detail': 'Lista mozliwych ocen posilku jest chwilowo niedostepna.',
				},
				status=status.HTTP_503_SERVICE_UNAVAILABLE,
			)

		return Response(
			{
				'count': len(possible_ratings),
				'oceny': possible_ratings,
			},
			status=status.HTTP_200_OK,
		)

	@extend_schema(
		tags=['kalendarz'],
		summary='Oznaczenie zaplanowanego posiłku jako zjedzony',
		description=(
			'Oznacza posiłek jako zjedzony. Dla obiadu oznacza cały rodzinny obiad '
			'z danego dnia i odejmuje składniki z magazynu rodziny. '
			'Parametr ocena_id jest opcjonalny i pozwala zapisac ocene posilku użytkownika.'
		),
		request=FamilyPlannedMealMarkEatenSerializer,
		responses={
			200: FamilyPlannedMealMarkEatenResponseSerializer,
			400: ApiErrorSerializer,
			401: ApiErrorSerializer,
			403: ApiErrorSerializer,
			404: ApiErrorSerializer,
			503: ApiErrorSerializer,
		},
	)
	@action(detail=False, methods=['post'], url_path='mark-eaten')
	def mark_eaten(self, request, *args, **kwargs):
		serializer = FamilyPlannedMealMarkEatenSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		try:
			membership, family, context_error = _ensure_family_membership_for_planning(request.user)
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

		planned_meal = (
			ProjektInflacjaMobileZaplanowaneposilkirodziny.objects
			.select_related('posilki_w_diecie__pora_posilku')
			.filter(id=serializer.validated_data['planned_meal_id'], rodzina_id=family.id)
			.first()
		)
		if planned_meal is None:
			return Response(
				{'CODE': 'PLANNED_MEAL_NOT_FOUND', 'detail': 'Nie znaleziono zaplanowanego posiłku.'},
				status=status.HTTP_404_NOT_FOUND,
			)

		meal_time_name = planned_meal.posilki_w_diecie.pora_posilku.pora_posilku.strip().lower()
		is_lunch = 'obiad' in meal_time_name

		meal_rating_id = serializer.validated_data.get('ocena_id')
		meal_rating = None
		meal_rating_lookup_unavailable = False
		if meal_rating_id is not None:
			try:
				meal_rating = (
					ProjektInflacjaMobileMozliweocenyposilku.objects
					.filter(id=meal_rating_id)
					.first()
				)
			except (ProgrammingError, OperationalError):
				meal_rating_lookup_unavailable = True

			if meal_rating is None and not meal_rating_lookup_unavailable:
				return Response(
					{
						'CODE': 'MEAL_RATING_NOT_FOUND',
						'detail': 'Wskazana ocena posilku nie istnieje.',
					},
					status=status.HTTP_400_BAD_REQUEST,
				)

		target_entries_qs = (
			ProjektInflacjaMobileZaplanowaneposilkirodziny.objects
			.select_related(
				'posilki_w_diecie__pora_posilku',
				'posilki_w_diecie__kalorycznosc_diety__kalorycznosc',
				'uzytkownik_w_rodzinie__kalorycznosc_diety__kalorycznosc',
			)
			.filter(rodzina_id=family.id)
		)
		if is_lunch:
			target_entries_qs = target_entries_qs.filter(
				data=planned_meal.data,
				posilki_w_diecie__pora_posilku_id=planned_meal.posilki_w_diecie.pora_posilku_id,
			)
		else:
			if planned_meal.uzytkownik_w_rodzinie_id != membership.id:
				return Response(
					{
						'CODE': 'FORBIDDEN_MEAL_MARK',
						'detail': 'Poza obiadem możesz oznaczyć jako zjedzony tylko swój posiłek.',
					},
					status=status.HTTP_403_FORBIDDEN,
				)
			target_entries_qs = target_entries_qs.filter(id=planned_meal.id)

		target_entries = list(target_entries_qs)
		entries_to_consume = [entry for entry in target_entries if not entry.czy_zjedzone]
		if not entries_to_consume:
			return Response(
				{
					'CODE': 'PLANNED_MEAL_ALREADY_EATEN',
					'detail': 'Ten posiłek został już oznaczony jako zjedzony.',
					'marked_entries': 0,
					'consumed_products': 0,
					'meal_rating_saved': False,
				},
				status=status.HTTP_200_OK,
			)

		meal_ids = [entry.posilki_w_diecie_id for entry in entries_to_consume]
		if is_lunch:
			consumed_products_count = self._subtract_planned_meal_ingredients_from_warehouse(
				family.id,
				meal_ids,
				planned_entries=entries_to_consume,
			)
		else:
			consumed_products_count = self._subtract_planned_meal_ingredients_from_warehouse(
				family.id,
				meal_ids,
			)

		for entry in entries_to_consume:
			entry.czy_zjedzone = True
			entry.save(update_fields=['czy_zjedzone'])

		meal_rating_saved = False
		if meal_rating is not None and not meal_rating_lookup_unavailable:
			rating_target_entry = planned_meal
			if is_lunch:
				for target_entry in target_entries:
					if target_entry.uzytkownik_w_rodzinie_id == membership.id:
						rating_target_entry = target_entry
						break

			try:
				ProjektInflacjaMobileOcenaposilkuprzezuzytkownika.objects.update_or_create(
					uzytkownik_id=request.user.id,
					posilek_id=rating_target_entry.posilki_w_diecie_id,
					data_oceny=planned_meal.data,
					defaults={'ocena_id': meal_rating.id},
				)
				meal_rating_saved = True
			except (ProgrammingError, OperationalError):
				meal_rating_saved = False

		emit_live_shopping_list_updates_for_date(
			family.id,
			planned_meal.data,
			reason='calendar.meal_eaten',
		)

		return Response(
			{
				'CODE': 'PLANNED_MEAL_MARKED_EATEN',
				'detail': 'Posiłek oznaczono jako zjedzony i odjęto składniki z magazynu rodziny.',
				'marked_entries': len(entries_to_consume),
				'consumed_products': consumed_products_count,
				'meal_rating_saved': meal_rating_saved,
			},
			status=status.HTTP_200_OK,
		)

	@extend_schema(
		tags=['kalendarz'],
		summary='Usuniecie zaplanowanego posilku',
		description='Usuwa zaplanowany posilek. Dla obiadu usuwa caly rodzinny obiad z danego dnia.',
		request=FamilyPlannedMealRemoveSerializer,
		responses={
			200: FamilyPlannedMealRemoveResponseSerializer,
			400: ApiErrorSerializer,
			401: ApiErrorSerializer,
			403: ApiErrorSerializer,
			404: ApiErrorSerializer,
			503: ApiErrorSerializer,
		},
	)
	@action(detail=False, methods=['post'], url_path='remove')
	def remove(self, request, *args, **kwargs):
		serializer = FamilyPlannedMealRemoveSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		try:
			membership, family, context_error = _ensure_family_membership_for_planning(request.user)
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

		planned_meal = (
			ProjektInflacjaMobileZaplanowaneposilkirodziny.objects
			.select_related('posilki_w_diecie__pora_posilku')
			.filter(id=serializer.validated_data['planned_meal_id'], rodzina_id=family.id)
			.first()
		)
		if planned_meal is None:
			return Response(
				{'CODE': 'PLANNED_MEAL_NOT_FOUND', 'detail': 'Nie znaleziono zaplanowanego posiłku.'},
				status=status.HTTP_404_NOT_FOUND,
			)

		meal_time_name = planned_meal.posilki_w_diecie.pora_posilku.pora_posilku.strip().lower()
		is_lunch = 'obiad' in meal_time_name

		if not is_lunch and planned_meal.uzytkownik_w_rodzinie_id != membership.id:
			return Response(
				{
					'CODE': 'FORBIDDEN_MEAL_REMOVE',
					'detail': 'Poza obiadem możesz usunąć tylko swój posiłek.',
				},
				status=status.HTTP_403_FORBIDDEN,
			)

		target_entries_qs = ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.filter(
			rodzina_id=family.id,
		)
		if is_lunch:
			target_entries_qs = target_entries_qs.filter(
				data=planned_meal.data,
				posilki_w_diecie__pora_posilku_id=planned_meal.posilki_w_diecie.pora_posilku_id,
			)
		else:
			target_entries_qs = target_entries_qs.filter(id=planned_meal.id)

		target_entries = list(target_entries_qs)
		if not target_entries:
			return Response(
				{'CODE': 'PLANNED_MEAL_NOT_FOUND', 'detail': 'Nie znaleziono zaplanowanego posiłku.'},
				status=status.HTTP_404_NOT_FOUND,
			)

		deleted_entries = len(target_entries)
		target_entries_qs.delete()

		emit_live_shopping_list_updates_for_date(
			family.id,
			planned_meal.data,
			reason='calendar.meal_removed',
		)

		return Response(
			{
				'CODE': 'PLANNED_MEAL_REMOVED',
				'detail': 'Posiłek usunięto z zaplanowanych posiłków rodziny.',
				'deleted_entries': deleted_entries,
			},
			status=status.HTTP_200_OK,
		)
