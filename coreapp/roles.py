from django.db import models
from django.utils.translation import gettext_lazy as _

class UserRoles(models.IntegerChoices):
    ADMIN = 1, _('Admin')
    ADMIN_STAFF = 2, _('Admin Staff')
    USER = 3, _('User')