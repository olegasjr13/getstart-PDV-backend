import uuid, time, json, logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("django.request")

class RequestLogMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request._start_time = time.time()
    def process_response(self, request, response):
        try:
            latency = int((time.time() - getattr(request,"_start_time", time.time()))*1000)
            payload = {
                "request_id": getattr(request,"request_id","-"),
                "path": request.path,
                "method": request.method,
                "status": response.status_code,
                "latency_ms": latency,
            }
            logger.info(json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass
        return response
