from rest_framework import serializers

from projects.models import EnvironmentVariable, GitOperation, Project
from projects.environment_services import EnvironmentCredentialCipher
from projects.git_services import GitCredentialCipher
from servers.services import SSHKeyParser
from servers.models import Server


class ProjectSerializer(serializers.ModelSerializer):
    git_private_key = serializers.CharField(
        write_only=True, required=False, trim_whitespace=False
    )
    server = serializers.PrimaryKeyRelatedField(
        queryset=Server.objects.filter(is_active=True, is_deleted=False)
    )
    framework_display = serializers.CharField(
        source='get_framework_display', read_only=True
    )

    class Meta:
        model = Project
        fields = [
            'id', 'server', 'name', 'framework', 'framework_display',
            'git_repository_url', 'branch', 'domain',
            'docker_compose_path', 'is_archived', 'archived_at', 'archived_by',
            'django_service_name',
            'git_private_key', 'git_cloned_at', 'current_branch',
            'current_commit', 'last_git_synced_at',
            'created_at', 'updated_at', 'created_by', 'updated_by',
        ]
        read_only_fields = [
            'id', 'framework', 'framework_display', 'is_archived',
            'archived_at', 'archived_by', 'created_at', 'updated_at',
            'git_cloned_at', 'current_branch', 'current_commit',
            'last_git_synced_at',
            'created_by', 'updated_by',
            'domain',
        ]

    def validate_git_private_key(self, value):
        try:
            SSHKeyParser.parse(value)
        except Exception as exc:
            if hasattr(exc, 'messages'):
                raise serializers.ValidationError(exc.messages[0]) from exc
            raise
        return value

    def validate(self, attrs):
        server = attrs.get('server', getattr(self.instance, 'server', None))
        if not server or not server.is_active or server.is_deleted:
            raise serializers.ValidationError(
                {'server': 'Select an active, non-deleted server.'}
            )
        if (
            self.instance
            and self.instance.git_cloned_at
            and 'branch' in attrs
            and attrs['branch'] != self.instance.branch
        ):
            raise serializers.ValidationError(
                {'branch': 'Use the Git Select Branch endpoint after cloning.'}
            )
        return attrs

    def create(self, validated_data):
        private_key = validated_data.pop('git_private_key', None)
        if private_key:
            validated_data['encrypted_git_private_key'] = (
                GitCredentialCipher.encrypt(private_key)
            )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        private_key = validated_data.pop('git_private_key', None)
        if private_key:
            validated_data['encrypted_git_private_key'] = (
                GitCredentialCipher.encrypt(private_key)
            )
        return super().update(instance, validated_data)


class BranchSelectionSerializer(serializers.Serializer):
    branch = serializers.CharField(max_length=255)


class GitActionResultSerializer(serializers.Serializer):
    branch = serializers.CharField(required=False)
    commit = serializers.CharField(required=False)
    workspace = serializers.CharField(required=False)
    branches = serializers.ListField(
        child=serializers.CharField(), required=False
    )


class GitOperationSerializer(serializers.ModelSerializer):
    class Meta:
        model = GitOperation
        fields = [
            'id', 'action', 'status', 'output', 'error_category',
            'commit_hash', 'duration_ms', 'started_at', 'completed_at',
            'initiated_by',
        ]
        read_only_fields = fields


class EnvironmentVariableSerializer(serializers.ModelSerializer):
    value = serializers.CharField(
        required=True, allow_blank=True, trim_whitespace=False, write_only=True
    )

    class Meta:
        model = EnvironmentVariable
        fields = [
            'id', 'key', 'value', 'is_secret', 'created_at', 'updated_at',
            'created_by', 'updated_by',
        ]

    def validate_key(self, value):
        project = self.context.get('project')
        queryset = EnvironmentVariable.objects.filter(project=project, key=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if project and queryset.exists():
            raise serializers.ValidationError(
                'An environment variable with this key already exists.'
            )
        return value
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'created_by', 'updated_by',
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['value'] = EnvironmentCredentialCipher.decrypt(instance.encrypted_value)
        return data

    def create(self, validated_data):
        value = validated_data.pop('value')
        validated_data['encrypted_value'] = EnvironmentCredentialCipher.encrypt(value)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'value' in validated_data:
            validated_data['encrypted_value'] = EnvironmentCredentialCipher.encrypt(
                validated_data.pop('value')
            )
        return super().update(instance, validated_data)


class EnvironmentGenerationResultSerializer(serializers.Serializer):
    variable_count = serializers.IntegerField()
    generated_at = serializers.DateTimeField()
