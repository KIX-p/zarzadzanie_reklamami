from django.contrib import admin
from .models import Store, Department, Stand, AdvertisementMaterial, EmissionSchedule, PlayerStatus

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'created_at', 'updated_at')

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'created_at', 'updated_at')

@admin.register(Stand)
class StandAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'display_time', 'transition_animation')

@admin.register(AdvertisementMaterial)
class AdvertisementMaterialAdmin(admin.ModelAdmin):
    list_display = ('id', 'stand', 'material_type', 'status', 'expires_at', 'order')
    list_filter = ('material_type', 'status')
    search_fields = ('stand__name',)

@admin.register(EmissionSchedule)
class EmissionScheduleAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'repeat_type', 'priority', 'is_active')
    filter_horizontal = ('materials',)  # lepsze UI dla ManyToMany
    search_fields = ('name',)

@admin.register(PlayerStatus)
class PlayerStatusAdmin(admin.ModelAdmin):
    list_display = ('stand', 'is_online', 'last_seen', 'ip_address')

