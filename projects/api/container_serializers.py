from rest_framework import serializers


class ContainerStatusSerializer(serializers.Serializer):
    service = serializers.CharField()
    container_id = serializers.CharField()
    container_name = serializers.CharField()
    image = serializers.CharField()
    state = serializers.CharField()
    health = serializers.CharField()
    exit_code = serializers.IntegerField(allow_null=True)
    created_at = serializers.CharField()
    ports = serializers.ListField(child=serializers.DictField())


class ContainerLogsSerializer(serializers.Serializer):
    service = serializers.CharField()
    tail = serializers.IntegerField()
    lines = serializers.ListField(child=serializers.CharField())


class ContainerLogQuerySerializer(serializers.Serializer):
    tail = serializers.IntegerField(required=False, default=200, min_value=1)

    def validate_tail(self, value):
        maximum = self.context['maximum']
        if value > maximum:
            raise serializers.ValidationError(
                f'Ensure this value is less than or equal to {maximum}.'
            )
        return value
