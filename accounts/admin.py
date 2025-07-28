from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from advertisements.models import Store, Department, Stand, AdvertisementMaterial
from .models import User

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'created_at')
    search_fields = ('name', 'location')
    list_filter = ('created_at',)

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'created_at')
    list_filter = ('store', 'created_at')
    search_fields = ('name', 'store__name')

@admin.register(Stand)
class StandAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'display_time', 'transition_animation', 'created_at')
    list_filter = ('department__store', 'department', 'transition_animation', 'created_at')
    search_fields = ('name', 'department__name', 'department__store__name')

@admin.register(AdvertisementMaterial)
class AdvertisementMaterialAdmin(admin.ModelAdmin):
    list_display = ('id', 'stand', 'material_type', 'status', 'order', 'duration', 'created_at')
    list_filter = ('material_type', 'status', 'stand__department__store', 'stand__department', 'stand')
    search_fields = ('stand__name', 'stand__department__name', 'stand__department__store__name')
    ordering = ('stand', 'order')


class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Informacje osobiste', {'fields': ('first_name', 'last_name', 'email')}),
        ('Uprawnienia', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Zarządzane obiekty', {'fields': ('managed_store', 'managed_stand')}),
        ('API Access', {'fields': ('access_token',)}),
        ('Daty', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'role'),
        }),
    )
    search_fields = ('username', 'email', 'first_name', 'last_name')

admin.site.register(User, CustomUserAdmin)