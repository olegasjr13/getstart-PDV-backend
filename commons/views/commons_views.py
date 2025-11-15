from django.http import JsonResponse
from django.db import connection
from datetime import datetime, timezone

def liveness(request):
    return JsonResponse({"ok": True})

def readiness(request):
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return JsonResponse({"ok": True, "tenants_degraded": 0})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=503)

def time_now(request):
    now = datetime.now(timezone.utc).astimezone()
    return JsonResponse({"now": now.isoformat()})
