from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from .base import BaseModel
from .managers import MyUserManager
from . import roles


class Country(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=3, unique=True, help_text="ISO 3166-1 alpha-3 code")
    phone_code = models.CharField(max_length=10, help_text="Country phone code")
    
    class Meta:
        verbose_name_plural = "Countries"
        ordering = ['name']
    
    def __str__(self):
        return self.name

class State(BaseModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, blank=True)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='states')
    
    class Meta:
        unique_together = ['name', 'country']
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name}, {self.country.name}"

class City(BaseModel):
    name = models.CharField(max_length=100)
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name='cities')
    postal_code = models.CharField(max_length=20, blank=True)
    
    class Meta:
        verbose_name_plural = "Cities"
        unique_together = ['name', 'state']
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name}, {self.state.name}"

class Address(BaseModel):
    street_address = models.TextField()
    apartment = models.CharField(max_length=100, blank=True)
    city = models.ForeignKey(City, on_delete=models.CASCADE)
    postal_code = models.CharField(max_length=20)
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    
    class Meta:
        verbose_name_plural = "Addresses"
    
    def __str__(self):
        return f"{self.street_address}, {self.city}"
    
    @property
    def full_address(self):
        parts = [self.street_address]
        if self.apartment:
            parts.append(self.apartment)
        parts.extend([str(self.city), self.postal_code])
        return ", ".join(parts)

class User(AbstractBaseUser, PermissionsMixin):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True, db_index=True)
    phone = models.CharField(max_length=20, blank=True)

    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True)
    is_verified = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    role = models.IntegerField(choices=roles.UserRoles.choices, default=roles.UserRoles.USER)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    objects = MyUserManager()
    
    class Meta:
        ordering = ['id']
    
    def __str__(self):
        return self.email
    
    @property
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
