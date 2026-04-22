from rest_framework import serializers
from django.conf import settings
from urllib.parse import urlsplit

from meals.models import ProjektInflacjaMobileDiety
from meals.models import ProjektInflacjaMobileKalorycznoscdiety
from meals.models import ProjektInflacjaMobileProduktywposilku
from meals.models import ProjektInflacjaMobileProduktyuproszczone
from meals.models import ProjektInflacjaMobilePosilkiwdiecie


class DietListSerializer(serializers.ModelSerializer):
	class Meta:
		model = ProjektInflacjaMobileDiety
		fields = ['id', 'dieta', 'opis_diety']


class DietMealIngredientSerializer(serializers.ModelSerializer):
	nazwa_produktu = serializers.CharField(source='nazwa_produktu.nazwa_produktu')
	miarka = serializers.CharField(source='miarka.nazwa_miarki')

	class Meta:
		model = ProjektInflacjaMobileProduktywposilku
		fields = ['nazwa_produktu', 'ilosc_produktu', 'miarka']


class DietMealListSerializer(serializers.ModelSerializer):
	nazwa_posilku = serializers.CharField(source='nazwa_posilku.nazwa_posilku')
	pora_posilku = serializers.CharField(source='pora_posilku.pora_posilku')
	dieta_id = serializers.IntegerField(source='kalorycznosc_diety.dieta_id')
	zdjecie_url = serializers.SerializerMethodField()
	czysta_kalorycznosc_diety = serializers.IntegerField(source='kalorycznosc_diety.kalorycznosc.czysta_kalorycznosc', read_only=True)
	skladniki = serializers.SerializerMethodField()
	cena_posilku = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, allow_null=True)
	brakujace_ceny_produktow = serializers.CharField(read_only=True, allow_null=True)
	ocena_uzytkownika_id = serializers.IntegerField(read_only=True, allow_null=True)
	ocena_uzytkownika = serializers.CharField(read_only=True, allow_null=True)
	czy_oceniony = serializers.SerializerMethodField()

	@staticmethod
	def _is_loopback_url(url):
		host = urlsplit(url).hostname or ''
		return host in {'localhost', '127.0.0.1', '::1'}

	def get_zdjecie_url(self, obj):
		obraz = getattr(obj.nazwa_posilku, 'obraz_bitowy', None)
		if not obraz:
			return None

		url = obraz.url
		request = self.context.get('request')
		if request is not None and (not settings.MEDIA_SERVER_URL or self._is_loopback_url(settings.MEDIA_SERVER_URL)):
			return request.build_absolute_uri(url)
		if settings.MEDIA_SERVER_URL:
			return f"{settings.MEDIA_SERVER_URL}{url}"
		if request is not None:
			return request.build_absolute_uri(url)
		return url

	def get_skladniki(self, obj):
		ingredients = obj.projektinflacjamobileproduktywposilku_set.all()
		return DietMealIngredientSerializer(ingredients, many=True).data

	def get_czy_oceniony(self, obj):
		return getattr(obj, 'ocena_uzytkownika_id', None) is not None

	class Meta:
		model = ProjektInflacjaMobilePosilkiwdiecie
		fields = [
			'id',
			'dieta_id',
			'czysta_kalorycznosc_diety',
			'nazwa_posilku',
			'zdjecie_url',
			'skladniki',
			'cena_posilku',
			'brakujace_ceny_produktow',
			'ocena_uzytkownika_id',
			'ocena_uzytkownika',
			'czy_oceniony',
			'pora_posilku',
			'czas_przygotowania',
			'kalorie',
			'bialko',
			'weglowodany',
			'tluszcze',
			'opis_posilku',
		]


class DietCalorieListSerializer(serializers.ModelSerializer):
	dieta_id = serializers.IntegerField(source='dieta.id')
	dieta = serializers.CharField(source='dieta.dieta')
	kalorycznosc_id = serializers.IntegerField(source='kalorycznosc.id')
	kalorycznosc = serializers.CharField(source='kalorycznosc.kalorycznosc')
	czysta_kalorycznosc = serializers.IntegerField(source='kalorycznosc.czysta_kalorycznosc')

	class Meta:
		model = ProjektInflacjaMobileKalorycznoscdiety
		fields = ['id', 'dieta_id', 'dieta', 'kalorycznosc_id', 'kalorycznosc', 'czysta_kalorycznosc']


class SimplifiedProductListSerializer(serializers.ModelSerializer):
	kategoria_produktu_id = serializers.IntegerField(source='kategoria_produktu.id', read_only=True)
	kategoria_produktu = serializers.CharField(source='kategoria_produktu.nazwa_kategorii', read_only=True)

	class Meta:
		model = ProjektInflacjaMobileProduktyuproszczone
		fields = [
			'id',
			'nazwa_produktu_uproszczonego',
			'kategoria_produktu_id',
			'kategoria_produktu',
			'kalorie',
			'bialko',
			'weglowodany',
			'tluszcze',
			'opis_produktu',
		]
