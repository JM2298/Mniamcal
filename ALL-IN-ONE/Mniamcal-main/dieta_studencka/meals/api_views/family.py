"""Family API views category."""
from collections import defaultdict

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter
from rest_framework.decorators import action
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db.utils import OperationalError, ProgrammingError
from django.template.response import TemplateResponse
from drf_spectacular.utils import extend_schema, extend_schema_view
from meals.models import AuthUser, ProjektInflacjaMobileKalorycznoscdiety, ProjektInflacjaMobileListazakupowrodziny, ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny, ProjektInflacjaMobileProduktynalisciezakupowrodziny, ProjektInflacjaMobileRodziny, ProjektInflacjaMobileUzytkownicywrodzinach, ProjektInflacjaMobileZaplanowaneposilkirodziny, ShoppingPackagePreference
from meals.serializers import AcceptFamilyInvitationSerializer, ApiErrorSerializer, CreateFamilySerializer, FamilyDetailSerializer, FamilyMembersResponseSerializer, FamilyUserMembershipSerializer, FamilyUserSetDietSerializer, InviteToFamilyByEmailSerializer
from meals.services.shopping_list_realtime import emit_live_shopping_list_updates_for_family


def _broadcast_family_event(payload):
	channel_layer = get_channel_layer()
	if not channel_layer:
		return

	async_to_sync(channel_layer.group_send)(
		'family_updates',
		{
			'type': 'family_event',
			'payload': payload,
		},
	)


def _resolve_user_family_membership_context(user):
	membership = (
		ProjektInflacjaMobileUzytkownicywrodzinach.objects
		.filter(uzytkownik_id=user.id)
		.select_related('rodzina', 'kalorycznosc_diety__dieta', 'kalorycznosc_diety__kalorycznosc')
		.first()
	)

	family = membership.rodzina if membership else None
	if family is None:
		family = ProjektInflacjaMobileRodziny.objects.filter(zalozyciel_rodziny_id=user.id).first()

	return family, membership


def _build_user_membership_payload(user, family, membership):
	kalorycznosc_diety = getattr(membership, 'kalorycznosc_diety', None)
	dieta = getattr(kalorycznosc_diety, 'dieta', None)
	kalorycznosc = getattr(kalorycznosc_diety, 'kalorycznosc', None)

	return {
		'id': user.id,
		'username': user.username,
		'first_name': user.first_name,
		'email': user.email,
		'rodzina_id': getattr(family, 'id', None),
		'is_founder': bool(family and family.zalozyciel_rodziny_id == user.id),
		'kalorycznosc_diety_id': getattr(kalorycznosc_diety, 'id', None),
		'dieta_id': getattr(dieta, 'id', None),
		'dieta': getattr(dieta, 'dieta', None),
		'kalorycznosc_id': getattr(kalorycznosc, 'id', None),
		'kalorycznosc': getattr(kalorycznosc, 'kalorycznosc', None),
		'czysta_kalorycznosc': getattr(kalorycznosc, 'czysta_kalorycznosc', None),
	}


def _delete_family_related_data(family_id):
	shopping_list_ids = list(
		ProjektInflacjaMobileListazakupowrodziny.objects
		.filter(rodzina_id=family_id)
		.values_list('id', flat=True)
	)

	if shopping_list_ids:
		ProjektInflacjaMobileProduktynalisciezakupowrodziny.objects.filter(
			lista_zakupow_id__in=shopping_list_ids,
		).delete()

	ProjektInflacjaMobileListazakupowrodziny.objects.filter(rodzina_id=family_id).delete()
	ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny.objects.filter(rodzina_id=family_id).delete()
	ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.filter(rodzina_id=family_id).delete()
	ProjektInflacjaMobileUzytkownicywrodzinach.objects.filter(rodzina_id=family_id).delete()
	ShoppingPackagePreference.objects.filter(rodzina_id=family_id).delete()


@extend_schema_view(
	create=extend_schema(
		tags=['family'],
		summary='Tworzenie rodziny',
		description='Tworzy nowa rodzine z podana nazwa. Uzytkownik tworacy rodzine staje sie jej zalozycielem.',
		responses={201: FamilyDetailSerializer()},
	)
)
class FamilyCreateViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
	permission_classes = [IsAuthenticated]
	serializer_class = CreateFamilySerializer
	queryset = ProjektInflacjaMobileRodziny.objects.all()
	http_method_names = ['post', 'get']

	def create(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		instance = self.perform_create(serializer)
		_broadcast_family_event(
			{
				'event': 'family_created',
				'rodzina_id': instance.id,
				'rodzina': instance.rodzina,
				'created_by_user_id': request.user.id,
			}
		)
		output_serializer = FamilyDetailSerializer(instance, context=self.get_serializer_context())
		return Response(output_serializer.data, status=status.HTTP_201_CREATED)

	def perform_create(self, serializer):
		return serializer.save()

	@extend_schema(
		tags=['family'],
		summary='Dane zalogowanego uzytkownika w rodzinie',
		description='Zwraca kontekst rodziny i aktualnie wybrana opcje diety dla zalogowanego uzytkownika.',
		responses={200: FamilyUserMembershipSerializer, 401: ApiErrorSerializer, 404: ApiErrorSerializer, 503: ApiErrorSerializer},
	)
	@action(detail=False, methods=['get'], url_path='my-membership')
	def my_membership(self, request, *args, **kwargs):
		try:
			family, membership = _resolve_user_family_membership_context(request.user)
		except (ProgrammingError, OperationalError):
			return Response(
				{'CODE': 'FAMILY_CONTEXT_UNAVAILABLE', 'detail': 'Kontekst rodziny jest chwilowo niedostepny.'},
				status=status.HTTP_503_SERVICE_UNAVAILABLE,
			)

		if family is None:
			return Response(
				{'CODE': 'FAMILY_NOT_FOUND', 'detail': 'Uzytkownik nie nalezy do zadnej rodziny.'},
				status=status.HTTP_404_NOT_FOUND,
			)

		return Response(_build_user_membership_payload(request.user, family, membership), status=status.HTTP_200_OK)

	@extend_schema(
		tags=['family'],
		summary='Ustawienie diety uzytkownika w rodzinie',
		description='Ustawia kalorycznosc diety dla zalogowanego uzytkownika w kontekscie jego rodziny.',
		request=FamilyUserSetDietSerializer,
		responses={200: FamilyUserMembershipSerializer, 400: ApiErrorSerializer, 401: ApiErrorSerializer, 404: ApiErrorSerializer, 503: ApiErrorSerializer},
	)
	@action(detail=False, methods=['post'], url_path='my-membership/diet')
	def my_membership_diet(self, request, *args, **kwargs):
		serializer = FamilyUserSetDietSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		try:
			family, membership = _resolve_user_family_membership_context(request.user)
		except (ProgrammingError, OperationalError):
			return Response(
				{'CODE': 'FAMILY_CONTEXT_UNAVAILABLE', 'detail': 'Zapis diety jest chwilowo niedostepny.'},
				status=status.HTTP_503_SERVICE_UNAVAILABLE,
			)

		if family is None:
			return Response(
				{'CODE': 'FAMILY_NOT_FOUND', 'detail': 'Uzytkownik nie nalezy do zadnej rodziny.'},
				status=status.HTTP_404_NOT_FOUND,
			)

		kalorycznosc_diety = (
			ProjektInflacjaMobileKalorycznoscdiety.objects
			.select_related('dieta', 'kalorycznosc')
			.filter(id=serializer.validated_data['kalorycznosc_diety_id'])
			.first()
		)
		if kalorycznosc_diety is None:
			return Response(
				{'CODE': 'DIET_OPTION_NOT_FOUND', 'detail': 'Wybrana opcja diety nie istnieje.'},
				status=status.HTTP_404_NOT_FOUND,
			)

		if membership:
			membership.kalorycznosc_diety = kalorycznosc_diety
			membership.save(update_fields=['kalorycznosc_diety'])
		else:
			auth_user = AuthUser.objects.filter(id=request.user.id).first()
			if auth_user is None:
				return Response(
					{'CODE': 'USER_MAPPING_NOT_FOUND', 'detail': 'Nie znaleziono mapowania uzytkownika w tabeli auth_user.'},
					status=status.HTTP_404_NOT_FOUND,
				)
			membership = ProjektInflacjaMobileUzytkownicywrodzinach.objects.create(
				rodzina=family,
				uzytkownik=auth_user,
				kalorycznosc_diety=kalorycznosc_diety,
			)

		emit_live_shopping_list_updates_for_family(family.id, reason='family_member_diet.updated')

		return Response(_build_user_membership_payload(request.user, family, membership), status=status.HTTP_200_OK)

	@extend_schema(
		tags=['family'],
		summary='Lista czlonkow rodziny',
		description=(
			'Zwraca liste czlonkow rodziny aktualnie zalogowanego uzytkownika wraz z informacja, '
			'kto jest zalozycielem oraz przyszlymi zaplanowanymi posilkami (w tym posilek_w_diecie_id).'
		),
		responses={200: FamilyMembersResponseSerializer, 401: ApiErrorSerializer, 404: ApiErrorSerializer},
	)
	@action(detail=False, methods=['get'], url_path='members')
	def members(self, request, *args, **kwargs):
		family = ProjektInflacjaMobileRodziny.objects.filter(zalozyciel_rodziny_id=request.user.id).first()

		if not family:
			membership = ProjektInflacjaMobileUzytkownicywrodzinach.objects.filter(uzytkownik_id=request.user.id).select_related('rodzina').first()
			if membership:
				family = membership.rodzina

		if not family:
			return Response(
				{'CODE': 'FAMILY_NOT_FOUND', 'detail': 'Uzytkownik nie nalezy do zadnej rodziny.'},
				status=status.HTTP_404_NOT_FOUND,
			)

		memberships = ProjektInflacjaMobileUzytkownicywrodzinach.objects.filter(rodzina_id=family.id).select_related(
			'uzytkownik',
			'kalorycznosc_diety__dieta',
			'kalorycznosc_diety__kalorycznosc',
		)

		today = timezone.localdate()
		planned_meals = (
			ProjektInflacjaMobileZaplanowaneposilkirodziny.objects
			.filter(rodzina_id=family.id, data__gte=today)
			.select_related(
				'uzytkownik_w_rodzinie',
				'posilki_w_diecie__nazwa_posilku',
				'posilki_w_diecie__pora_posilku',
			)
			.order_by('data')
		)

		planned_meals_by_user_id = defaultdict(list)
		for planned_meal in planned_meals:
			member_user_id = getattr(planned_meal.uzytkownik_w_rodzinie, 'uzytkownik_id', None)
			if member_user_id is None:
				continue
			planned_meals_by_user_id[member_user_id].append(
				{
					'planned_meal_id': planned_meal.id,
					'posilek_w_diecie_id': getattr(planned_meal, 'posilki_w_diecie_id', None),
					'data': planned_meal.data,
					'posilek': getattr(planned_meal.posilki_w_diecie.nazwa_posilku, 'nazwa_posilku', ''),
					'pora_posilku': getattr(planned_meal.posilki_w_diecie.pora_posilku, 'pora_posilku', ''),
					'czy_zjedzone': bool(planned_meal.czy_zjedzone),
				}
			)

		def to_member_payload(user, is_founder, membership=None):
			kalorycznosc_diety = getattr(membership, 'kalorycznosc_diety', None)
			dieta = getattr(kalorycznosc_diety, 'dieta', None)
			kalorycznosc = getattr(kalorycznosc_diety, 'kalorycznosc', None)

			return {
				'id': user.id,
				'username': user.username,
				'first_name': user.first_name,
				'email': user.email,
				'is_founder': is_founder,
				'is_current_user': user.id == request.user.id,
				'dieta_id': getattr(dieta, 'id', None),
				'dieta': getattr(dieta, 'dieta', None),
				'kalorycznosc_id': getattr(kalorycznosc, 'id', None),
				'kalorycznosc': getattr(kalorycznosc, 'kalorycznosc', None),
				'czysta_kalorycznosc': getattr(kalorycznosc, 'czysta_kalorycznosc', None),
				'zaplanowane_posilki': planned_meals_by_user_id.get(user.id, []),
			}

		member_by_user_id = {membership.uzytkownik.id: membership for membership in memberships}
		members = [
			to_member_payload(
				family.zalozyciel_rodziny,
				True,
				member_by_user_id.get(family.zalozyciel_rodziny_id),
			)
		]

		for membership in memberships:
			user = membership.uzytkownik
			if user.id == family.zalozyciel_rodziny_id:
				continue

			members.append(to_member_payload(user, False, membership))

		return Response(
			{
				'rodzina_id': family.id,
				'rodzina': family.rodzina,
				'members': members,
			},
			status=status.HTTP_200_OK,
		)

	@extend_schema(
		tags=['family'],
		summary='Opuszczenie rodziny',
		description='Pozwala zalogowanemu uzytkownikowi opuscic rodzine. Zalozyciel rodziny nie moze opuscic rodziny tym endpointem.',
		responses={200: ApiErrorSerializer, 400: ApiErrorSerializer, 404: ApiErrorSerializer},
	)
	@action(detail=False, methods=['post'], url_path='leave')
	def leave(self, request, *args, **kwargs):
		membership = ProjektInflacjaMobileUzytkownicywrodzinach.objects.filter(
			uzytkownik_id=request.user.id
		).select_related('rodzina').first()

		if not membership:
			founder_family = ProjektInflacjaMobileRodziny.objects.filter(zalozyciel_rodziny_id=request.user.id).first()
			if founder_family:
				return Response(
					{
						'CODE': 'FOUNDER_CANNOT_LEAVE',
						'detail': 'Zalozyciel rodziny nie moze opuscic rodziny tym endpointem.',
					},
					status=status.HTTP_400_BAD_REQUEST,
				)

			return Response(
				{
					'CODE': 'FAMILY_NOT_FOUND',
					'detail': 'Uzytkownik nie nalezy do zadnej rodziny.',
				},
				status=status.HTTP_404_NOT_FOUND,
			)

		family = membership.rodzina
		if family and family.zalozyciel_rodziny_id == request.user.id:
			return Response(
				{
					'CODE': 'FOUNDER_CANNOT_LEAVE',
					'detail': 'Zalozyciel rodziny nie moze opuscic rodziny tym endpointem.',
				},
				status=status.HTTP_400_BAD_REQUEST,
			)

		membership.delete()
		_broadcast_family_event(
			{
				'event': 'family_left',
				'rodzina_id': getattr(family, 'id', None),
				'rodzina': getattr(family, 'rodzina', None),
				'user_id': request.user.id,
			}
		)

		return Response(
			{
				'CODE': 'FAMILY_LEFT',
				'detail': 'Opuszczono rodzine.',
			},
			status=status.HTTP_200_OK,
		)

	@extend_schema(
		tags=['family'],
		summary='Usuniecie rodziny',
		description='Pozwala zalozycielowi usunac cala rodzine wraz z danymi powiazanymi.',
		responses={200: ApiErrorSerializer, 403: ApiErrorSerializer, 404: ApiErrorSerializer},
	)
	@action(detail=False, methods=['post'], url_path='delete')
	def delete_family(self, request, *args, **kwargs):
		family = ProjektInflacjaMobileRodziny.objects.filter(zalozyciel_rodziny_id=request.user.id).first()

		if family is None:
			is_member = ProjektInflacjaMobileUzytkownicywrodzinach.objects.filter(
				uzytkownik_id=request.user.id,
			).exists()
			if is_member:
				return Response(
					{
						'CODE': 'ONLY_FOUNDER_CAN_DELETE_FAMILY',
						'detail': 'Tylko zalozyciel rodziny moze ja usunac.',
					},
					status=status.HTTP_403_FORBIDDEN,
				)

			return Response(
				{
					'CODE': 'FAMILY_NOT_FOUND',
					'detail': 'Uzytkownik nie nalezy do zadnej rodziny.',
				},
				status=status.HTTP_404_NOT_FOUND,
			)

		family_id = family.id
		family_name = family.rodzina

		with transaction.atomic():
			_delete_family_related_data(family_id)
			family.delete()

		emit_live_shopping_list_updates_for_family(family_id, reason='family.deleted')
		_broadcast_family_event(
			{
				'event': 'family_deleted',
				'rodzina_id': family_id,
				'rodzina': family_name,
				'deleted_by_user_id': request.user.id,
			}
		)

		return Response(
			{
				'CODE': 'FAMILY_DELETED',
				'detail': 'Rodzina zostala usunieta.',
			},
			status=status.HTTP_200_OK,
		)


@extend_schema_view(
	create=extend_schema(
		tags=['family'],
			summary='Zaproszenie do rodziny przez email',
			description='Wysyla zaproszenie do rodziny na podany adres email. Zaproszenie zawiera link z tokenem, ktory pozwala zaakceptowac zaproszenie i dolaczyc do rodziny.',	
		request=InviteToFamilyByEmailSerializer,
		responses={201: InviteToFamilyByEmailSerializer},
	)
)
class FamilyInviteByEmailViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
	permission_classes = [IsAuthenticated]
	serializer_class = InviteToFamilyByEmailSerializer
	http_method_names = ['post', 'get']

	def create(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		result = serializer.save()
		return Response(result, status=status.HTTP_201_CREATED)

	@extend_schema(
		tags=['family'],
		summary='Akceptacja zaproszenia do rodziny',
		description='Akceptuje zaproszenie do rodziny na podstawie tokenu z linku i dodaje powiazanego uzytkownika do rodziny, jesli nie jest jeszcze jej czlonkiem.',
		parameters=[
			OpenApiParameter(
				name='token',
				type=str,
				location=OpenApiParameter.QUERY,
				required=True,
				description='Token z linku zaproszenia do rodziny.',
			),
		],
		responses={200: AcceptFamilyInvitationSerializer},
	)
	@action(detail=False, methods=['get'],
		 
		  permission_classes=[AllowAny], url_path='accept')
	def accept(self, request, *args, **kwargs):
		as_page = (request.query_params.get('view') or '').lower() == 'page'
		frontend_base_url = getattr(settings, 'FRONTEND_APP_URL', '').rstrip('/')
		login_url = f"{frontend_base_url}/" if frontend_base_url else '/login/'
		serializer = AcceptFamilyInvitationSerializer(
			data={'token': request.query_params.get('token')},
			context=self.get_serializer_context(),
		)

		try:
			serializer.is_valid(raise_exception=True)
			result = serializer.save()
		except ValidationError as exc:
			if not as_page:
				raise

			detail = getattr(exc, 'detail', None)
			if isinstance(detail, dict):
				first_error = next(iter(detail.values()), 'Nie udalo sie zaakceptowac zaproszenia.')
				if isinstance(first_error, list):
					message = str(first_error[0]) if first_error else 'Nie udalo sie zaakceptowac zaproszenia.'
				else:
					message = str(first_error)
			else:
				message = 'Nie udalo sie zaakceptowac zaproszenia.'

			return TemplateResponse(
				request,
				'family_invitation_result.html',
				{
					'title': 'Nie udalo sie zaakceptowac zaproszenia',
					'message': message,
					'is_error': True,
					'login_url': login_url,
				},
				status=status.HTTP_400_BAD_REQUEST,
			)

		_broadcast_family_event(
			{
				'event': 'family_invitation_accepted',
				'rodzina_id': result.get('rodzina_id'),
				'rodzina': result.get('rodzina'),
				'email': result.get('email'),
				'user_added': result.get('user_added'),
				'already_member': result.get('already_member'),
			}
		)

		if as_page:
			if result.get('already_member'):
				title = 'Zaproszenie juz wykorzystane'
				message = f"Uzytkownik {result.get('email', '')} jest juz czlonkiem rodziny '{result.get('rodzina', '')}'."
			else:
				title = 'Dolaczono do rodziny'
				message = f"Dodano {result.get('email', '')} do rodziny '{result.get('rodzina', '')}'."

			return TemplateResponse(
				request,
				'family_invitation_result.html',
				{
					'title': title,
					'message': message,
					'is_error': False,
					'login_url': login_url,
				},
				status=status.HTTP_200_OK,
			)

		return Response(result, status=status.HTTP_200_OK)
