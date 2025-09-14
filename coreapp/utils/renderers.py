from rest_framework.renderers import JSONRenderer
from django.utils.translation import gettext_lazy as _

class CustomJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        response_data = data
        
        if renderer_context:
            response = renderer_context.get('response')
            if response:
                status_code = response.status_code
                
                # Check if data is already in custom format
                if isinstance(data, dict) and 'success' in data:
                    return super().render(data, accepted_media_type, renderer_context)
                
                # Wrap data in custom format
                if 200 <= status_code < 300:
                    response_data = {
                        'success': True,
                        'message': _('Success'),
                        'data': data,
                        'status_code': status_code
                    }
                else:
                    response_data = {
                        'success': False,
                        'message': _('Error'),
                        'errors': data,
                        'status_code': status_code
                    }
        
        return super().render(response_data, accepted_media_type, renderer_context)