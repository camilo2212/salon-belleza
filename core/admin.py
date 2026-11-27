from datetime import datetime, time, timedelta

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Max, Q
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.html import format_html

from .models import Appointment, Customer, Product, Service
from .whatsapp import confirmation_message, whatsapp_url

admin.site.site_header = "Salón de Belleza - Panel"
admin.site.site_title = "Salón de Belleza"
admin.site.index_title = "Administración del salón"


LOW_STOCK = 3  # de este número hacia abajo se avisa "pocas existencias"


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    # Precio, duración y visibilidad se editan directo en la lista, sin abrir cada servicio.
    list_display = ("name", "duration_minutes", "price", "is_active")
    list_editable = ("duration_minutes", "price", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


class StockFilter(admin.SimpleListFilter):
    title = "existencias"
    parameter_name = "stock"

    def lookups(self, request, model_admin):
        return [("out", "Agotados"), ("low", f"Pocas (hasta {LOW_STOCK})")]

    def queryset(self, request, queryset):
        if self.value() == "out":
            return queryset.filter(stock=0)
        if self.value() == "low":
            return queryset.filter(stock__lte=LOW_STOCK)
        return queryset


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("thumbnail", "name", "price", "stock", "stock_status", "is_active")
    list_display_links = ("thumbnail", "name")
    list_editable = ("price", "stock", "is_active")
    list_filter = ("is_active", StockFilter)
    search_fields = ("name",)
    readonly_fields = ("preview",)
    fields = ("name", "description", "price", "stock", "image", "preview", "is_active")

    @admin.display(description="Foto")
    def thumbnail(self, obj):
        if not obj.image:
            return "-"
        return format_html(
            '<img src="{}" alt="" style="height:44px;width:44px;object-fit:cover;border-radius:6px">',
            obj.image.url,
        )

    @admin.display(description="Vista previa")
    def preview(self, obj):
        if not obj.image:
            return "Aún no hay foto."
        return format_html(
            '<img src="{}" alt="" style="max-height:180px;max-width:100%;border-radius:8px">',
            obj.image.url,
        )

    @admin.display(description="Estado", ordering="stock")
    def stock_status(self, obj):
        if obj.stock == 0:
            return format_html('<strong style="color:#b91c1c">Agotado</strong>')
        if obj.stock <= LOW_STOCK:
            return format_html('<strong style="color:#b45309">Pocas</strong>')
        return format_html('<span style="color:#15803d">Disponible</span>')


class CustomerAppointmentInline(admin.TabularInline):
    """Historial de citas dentro de la ficha de la clienta (solo lectura)."""

    model = Appointment
    extra = 0
    max_num = 0
    can_delete = False
    show_change_link = True
    ordering = ("-start",)
    fields = ("start", "service", "status")
    readonly_fields = ("start", "service", "status")
    verbose_name_plural = "historial de citas"


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "visits", "last_visit", "no_shows", "whatsapp")
    search_fields = ("name", "phone")
    inlines = [CustomerAppointmentInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _visits=Count(
                "appointments",
                filter=Q(appointments__status=Appointment.Status.COMPLETED),
            ),
            _last=Max("appointments__start"),
            _no_shows=Count(
                "appointments", filter=Q(appointments__status=Appointment.Status.NO_SHOW)
            ),
        )

    @admin.display(description="Visitas", ordering="_visits")
    def visits(self, obj):
        return obj._visits

    @admin.display(description="Última cita", ordering="_last")
    def last_visit(self, obj):
        if not obj._last:
            return "-"
        return timezone.localtime(obj._last).strftime("%d/%m/%Y")

    @admin.display(description="No asistió", ordering="_no_shows")
    def no_shows(self, obj):
        if obj._no_shows:
            return format_html('<strong style="color:#b91c1c">{}</strong>', obj._no_shows)
        return 0

    @admin.display(description="Escribir")
    def whatsapp(self, obj):
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">WhatsApp</a>', whatsapp_url(obj.phone)
        )


class WhenFilter(admin.SimpleListFilter):
    """Filtros rápidos por fecha para la agenda: Hoy, Mañana, Esta semana..."""

    title = "cuándo"
    parameter_name = "when"

    def lookups(self, request, model_admin):
        return [
            ("upcoming", "Próximas"),
            ("today", "Hoy"),
            ("tomorrow", "Mañana"),
            ("week", "Próximos 7 días"),
            ("past", "Pasadas"),
            ("all", "Todas"),
        ]

    def choices(self, changelist):
        # Sin la opción "Todas" automática de Django: aquí "Todas" es una opción explícita.
        for value, label in self.lookup_choices:
            yield {
                "selected": self.value() == value,
                "query_string": changelist.get_query_string({self.parameter_name: value}),
                "display": label,
            }

    @staticmethod
    def _midnight(day):
        return timezone.make_aware(datetime.combine(day, time.min))

    def queryset(self, request, queryset):
        today = timezone.localdate()
        value = self.value()
        if value == "upcoming":
            return queryset.filter(start__gte=self._midnight(today))
        if value == "today":
            return queryset.filter(
                start__gte=self._midnight(today), start__lt=self._midnight(today + timedelta(days=1))
            )
        if value == "tomorrow":
            return queryset.filter(
                start__gte=self._midnight(today + timedelta(days=1)),
                start__lt=self._midnight(today + timedelta(days=2)),
            )
        if value == "week":
            return queryset.filter(
                start__gte=self._midnight(today), start__lt=self._midnight(today + timedelta(days=7))
            )
        if value == "past":
            return queryset.filter(start__lt=self._midnight(today)).order_by("-start")
        return queryset


STATUS_COLORS = {
    Appointment.Status.PENDING: "#b45309",  # ámbar
    Appointment.Status.CONFIRMED: "#15803d",  # verde
    Appointment.Status.COMPLETED: "#475569",  # gris
    Appointment.Status.CANCELLED: "#b91c1c",  # rojo
    Appointment.Status.NO_SHOW: "#7f1d1d",  # rojo oscuro
}


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("start_local", "customer", "phone", "service", "colored_status", "whatsapp")
    list_filter = (WhenFilter, "status", "service")
    list_select_related = ("customer", "service")
    list_per_page = 50
    search_fields = ("customer__name", "customer__phone")
    date_hierarchy = "start"
    autocomplete_fields = ("customer",)
    actions = ["confirm", "cancel", "mark_completed", "mark_no_show"]

    def changelist_view(self, request, extra_context=None):
        # Al abrir la lista sin filtros se muestran las citas de hoy en adelante.
        if request.method == "GET" and not request.GET:
            return redirect(f"{request.path}?{WhenFilter.parameter_name}=upcoming")
        return super().changelist_view(request, extra_context)

    @admin.display(description="Inicio", ordering="start")
    def start_local(self, obj):
        return timezone.localtime(obj.start).strftime("%d/%m/%Y %H:%M")

    @admin.display(description="WhatsApp", ordering="customer__phone")
    def phone(self, obj):
        return obj.customer.phone

    @admin.display(description="Estado", ordering="status")
    def colored_status(self, obj):
        color = STATUS_COLORS.get(obj.status, "#475569")
        return format_html(
            '<strong style="color:{}">{}</strong>', color, obj.get_status_display()
        )

    @admin.display(description="Escribir")
    def whatsapp(self, obj):
        if obj.status not in (Appointment.Status.PENDING, Appointment.Status.CONFIRMED):
            return "-"
        url = whatsapp_url(obj.customer.phone, confirmation_message(obj))
        return format_html('<a href="{}" target="_blank" rel="noopener">Confirmar por WhatsApp</a>', url)

    def _change_status(self, request, queryset, new_status, label):
        """Cambia el estado cita por cita, respetando las validaciones del modelo."""
        done = 0
        for appt in queryset.select_related("customer", "service"):
            appt.status = new_status
            try:
                appt.full_clean()
            except ValidationError as err:
                self.message_user(
                    request, f"No se pudo {label} la cita de {appt}: {'; '.join(err.messages)}",
                    level=messages.ERROR,
                )
                continue
            appt.save()
            done += 1
        if done:
            self.message_user(request, f"{done} cita(s): {label} correctamente.")

    @admin.action(description="Confirmar citas seleccionadas")
    def confirm(self, request, queryset):
        self._change_status(request, queryset, Appointment.Status.CONFIRMED, "confirmar")

    @admin.action(description="Cancelar citas seleccionadas")
    def cancel(self, request, queryset):
        self._change_status(request, queryset, Appointment.Status.CANCELLED, "cancelar")

    @admin.action(description="Marcar como realizadas")
    def mark_completed(self, request, queryset):
        self._change_status(request, queryset, Appointment.Status.COMPLETED, "marcar como realizada")

    @admin.action(description="Marcar como 'No asistió'")
    def mark_no_show(self, request, queryset):
        self._change_status(request, queryset, Appointment.Status.NO_SHOW, "marcar como 'No asistió'")
