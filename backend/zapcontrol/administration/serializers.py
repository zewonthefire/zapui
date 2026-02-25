from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from rest_framework import serializers

from targets.models import ZapNode

from .models import AppSetting, AuditEvent, ZapPool
from .services import decrypt_api_key, encrypt_api_key


class GroupSerializer(serializers.ModelSerializer):
    members_count = serializers.IntegerField(source='user_set.count', read_only=True)

    class Meta:
        model = Group
        fields = ['id', 'name', 'members_count']


class UserSerializer(serializers.ModelSerializer):
    groups = serializers.PrimaryKeyRelatedField(many=True, queryset=Group.objects.all(), required=False)
    username = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'email', 'is_active', 'last_login', 'date_joined', 'groups']

    def get_username(self, obj):
        return getattr(obj, 'username', None) or obj.email


class UserCreateSerializer(UserSerializer):
    password = serializers.CharField(write_only=True)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ['password']

    def create(self, validated_data):
        groups = validated_data.pop('groups', [])
        password = validated_data.pop('password')
        user = get_user_model().objects.create_user(password=password, **validated_data)
        user.groups.set(groups)
        return user


class GroupPermissionSerializer(serializers.Serializer):
    permission_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)


class ZapNodeSerializer(serializers.ModelSerializer):
    api_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    api_key_masked = serializers.SerializerMethodField()

    class Meta:
        model = ZapNode
        fields = [
            'id',
            'name',
            'base_url',
            'api_key',
            'api_key_masked',
            'is_active',
            'max_concurrent',
            'tags',
            'health_status',
            'last_seen_at',
            'last_error',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['health_status', 'last_seen_at', 'last_error', 'created_at', 'updated_at']

    def get_api_key_masked(self, obj):
        return '********' if obj.api_key else ''

    def create(self, validated_data):
        api_key = validated_data.pop('api_key', '')
        if api_key:
            validated_data['api_key'] = encrypt_api_key(api_key)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        api_key = validated_data.pop('api_key', None)
        if api_key is not None:
            validated_data['api_key'] = encrypt_api_key(api_key)
        return super().update(instance, validated_data)


class ZapPoolSerializer(serializers.ModelSerializer):
    nodes = serializers.PrimaryKeyRelatedField(many=True, queryset=ZapNode.objects.all(), required=False)

    class Meta:
        model = ZapPool
        fields = ['id', 'name', 'description', 'nodes', 'selection_strategy', 'is_active', 'created_at', 'updated_at']


class AppSettingSerializer(serializers.ModelSerializer):
    value = serializers.SerializerMethodField()

    class Meta:
        model = AppSetting
        fields = ['id', 'key', 'value', 'value_type', 'description', 'is_secret', 'updated_by', 'updated_at']

    def get_value(self, obj):
        return obj.masked_value


class AppSettingUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppSetting
        fields = ['value']


class AuditEventSerializer(serializers.ModelSerializer):
    actor_email = serializers.SerializerMethodField()

    class Meta:
        model = AuditEvent
        fields = '__all__'

    def get_actor_email(self, obj):
        return obj.actor.email if obj.actor else None
