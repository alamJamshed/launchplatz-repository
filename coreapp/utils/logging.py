import logging

class RequestLoggerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger('api_requests')

    def __call__(self, request):
        response = self.get_response(request)
        
        # Only log errors (4xx, 5xx)
        if response.status_code >= 400:
            self.logger.error(
                f"API Error: {request.method} {request.path} - Status: {response.status_code}",
                extra={'request': request}
            )
        
        return response