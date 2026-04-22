"""Warehouse serializers category."""

from rest_framework import serializers


class FamilyWarehouseProductSerializer(serializers.Serializer):
	produkt_id = serializers.IntegerField()
	nazwa_produktu = serializers.CharField()
	ilosc_produktu = serializers.FloatField()


class FamilyWarehouseUpdateProductSerializer(serializers.Serializer):
	produkt_id = serializers.IntegerField(min_value=1)
	ilosc_produktu = serializers.FloatField(min_value=0.0)


class FamilyWarehouseUpdateProductResponseSerializer(serializers.Serializer):
	CODE = serializers.CharField()
	detail = serializers.CharField()
	produkt_id = serializers.IntegerField()
	nazwa_produktu = serializers.CharField(allow_blank=True)
	ilosc_produktu = serializers.FloatField()


class FamilyWarehouseListResponseSerializer(serializers.Serializer):
	rodzina_id = serializers.IntegerField()
	liczba_pozycji = serializers.IntegerField()
	produkty = FamilyWarehouseProductSerializer(many=True)


class FamilyWarehouseClearResponseSerializer(serializers.Serializer):
	CODE = serializers.CharField()
	detail = serializers.CharField()
	deleted_entries = serializers.IntegerField()


class FamilyWarehouseMealCoverageResponseSerializer(serializers.Serializer):
	rodzina_id = serializers.IntegerField()
	total_planned_meals = serializers.IntegerField()
	covered_meals = serializers.IntegerField()
	uncovered_meals = serializers.IntegerField()
	coverage_percent = serializers.FloatField()


class FamilyWarehousePossibleMealSerializer(serializers.Serializer):
	posilek_w_diecie_id = serializers.IntegerField()
	nazwa_posilku = serializers.CharField()
	pora_posilku = serializers.CharField()
	czas_przygotowania = serializers.CharField()
	liczba_skladnikow = serializers.IntegerField()
	coverage_percent = serializers.FloatField()
	can_prepare = serializers.BooleanField()


class FamilyWarehousePossibleMealsResponseSerializer(serializers.Serializer):
	rodzina_id = serializers.IntegerField()
	liczba_mozliwych_posilkow = serializers.IntegerField()
	mozliwe_posilki = FamilyWarehousePossibleMealSerializer(many=True)
