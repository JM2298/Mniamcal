"""Settings serializers category."""

from rest_framework import serializers


class StoreCurrentPriceItemSerializer(serializers.Serializer):
	nazwa_produktu_uproszczonego_id = serializers.IntegerField(min_value=1)
	dokladna_nazwa_produktu = serializers.CharField(max_length=100)
	cena_produktu = serializers.DecimalField(max_digits=10, decimal_places=2)
	cena_produktu_za_kg = serializers.DecimalField(max_digits=10, decimal_places=2)
	producent = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
	opakowanie = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
	data_dodania = serializers.DateField()


class StoreCurrentPriceUpdateRequestSerializer(serializers.Serializer):
	sklep_id = serializers.IntegerField(min_value=1)
	produkty = StoreCurrentPriceItemSerializer(many=True, allow_empty=False)


class StoreCurrentPriceUpdateResponseSerializer(serializers.Serializer):
	CODE = serializers.CharField()
	detail = serializers.CharField()
	sklep_id = serializers.IntegerField()
	processed_products = serializers.IntegerField()
	created_current_prices = serializers.IntegerField()
	updated_current_prices = serializers.IntegerField()
	created_history_rows = serializers.IntegerField()
	meal_price_recalculation_status = serializers.CharField()
	meal_price_recalculation_task_id = serializers.CharField()
