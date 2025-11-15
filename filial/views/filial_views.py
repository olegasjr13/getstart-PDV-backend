from filial.models.filial_models import Filial
from filial.serializers import FilialSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response



@api_view(["GET"])
@permission_classes([IsAuthenticated])
def filial_detail(request, id):
    try:
        f = Filial.objects.get(id=id)
    except Filial.DoesNotExist:
        return Response(status=404)
    return Response(FilialSerializer(f).data)
