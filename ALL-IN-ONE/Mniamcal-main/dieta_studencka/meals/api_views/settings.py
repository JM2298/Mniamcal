"""Settings API views category."""

from django.db import IntegrityError, transaction
from django.db.utils import OperationalError, ProgrammingError
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from meals.models import (
	ProjektInflacjaMobileAktualnecenyproduktowwdanymsklepie,
	ProjektInflacjaMobileHistoriacenproduktow,
)
from meals.serializers import (
	ApiErrorSerializer,
	StoreCurrentPriceUpdateRequestSerializer,
	StoreCurrentPriceUpdateResponseSerializer,
)
from meals.tasks import recalculate_meal_prices_for_store_task


@extend_schema_view(
	create=extend_schema(
		tags=['settings'],
		summary='Aktualizacja cen produktow w sklepie (POST)',
		description='Tworzy lub aktualizuje aktualne ceny produktow dla wskazanego sklepu oraz dopisuje wpisy do historii cen. Po zapisie uruchamia asynchroniczne zadanie Celery do przeliczenia kosztu posilkow na podstawie ilosci skladnikow i dostepnych cen produktow. Po zakonczeniu zadania wysylane jest push notification do wszystkich aktywnych uzytkownikow.',
		request=StoreCurrentPriceUpdateRequestSerializer,
		responses={
			200: StoreCurrentPriceUpdateResponseSerializer,
			400: ApiErrorSerializer,
			401: ApiErrorSerializer,
			503: ApiErrorSerializer,
		},
	),
	update=extend_schema(
		tags=['settings'],
		summary='Aktualizacja cen produktow w sklepie (PUT)',
		description='Idempotentna aktualizacja cen produktow dla wskazanego sklepu. Dla kazdego produktu utrzymuje aktualna cene i dopisuje rekord historii, a przeliczenie kosztu posilkow uruchamia asynchronicznie przez Celery. Po zakonczeniu zadania wysylane jest push notification do wszystkich aktywnych uzytkownikow.',
		request=StoreCurrentPriceUpdateRequestSerializer,
		responses={
			200: StoreCurrentPriceUpdateResponseSerializer,
			400: ApiErrorSerializer,
			401: ApiErrorSerializer,
			503: ApiErrorSerializer,
		},
	),
)
class StoreCurrentPriceUpdateViewSet(viewsets.GenericViewSet):
	permission_classes = [IsAuthenticated]
	serializer_class = StoreCurrentPriceUpdateRequestSerializer
	http_method_names = ['post', 'put']

	def _upsert_current_prices(self, request):
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		sklep_id = serializer.validated_data['sklep_id']
		produkty = serializer.validated_data['produkty']

		created_current_prices = 0
		updated_current_prices = 0
		created_history_rows = 0
		data_wyliczenia = max((produkt['data_dodania'] for produkt in produkty), default=None)

		try:
			with transaction.atomic():
				for produkt in produkty:
					lookup = {
						'sklep_id': sklep_id,
						'nazwa_produktu_uproszczonego_id': produkt['nazwa_produktu_uproszczonego_id'],
					}
					defaults = {
						'dokladna_nazwa_produktu': produkt['dokladna_nazwa_produktu'],
						'cena_produktu': produkt['cena_produktu'],
						'cena_produktu_za_kg': produkt['cena_produktu_za_kg'],
						'producent': produkt.get('producent', ''),
						'opakowanie': produkt.get('opakowanie', ''),
						'data_dodania': produkt['data_dodania'],
					}

					existing_current_price = (
						ProjektInflacjaMobileAktualnecenyproduktowwdanymsklepie.objects
						.filter(**lookup)
						.first()
					)

					if existing_current_price is None:
						ProjektInflacjaMobileAktualnecenyproduktowwdanymsklepie.objects.create(**lookup, **defaults)
						created_current_prices += 1
					else:
						for field_name, field_value in defaults.items():
							setattr(existing_current_price, field_name, field_value)
						existing_current_price.save(update_fields=list(defaults.keys()))
						updated_current_prices += 1

					ProjektInflacjaMobileHistoriacenproduktow.objects.create(**lookup, **defaults)
					created_history_rows += 1
		except IntegrityError:
			return Response(
				{
					'CODE': 'INVALID_REFERENCE',
					'detail': 'Niepoprawny sklep_id lub nazwa_produktu_uproszczonego_id.',
				},
				status=status.HTTP_400_BAD_REQUEST,
			)
		except (ProgrammingError, OperationalError):
			return Response(
				{
					'CODE': 'SETTINGS_CONTEXT_UNAVAILABLE',
					'detail': 'Kontekst ustawien jest chwilowo niedostepny.',
				},
				status=status.HTTP_503_SERVICE_UNAVAILABLE,
			)

		if data_wyliczenia is None:
			return Response(
				{
					'CODE': 'VALIDATION_ERROR',
					'detail': 'Brakuje daty do wyliczenia kosztu posilkow.',
				},
				status=status.HTTP_400_BAD_REQUEST,
			)

		try:
			task_result = recalculate_meal_prices_for_store_task.delay(
				sklep_id=sklep_id,
				data_wyliczenia=data_wyliczenia.isoformat(),
			)
		except Exception:
			return Response(
				{
					'CODE': 'MEAL_PRICE_TASK_QUEUE_UNAVAILABLE',
					'detail': 'Nie udalo sie zakolejkowac przeliczania cen posilkow.',
				},
				status=status.HTTP_503_SERVICE_UNAVAILABLE,
			)

		return Response(
			{
				'CODE': 'STORE_CURRENT_PRICES_UPDATED',
				'detail': 'Ceny produktow zostaly zaktualizowane. Przeliczanie cen posilkow uruchomiono asynchronicznie.',
				'sklep_id': sklep_id,
				'processed_products': len(produkty),
				'created_current_prices': created_current_prices,
				'updated_current_prices': updated_current_prices,
				'created_history_rows': created_history_rows,
				'meal_price_recalculation_status': 'queued',
				'meal_price_recalculation_task_id': str(task_result.id),
			},
			status=status.HTTP_200_OK,
		)

	def create(self, request, *args, **kwargs):
		return self._upsert_current_prices(request)

	def update(self, request, *args, **kwargs):
		return self._upsert_current_prices(request)
