from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Country, State, City, Address

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'first_name', 'last_name', 'role', 'is_active', 'created_at']
    list_filter = ['role', 'is_active', 'is_verified']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['email']
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone',  'address')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'is_verified', 'is_approved')}),
        ('Important dates', {'fields': ('last_login', 'created_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2', 'role'),
        }),
    )
    
    readonly_fields = ['created_at']


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'phone_code']
    search_fields = ['name', 'code']

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'country']
    list_filter = ['country']
    search_fields = ['name', 'country__name']

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ['name', 'state', 'postal_code']
    list_filter = ['state__country', 'state']
    search_fields = ['name', 'state__name']

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['street_address', 'city', 'postal_code', 'is_default']
    list_filter = ['city__state__country', 'is_default']
    search_fields = ['street_address', 'city__name']