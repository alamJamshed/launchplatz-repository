from rest_framework.views import exception_handler
from rest_framework import status
from django.utils.translation import gettext_lazy as _
from .responses import APIResponse

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    
    if response is not None:
        if response.status_code == status.HTTP_404_NOT_FOUND:
            return APIResponse.not_found(_("Resource not found"))
        elif response.status_code == status.HTTP_403_FORBIDDEN:
            return APIResponse.forbidden(_("You don't have permission to perform this action"))
        elif response.status_code == status.HTTP_401_UNAUTHORIZED:
            return APIResponse.unauthorized(_("Authentication credentials were not provided"))
        elif response.status_code == status.HTTP_400_BAD_REQUEST:
            return APIResponse.error(
                message=_("Validation failed"),
                errors=response.data,
                status_code=response.status_code
            )
        else:
            return APIResponse.error(
                message=_("An error occurred"),
                errors=response.data,
                status_code=response.status_code
            )
    
    return response