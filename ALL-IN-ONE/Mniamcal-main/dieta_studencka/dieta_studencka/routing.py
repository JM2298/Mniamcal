from django.urls import path

from meals.consumers import FamilyUpdatesConsumer, ShoppingListLiveFromCalendarConsumer


websocket_urlpatterns = [
    path('ws/family/updates/', FamilyUpdatesConsumer.as_asgi()),
    path('ws/shopping-lists/live-from-calendar/', ShoppingListLiveFromCalendarConsumer.as_asgi()),
]
