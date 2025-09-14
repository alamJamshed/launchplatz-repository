from django.contrib import admin
from .models import SiteSettings, SMTPSettings, NotificationSettings

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ['site_name', 'contact_email', 'maintenance_mode', 'is_active']
    list_filter = ['maintenance_mode', 'is_active']

@admin.register(SMTPSettings)
class SMTPSettingsAdmin(admin.ModelAdmin):
    list_display = ['host', 'port', 'from_email', 'is_active']
    list_filter = ['use_tls', 'use_ssl', 'is_active']

@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ['type', 'event', 'is_enabled']
    list_filter = ['type', 'is_enabled']
