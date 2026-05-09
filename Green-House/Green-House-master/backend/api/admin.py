from django.contrib import admin
from .models import Alert, Device, DeviceCommand, DeviceState, SensorData


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'code', 'device_type', 'status', 'is_enabled', 'last_seen_at')
    search_fields = ('name', 'code')
    list_filter = ('device_type', 'status', 'is_enabled')


@admin.register(DeviceState)
class DeviceStateAdmin(admin.ModelAdmin):
    list_display = ('device', 'is_on', 'desired_on', 'last_command', 'updated_at')


@admin.register(SensorData)
class SensorDataAdmin(admin.ModelAdmin):
    list_display = ('id', 'temperature', 'humidity', 'light', 'soil_moisture', 'recorded_at')
    date_hierarchy = 'recorded_at'


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('id', 'level', 'title', 'is_read', 'happened_at', 'device')
    list_filter = ('level', 'is_read')


@admin.register(DeviceCommand)
class DeviceCommandAdmin(admin.ModelAdmin):
    list_display = ('id', 'device', 'command', 'value', 'status', 'created_at', 'acked_at')
    list_filter = ('status', 'device')