import logging
from collections import defaultdict
import datetime as dt
import json
from decimal import Decimal, ROUND_HALF_UP

from celery import shared_task
from django.db.utils import OperationalError, ProgrammingError

from meals.models import (
    FcmDeviceToken,
    ProjektInflacjaMobileAktualnecenyproduktowwdanymsklepie,
    ProjektInflacjaMobileCenacalegoposilku,
    ProjektInflacjaMobileProduktywposilku,
)
from meals.services.fcm import send_push_notification

logger = logging.getLogger(__name__)


@shared_task(name='meals.tasks.heartbeat_task')
def heartbeat_task():
    logger.info('Celery beat heartbeat task executed.')
    return 'ok'


def _resolve_missing_product_name(ingredient):
    product = getattr(ingredient, 'nazwa_produktu', None)
    simplified = getattr(product, 'nazwa_produktu_uproszczonego', None)
    simplified_name = getattr(simplified, 'nazwa_produktu_uproszczonego', '')
    if simplified_name:
        return simplified_name

    product_name = getattr(product, 'nazwa_produktu', '')
    if product_name:
        return product_name

    return 'Nieznany produkt'


def recalculate_meal_prices_for_store(sklep_id, data_wyliczenia):
    prices_qs = (
        ProjektInflacjaMobileAktualnecenyproduktowwdanymsklepie.objects
        .filter(sklep_id=sklep_id)
        .order_by('nazwa_produktu_uproszczonego_id', '-data_dodania', '-id')
    )

    latest_price_per_simplified_id = {}
    for price_row in prices_qs:
        simplified_product_id = price_row.nazwa_produktu_uproszczonego_id
        if simplified_product_id in latest_price_per_simplified_id:
            continue
        price_per_kg = Decimal(str(price_row.cena_produktu_za_kg or 0))
        latest_price_per_simplified_id[simplified_product_id] = price_per_kg

    ingredients_qs = (
        ProjektInflacjaMobileProduktywposilku.objects
        .select_related('nazwa_produktu__nazwa_produktu_uproszczonego')
        .order_by('nazwa_posilku_id', 'id')
    )

    ingredients_by_meal_id = defaultdict(list)
    for ingredient in ingredients_qs:
        ingredients_by_meal_id[ingredient.nazwa_posilku_id].append(ingredient)

    updated_meal_prices = 0
    meals_with_missing_products = 0

    for meal_id, meal_ingredients in ingredients_by_meal_id.items():
        total_cost = Decimal('0.00')
        missing_products = set()

        for ingredient in meal_ingredients:
            product = getattr(ingredient, 'nazwa_produktu', None)
            simplified_product_id = getattr(product, 'nazwa_produktu_uproszczonego_id', None)

            try:
                grams = Decimal(str(getattr(ingredient, 'czysta_ilosc_produktu', 0) or 0))
            except Exception:
                grams = Decimal('0')

            price_per_kg = latest_price_per_simplified_id.get(simplified_product_id)
            if price_per_kg is None or price_per_kg <= 0:
                missing_products.add(_resolve_missing_product_name(ingredient))
                continue

            total_cost += (grams / Decimal('1000')) * price_per_kg

        total_cost = total_cost.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        missing_products_text = json.dumps(sorted(missing_products), ensure_ascii=False)

        ProjektInflacjaMobileCenacalegoposilku.objects.update_or_create(
            sklep_id=sklep_id,
            posilek_id=meal_id,
            data=data_wyliczenia,
            defaults={
                'cena_calego_posilku': total_cost,
                'brakujace_ceny_produktu': missing_products_text,
            },
        )
        updated_meal_prices += 1
        if missing_products:
            meals_with_missing_products += 1

    return {
        'updated_meal_prices': updated_meal_prices,
        'meals_with_missing_products': meals_with_missing_products,
    }


def send_meal_price_recalculated_push_to_all_users(sklep_id, data_wyliczenia, stats):
    tokens = list(
        FcmDeviceToken.objects
        .filter(is_active=True)
        .values_list('token', flat=True)
    )

    if not tokens:
        logger.info('No active FCM tokens found for meal price recalculation broadcast.')
        return {
            'push_tokens_total': 0,
            'push_sent': 0,
            'push_failed': 0,
        }

    title = 'Ceny posilkow zostaly przeliczone'
    body = f'Zaktualizowano ceny posilkow dla sklepu {sklep_id}.'
    data = {
        'type': 'meal_prices_recalculated',
        'sklep_id': sklep_id,
        'data_wyliczenia': data_wyliczenia.isoformat(),
        'updated_meal_prices': stats['updated_meal_prices'],
        'meals_with_missing_products': stats['meals_with_missing_products'],
    }

    sent = 0
    failed = 0
    for token in tokens:
        try:
            send_push_notification(token=token, title=title, body=body, data=data)
            sent += 1
        except Exception:
            failed += 1
            logger.exception('Failed to send meal price recalculation push for token=%s', token)

    return {
        'push_tokens_total': len(tokens),
        'push_sent': sent,
        'push_failed': failed,
    }


@shared_task(name='meals.tasks.recalculate_meal_prices_for_store_task')
def recalculate_meal_prices_for_store_task(sklep_id, data_wyliczenia):
    if isinstance(data_wyliczenia, str):
        data_wyliczenia = dt.date.fromisoformat(data_wyliczenia)

    try:
        stats = recalculate_meal_prices_for_store(sklep_id=sklep_id, data_wyliczenia=data_wyliczenia)
    except (ProgrammingError, OperationalError):
        logger.exception('Meal price recalculation failed for sklep_id=%s.', sklep_id)
        raise

    push_stats = send_meal_price_recalculated_push_to_all_users(
        sklep_id=sklep_id,
        data_wyliczenia=data_wyliczenia,
        stats=stats,
    )

    logger.info(
        'Meal prices recalculated for sklep_id=%s, date=%s, updated=%s, missing=%s, push_total=%s, push_sent=%s, push_failed=%s',
        sklep_id,
        data_wyliczenia,
        stats['updated_meal_prices'],
        stats['meals_with_missing_products'],
        push_stats['push_tokens_total'],
        push_stats['push_sent'],
        push_stats['push_failed'],
    )
    return {
        **stats,
        **push_stats,
    }
