"""Shoping list serializers category."""

from rest_framework import serializers


class FamilyShoppingListCreateFromCalendarSerializer(serializers.Serializer):
	data_od = serializers.DateField()
	data_do = serializers.DateField()
	nazwa_listy_zakupow = serializers.CharField(required=False, allow_blank=True, max_length=100)

	def validate(self, attrs):
		if attrs['data_do'] < attrs['data_od']:
			raise serializers.ValidationError({'data_do': 'data_do nie moze byc wczesniejsza niz data_od.'})
		return attrs


class FamilyShoppingListProductSerializer(serializers.Serializer):
	produkt_id = serializers.IntegerField()
	nazwa_produktu = serializers.CharField()
	ilosc_produktu_do_kupienia = serializers.CharField()
	kolejnosc_kategorii = serializers.IntegerField(allow_null=True)
	kategoria_nazwa = serializers.CharField(allow_null=True, required=False)
	ostatnia_wielkosc_opakowania = serializers.FloatField(allow_null=True, required=False)
	jednostka_ostatniego_opakowania = serializers.ChoiceField(choices=['g', 'ml'], allow_null=True, required=False)


class FamilyShoppingListCreateFromCalendarResponseSerializer(serializers.Serializer):
	lista_zakupow_id = serializers.IntegerField()
	nazwa_listy_zakupow = serializers.CharField()
	rodzina_id = serializers.IntegerField()
	data_od = serializers.DateField()
	data_do = serializers.DateField()
	liczba_zaplanowanych_posilkow = serializers.IntegerField()
	liczba_pozycji_na_liscie = serializers.IntegerField()


class FamilyShoppingListSummarySerializer(serializers.Serializer):
	id = serializers.IntegerField()
	nazwa_listy_zakupow = serializers.CharField()
	data_od = serializers.DateField()
	data_do = serializers.DateField()
	liczba_pozycji_na_liscie = serializers.IntegerField()


class FamilyShoppingListDeleteResponseSerializer(serializers.Serializer):
	CODE = serializers.CharField()
	detail = serializers.CharField()
	shopping_list_id = serializers.IntegerField()
	deleted_products = serializers.IntegerField()


class FamilyShoppingListReadProductSerializer(serializers.Serializer):
	produkt_id = serializers.IntegerField()
	nazwa_produktu = serializers.CharField()
	ilosc_produktu_do_kupienia = serializers.CharField()
	kolejnosc_kategorii = serializers.IntegerField(allow_null=True)
	kategoria_nazwa = serializers.CharField(allow_null=True, required=False)
	ostatnia_wielkosc_opakowania = serializers.FloatField(allow_null=True, required=False)
	jednostka_ostatniego_opakowania = serializers.ChoiceField(choices=['g', 'ml'], allow_null=True, required=False)


class FamilyShoppingListReadDetailSerializer(serializers.Serializer):
	id = serializers.IntegerField()
	nazwa_listy_zakupow = serializers.CharField()
	rodzina_id = serializers.IntegerField()
	data_od = serializers.DateField()
	data_do = serializers.DateField()
	liczba_pozycji_na_liscie = serializers.IntegerField()
	produkty = FamilyShoppingListReadProductSerializer(many=True)


class FamilyShoppingListLiveFromCalendarQuerySerializer(serializers.Serializer):
	shopping_list_id = serializers.IntegerField(min_value=1)


class FamilyShoppingListLiveFromCalendarResponseSerializer(serializers.Serializer):
	rodzina_id = serializers.IntegerField()
	data_od = serializers.DateField()
	data_do = serializers.DateField()
	liczba_zaplanowanych_posilkow = serializers.IntegerField()
	liczba_pozycji_na_liscie = serializers.IntegerField()
	produkty = FamilyShoppingListProductSerializer(many=True)


class FamilyShoppingListMarkBoughtSerializer(serializers.Serializer):
	shopping_list_id = serializers.IntegerField(min_value=1)
	produkt_id = serializers.IntegerField(min_value=1)
	wielkosc_opakowania = serializers.FloatField(required=False, min_value=0.01)
	jednostka_opakowania = serializers.ChoiceField(required=False, choices=['g', 'ml'])

	def validate(self, attrs):
		has_package_size = attrs.get('wielkosc_opakowania') is not None
		has_package_unit = attrs.get('jednostka_opakowania') is not None
		if has_package_size != has_package_unit:
			raise serializers.ValidationError(
				{'detail': 'Pola wielkosc_opakowania i jednostka_opakowania musza byc przekazane razem.'}
			)
		return attrs


class FamilyShoppingListMarkBoughtResponseSerializer(serializers.Serializer):
	shopping_list_id = serializers.IntegerField()
	produkt_id = serializers.IntegerField()
	ilosc_dodana_do_magazynu = serializers.FloatField()
	jednostka_dodanej_ilosci = serializers.ChoiceField(choices=['g', 'ml'])
