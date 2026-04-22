from .account import urlpatterns as account_urlpatterns
from .diet import urlpatterns as diet_urlpatterns
from .family import urlpatterns as family_urlpatterns
from .kalendar import urlpatterns as kalendar_urlpatterns
from .settings import urlpatterns as settings_urlpatterns
from .shoping_list import urlpatterns as shoping_list_urlpatterns
from .warehouse import urlpatterns as warehouse_urlpatterns

urlpatterns = [
    *account_urlpatterns,
    *family_urlpatterns,
    *diet_urlpatterns,
    *kalendar_urlpatterns,
    *shoping_list_urlpatterns,
    *warehouse_urlpatterns,
    *settings_urlpatterns,
]
