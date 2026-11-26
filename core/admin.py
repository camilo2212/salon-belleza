from django.contrib import admin
from django.utils import timezone

from .models import Appointment, Customer, Product, Service

admin.site.site_header = "Salón de Belleza - Panel"
admin.site.site_title = "Salón de Belleza"
admin.site.index_title = "Administración del salón"


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "duration_minutes", "price", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    list_editable = ("is_active",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "stock", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    list_editable = ("price", "stock", "is_active")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "created_at")
    search_fields = ("name", "phone")


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("start_local", "customer", "service", "status")
    list_filter = ("status", "start")
    search_fields = ("customer__name", "customer__phone")
    date_hierarchy = "start"
    autocomplete_fields = ("customer",)
    actions = ["confirm", "cancel"]

    @admin.display(description="Inicio", ordering="start")
    def start_local(self, obj):
        return timezone.localtime(obj.start).strftime("%d/%m/%Y %H:%M")

    @admin.action(description="Confirmar citas seleccionadas")
    def confirm(self, request, queryset):
        queryset.update(status=Appointment.Status.CONFIRMED)

    @admin.action(description="Cancelar citas seleccionadas")
    def cancel(self, request, queryset):
        queryset.update(status=Appointment.Status.CANCELLED)
