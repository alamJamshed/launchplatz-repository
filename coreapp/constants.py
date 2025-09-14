from django.db import models
from django.utils.translation import gettext_lazy as _

class GenderChoices(models.IntegerChoices):
    MALE = 1, _('Male')
    FEMALE = 2, _('Female')
    OTHER = 3, _('Other')