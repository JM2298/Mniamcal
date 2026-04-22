# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from django.conf import settings


class AuthGroup(models.Model):
    name = models.CharField(unique=True, max_length=150)

    class Meta:
        managed = False
        db_table = 'auth_group'

    def __str__(self):
        return self.name


class AuthGroupPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)
    permission = models.ForeignKey('AuthPermission', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_group_permissions'
        unique_together = (('group', 'permission'),)

    def __str__(self):
        return f"{self.group} - {self.permission}"


class AuthPermission(models.Model):
    name = models.CharField(max_length=255)
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING)
    codename = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'auth_permission'
        unique_together = (('content_type', 'codename'),)

    def __str__(self):
        return self.name


class AuthUser(models.Model):
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.BooleanField()
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.BooleanField()
    is_active = models.BooleanField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'

    def __str__(self):
        return self.username


class AuthUserGroups(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_groups'
        unique_together = (('user', 'group'),)

    def __str__(self):
        return f"{self.user} - {self.group}"


class AuthUserUserPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    permission = models.ForeignKey(AuthPermission, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_user_permissions'
        unique_together = (('user', 'permission'),)

    def __str__(self):
        return f"{self.user} - {self.permission}"


class AuthtokenToken(models.Model):
    key = models.CharField(primary_key=True, max_length=40)
    created = models.DateTimeField()
    user = models.OneToOneField(AuthUser, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'authtoken_token'

    def __str__(self):
        return self.key


class DjangoAdminLog(models.Model):
    action_time = models.DateTimeField()
    object_id = models.TextField(blank=True, null=True)
    object_repr = models.CharField(max_length=200)
    action_flag = models.SmallIntegerField()
    change_message = models.TextField()
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'django_admin_log'

    def __str__(self):
        return f"{self.object_repr} - {self.action_time}"


class DjangoContentType(models.Model):
    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'django_content_type'
        unique_together = (('app_label', 'model'),)

    def __str__(self):
        return f"{self.app_label}.{self.model}"


class DjangoMigrations(models.Model):
    id = models.BigAutoField(primary_key=True)
    app = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    applied = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_migrations'

    def __str__(self):
        return f"{self.app} - {self.name}"


class DjangoSession(models.Model):
    session_key = models.CharField(primary_key=True, max_length=40)
    session_data = models.TextField()
    expire_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_session'

    def __str__(self):
        return self.session_key


class FcmDeviceToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='fcm_device_tokens')
    token = models.CharField(max_length=512, unique=True)
    platform = models.CharField(max_length=20, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'meals_fcm_device_tokens'

    def __str__(self):
        return f"{self.user_id}:{self.platform or 'unknown'}"


class FcmUserPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='fcm_preference')
    push_enabled = models.BooleanField(default=True)
    shopping_package_size_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'meals_fcm_user_preferences'

    def __str__(self):
        return (
            f"{self.user_id}:push={'on' if self.push_enabled else 'off'}"
            f":shopping_package_size={'on' if self.shopping_package_size_enabled else 'off'}"
        )


class ShoppingPackagePreference(models.Model):
    rodzina_id = models.PositiveIntegerField(db_index=True)
    nazwa_produktu_uproszczonego_id = models.PositiveIntegerField(db_index=True)
    wielkosc_opakowania = models.FloatField()
    jednostka_opakowania = models.CharField(max_length=2, choices=[('g', 'g'), ('ml', 'ml')])
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'meals_shopping_package_preferences'
        unique_together = (('rodzina_id', 'nazwa_produktu_uproszczonego_id'),)

    def __str__(self):
        return (
            f"{self.rodzina_id}:{self.nazwa_produktu_uproszczonego_id}="
            f"{self.wielkosc_opakowania}{self.jednostka_opakowania}"
        )


class ProjektInflacjaMobileAktualnecenyproduktowwdanymsklepie(models.Model):
    dokladna_nazwa_produktu = models.CharField(max_length=100)
    cena_produktu = models.DecimalField(max_digits=10, decimal_places=2)
    cena_produktu_za_kg = models.DecimalField(max_digits=10, decimal_places=2)
    producent = models.CharField(max_length=100)
    opakowanie = models.CharField(max_length=100)
    data_dodania = models.DateField()
    nazwa_produktu_uproszczonego = models.ForeignKey('ProjektInflacjaMobileProduktyuproszczone', models.DO_NOTHING)
    sklep = models.ForeignKey('ProjektInflacjaMobileSklepy', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_aktualnecenyproduktowwdanymsklepie'

    def __str__(self):
        return f"{self.dokladna_nazwa_produktu} - {self.cena_produktu} zł"


class ProjektInflacjaMobileCenacalegoposilku(models.Model):
    cena_calego_posilku = models.DecimalField(max_digits=10, decimal_places=2)
    data = models.DateField()
    posilek = models.ForeignKey('ProjektInflacjaMobilePosilkiwdiecie', models.DO_NOTHING)
    sklep = models.ForeignKey('ProjektInflacjaMobileSklepy', models.DO_NOTHING)
    brakujace_ceny_produktu = models.TextField()

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_cenacalegoposilku'

    def __str__(self):
        return f"{self.posilek} - {self.cena_calego_posilku} zł ({self.data})"


class ProjektInflacjaMobileDiety(models.Model):
    dieta = models.CharField(max_length=50)
    opis_diety = models.TextField()

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_diety'

    def __str__(self):
        return self.dieta


class ProjektInflacjaMobileHistoriacenproduktow(models.Model):
    dokladna_nazwa_produktu = models.CharField(max_length=100)
    cena_produktu = models.DecimalField(max_digits=10, decimal_places=2)
    cena_produktu_za_kg = models.DecimalField(max_digits=10, decimal_places=2)
    producent = models.CharField(max_length=100)
    opakowanie = models.CharField(max_length=100)
    data_dodania = models.DateField()
    nazwa_produktu_uproszczonego = models.ForeignKey('ProjektInflacjaMobileProduktyuproszczone', models.DO_NOTHING)
    sklep = models.ForeignKey('ProjektInflacjaMobileSklepy', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_historiacenproduktow'

    def __str__(self):
        return f"{self.dokladna_nazwa_produktu} - {self.data_dodania}"


class ProjektInflacjaMobileKalorycznosc(models.Model):
    kalorycznosc = models.CharField(max_length=20)
    czysta_kalorycznosc = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_kalorycznosc'

    def __str__(self):
        return self.kalorycznosc


class ProjektInflacjaMobileKalorycznoscdiety(models.Model):
    dieta = models.ForeignKey(ProjektInflacjaMobileDiety, models.DO_NOTHING)
    kalorycznosc = models.ForeignKey(ProjektInflacjaMobileKalorycznosc, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_kalorycznoscdiety'

    def __str__(self):
        return f"{self.dieta} - {self.kalorycznosc}"


class ProjektInflacjaMobileKategorieproduktow(models.Model):
    nazwa_kategorii = models.CharField(max_length=50)

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_kategorieproduktow'

    def __str__(self):
        return self.nazwa_kategorii


class ProjektInflacjaMobileKolejnosckategoriiwsklepie(models.Model):
    kolejnosc = models.IntegerField()
    kategoria_produktu = models.ForeignKey(ProjektInflacjaMobileKategorieproduktow, models.DO_NOTHING)
    sklep = models.ForeignKey('ProjektInflacjaMobileSklepy', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_kolejnosckategoriiwsklepie'

    def __str__(self):
        return f"{self.sklep} - {self.kategoria_produktu} ({self.kolejnosc})"


class ProjektInflacjaMobileListazakupowrodziny(models.Model):
    nazwa_listy_zakupow = models.CharField(unique=True, max_length=100)
    data_od = models.DateField()
    data_do = models.DateField()
    rodzina = models.ForeignKey('ProjektInflacjaMobileRodziny', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_listazakupowrodziny'

    def __str__(self):
        return self.nazwa_listy_zakupow


class ProjektInflacjaMobileMagazynwszystkichuzytkownikowrodziny(models.Model):
    ilosc_produktu = models.FloatField()
    rodzina = models.ForeignKey('ProjektInflacjaMobileRodziny', models.DO_NOTHING)
    nazwa_produktu_uproszczonego = models.ForeignKey('ProjektInflacjaMobileProduktyuproszczone', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_magazynwszystkichuzytkownikowrodziny'

    def __str__(self):
        return f"{self.nazwa_produktu_uproszczonego} - {self.ilosc_produktu}"


class ProjektInflacjaMobileMiarki(models.Model):
    nazwa_miarki = models.CharField(max_length=50)

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_miarki'

    def __str__(self):
        return self.nazwa_miarki


class ProjektInflacjaMobileMozliweocenyposilku(models.Model):
    ocena = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_mozliweocenyposilku'

    def __str__(self):
        return self.ocena


class ProjektInflacjaMobileOcenaposilkuprzezuzytkownika(models.Model):
    data_oceny = models.DateField()
    ocena = models.ForeignKey(ProjektInflacjaMobileMozliweocenyposilku, models.DO_NOTHING)
    posilek = models.ForeignKey('ProjektInflacjaMobilePosilkiwdiecie', models.DO_NOTHING)
    uzytkownik = models.ForeignKey(AuthUser, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_ocenaposilkuprzezuzytkownika'

    def __str__(self):
        return f"{self.uzytkownik} - {self.posilek} ({self.ocena})"


class ProjektInflacjaMobilePoraposilku(models.Model):
    pora_posilku = models.CharField(max_length=20)

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_poraposilku'

    def __str__(self):
        return self.pora_posilku


class ProjektInflacjaMobilePosilki(models.Model):
    nazwa_posilku = models.CharField(max_length=100)
    obraz_bitowy = models.FileField(upload_to='posilki/', blank=True, null=True)
    czy_wlasny = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_posilki'

    def __str__(self):
        return self.nazwa_posilku


class ProjektInflacjaMobilePosilkiwdiecie(models.Model):
    kalorie = models.IntegerField()
    bialko = models.IntegerField()
    weglowodany = models.IntegerField()
    tluszcze = models.IntegerField()
    opis_posilku = models.TextField()
    kalorycznosc_diety = models.ForeignKey(ProjektInflacjaMobileKalorycznoscdiety, models.DO_NOTHING)
    nazwa_posilku = models.ForeignKey(ProjektInflacjaMobilePosilki, models.DO_NOTHING)
    pora_posilku = models.ForeignKey(ProjektInflacjaMobilePoraposilku, models.DO_NOTHING)
    czas_przygotowania = models.CharField(max_length=20)

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_posilkiwdiecie'

    def __str__(self):
        return f"{self.nazwa_posilku} - {self.pora_posilku}"


class ProjektInflacjaMobileProdukty(models.Model):
    nazwa_produktu = models.CharField(max_length=100)
    nazwa_produktu_uproszczonego = models.ForeignKey('ProjektInflacjaMobileProduktyuproszczone', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_produkty'

    def __str__(self):
        return self.nazwa_produktu


class ProjektInflacjaMobileProduktynalisciezakupowrodziny(models.Model):
    ilosc_produktu_do_kupienia = models.CharField(max_length=100)
    kolejnosc_kategorii_w_sklepie = models.ForeignKey(ProjektInflacjaMobileKolejnosckategoriiwsklepie, models.DO_NOTHING)
    lista_zakupow = models.ForeignKey(ProjektInflacjaMobileListazakupowrodziny, models.DO_NOTHING)
    nazwa_produktu = models.ForeignKey(ProjektInflacjaMobileProdukty, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_produktynalisciezakupowrodziny'

    def __str__(self):
        return f"{self.nazwa_produktu} - {self.ilosc_produktu_do_kupienia}"


class ProjektInflacjaMobileProduktyuproszczone(models.Model):
    nazwa_produktu_uproszczonego = models.CharField(max_length=100)
    kalorie = models.IntegerField()
    bialko = models.IntegerField()
    weglowodany = models.IntegerField()
    tluszcze = models.IntegerField()
    opis_produktu = models.TextField()
    kategoria_produktu = models.ForeignKey(ProjektInflacjaMobileKategorieproduktow, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_produktyuproszczone'

    def __str__(self):
        return self.nazwa_produktu_uproszczonego


class ProjektInflacjaMobileProduktywposilku(models.Model):
    ilosc_produktu = models.CharField(max_length=20)
    czysta_ilosc_produktu = models.IntegerField()
    nazwa_posilku = models.ForeignKey(ProjektInflacjaMobilePosilkiwdiecie, models.DO_NOTHING)
    nazwa_produktu = models.ForeignKey(ProjektInflacjaMobileProdukty, models.DO_NOTHING)
    miarka = models.ForeignKey('ProjektInflacjaMobileWszystkiemiarki', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_produktywposilku'

    def __str__(self):
        return f"{self.nazwa_produktu} - {self.ilosc_produktu}"


class ProjektInflacjaMobileRodziny(models.Model):
    rodzina = models.CharField(max_length=50)
    pin = models.CharField(max_length=4)
    zalozyciel_rodziny = models.OneToOneField(AuthUser, models.DO_NOTHING)
    sklep = models.ForeignKey('ProjektInflacjaMobileSklepy', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_rodziny'

    def __str__(self):
        return self.rodzina


class ProjektInflacjaMobileSklepy(models.Model):
    nazwa_sklepu = models.CharField(max_length=50)

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_sklepy'

    def __str__(self):
        return self.nazwa_sklepu


class ProjektInflacjaMobileUzytkownicywrodzinach(models.Model):
    rodzina = models.ForeignKey(ProjektInflacjaMobileRodziny, models.DO_NOTHING)
    uzytkownik = models.ForeignKey(AuthUser, models.DO_NOTHING)
    kalorycznosc_diety = models.ForeignKey(ProjektInflacjaMobileKalorycznoscdiety, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_uzytkownicywrodzinach'

    def __str__(self):
        return f"{self.uzytkownik} - {self.rodzina}"


class ProjektInflacjaMobileWszystkiemiarki(models.Model):
    nazwa_miarki = models.CharField(max_length=50)

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_wszystkiemiarki'

    def __str__(self):
        return self.nazwa_miarki


class ProjektInflacjaMobileZaplanowaneposilkirodziny(models.Model):
    data = models.DateField()
    czy_zjedzone = models.BooleanField()
    posilki_w_diecie = models.ForeignKey(ProjektInflacjaMobilePosilkiwdiecie, models.DO_NOTHING)
    rodzina = models.ForeignKey(ProjektInflacjaMobileRodziny, models.DO_NOTHING)
    uzytkownik_w_rodzinie = models.ForeignKey(ProjektInflacjaMobileUzytkownicywrodzinach, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'projekt_inflacja_mobile_zaplanowaneposilkirodziny'

    def __str__(self):
        return f"{self.rodzina} - {self.posilki_w_diecie} ({self.data})"


def _shorten_verbose_names():
    """
    Keep DB table names intact, but clean labels in Django Admin.
    Apply it to all mirrored tables for consistent naming.
    """
    custom_labels = {
        "projekt_inflacja_mobile_aktualnecenyproduktowwdanymsklepie": "aktualne ceny produktow w danym sklepie",
        "projekt_inflacja_mobile_cenacalegoposilku": "cena calego posilku",
        "projekt_inflacja_mobile_diety": "diety",
        "projekt_inflacja_mobile_historiacenproduktow": "historia cen produktow",
        "projekt_inflacja_mobile_kalorycznosc": "kalorycznosc",
        "projekt_inflacja_mobile_kalorycznoscdiety": "kalorycznosc diety",
        "projekt_inflacja_mobile_kategorieproduktow": "kategorie produktow",
        "projekt_inflacja_mobile_kolejnosckategoriiwsklepie": "kolejnosc kategorii w sklepie",
        "projekt_inflacja_mobile_listazakupowrodziny": "lista zakupow rodziny",
        "projekt_inflacja_mobile_magazynwszystkichuzytkownikowrodziny": "magazyn wszystkich uzytkownikow rodziny",
        "projekt_inflacja_mobile_miarki": "miarki",
        "projekt_inflacja_mobile_mozliweocenyposilku": "mozliwe oceny posilku",
        "projekt_inflacja_mobile_ocenaposilkuprzezuzytkownika": "ocena posilku przez uzytkownika",
        "projekt_inflacja_mobile_poraposilku": "pora posilku",
        "projekt_inflacja_mobile_posilki": "posilki",
        "projekt_inflacja_mobile_posilkiwdiecie": "posilki w diecie",
        "projekt_inflacja_mobile_produkty": "produkty",
        "projekt_inflacja_mobile_produktynalisciezakupowrodziny": "produkty na liscie zakupow rodziny",
        "projekt_inflacja_mobile_produktyuproszczone": "produkty uproszczone",
        "projekt_inflacja_mobile_produktywposilku": "produkty w posilku",
        "projekt_inflacja_mobile_rodziny": "rodziny",
        "projekt_inflacja_mobile_sklepy": "sklepy",
        "projekt_inflacja_mobile_uzytkownicywrodzinach": "uzytkownicy w rodzinach",
        "projekt_inflacja_mobile_wszystkiemiarki": "wszystkie miarki",
        "projekt_inflacja_mobile_zaplanowaneposilkirodziny": "zaplanowane posilki rodziny",
    }

    for value in globals().values():
        if not isinstance(value, type):
            continue
        if not issubclass(value, models.Model):
            continue
        opts = value._meta
        short_label = custom_labels.get(opts.db_table, opts.db_table.replace("_", " "))
        opts.verbose_name = short_label
        opts.verbose_name_plural = short_label


_shorten_verbose_names()
