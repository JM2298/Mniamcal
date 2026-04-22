"""Family serializers category."""
import random
from smtplib import SMTPException
from urllib.parse import quote

from django.core import signing
from rest_framework import serializers
from django.core.mail import send_mail
from django.conf import settings

from meals.models import (
	AuthUser,
	ProjektInflacjaMobileKalorycznoscdiety,
	ProjektInflacjaMobileRodziny,
	ProjektInflacjaMobileSklepy,
	ProjektInflacjaMobileUzytkownicywrodzinach,
)


INVITE_TOKEN_SALT = 'family-invite-token-v1'
INVITE_TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 7


class CreateFamilySerializer(serializers.ModelSerializer):
	class Meta:
		model = ProjektInflacjaMobileRodziny
		fields = ['id', 'rodzina']
		extra_kwargs = {
			'rodzina': {'required': True},
		}

	def validate(self, attrs):
		user = self.context['request'].user
		if ProjektInflacjaMobileRodziny.objects.filter(zalozyciel_rodziny_id=user.id).exists():
			raise serializers.ValidationError({'rodzina': 'Mozesz miec tylko jedna rodzine.'})
		return attrs

	def create(self, validated_data):
		user = self.context['request'].user
		# Fetch AuthUser instance from database using the user's id
		auth_user = AuthUser.objects.get(id=user.id)
		sklep = ProjektInflacjaMobileSklepy.objects.order_by('id').first()
		if not sklep:
			raise serializers.ValidationError({'detail': 'Brak sklepu do przypisania rodziny.'})

		validated_data['zalozyciel_rodziny'] = auth_user
		validated_data['sklep'] = sklep
		validated_data['pin'] = f"{random.randint(0, 9999):04d}"
		return super().create(validated_data)


class FamilyDetailSerializer(serializers.ModelSerializer):
	zalozyciel_rodziny_username = serializers.CharField(source='zalozyciel_rodziny.username', read_only=True)

	class Meta:
		model = ProjektInflacjaMobileRodziny
		fields = ['id', 'rodzina', 'zalozyciel_rodziny', 'zalozyciel_rodziny_username']


class FamilyMemberPlannedMealSerializer(serializers.Serializer):
	planned_meal_id = serializers.IntegerField()
	posilek_w_diecie_id = serializers.IntegerField(allow_null=True)
	data = serializers.DateField()
	posilek = serializers.CharField()
	pora_posilku = serializers.CharField(allow_blank=True)
	czy_zjedzone = serializers.BooleanField()


class FamilyMemberSerializer(serializers.Serializer):
	id = serializers.IntegerField()
	username = serializers.CharField()
	first_name = serializers.CharField(allow_blank=True)
	email = serializers.EmailField(allow_blank=True)
	is_founder = serializers.BooleanField()
	is_current_user = serializers.BooleanField(required=False)
	dieta_id = serializers.IntegerField(allow_null=True)
	dieta = serializers.CharField(allow_blank=True, allow_null=True)
	kalorycznosc_id = serializers.IntegerField(allow_null=True)
	kalorycznosc = serializers.CharField(allow_blank=True, allow_null=True)
	czysta_kalorycznosc = serializers.IntegerField(allow_null=True)
	zaplanowane_posilki = FamilyMemberPlannedMealSerializer(many=True, required=False)


class FamilyMembersResponseSerializer(serializers.Serializer):
	rodzina_id = serializers.IntegerField()
	rodzina = serializers.CharField()
	members = FamilyMemberSerializer(many=True)


class FamilyUserMembershipSerializer(serializers.Serializer):
	id = serializers.IntegerField()
	username = serializers.CharField()
	first_name = serializers.CharField(allow_blank=True)
	email = serializers.EmailField(allow_blank=True)
	rodzina_id = serializers.IntegerField(allow_null=True)
	is_founder = serializers.BooleanField()
	kalorycznosc_diety_id = serializers.IntegerField(allow_null=True)
	dieta_id = serializers.IntegerField(allow_null=True)
	dieta = serializers.CharField(allow_blank=True, allow_null=True)
	kalorycznosc_id = serializers.IntegerField(allow_null=True)
	kalorycznosc = serializers.CharField(allow_blank=True, allow_null=True)
	czysta_kalorycznosc = serializers.IntegerField(allow_null=True)


class FamilyUserSetDietSerializer(serializers.Serializer):
	kalorycznosc_diety_id = serializers.IntegerField(min_value=1)


class InviteToFamilyByEmailSerializer(serializers.Serializer):
	rodzina_id = serializers.IntegerField(required=False)
	email = serializers.EmailField(required=True)

	def validate(self, attrs):
		request_user = self.context['request'].user
		rodzina_id = attrs.get('rodzina_id')
		email = attrs['email'].strip().lower()

		if rodzina_id is not None:
			try:
				rodzina = ProjektInflacjaMobileRodziny.objects.get(id=rodzina_id)
			except ProjektInflacjaMobileRodziny.DoesNotExist as exc:
				raise serializers.ValidationError({'rodzina_id': 'Rodzina nie istnieje.'}) from exc

			if rodzina.zalozyciel_rodziny_id != request_user.id:
				raise serializers.ValidationError({'rodzina_id': 'Tylko zalozyciel rodziny moze wysylac zaproszenia.'})
		else:
			rodzina = ProjektInflacjaMobileRodziny.objects.filter(zalozyciel_rodziny_id=request_user.id).first()
			if not rodzina:
				raise serializers.ValidationError({'rodzina_id': 'Nie masz zalozonej rodziny do zapraszania.'})

		if rodzina.zalozyciel_rodziny.email.lower() == email:
			raise serializers.ValidationError({'email': 'Zalozyciel juz nalezy do tej rodziny.'})

		invited_user = AuthUser.objects.filter(email__iexact=email).first()
		if invited_user and ProjektInflacjaMobileUzytkownicywrodzinach.objects.filter(
			rodzina=rodzina,
			uzytkownik=invited_user,
		).exists():
			raise serializers.ValidationError({'email': 'Ten uzytkownik juz jest czlonkiem tej rodziny.'})

		attrs['rodzina'] = rodzina
		attrs['email'] = email
		attrs['invited_user'] = invited_user
		return attrs

	def create(self, validated_data):
		rodzina = validated_data['rodzina']
		email = validated_data['email']

		token = signing.dumps({'rodzina_id': rodzina.id, 'email': email}, salt=INVITE_TOKEN_SALT)
		api_server_url = settings.API_SERVER_URL
		if api_server_url:
			invitation_link = f"{api_server_url}/api/family-invitations/accept/?token={quote(token)}&view=page"
		else:
			invitation_link = f"/api/family-invitations/accept/?token={quote(token)}&view=page"

		user_added = False
		email_sent = True
		email_error = None

		try:
			send_mail(
				subject='Zaproszenie do rodziny w Dieta Studencka',
				message=(
					f"Otrzymales zaproszenie do rodziny '{rodzina.rodzina}'.\n"
					f"Kliknij link, aby dolaczyc: {invitation_link}"
				),
				from_email=settings.DEFAULT_FROM_EMAIL,
				recipient_list=[email],
				fail_silently=False,
			)
		except (SMTPException, OSError, TimeoutError) as exc:
			email_sent = False
			email_error = 'Nie udalo sie wyslac maila. Sprawdz konfiguracje EMAIL_BACKEND/SMTP.'

		return {
			'rodzina_id': rodzina.id,
			'rodzina': rodzina.rodzina,
			'email': email,
			'user_added': user_added,
			'email_sent': email_sent,
			'email_error': email_error,
			'invitation_link': invitation_link,
			'invitation_token': token,
		}


class AcceptFamilyInvitationSerializer(serializers.Serializer):
	token = serializers.CharField(required=True)

	def validate(self, attrs):
		token = attrs['token']
		try:
			payload = signing.loads(token, salt=INVITE_TOKEN_SALT, max_age=INVITE_TOKEN_MAX_AGE_SECONDS)
		except signing.SignatureExpired as exc:
			raise serializers.ValidationError({'token': 'Link zaproszenia wygasl.'}) from exc
		except signing.BadSignature as exc:
			raise serializers.ValidationError({'token': 'Nieprawidlowy link zaproszenia.'}) from exc

		attrs['payload'] = payload
		return attrs

	def create(self, validated_data):
		payload = validated_data['payload']
		rodzina_id = payload['rodzina_id']
		email = payload['email']

		try:
			rodzina = ProjektInflacjaMobileRodziny.objects.get(id=rodzina_id)
		except ProjektInflacjaMobileRodziny.DoesNotExist as exc:
			raise serializers.ValidationError({'detail': 'Rodzina z zaproszenia juz nie istnieje.'}) from exc

		invited_user = AuthUser.objects.filter(email__iexact=email).first()
		if not invited_user:
			raise serializers.ValidationError({'detail': 'Dla tego emaila nie ma konta. Zarejestruj sie i kliknij link ponownie.'})

		if ProjektInflacjaMobileUzytkownicywrodzinach.objects.filter(
			rodzina=rodzina,
			uzytkownik=invited_user,
		).exists():
			return {
				'accepted': True,
				'user_added': False,
				'already_member': True,
				'rodzina_id': rodzina.id,
				'rodzina': rodzina.rodzina,
				'email': email,
			}

		kalorycznosc_diety = ProjektInflacjaMobileKalorycznoscdiety.objects.order_by('id').first()
		if not kalorycznosc_diety:
			raise serializers.ValidationError({'detail': 'Brak skonfigurowanej kalorycznosci diety.'})

		ProjektInflacjaMobileUzytkownicywrodzinach.objects.create(
			rodzina=rodzina,
			uzytkownik=invited_user,
			kalorycznosc_diety=kalorycznosc_diety,
		)

		return {
			'accepted': True,
			'user_added': True,
			'already_member': False,
			'rodzina_id': rodzina.id,
			'rodzina': rodzina.rodzina,
			'email': email,
		}
