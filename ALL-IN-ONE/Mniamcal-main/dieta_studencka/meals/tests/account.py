from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase


User = get_user_model()


class AccountAuthApiTests(APITestCase):
	register_url = '/api/auth/register/'
	login_url = '/api/auth/login/'
	auth_me_url = '/api/auth/me/'
	auth_me_delete_url = '/api/auth/me/delete/'
	auth_me_diet_url = '/api/auth/me/diet/'
	token_refresh_url = '/api/auth/token/refresh/'
	firebase_login_url = '/api/auth/login/firebase/'
	google_login_url = '/api/auth/login/google/'
	fcm_device_url = '/api/fcm/devices/'
	fcm_send_url = '/api/fcm/send/'

	def test_auth_me_delete_requires_authentication(self):
		response = self.client.post(self.auth_me_delete_url, {}, format='json')

		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_auth_me_delete_removes_authenticated_user(self):
		user = User.objects.create_user(
			username='delete_me',
			email='delete_me@example.com',
			password='SilneHaslo123',
		)
		self.client.force_authenticate(user=user)

		response = self.client.post(self.auth_me_delete_url, {}, format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data.get('CODE'), 'ACCOUNT_DELETED')
		self.assertFalse(User.objects.filter(id=user.id).exists())

	def test_auth_me_returns_extended_payload_for_authenticated_user(self):
		user = User.objects.create_user(username='profil_user', email='profil@example.com', password='SilneHaslo123')
		self.client.force_authenticate(user=user)

		response = self.client.get(self.auth_me_url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data.get('id'), user.id)
		self.assertIn('dieta_id', response.data)
		self.assertIn('kalorycznosc_diety_id', response.data)

	def test_auth_me_diet_requires_authentication(self):
		response = self.client.post(self.auth_me_diet_url, {'kalorycznosc_diety_id': 1}, format='json')

		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_auth_me_diet_validates_payload(self):
		user = User.objects.create_user(username='diet_user', email='diet@example.com', password='SilneHaslo123')
		self.client.force_authenticate(user=user)

		response = self.client.post(self.auth_me_diet_url, {'kalorycznosc_diety_id': 0}, format='json')

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(response.data.get('CODE'), 'VALIDATION_ERROR')

	def test_register_success(self):
		payload = {
			'username': 'nowy_uzytkownik',
			'first_name': 'Nowy',
			'email': 'nowy@example.com',
			'password': 'BezpieczneHaslo123',
		}

		response = self.client.post(self.register_url, payload, format='json')

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data.get('CODE'), 'REGISTER_SUCCESS')
		self.assertEqual(response.data.get('detail'), 'Rejestracja zakonczona sukcesem.')
		self.assertIn('access', response.data)
		self.assertIn('refresh', response.data)
		self.assertTrue(User.objects.filter(username='nowy_uzytkownik').exists())
		self.assertEqual(User.objects.get(username='nowy_uzytkownik').first_name, 'Nowy')

	def test_register_existing_user_returns_code(self):
		User.objects.create_user(username='istniejacy', email='a@a.pl', password='SilneHaslo123')
		payload = {
			'username': 'istniejacy',
			'first_name': 'Inny',
			'email': 'inne@example.com',
			'password': 'InneSilneHaslo123',
		}

		response = self.client.post(self.register_url, payload, format='json')

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(response.data.get('CODE'), 'USER_ALREADY_EXISTS')

	def test_login_success(self):
		User.objects.create_user(username='jan', email='jan@example.com', password='MojeHaslo123')

		response = self.client.post(
			self.login_url,
			{'username': 'jan', 'password': 'MojeHaslo123'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data.get('CODE'), 'LOGIN_SUCCESS')
		self.assertEqual(response.data.get('detail'), 'Logowanie poprawne.')
		self.assertIn('access', response.data)
		self.assertIn('refresh', response.data)

	def test_login_invalid_credentials_returns_code(self):
		User.objects.create_user(username='ania', email='ania@example.com', password='BardzoSilne123')

		response = self.client.post(
			self.login_url,
			{'username': 'ania', 'password': 'zlehaslo'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
		self.assertEqual(response.data.get('CODE'), 'INVALID_CREDENTIALS')

	def test_token_refresh_returns_new_access_token(self):
		User.objects.create_user(username='refresh_user', email='refresh@example.com', password='SilneHaslo123')

		login_response = self.client.post(
			self.login_url,
			{'username': 'refresh_user', 'password': 'SilneHaslo123'},
			format='json',
		)

		self.assertEqual(login_response.status_code, status.HTTP_200_OK)
		refresh = login_response.data.get('refresh')
		self.assertTrue(refresh)

		refresh_response = self.client.post(
			self.token_refresh_url,
			{'refresh': refresh},
			format='json',
		)

		self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
		self.assertIn('access', refresh_response.data)

	def test_register_validation_error_returns_validation_code(self):
		payload = {
			'username': 'za_krotkie_haslo',
			'first_name': 'Test',
			'email': 'test@example.com',
			'password': '123',
		}

		response = self.client.post(self.register_url, payload, format='json')

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(response.data.get('CODE'), 'VALIDATION_ERROR')
		self.assertIn('errors', response.data)

	def test_google_oauth_login_creates_user_and_returns_tokens(self):
		from unittest.mock import patch

		with patch('meals.api_views.account.verify_firebase_id_token') as mocked_verify:
			mocked_verify.return_value = {
				'email': 'google.user@example.com',
				'name': 'Google User',
				'given_name': 'Google',
				'family_name': 'User',
			}

			response = self.client.post(self.google_login_url, {'id_token': 'fake-token'}, format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn(response.data.get('CODE'), {'OAUTH_REGISTER_SUCCESS', 'OAUTH_LOGIN_SUCCESS'})
		self.assertIn('access', response.data)
		self.assertIn('refresh', response.data)
		self.assertTrue(User.objects.filter(email='google.user@example.com').exists())

	def test_firebase_login_alias_creates_user_and_returns_tokens(self):
		from unittest.mock import patch

		with patch('meals.api_views.account.verify_firebase_id_token') as mocked_verify:
			mocked_verify.return_value = {
				'email': 'firebase.user@example.com',
				'name': 'Firebase User',
				'given_name': 'Firebase',
				'family_name': 'User',
			}

			response = self.client.post(self.firebase_login_url, {'id_token': 'fake-token'}, format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn(response.data.get('CODE'), {'OAUTH_REGISTER_SUCCESS', 'OAUTH_LOGIN_SUCCESS'})
		self.assertIn('access', response.data)
		self.assertIn('refresh', response.data)
		self.assertTrue(User.objects.filter(email='firebase.user@example.com').exists())

	def test_firebase_login_returns_configuration_error_when_backend_not_configured(self):
		from unittest.mock import patch

		from meals.services import FirebaseConfigurationError

		with patch(
			'meals.api_views.account.verify_firebase_id_token',
			side_effect=FirebaseConfigurationError('Brak konfiguracji Firebase.'),
		):
			response = self.client.post(self.firebase_login_url, {'id_token': 'fake-token'}, format='json')

		self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
		self.assertEqual(response.data.get('CODE'), 'FIREBASE_NOT_CONFIGURED')

	def test_fcm_register_requires_authentication(self):
		response = self.client.post(self.fcm_device_url, {'token': 'abc123'}, format='json')
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_fcm_register_and_send_success(self):
		from unittest.mock import patch

		user = User.objects.create_user(username='push_user', email='push@example.com', password='SilneHaslo123')
		self.client.force_authenticate(user=user)

		register_response = self.client.post(
			self.fcm_device_url,
			{'token': 'fcm_token_1', 'platform': 'android'},
			format='json',
		)
		self.assertEqual(register_response.status_code, status.HTTP_200_OK)

		with patch('meals.api_views.account.send_push_notification') as mocked_send:
			mocked_send.return_value = 'msg-id-1'
			send_response = self.client.post(
				self.fcm_send_url,
				{'title': 'Test', 'body': 'Wiadomosc testowa'},
				format='json',
			)

		self.assertEqual(send_response.status_code, status.HTTP_200_OK)
		self.assertEqual(send_response.data.get('CODE'), 'FCM_SEND_COMPLETED')
		self.assertEqual(send_response.data.get('sent'), 1)
		self.assertEqual(send_response.data.get('failed'), 0)
