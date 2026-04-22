"""Family tests."""
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from meals.serializers.family import CreateFamilySerializer
from meals.serializers.family import FamilyMemberPlannedMealSerializer
from meals.serializers.family import InviteToFamilyByEmailSerializer


User = get_user_model()


class FamilyApiTests(APITestCase):
	families_url = '/api/families/'
	family_delete_url = '/api/families/delete/'
	family_leave_url = '/api/families/leave/'
	family_members_url = '/api/families/members/'
	family_my_membership_url = '/api/families/my-membership/'
	family_my_membership_diet_url = '/api/families/my-membership/diet/'
	family_invitations_url = '/api/family-invitations/'
	family_invitations_accept_url = '/api/family-invitations/accept/'

	def setUp(self):
		"""Create test user."""
		self.user = User.objects.create_user(username='testuser', password='testpass123')

	def test_create_family_requires_authentication(self):
		"""Test that creating a family requires authentication."""
		response = self.client.post(
			self.families_url,
			{'rodzina': 'Test Family'},
		)
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	@patch('meals.api_views.family.async_to_sync')
	@patch('meals.api_views.family.get_channel_layer')
	@patch('meals.api_views.family.FamilyDetailSerializer')
	@patch('meals.api_views.family.FamilyCreateViewSet.perform_create')
	@patch('meals.api_views.family.FamilyCreateViewSet.get_serializer')
	def test_create_family_emits_websocket_event(
		self,
		mocked_get_serializer,
		mocked_perform_create,
		mocked_detail_serializer,
		mocked_get_channel_layer,
		mocked_async_to_sync,
	):
		"""Test creating family emits websocket event."""
		self.client.force_authenticate(user=self.user)

		serializer = MagicMock()
		mocked_get_serializer.return_value = serializer
		mocked_perform_create.return_value = SimpleNamespace(id=10, rodzina='Rodzina Testowa')
		mocked_detail_serializer.return_value.data = {'id': 10, 'rodzina': 'Rodzina Testowa'}

		group_send = MagicMock()
		mocked_async_to_sync.return_value = group_send
		mocked_get_channel_layer.return_value = MagicMock()

		response = self.client.post(self.families_url, {'rodzina': 'Rodzina Testowa'}, format='json')

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		group_send.assert_called_once_with(
			'family_updates',
			{
				'type': 'family_event',
				'payload': {
					'event': 'family_created',
					'rodzina_id': 10,
					'rodzina': 'Rodzina Testowa',
					'created_by_user_id': self.user.id,
				},
			},
		)

	def test_create_family_serializer_requires_only_family_name(self):
		"""Test family serializer input contract for creating family."""
		serializer = CreateFamilySerializer()
		self.assertIn('rodzina', serializer.fields)
		self.assertNotIn('pin', serializer.fields)
		self.assertNotIn('sklep_id', serializer.fields)

	def test_family_planned_meal_serializer_contains_meal_id(self):
		"""Test family planned meal serializer exposes meal id for details lookup."""
		serializer = FamilyMemberPlannedMealSerializer()
		self.assertIn('posilek_w_diecie_id', serializer.fields)

	@patch('meals.serializers.family.ProjektInflacjaMobileRodziny.objects.filter')
	def test_create_family_serializer_allows_only_one_family_per_user(self, mocked_filter):
		"""Test user cannot create more than one family."""
		mocked_filter.return_value.exists.return_value = True
		request = type('Request', (), {'user': type('User', (), {'id': 1})()})()
		serializer = CreateFamilySerializer(data={'rodzina': 'Test Family'}, context={'request': request})

		self.assertFalse(serializer.is_valid())
		self.assertIn('rodzina', serializer.errors)

	def test_invite_to_family_requires_authentication(self):
		"""Test that inviting to family requires authentication."""
		response = self.client.post(
			self.family_invitations_url,
			{'email': 'invitee@example.com'},
		)
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_family_members_requires_authentication(self):
		"""Test that listing family members requires authentication."""
		response = self.client.get(self.family_members_url)
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_my_membership_requires_authentication(self):
		response = self.client.get(self.family_my_membership_url)
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_my_membership_diet_requires_authentication(self):
		response = self.client.post(
			self.family_my_membership_diet_url,
			{'kalorycznosc_diety_id': 1},
			format='json',
		)
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_leave_family_requires_authentication(self):
		response = self.client.post(self.family_leave_url)
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_delete_family_requires_authentication(self):
		response = self.client.post(self.family_delete_url)
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	@patch('meals.api_views.family.emit_live_shopping_list_updates_for_family')
	@patch('meals.api_views.family._broadcast_family_event')
	@patch('meals.api_views.family._delete_family_related_data')
	@patch('meals.api_views.family.ProjektInflacjaMobileRodziny.objects.filter')
	def test_delete_family_for_founder_success(
		self,
		mocked_family_filter,
		mocked_delete_related,
		mocked_broadcast,
		mocked_emit_updates,
	):
		self.client.force_authenticate(user=self.user)

		family = MagicMock()
		family.id = 10
		family.rodzina = 'Rodzina Testowa'
		mocked_family_filter.return_value.first.return_value = family

		response = self.client.post(self.family_delete_url, format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data.get('CODE'), 'FAMILY_DELETED')
		mocked_delete_related.assert_called_once_with(10)
		family.delete.assert_called_once()
		mocked_emit_updates.assert_called_once_with(10, reason='family.deleted')
		mocked_broadcast.assert_called_once_with(
			{
				'event': 'family_deleted',
				'rodzina_id': 10,
				'rodzina': 'Rodzina Testowa',
				'deleted_by_user_id': self.user.id,
			}
		)

	@patch('meals.api_views.family.ProjektInflacjaMobileUzytkownicywrodzinach.objects.filter')
	@patch('meals.api_views.family.ProjektInflacjaMobileRodziny.objects.filter')
	def test_delete_family_for_member_returns_forbidden(
		self,
		mocked_family_filter,
		mocked_membership_filter,
	):
		self.client.force_authenticate(user=self.user)

		mocked_family_filter.return_value.first.return_value = None
		mocked_membership_filter.return_value.exists.return_value = True

		response = self.client.post(self.family_delete_url, format='json')

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
		self.assertEqual(response.data.get('CODE'), 'ONLY_FOUNDER_CAN_DELETE_FAMILY')

	@patch('meals.api_views.family._broadcast_family_event')
	@patch('meals.api_views.family.ProjektInflacjaMobileUzytkownicywrodzinach.objects.filter')
	def test_leave_family_member_success(self, mocked_membership_filter, mocked_broadcast):
		"""Test authenticated family member can leave family."""
		self.client.force_authenticate(user=self.user)

		membership = MagicMock()
		membership.rodzina = SimpleNamespace(id=10, rodzina='Rodzina Testowa', zalozyciel_rodziny_id=999)

		mocked_membership_filter.return_value.select_related.return_value.first.return_value = membership

		response = self.client.post(self.family_leave_url, format='json')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data.get('CODE'), 'FAMILY_LEFT')
		membership.delete.assert_called_once()
		mocked_broadcast.assert_called_once()

	@patch('meals.api_views.family.ProjektInflacjaMobileUzytkownicywrodzinach.objects.filter')
	@patch('meals.api_views.family.ProjektInflacjaMobileRodziny.objects.filter')
	@patch('meals.api_views.family.ProjektInflacjaMobileZaplanowaneposilkirodziny.objects.filter')
	def test_family_members_returns_founder_and_members(
		self,
		mocked_planned_meals_filter,
		mocked_family_filter,
		mocked_membership_filter,
	):
		"""Test members endpoint returns founder and family members payload."""
		self.client.force_authenticate(user=self.user)

		founder = SimpleNamespace(
			id=self.user.id,
			username=self.user.username,
			first_name='Founder',
			email='founder@example.com',
		)
		family = SimpleNamespace(
			id=10,
			rodzina='Rodzina Testowa',
			zalozyciel_rodziny=founder,
			zalozyciel_rodziny_id=founder.id,
		)
		member_user = SimpleNamespace(
			id=22,
			username='member1',
			first_name='Member',
			email='member@example.com',
		)
		dieta = SimpleNamespace(id=5, dieta='Keto')
		kalorycznosc = SimpleNamespace(id=7, kalorycznosc='2000 kcal', czysta_kalorycznosc=2000)
		kalorycznosc_diety = SimpleNamespace(dieta=dieta, kalorycznosc=kalorycznosc)

		mocked_family_filter.return_value.first.return_value = family
		mocked_membership_filter.return_value.select_related.return_value = [
			SimpleNamespace(uzytkownik=member_user, kalorycznosc_diety=kalorycznosc_diety),
		]
		mocked_planned_meals_filter.return_value.select_related.return_value.order_by.return_value = []

		response = self.client.get(self.family_members_url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['rodzina_id'], 10)
		self.assertEqual(response.data['rodzina'], 'Rodzina Testowa')
		self.assertEqual(len(response.data['members']), 2)
		self.assertTrue(response.data['members'][0]['is_founder'])
		self.assertIsNone(response.data['members'][0]['dieta'])
		self.assertFalse(response.data['members'][1]['is_founder'])
		self.assertEqual(response.data['members'][1]['dieta'], 'Keto')
		self.assertEqual(response.data['members'][1]['kalorycznosc'], '2000 kcal')
		self.assertEqual(response.data['members'][1]['czysta_kalorycznosc'], 2000)

	@patch('meals.api_views.family._resolve_user_family_membership_context')
	def test_my_membership_returns_404_when_user_has_no_family(self, mocked_resolve_context):
		self.client.force_authenticate(user=self.user)
		mocked_resolve_context.return_value = (None, None)

		response = self.client.get(self.family_my_membership_url)

		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
		self.assertEqual(response.data.get('CODE'), 'FAMILY_NOT_FOUND')

	@patch('meals.api_views.family.ProjektInflacjaMobileKalorycznoscdiety.objects')
	@patch('meals.api_views.family.ProjektInflacjaMobileUzytkownicywrodzinach.objects')
	@patch('meals.api_views.family.AuthUser.objects')
	@patch('meals.api_views.family._resolve_user_family_membership_context')
	def test_my_membership_diet_creates_membership_when_missing(
		self,
		mocked_resolve_context,
		mocked_auth_user_objects,
		mocked_membership_objects,
		mocked_diet_option_objects,
	):
		self.client.force_authenticate(user=self.user)

		family = SimpleNamespace(id=10, zalozyciel_rodziny_id=self.user.id)
		mocked_resolve_context.return_value = (family, None)

		dieta = SimpleNamespace(id=2, dieta='Classic')
		kalorycznosc = SimpleNamespace(id=3, kalorycznosc='1800 kcal', czysta_kalorycznosc=1800)
		kalorycznosc_diety = SimpleNamespace(id=7, dieta=dieta, kalorycznosc=kalorycznosc)
		mocked_diet_option_objects.select_related.return_value.filter.return_value.first.return_value = kalorycznosc_diety

		created_membership = SimpleNamespace(kalorycznosc_diety=kalorycznosc_diety)
		mocked_membership_objects.create.return_value = created_membership
		auth_user = SimpleNamespace(id=self.user.id)
		mocked_auth_user_objects.filter.return_value.first.return_value = auth_user

		response = self.client.post(
			self.family_my_membership_diet_url,
			{'kalorycznosc_diety_id': 7},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data.get('kalorycznosc_diety_id'), 7)
		self.assertEqual(response.data.get('dieta_id'), 2)
		self.assertEqual(response.data.get('czysta_kalorycznosc'), 1800)
		mocked_membership_objects.create.assert_called_once_with(
			rodzina=family,
			uzytkownik=auth_user,
			kalorycznosc_diety=kalorycznosc_diety,
		)

	@patch('meals.serializers.family.InviteToFamilyByEmailSerializer.create')
	@patch('meals.serializers.family.InviteToFamilyByEmailSerializer.validate')
	def test_invite_to_family_authenticated_returns_created(self, mocked_validate, mocked_create):
		"""Test authenticated user can call invite endpoint."""
		self.client.force_authenticate(user=self.user)
		mocked_validate.side_effect = lambda attrs: attrs
		mocked_create.return_value = {
			'rodzina_id': 1,
			'rodzina': 'Rodzina Testowa',
			'email': 'invitee@example.com',
			'user_added': False,
			'email_sent': True,
			'email_error': None,
			'invitation_link': 'http://localhost:8000/api/family-invitations/accept/?token=abc&view=page',
			'invitation_token': 'abc',
		}

		response = self.client.post(
			self.family_invitations_url,
			{'email': 'invitee@example.com'},
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertFalse(response.data['user_added'])
		self.assertEqual(response.data['email'], 'invitee@example.com')
		self.assertIn('invitation_link', response.data)
		self.assertIn('invitation_token', response.data)
		self.assertIn('view=page', response.data['invitation_link'])

	@patch('meals.serializers.family.AcceptFamilyInvitationSerializer.create')
	@patch('meals.serializers.family.AcceptFamilyInvitationSerializer.validate')
	def test_accept_invitation_page_view_renders_html(self, mocked_validate, mocked_create):
		mocked_validate.side_effect = lambda attrs: {**attrs, 'payload': {'rodzina_id': 1, 'email': 'invitee@example.com'}}
		mocked_create.return_value = {
			'accepted': True,
			'user_added': True,
			'already_member': False,
			'rodzina_id': 1,
			'rodzina': 'Rodzina Testowa',
			'email': 'invitee@example.com',
		}

		response = self.client.get(f'{self.family_invitations_accept_url}?token=abc&view=page')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('text/html', response['Content-Type'])
		self.assertContains(response, 'Dolaczono do rodziny')

	@patch('meals.serializers.family.send_mail', side_effect=OSError('smtp auth failed'))
	def test_invite_serializer_does_not_fail_when_email_send_fails(self, _mocked_send_mail):
		"""Test invite serializer returns success payload even when SMTP fails."""
		serializer = InviteToFamilyByEmailSerializer()
		rodzina = SimpleNamespace(id=12, rodzina='Rodzina Testowa')

		result = serializer.create(
			{
				'rodzina': rodzina,
				'email': 'invitee@example.com',
				'invited_user': None,
			}
		)

		self.assertFalse(result['user_added'])
		self.assertFalse(result['email_sent'])
		self.assertEqual(result['email'], 'invitee@example.com')
		self.assertEqual(
			result['email_error'],
			'Nie udalo sie wyslac maila. Sprawdz konfiguracje EMAIL_BACKEND/SMTP.',
		)

	def test_accept_invitation_requires_token(self):
		"""Test accept endpoint validates token presence."""
		response = self.client.get(self.family_invitations_accept_url)
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	@patch('meals.serializers.family.AcceptFamilyInvitationSerializer.create')
	@patch('meals.serializers.family.AcceptFamilyInvitationSerializer.validate')
	@patch('meals.api_views.family.async_to_sync')
	@patch('meals.api_views.family.get_channel_layer')
	def test_accept_invitation_by_link_returns_ok(
		self,
		mocked_get_channel_layer,
		mocked_async_to_sync,
		mocked_validate,
		mocked_create,
	):
		"""Test accepting invitation link returns success payload."""
		mocked_validate.side_effect = lambda attrs: {**attrs, 'payload': {'rodzina_id': 1, 'email': 'invitee@example.com'}}
		mocked_create.return_value = {
			'accepted': True,
			'user_added': True,
			'already_member': False,
			'rodzina_id': 1,
			'rodzina': 'Rodzina Testowa',
			'email': 'invitee@example.com',
		}

		group_send = MagicMock()
		mocked_async_to_sync.return_value = group_send
		mocked_get_channel_layer.return_value = MagicMock()

		response = self.client.get(f'{self.family_invitations_accept_url}?token=abc')

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertTrue(response.data['accepted'])
		self.assertTrue(response.data['user_added'])
		group_send.assert_called_once_with(
			'family_updates',
			{
				'type': 'family_event',
				'payload': {
					'event': 'family_invitation_accepted',
					'rodzina_id': 1,
					'rodzina': 'Rodzina Testowa',
					'email': 'invitee@example.com',
					'user_added': True,
					'already_member': False,
				},
			},
		)
