from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from meals.models import FcmDeviceToken, FcmUserPreference


User = get_user_model()


class AccountPreferenceApiTests(APITestCase):
    preferences_url = '/api/fcm/devices/preferences/'

    def setUp(self):
        self.user = User.objects.create_user(
            username='pref_user',
            email='pref@example.com',
            password='SilneHaslo123',
        )
        self.client.force_authenticate(user=self.user)

    def test_get_preferences_returns_defaults_when_record_missing(self):
        response = self.client.get(self.preferences_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('CODE'), 'FCM_PREFERENCE_LOADED')
        self.assertTrue(response.data.get('push_enabled'))
        self.assertTrue(response.data.get('shopping_package_size_enabled'))

    def test_post_preferences_updates_only_shopping_package_size_flag(self):
        response = self.client.post(
            self.preferences_url,
            {'shopping_package_size_enabled': False},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('CODE'), 'FCM_PREFERENCE_UPDATED')
        self.assertTrue(response.data.get('push_enabled'))
        self.assertFalse(response.data.get('shopping_package_size_enabled'))

        preference = FcmUserPreference.objects.get(user=self.user)
        self.assertTrue(preference.push_enabled)
        self.assertFalse(preference.shopping_package_size_enabled)

    def test_post_preferences_updates_both_flags_and_disables_device_tokens(self):
        FcmDeviceToken.objects.create(
            user=self.user,
            token='pref-token-1',
            platform='android',
            is_active=True,
        )

        response = self.client.post(
            self.preferences_url,
            {'push_enabled': False, 'shopping_package_size_enabled': False},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data.get('push_enabled'))
        self.assertFalse(response.data.get('shopping_package_size_enabled'))

        preference = FcmUserPreference.objects.get(user=self.user)
        self.assertFalse(preference.push_enabled)
        self.assertFalse(preference.shopping_package_size_enabled)

        device = FcmDeviceToken.objects.get(token='pref-token-1')
        self.assertFalse(device.is_active)
