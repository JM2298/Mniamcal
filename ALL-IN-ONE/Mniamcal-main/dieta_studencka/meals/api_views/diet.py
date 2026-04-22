from django.db.utils import OperationalError, ProgrammingError
from django.db.models import DecimalField, F, IntegerField, OuterRef, Prefetch, Subquery, TextField, Value
from django.db.models.functions import Cast, Coalesce, NullIf, Replace
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from meals.models import (
	ProjektInflacjaMobileCenacalegoposilku,
	ProjektInflacjaMobileKalorycznoscdiety,
	ProjektInflacjaMobileDiety,
	ProjektInflacjaMobileOcenaposilkuprzezuzytkownika,
	ProjektInflacjaMobileProduktyuproszczone,
	ProjektInflacjaMobileProduktywposilku,
	ProjektInflacjaMobilePosilkiwdiecie,
)
from meals.serializers import DietCalorieListSerializer, DietListSerializer, DietMealListSerializer, SimplifiedProductListSerializer


def _empty_fallback_response(view, request):
	if view.paginator is not None:
		view.paginator.paginate_queryset([], request, view=view)
		return view.paginator.get_paginated_response([])
	return Response([], status=status.HTTP_200_OK)


@extend_schema_view(
	list=extend_schema(
		tags=['diet'],
		summary='Lista diet',
		description='Zwraca liste wszystkich dostepnych diet z ich podstawowymi informacjami.',
		responses={200: DietListSerializer(many=True)},
	)
)
class DietListViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
	
	permission_classes = [AllowAny]
	serializer_class = DietListSerializer
	queryset = ProjektInflacjaMobileDiety.objects.all().order_by('dieta')
	http_method_names = ['get']

	def list(self, request, *args, **kwargs):
		try:
			return super().list(request, *args, **kwargs)
		except (ProgrammingError, OperationalError):
			return _empty_fallback_response(self, request)


@extend_schema_view(
	list=extend_schema(
		tags=['diet'],
		summary='Lista posilkow w diecie',
		description='Zwraca liste posilkow przypisanych do diety. Mozna dodatkowo filtrowac i sortowac wyniki za pomoca parametrow query.',
		parameters=[
			OpenApiParameter(
				name='posilek-w-diecie-id',
				type=int,
				location=OpenApiParameter.QUERY,
				required=False,
				description='Filtruje po identyfikatorze konkretnego posilku w diecie.',
			),
			OpenApiParameter(
				name='dieta-id',
				type=int,
				location=OpenApiParameter.QUERY,
				required=False,
				description='Filtruje posilki po identyfikatorze diety.',
			),
			OpenApiParameter(
				name='kalorycznosc-diety-id',
				type=int,
				location=OpenApiParameter.QUERY,
				required=False,
				description='Filtruje posilki po identyfikatorze opcji kalorycznosci dla wybranej diety.',
			),
			OpenApiParameter(
				name='kalorycznosc-id',
				type=int,
				location=OpenApiParameter.QUERY,
				required=False,
				description='Filtruje posilki po identyfikatorze kalorycznosci.',
			),
			OpenApiParameter(
				name='czysta-kalorycznosc',
				type=int,
				location=OpenApiParameter.QUERY,
				required=False,
				description='Filtruje posilki po wartosci kcal (np. 1500, 1800).',
			),
			OpenApiParameter(
				name='pora-posilku',
				type=str,
				location=OpenApiParameter.QUERY,
				required=False,
				description='Filtr po porze posilku (np. sniadanie, obiad).',
			),
			OpenApiParameter(
				name='nazwa-posilku',
				type=str,
				location=OpenApiParameter.QUERY,
				required=False,
				description='Filtr po nazwie posilku.',
			),
			OpenApiParameter(
				name='czas-przygotowania',
				type=str,
				location=OpenApiParameter.QUERY,
				required=False,
				description='Filtr po tekscie czasu przygotowania.',
			),
			OpenApiParameter(
				name='czas-przygotowania-max-minut',
				type=int,
				location=OpenApiParameter.QUERY,
				required=False,
				description='Maksymalny czas przygotowania w minutach.',
			),
			OpenApiParameter(
				name='sortowanie-cena',
				type=str,
				location=OpenApiParameter.QUERY,
				required=False,
				description='Sortowanie po cenie posilku: najtansze albo najdrozsze.',
			),
		],
		responses={200: DietMealListSerializer(many=True)},
	)
)
class DietMealsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
	permission_classes = [AllowAny]
	serializer_class = DietMealListSerializer
	http_method_names = ['get']
	queryset = ProjektInflacjaMobilePosilkiwdiecie.objects.select_related(
		'nazwa_posilku', 'pora_posilku', 'kalorycznosc_diety'
	).prefetch_related(
		Prefetch(
			'projektinflacjamobileproduktywposilku_set',
			queryset=ProjektInflacjaMobileProduktywposilku.objects.select_related('nazwa_produktu', 'miarka'),
		)
	).all().order_by('id')

	def get_queryset(self):
		latest_price_for_meal = ProjektInflacjaMobileCenacalegoposilku.objects.filter(
			posilek_id=OuterRef('pk')
		).order_by('-data', '-id')

		current_user = getattr(self.request, 'user', None)
		latest_user_rating_for_meal = None
		if current_user is not None and getattr(current_user, 'is_authenticated', False):
			latest_user_rating_for_meal = (
				ProjektInflacjaMobileOcenaposilkuprzezuzytkownika.objects
				.filter(posilek_id=OuterRef('pk'), uzytkownik_id=current_user.id)
				.order_by('-data_oceny', '-id')
			)

		queryset = super().get_queryset().annotate(
			cena_posilku=Subquery(
				latest_price_for_meal.values('cena_calego_posilku')[:1],
				output_field=DecimalField(max_digits=10, decimal_places=2),
			),
			brakujace_ceny_produktow=Subquery(
				latest_price_for_meal.values('brakujace_ceny_produktu')[:1],
				output_field=TextField(),
			),
			ocena_uzytkownika_id=(
				Subquery(
					latest_user_rating_for_meal.values('ocena_id')[:1],
					output_field=IntegerField(),
				)
				if latest_user_rating_for_meal is not None
				else Value(None, output_field=IntegerField())
			),
			ocena_uzytkownika=(
				Subquery(
					latest_user_rating_for_meal.values('ocena__ocena')[:1],
					output_field=TextField(),
				)
				if latest_user_rating_for_meal is not None
				else Value(None, output_field=TextField())
			),
		)
		dieta_id = self.request.query_params.get('dieta-id')
		posilek_w_diecie_id = self.request.query_params.get('posilek-w-diecie-id')
		kalorycznosc_diety_id = self.request.query_params.get('kalorycznosc-diety-id')
		kalorycznosc_id = self.request.query_params.get('kalorycznosc-id')
		czysta_kalorycznosc = self.request.query_params.get('czysta-kalorycznosc')
		pora_posilku = self.request.query_params.get('pora-posilku')
		nazwa_posilku = self.request.query_params.get('nazwa-posilku')
		czas_przygotowania = self.request.query_params.get('czas-przygotowania')
		czas_przygotowania_max = self.request.query_params.get('czas-przygotowania-max-minut')
		sortowanie_cena = self.request.query_params.get('sortowanie-cena')

		if posilek_w_diecie_id:
			queryset = queryset.filter(id=posilek_w_diecie_id)
		if dieta_id:
			queryset = queryset.filter(kalorycznosc_diety__dieta_id=dieta_id)
		if kalorycznosc_diety_id:
			queryset = queryset.filter(kalorycznosc_diety_id=kalorycznosc_diety_id)
		if kalorycznosc_id:
			queryset = queryset.filter(kalorycznosc_diety__kalorycznosc_id=kalorycznosc_id)
		if czysta_kalorycznosc:
			queryset = queryset.filter(kalorycznosc_diety__kalorycznosc__czysta_kalorycznosc=czysta_kalorycznosc)
		if pora_posilku:
			queryset = queryset.filter(pora_posilku__pora_posilku__icontains=pora_posilku)
		if nazwa_posilku:
			queryset = queryset.filter(nazwa_posilku__nazwa_posilku__icontains=nazwa_posilku)
		if czas_przygotowania:
			queryset = queryset.filter(czas_przygotowania__icontains=czas_przygotowania)
		if czas_przygotowania_max:
			try:
				max_minutes = int(czas_przygotowania_max)
			except (TypeError, ValueError):
				max_minutes = None
			if max_minutes is not None:
				minutes_text = Replace(
					Replace(
						Replace(F('czas_przygotowania'), Value('min'), Value('')),
						Value(' '),
						Value(''),
					),
					Value(','),
					Value('.'),
				)
				queryset = queryset.annotate(
					czas_przygotowania_minuty=Coalesce(
						Cast(NullIf(minutes_text, Value('')), IntegerField()),
						Value(0),
					)
				).filter(czas_przygotowania_minuty__lte=max_minutes)

		if sortowanie_cena == 'najtansze':
			queryset = queryset.order_by(F('cena_posilku').asc(nulls_last=True), 'id')
		elif sortowanie_cena == 'najdrozsze':
			queryset = queryset.order_by(F('cena_posilku').desc(nulls_last=True), 'id')
		return queryset

	def list(self, request, *args, **kwargs):
		try:
			return super().list(request, *args, **kwargs)
		except (ProgrammingError, OperationalError):
			return _empty_fallback_response(self, request)


@extend_schema_view(
	list=extend_schema(
		tags=['diet'],
		summary='Lista kalorycznosci diet',
		description='Zwraca liste kalorycznosci przypisanych do diet. Mozna dodatkowo filtrowac wyniki po identyfikatorze diety za pomoca parametru query.',
		parameters=[
			OpenApiParameter(
				name='dieta-id',
				type=int,
				location=OpenApiParameter.QUERY,
				required=False,
				description='Filtruje kalorycznosc po identyfikatorze diety.',
			),
		],
		responses={200: DietCalorieListSerializer(many=True)},
	)
)
class DietCalorieViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
	permission_classes = [AllowAny]
	serializer_class = DietCalorieListSerializer
	http_method_names = ['get']
	queryset = ProjektInflacjaMobileKalorycznoscdiety.objects.select_related('dieta', 'kalorycznosc').all().order_by('id')

	def get_queryset(self):
		queryset = super().get_queryset()
		dieta_id = self.request.query_params.get('dieta-id')
		if dieta_id:
			queryset = queryset.filter(dieta_id=dieta_id)
		return queryset

	def list(self, request, *args, **kwargs):
		try:
			return super().list(request, *args, **kwargs)
		except (ProgrammingError, OperationalError):
			return _empty_fallback_response(self, request)


@extend_schema_view(
	list=extend_schema(
		tags=['diet'],
		summary='Lista produktow uproszczonych',
		description='Zwraca liste produktow uproszczonych wraz z makroskladnikami i kategoria produktu.',
		parameters=[
			OpenApiParameter(
				name='nazwa-produktu',
				type=str,
				location=OpenApiParameter.QUERY,
				required=False,
				description='Filtruje po nazwie produktu uproszczonego.',
			),
			OpenApiParameter(
				name='kategoria-id',
				type=int,
				location=OpenApiParameter.QUERY,
				required=False,
				description='Filtruje po identyfikatorze kategorii produktu.',
			),
		],
		responses={200: SimplifiedProductListSerializer(many=True)},
	)
)
class SimplifiedProductsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
	permission_classes = [AllowAny]
	serializer_class = SimplifiedProductListSerializer
	http_method_names = ['get']
	queryset = ProjektInflacjaMobileProduktyuproszczone.objects.select_related('kategoria_produktu').all().order_by('nazwa_produktu_uproszczonego', 'id')

	def get_queryset(self):
		queryset = super().get_queryset()
		nazwa_produktu = self.request.query_params.get('nazwa-produktu')
		kategoria_id = self.request.query_params.get('kategoria-id')

		if nazwa_produktu:
			queryset = queryset.filter(nazwa_produktu_uproszczonego__icontains=nazwa_produktu)
		if kategoria_id:
			queryset = queryset.filter(kategoria_produktu_id=kategoria_id)

		return queryset

	def list(self, request, *args, **kwargs):
		try:
			return super().list(request, *args, **kwargs)
		except (ProgrammingError, OperationalError):
			return _empty_fallback_response(self, request)
