from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError
from django.utils.text import slugify
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken

from meals.models import (
    AuthUser,
    FcmDeviceToken,
    FcmUserPreference,
    ProjektInflacjaMobileKalorycznoscdiety,
    ProjektInflacjaMobileListazakupowrodziny,
    ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny,
    ProjektInflacjaMobileOcenaposilkuprzezuzytkownika,
    ProjektInflacjaMobileProduktynalisciezakupowrodziny,
    ProjektInflacjaMobileRodziny,
    ProjektInflacjaMobileUzytkownicywrodzinach,
    ProjektInflacjaMobileZaplanowaneposilkirodziny,
    ShoppingPackagePreference,
)
from meals.serializers import ApiErrorSerializer, AuthMeResponseSerializer, AuthResponseSerializer, AuthSetDietSerializer, AuthTokenResponseSerializer, FcmDevicePreferenceResponseSerializer, FcmDevicePreferenceSerializer, FcmDeviceRegisterSerializer, FcmSendNotificationResponseSerializer, FcmSendNotificationSerializer, GoogleOAuthLoginSerializer, LoginSerializer, RegisterSerializer
from meals.services import FirebaseConfigurationError, FirebaseTokenValidationError, send_push_notification, verify_firebase_id_token
from meals.services.shopping_list_realtime import emit_live_shopping_list_updates_for_family


User = get_user_model()


def _issue_auth_tokens(user, code, detail):
    refresh = RefreshToken.for_user(user)
    return {
        'CODE': code,
        'detail': detail,
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


def _generate_unique_username(base_name):
    base = slugify(base_name)[:130] or 'user'
    username = base
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base[:120]}-{counter}"
        counter += 1
    return username


def _resolve_user_family_and_membership(user):
    membership = (
        ProjektInflacjaMobileUzytkownicywrodzinach.objects
        .filter(uzytkownik_id=user.id)
        .select_related('rodzina', 'kalorycznosc_diety__dieta', 'kalorycznosc_diety__kalorycznosc')
        .first()
    )

    family = None
    if membership:
        family = membership.rodzina
    else:
        family = ProjektInflacjaMobileRodziny.objects.filter(zalozyciel_rodziny_id=user.id).first()

    return family, membership


def _build_auth_me_payload(user, family, membership):
    kalorycznosc_diety = getattr(membership, 'kalorycznosc_diety', None)
    dieta = getattr(kalorycznosc_diety, 'dieta', None)
    kalorycznosc = getattr(kalorycznosc_diety, 'kalorycznosc', None)

    return {
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'email': user.email,
        'rodzina_id': getattr(family, 'id', None),
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


def _cleanup_user_account_context(user_id):
    founded_family_ids = list(
        ProjektInflacjaMobileRodziny.objects
        .filter(zalozyciel_rodziny_id=user_id)
        .values_list('id', flat=True)
    )
    founded_family_ids_set = set(founded_family_ids)

    for family_id in founded_family_ids:
        _delete_family_related_data(family_id)

    if founded_family_ids:
        ProjektInflacjaMobileRodziny.objects.filter(id__in=founded_family_ids).delete()

    membership_qs = ProjektInflacjaMobileUzytkownicywrodzinach.objects.filter(
        uzytkownik_id=user_id,
    )
    membership_ids = list(membership_qs.values_list('id', flat=True))
    membership_family_ids = list(
        membership_qs.values_list('rodzina_id', flat=True).distinct(),
    )

    if membership_ids:
        ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.filter(
            uzytkownik_w_rodzinie_id__in=membership_ids,
        ).delete()

    membership_qs.delete()

    for family_id in founded_family_ids:
        emit_live_shopping_list_updates_for_family(
            family_id,
            reason='family.founder_deleted_account',
        )

    for family_id in membership_family_ids:
        if family_id is None or family_id in founded_family_ids_set:
            continue
        emit_live_shopping_list_updates_for_family(
            family_id,
            reason='family.member_deleted_account',
        )


@extend_schema_view(
    create=extend_schema(
        tags=['register'],
        summary='Rejestracja uzytkownika',
        description='Tworzy nowe konto uzytkownika na podstawie username, first_name, email i hasla. W odpowiedzi zwraca pare tokenow JWT: access oraz refresh.',
        request=RegisterSerializer,
        responses={201: AuthTokenResponseSerializer, 400: ApiErrorSerializer},
    )
)
class RegisterViewSet(viewsets.GenericViewSet):

    
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer
    http_method_names = ['post']

    def create(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data['username']
        first_name = serializer.validated_data['first_name']
        email = serializer.validated_data.get('email', '')
        password = serializer.validated_data['password']

        if User.objects.filter(username=username).exists():
            return Response({'CODE': 'USER_ALREADY_EXISTS', 'detail': 'Uzytkownik o tej nazwie juz istnieje.'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(username=username, first_name=first_name, email=email, password=password)
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                'CODE': 'REGISTER_SUCCESS',
                'detail': 'Rejestracja zakonczona sukcesem.',
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(
    create=extend_schema(
        tags=['login'],
        summary='Logowanie uzytkownika',
        description='Weryfikuje dane logowania i zwraca tokeny JWT (access, refresh) dla poprawnych danych.',
        request=LoginSerializer,
        responses={200: AuthTokenResponseSerializer, 400: ApiErrorSerializer, 401: ApiErrorSerializer},
    )
)
class LoginViewSet(viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer
    http_method_names = ['post']

    def create(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request,
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password'],
        )

        if user is None:
            return Response({'CODE': 'INVALID_CREDENTIALS', 'detail': 'Nieprawidlowe dane logowania.'}, status=status.HTTP_401_UNAUTHORIZED)

        return Response(_issue_auth_tokens(user, 'LOGIN_SUCCESS', 'Logowanie poprawne.'), status=status.HTTP_200_OK)


@extend_schema_view(
    create=extend_schema(
        tags=['login'],
        summary='Logowanie Firebase (Google)',
        description='Logowanie na podstawie Firebase ID token (web/android). Dla nowego uzytkownika konto zostanie utworzone automatycznie.',
        request=GoogleOAuthLoginSerializer,
        responses={200: AuthTokenResponseSerializer, 400: ApiErrorSerializer, 401: ApiErrorSerializer},
    )
)
class GoogleOAuthLoginViewSet(viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    serializer_class = GoogleOAuthLoginSerializer
    http_method_names = ['post']

    @transaction.atomic
    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payload = verify_firebase_id_token(serializer.validated_data['id_token'])
        except FirebaseConfigurationError as exc:
            return Response(
                {'CODE': 'FIREBASE_NOT_CONFIGURED', 'detail': str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except FirebaseTokenValidationError as exc:
            detail = 'Nieprawidlowy Firebase ID token.'
            if settings.DEBUG:
                detail = f'{detail} Powod: {exc}'
            return Response(
                {'CODE': 'INVALID_OAUTH_TOKEN', 'detail': detail},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        email = payload.get('email')

        if not email:
            return Response({'CODE': 'INVALID_OAUTH_TOKEN', 'detail': 'Token OAuth2 nie zawiera email.'}, status=status.HTTP_400_BAD_REQUEST)

        token_name = (payload.get('name') or '').strip()
        first_name = (payload.get('given_name') or '').strip()
        if not first_name and token_name:
            first_name = token_name.split()[0]
        last_name = payload.get('family_name', '')

        user = User.objects.filter(email__iexact=email).first()
        created = False
        if user is None:
            username = _generate_unique_username(payload.get('name') or email.split('@')[0])
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=None,
            )
            user.set_unusable_password()
            user.save(update_fields=['password'])
            created = True
        elif not (user.first_name or '').strip() and first_name:
            user.first_name = first_name
            user.save(update_fields=['first_name'])

        code = 'OAUTH_REGISTER_SUCCESS' if created else 'OAUTH_LOGIN_SUCCESS'
        detail = 'Logowanie OAuth2 poprawne.'
        return Response(_issue_auth_tokens(user, code, detail), status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(
        tags=['account'],
        summary='Dane zalogowanego uzytkownika',
        description='Zwraca podstawowe dane aktualnie zalogowanego uzytkownika na podstawie tokenu JWT przekazanego w naglowku Authorization.',
        responses={200: AuthMeResponseSerializer, 401: ApiErrorSerializer},
    )
)
class AuthMeViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AuthMeResponseSerializer
    http_method_names = ['get', 'post']

    def list(self, request):
        user = request.user

        try:
            family, membership = _resolve_user_family_and_membership(user)
        except (ProgrammingError, OperationalError):
            family, membership = None, None

        return Response(_build_auth_me_payload(user, family, membership), status=status.HTTP_200_OK)

    @extend_schema(
        tags=['account'],
        summary='Ustawienie diety zalogowanego uzytkownika',
        description='Ustawia preferencje diety (kalorycznosc_diety) dla zalogowanego uzytkownika. Po zapisie wybor jest widoczny w auth/me i moze byc uzyty do domyslnego zaznaczenia diety.',
        request=AuthSetDietSerializer,
        responses={
            200: OpenApiResponse(response=AuthMeResponseSerializer, description='Zapisano wybor diety.'),
            400: OpenApiResponse(response=ApiErrorSerializer, description='Nieprawidlowe dane.'),
            404: OpenApiResponse(response=ApiErrorSerializer, description='Nie znaleziono rodziny lub opcji diety.'),
        },
    )
    @action(detail=False, methods=['post'], url_path='diet')
    def diet(self, request, *args, **kwargs):
        serializer = AuthSetDietSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            family, membership = _resolve_user_family_and_membership(request.user)
        except (ProgrammingError, OperationalError):
            return Response(
                {
                    'CODE': 'DIET_SELECTION_UNAVAILABLE',
                    'detail': 'Wybor diety jest chwilowo niedostepny.',
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if family is None:
            return Response(
                {
                    'CODE': 'FAMILY_NOT_FOUND',
                    'detail': 'Uzytkownik nie nalezy do zadnej rodziny.',
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        kalorycznosc_diety_id = serializer.validated_data['kalorycznosc_diety_id']
        kalorycznosc_diety = (
            ProjektInflacjaMobileKalorycznoscdiety.objects
            .select_related('dieta', 'kalorycznosc')
            .filter(id=kalorycznosc_diety_id)
            .first()
        )
        if kalorycznosc_diety is None:
            return Response(
                {
                    'CODE': 'DIET_OPTION_NOT_FOUND',
                    'detail': 'Wybrana opcja diety nie istnieje.',
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if membership:
            membership.kalorycznosc_diety = kalorycznosc_diety
            membership.save(update_fields=['kalorycznosc_diety'])
        else:
            auth_user = AuthUser.objects.filter(id=request.user.id).first()
            if auth_user is None:
                return Response(
                    {
                        'CODE': 'USER_MAPPING_NOT_FOUND',
                        'detail': 'Nie znaleziono mapowania uzytkownika w tabeli auth_user.',
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
            membership = ProjektInflacjaMobileUzytkownicywrodzinach.objects.create(
                rodzina=family,
                uzytkownik=auth_user,
                kalorycznosc_diety=kalorycznosc_diety,
            )

        emit_live_shopping_list_updates_for_family(family.id, reason='family_member_diet.updated')

        return Response(
            _build_auth_me_payload(request.user, family, membership),
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=['account'],
        summary='Usuniecie konta zalogowanego uzytkownika',
        description='Usuwa konto zalogowanego uzytkownika wraz z powiazanym kontekstem rodziny i dodatkowymi danymi konta.',
        responses={200: AuthResponseSerializer, 401: ApiErrorSerializer, 500: ApiErrorSerializer},
    )
    @action(detail=False, methods=['post'], url_path='delete')
    def delete_account(self, request, *args, **kwargs):
        user_id = request.user.id

        try:
            with transaction.atomic():
                try:
                    # Isolate legacy-table cleanup in a savepoint so optional DB errors
                    # don't invalidate the main transaction for deleting auth user.
                    with transaction.atomic():
                        _cleanup_user_account_context(user_id)
                        ProjektInflacjaMobileOcenaposilkuprzezuzytkownika.objects.filter(
                            uzytkownik_id=user_id,
                        ).delete()
                except (ProgrammingError, OperationalError):
                    # Some mirrored legacy tables may be unavailable in constrained environments.
                    pass

                request.user.delete()
        except Exception:
            return Response(
                {
                    'CODE': 'ACCOUNT_DELETE_FAILED',
                    'detail': 'Nie udalo sie usunac konta.',
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                'CODE': 'ACCOUNT_DELETED',
                'detail': 'Konto zostalo usuniete.',
            },
            status=status.HTTP_200_OK,
        )


@extend_schema_view(
    create=extend_schema(
        tags=['fcm'],
        summary='Rejestracja tokenu FCM',
        description='Rejestruje lub aktualizuje token urzadzenia FCM dla zalogowanego uzytkownika.',
        request=FcmDeviceRegisterSerializer,
        responses={200: AuthResponseSerializer, 400: ApiErrorSerializer, 401: ApiErrorSerializer},
    )
)
class FcmDeviceRegisterViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = FcmDeviceRegisterSerializer
    http_method_names = ['get', 'post']

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data['token']
        platform = serializer.validated_data.get('platform', '')

        device, created = FcmDeviceToken.objects.update_or_create(
            token=token,
            defaults={'user': request.user, 'platform': platform, 'is_active': True},
        )

        return Response(
            {
                'CODE': 'FCM_TOKEN_REGISTERED' if created else 'FCM_TOKEN_UPDATED',
                'detail': 'Token FCM zapisany poprawnie.',
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=['fcm'],
        summary='Pobranie lub zapis ustawien konta',
        description='GET zwraca aktualne ustawienia konta (powiadomienia push i podawanie wielkosci opakowania na liscie zakupow). POST zapisuje przekazane preferencje.',
        request=FcmDevicePreferenceSerializer,
        responses={200: FcmDevicePreferenceResponseSerializer, 400: ApiErrorSerializer, 401: ApiErrorSerializer},
    )
    @action(detail=False, methods=['get', 'post'], url_path='preferences')
    def preferences(self, request):
        if request.method.lower() == 'post':
            serializer = FcmDevicePreferenceSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            preference, _ = FcmUserPreference.objects.get_or_create(user=request.user)
            push_enabled = bool(preference.push_enabled)
            shopping_package_size_enabled = bool(preference.shopping_package_size_enabled)
            updated_fields = []

            if 'push_enabled' in serializer.validated_data:
                push_enabled = serializer.validated_data['push_enabled']
                preference.push_enabled = push_enabled
                updated_fields.append('push_enabled')
                FcmDeviceToken.objects.filter(user=request.user).update(
                    is_active=push_enabled,
                )

            if 'shopping_package_size_enabled' in serializer.validated_data:
                shopping_package_size_enabled = serializer.validated_data['shopping_package_size_enabled']
                preference.shopping_package_size_enabled = shopping_package_size_enabled
                updated_fields.append('shopping_package_size_enabled')

            if updated_fields:
                preference.save(update_fields=updated_fields + ['updated_at'])

            return Response(
                {
                    'CODE': 'FCM_PREFERENCE_UPDATED',
                    'detail': 'Zapisano ustawienia konta.',
                    'push_enabled': push_enabled,
                    'shopping_package_size_enabled': shopping_package_size_enabled,
                },
                status=status.HTTP_200_OK,
            )

        preference = FcmUserPreference.objects.filter(user=request.user).first()
        push_enabled = True if preference is None else bool(preference.push_enabled)
        shopping_package_size_enabled = (
            True if preference is None else bool(preference.shopping_package_size_enabled)
        )
        return Response(
            {
                'CODE': 'FCM_PREFERENCE_LOADED',
                'detail': 'Pobrano ustawienia konta.',
                'push_enabled': push_enabled,
                'shopping_package_size_enabled': shopping_package_size_enabled,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema_view(
    create=extend_schema(
        tags=['fcm'],
        summary='Wysylka wiadomosci FCM',
        description='Wysyla push notification FCM na wskazany token lub na tokeny zalogowanego uzytkownika.',
        request=FcmSendNotificationSerializer,
        responses={200: FcmSendNotificationResponseSerializer, 400: ApiErrorSerializer, 401: ApiErrorSerializer},
    )
)
class FcmSendNotificationViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = FcmSendNotificationSerializer
    http_method_names = ['post']

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        title = serializer.validated_data['title']
        body = serializer.validated_data['body']
        data = serializer.validated_data.get('data', {})
        token = serializer.validated_data.get('token')
        user_id = serializer.validated_data.get('user_id')

        if token:
            tokens = [token]
        else:
            target_user_id = user_id or request.user.id
            tokens = list(
                FcmDeviceToken.objects.filter(user_id=target_user_id, is_active=True).values_list('token', flat=True)
            )

        if not tokens:
            return Response(
                {'CODE': 'FCM_TOKEN_NOT_FOUND', 'detail': 'Brak aktywnych tokenow FCM dla wskazanego uzytkownika.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        message_ids = []
        errors = []
        for current_token in tokens:
            try:
                message_ids.append(send_push_notification(current_token, title, body, data=data))
            except Exception as exc:
                errors.append(str(exc))

        return Response(
            {
                'CODE': 'FCM_SEND_COMPLETED',
                'detail': 'Wysylka wiadomosci FCM zakonczona.',
                'sent': len(message_ids),
                'failed': len(errors),
                'message_ids': message_ids,
                'errors': errors,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=['login'],
    summary='Odswiezenie tokenu JWT',
    description='Przyjmuje refresh token i zwraca nowy access token (oraz opcjonalnie refresh token zgodnie z konfiguracja JWT).',
    request=inline_serializer(
        name='TokenRefreshRequest',
        fields={
            'refresh': serializers.CharField(),
        },
    ),
    responses={
        200: inline_serializer(
            name='TokenRefreshResponse',
            fields={
                'access': serializers.CharField(),
                'refresh': serializers.CharField(required=False),
            },
        ),
        401: inline_serializer(
            name='TokenRefreshErrorResponse',
            fields={
                'detail': serializers.CharField(),
                'code': serializers.CharField(required=False),
            },
        ),
    },
)
class AuthTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
