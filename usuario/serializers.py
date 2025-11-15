from rest_framework import serializers

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
    terminal_id = serializers.UUIDField()

class PinSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    pin = serializers.CharField(min_length=4)
