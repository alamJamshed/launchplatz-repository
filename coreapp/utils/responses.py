from rest_framework.response import Response
from rest_framework import status
from django.utils.translation import gettext_lazy as _

class APIResponse:
    @staticmethod
    def success(data=None, message=_("Success"), status_code=status.HTTP_200_OK):
        return Response({
            'success': True,
            'message': message,
            'data': data,
            'status_code': status_code
        }, status=status_code)
    
    @staticmethod
    def error(message=_("Error"), errors=None, status_code=status.HTTP_400_BAD_REQUEST):
        return Response({
            'success': False,
            'message': message,
            'errors': errors,
            'status_code': status_code
        }, status=status_code)
    
    @staticmethod
    def created(data=None, message=_("Created successfully")):
        return APIResponse.success(data, message, status.HTTP_201_CREATED)
    
    @staticmethod
    def not_found(message=_("Not found")):
        return APIResponse.error(message, status_code=status.HTTP_404_NOT_FOUND)
    
    @staticmethod
    def forbidden(message=_("Permission denied")):
        return APIResponse.error(message, status_code=status.HTTP_403_FORBIDDEN)
    
    @staticmethod
    def unauthorized(message=_("Authentication required")):
        return APIResponse.error(message, status_code=status.HTTP_401_UNAUTHORIZED)
    
    @staticmethod
    def paginated(data, message=_("Data retrieved successfully"), count=None, next_url=None, previous_url=None):
        return Response({
            'success': True,
            'message': message,
            'data': {
                'count': count,
                'next': next_url,
                'previous': previous_url,
                'results': data
            },
            'status_code': status.HTTP_200_OK
        }, status=status.HTTP_200_OK)

