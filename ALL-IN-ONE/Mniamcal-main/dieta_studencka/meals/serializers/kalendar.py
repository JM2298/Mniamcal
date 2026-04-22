"""Kalendar serializers category."""

from rest_framework import serializers


class FamilyPlannedMealCreateSerializer(serializers.Serializer):
	data = serializers.DateField()
	posilek_w_diecie_id = serializers.IntegerField(min_value=1)
	czy_zjedzone = serializers.BooleanField(required=False, default=False)


class FamilyPlannedMealMemberSerializer(serializers.Serializer):
	uzytkownik_id = serializers.IntegerField()
	uzytkownik_w_rodzinie_id = serializers.IntegerField()
	posilek_w_diecie_id = serializers.IntegerField()
	kalorycznosc_diety = serializers.IntegerField(allow_null=True)
	proporcja_kaloryczna = serializers.FloatField()


class FamilyPlannedMealResponseSerializer(serializers.Serializer):
	data = serializers.DateField()
	czy_zjedzone = serializers.BooleanField()
	pora_posilku = serializers.CharField()
	rodzina_id = serializers.IntegerField()
	liczba_czlonkow_rodziny = serializers.IntegerField()
	liczba_osob_przy_posilku = serializers.IntegerField()
	zaplanowane_posilki = FamilyPlannedMealMemberSerializer(many=True)


class FamilyMealPossibleRatingSerializer(serializers.Serializer):
	id = serializers.IntegerField()
	ocena = serializers.CharField()


class FamilyMealPossibleRatingsResponseSerializer(serializers.Serializer):
	count = serializers.IntegerField()
	oceny = FamilyMealPossibleRatingSerializer(many=True)


class FamilyPlannedMealMarkEatenSerializer(serializers.Serializer):
	planned_meal_id = serializers.IntegerField(min_value=1)
	ocena_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class FamilyPlannedMealMarkEatenResponseSerializer(serializers.Serializer):
	CODE = serializers.CharField()
	detail = serializers.CharField()
	marked_entries = serializers.IntegerField()
	consumed_products = serializers.IntegerField()
	meal_rating_saved = serializers.BooleanField(required=False)


class FamilyPlannedMealRemoveSerializer(serializers.Serializer):
	planned_meal_id = serializers.IntegerField(min_value=1)


class FamilyPlannedMealRemoveResponseSerializer(serializers.Serializer):
	CODE = serializers.CharField()
	detail = serializers.CharField()
	deleted_entries = serializers.IntegerField()
