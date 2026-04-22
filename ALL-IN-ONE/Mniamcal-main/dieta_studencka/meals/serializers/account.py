from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    first_name = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class GoogleOAuthLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField()


class AuthResponseSerializer(serializers.Serializer):
    CODE = serializers.CharField()
    detail = serializers.CharField()


class AuthTokenResponseSerializer(serializers.Serializer):
    CODE = serializers.CharField()
    detail = serializers.CharField()
    access = serializers.CharField()
    refresh = serializers.CharField()


class AuthMeResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    first_name = serializers.CharField(allow_blank=True)
    email = serializers.EmailField(allow_blank=True)
    rodzina_id = serializers.IntegerField(required=False, allow_null=True)
    kalorycznosc_diety_id = serializers.IntegerField(required=False, allow_null=True)
    dieta_id = serializers.IntegerField(required=False, allow_null=True)
    dieta = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    kalorycznosc_id = serializers.IntegerField(required=False, allow_null=True)
    kalorycznosc = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    czysta_kalorycznosc = serializers.IntegerField(required=False, allow_null=True)


class AuthSetDietSerializer(serializers.Serializer):
    kalorycznosc_diety_id = serializers.IntegerField(min_value=1)


class FcmDeviceRegisterSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=512)
    platform = serializers.CharField(max_length=20, required=False, allow_blank=True)


class FcmDevicePreferenceSerializer(serializers.Serializer):
    push_enabled = serializers.BooleanField(required=False)
    shopping_package_size_enabled = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                {'detail': 'Nalezy przekazac przynajmniej jedno pole preferencji.'}
            )
        return attrs


class FcmDevicePreferenceResponseSerializer(serializers.Serializer):
    CODE = serializers.CharField()
    detail = serializers.CharField()
    push_enabled = serializers.BooleanField()
    shopping_package_size_enabled = serializers.BooleanField()


class FcmSendNotificationSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=120)
    body = serializers.CharField(max_length=500)
    token = serializers.CharField(max_length=512, required=False, allow_blank=False)
    user_id = serializers.IntegerField(required=False)
    data = serializers.DictField(required=False)


class FcmSendNotificationResponseSerializer(serializers.Serializer):
    CODE = serializers.CharField()
    detail = serializers.CharField()
    sent = serializers.IntegerField()
    failed = serializers.IntegerField()
    message_ids = serializers.ListField(child=serializers.CharField())
    errors = serializers.ListField(child=serializers.CharField())


class ApiErrorSerializer(serializers.Serializer):
    CODE = serializers.CharField()
    detail = serializers.CharField(required=False, allow_blank=True)
    errors = serializers.DictField(required=False)
