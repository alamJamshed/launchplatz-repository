from django.db import models
from coreapp.base import BaseModel
from .constants import NOTIFICATION_TYPES

class SiteSettings(BaseModel):
    site_name = models.CharField(max_length=255, default="My Site")
    site_description = models.TextField(blank=True)
    site_logo = models.ImageField(upload_to='site/', blank=True, null=True)
    site_favicon = models.ImageField(upload_to='site/', blank=True, null=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    maintenance_mode = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Site Setting"
        verbose_name_plural = "Site Settings"

class SMTPSettings(BaseModel):
    host = models.CharField(max_length=255)
    port = models.IntegerField(default=587)
    username = models.CharField(max_length=255)
    password = models.CharField(max_length=255)
    use_tls = models.BooleanField(default=True)
    use_ssl = models.BooleanField(default=False)
    from_email = models.EmailField()
    from_name = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "SMTP Setting"
        verbose_name_plural = "SMTP Settings"

class NotificationSettings(BaseModel):
    type = models.CharField(max_length=10, choices=NOTIFICATION_TYPES)
    event = models.CharField(max_length=100)
    is_enabled = models.BooleanField(default=True)
    template_subject = models.CharField(max_length=255, blank=True)
    template_body = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Notification Setting"
        verbose_name_plural = "Notification Settings"