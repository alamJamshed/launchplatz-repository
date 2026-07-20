from rest_framework import serializers

from servers.models import Server
from servers.services import SSHKeyParser, ServerCredentialCipher


class ServerSerializer(serializers.ModelSerializer):
    private_key = serializers.CharField(write_only=True, required=False, trim_whitespace=False)

    class Meta:
        model = Server
        fields = [
            'id', 'name', 'ip_address', 'ssh_port', 'username', 'private_key',
            'status', 'last_checked_at', 'last_latency_ms',
            'last_failure_reason',
            'created_at', 'updated_at', 'created_by', 'updated_by',
        ]
        read_only_fields = [
            'id', 'status', 'last_checked_at', 'last_latency_ms',
            'last_failure_reason', 'created_at', 'updated_at', 'created_by',
            'updated_by',
        ]

    def validate_ssh_port(self, value):
        if not 1 <= value <= 65535:
            raise serializers.ValidationError('SSH port must be between 1 and 65535.')
        return value

    def validate_private_key(self, value):
        try:
            SSHKeyParser.parse(value)
        except Exception as exc:
            if hasattr(exc, 'messages'):
                raise serializers.ValidationError(exc.messages[0]) from exc
            raise
        return value

    def validate(self, attrs):
        if self.instance is None and not attrs.get('private_key'):
            raise serializers.ValidationError({'private_key': 'This field is required.'})

        ip_address = attrs.get('ip_address', getattr(self.instance, 'ip_address', None))
        ssh_port = attrs.get('ssh_port', getattr(self.instance, 'ssh_port', 22))
        username = attrs.get('username', getattr(self.instance, 'username', None))
        duplicates = Server.objects.filter(
            ip_address=ip_address,
            ssh_port=ssh_port,
            username=username,
            is_deleted=False,
        )
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(
                'An active server with this IP, port, and username already exists.'
            )
        return attrs

    def create(self, validated_data):
        private_key = validated_data.pop('private_key')
        validated_data['encrypted_private_key'] = ServerCredentialCipher.encrypt(private_key)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        private_key = validated_data.pop('private_key', None)
        if private_key is not None:
            validated_data['encrypted_private_key'] = ServerCredentialCipher.encrypt(private_key)
        return super().update(instance, validated_data)


class ConnectionTestResultSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['Online', 'Offline'])
    latency_ms = serializers.FloatField(required=False)
    reason = serializers.ChoiceField(
        choices=[
            'authentication_failed', 'timeout', 'host_unreachable',
            'credential_error', 'ssh_error',
        ],
        required=False,
    )
    checked_at = serializers.DateTimeField()
