# tef/serializers/tef_serializers.py

from rest_framework import serializers

from tef.models.tef_models import TefConfig




class TefConfigSerializer(serializers.ModelSerializer):
    provider_display = serializers.CharField(
        source="get_provider_display",
        read_only=True,
    )

    class Meta:
        model = TefConfig
        fields = [
            "id",
            "filial",
            "terminal",
            "provider",
            "provider_display",
            "merchant_id",
            "store_id",
            "endpoint_base",
            "api_key_alias",
            "ativo",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        """
        Reaproveita as validações de model.clean() para garantir consistência.
        """
        instance = TefConfig(
            **{
                **getattr(self.instance, "__dict__", {}),
                **attrs,
            }
        )
        instance.__dict__.pop("_state", None)
        instance.clean()
        return attrs
