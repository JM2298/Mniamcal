from django.apps import apps
from django.contrib import admin
from django.contrib.admin.sites import AlreadyRegistered
from django.db import models
from django.utils.html import format_html

from .models import ProjektInflacjaMobilePosilki


SYSTEM_DB_TABLE_PREFIXES = ("auth_", "authtoken_", "django_")


class BetterModelAdmin(admin.ModelAdmin):
    list_per_page = 50

    def get_list_display(self, request):
        model_fields = list(self.model._meta.fields)
        pk_name = self.model._meta.pk.name if self.model._meta.pk else None
        text_fields = [
            field.name
            for field in model_fields
            if isinstance(field, (models.CharField, models.TextField))
        ]

        ordered = []
        if pk_name:
            ordered.append(pk_name)

        for field_name in text_fields:
            if field_name not in ordered:
                ordered.append(field_name)

        for field in model_fields:
            if field.name not in ordered:
                ordered.append(field.name)

        return tuple(ordered[:5] or ["__str__"])

    def get_search_fields(self, request):
        search_fields = [
            field.name
            for field in self.model._meta.fields
            if isinstance(field, (models.CharField, models.TextField))
        ]
        return tuple(search_fields[:8])

    def get_list_filter(self, request):
        filter_fields = [
            field.name
            for field in self.model._meta.fields
            if isinstance(field, (models.BooleanField, models.DateField, models.DateTimeField))
        ]
        return tuple(filter_fields[:5])


def _should_register_model(model):
    """
    Hide framework/system tables imported via inspectdb.
    """
    db_table = model._meta.db_table
    return not db_table.startswith(SYSTEM_DB_TABLE_PREFIXES)


for model in apps.get_app_config("meals").get_models():
    if model is ProjektInflacjaMobilePosilki:
        continue
    if not _should_register_model(model):
        continue

    try:
        admin.site.register(model, BetterModelAdmin)
    except AlreadyRegistered:
        pass


@admin.register(ProjektInflacjaMobilePosilki)
class PosilkiAdmin(BetterModelAdmin):
    readonly_fields = ("obraz_podglad", "obraz_link")

    def get_fields(self, request, obj=None):
        return ("nazwa_posilku", "obraz_bitowy", "obraz_podglad", "obraz_link", "czy_wlasny")

    def obraz_podglad(self, obj):
        if obj and obj.obraz_bitowy:
            try:
                return format_html(
                    '<img src="{}" alt="podglad" style="max-height: 150px; border: 1px solid #ddd;" />',
                    obj.obraz_bitowy.url,
                )
            except ValueError:
                return "Brak podgladu"
        return "Brak obrazu"

    obraz_podglad.short_description = "Podglad"

    def obraz_link(self, obj):
        if obj and obj.obraz_bitowy:
            try:
                return format_html('<a href="{}" target="_blank">{}</a>', obj.obraz_bitowy.url, obj.obraz_bitowy.name)
            except ValueError:
                return "-"
        return "-"

    obraz_link.short_description = "Link do pliku"
