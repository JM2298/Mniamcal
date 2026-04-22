from rest_framework.routers import DefaultRouter

from ..api_views.diet import DietCalorieViewSet, DietListViewSet, DietMealsViewSet, SimplifiedProductsViewSet

router = DefaultRouter()
router.register('diets', DietListViewSet, basename='diet-list')
router.register('diets/meals', DietMealsViewSet, basename='diet-meals-list')
router.register('diets/calories', DietCalorieViewSet, basename='diet-calories-list')
router.register('products/simplified', SimplifiedProductsViewSet, basename='simplified-products-list')



urlpatterns = router.urls
