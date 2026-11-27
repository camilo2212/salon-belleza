from datetime import date

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .availability import available_slots
from .models import Appointment, Product, Service
from .notifications import notify_cancellation
from .serializers import (
    AppointmentConfirmationSerializer,
    BookingSerializer,
    LoginSerializer,
    MyAppointmentSerializer,
    ProductSerializer,
    RegisterSerializer,
    ServiceSerializer,
    profile,
)


class ServiceListView(generics.ListAPIView):
    queryset = Service.objects.filter(is_active=True)
    serializer_class = ServiceSerializer
    pagination_class = None


class ProductListView(generics.ListAPIView):
    queryset = Product.objects.filter(is_active=True)
    serializer_class = ProductSerializer
    pagination_class = None


class AvailabilityView(APIView):
    """GET /api/availability/?service=1&date=2026-12-01"""

    def get(self, request):
        try:
            service = Service.objects.get(pk=request.query_params.get("service"), is_active=True)
            day = date.fromisoformat(request.query_params.get("date", ""))
        except (Service.DoesNotExist, ValueError, TypeError):
            return Response(
                {"detail": "Indica un servicio válido y una fecha con formato AAAA-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if day < timezone.localdate():
            return Response({"date": day, "slots": []})
        slots = [timezone.localtime(s).isoformat() for s in available_slots(day, service.duration_minutes)]
        return Response({"date": day, "service": service.id, "slots": slots})


class BookingView(generics.CreateAPIView):
    """POST /api/appointments/  {name, phone, service, start}"""

    serializer_class = BookingSerializer

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        user = request.user if request.user.is_authenticated and not request.user.is_staff else None
        if user:
            # Con sesión iniciada se usan los datos de la cuenta, no los del formulario.
            data["name"] = user.first_name or user.username
            data["phone"] = user.username
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        appointment = serializer.save(user=user)
        return Response(
            AppointmentConfirmationSerializer(appointment).data, status=status.HTTP_201_CREATED
        )


# --- Cuentas de clientas -------------------------------------------------------


class AuthEntryView(APIView):
    """Base de registro e ingreso: sin autenticación previa y con límite de intentos."""

    authentication_classes = []  # un token viejo no debe impedir ingresar de nuevo
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def token_response(self, user, http_status):
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": profile(user)}, status=http_status)


class RegisterView(AuthEntryView):
    """POST /api/auth/register/  {name, phone, password}"""

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self.token_response(serializer.save(), status.HTTP_201_CREATED)


class LoginView(AuthEntryView):
    """POST /api/auth/login/  {phone, password}"""

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return self.token_response(serializer.validated_data["user"], status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.auth.delete()  # el token deja de servir en todos los dispositivos
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(profile(request.user))


class MyAppointmentsView(generics.ListAPIView):
    """GET /api/my/appointments/ : solo las citas reservadas con la cuenta de la clienta."""

    permission_classes = [IsAuthenticated]
    serializer_class = MyAppointmentSerializer
    pagination_class = None

    def get_queryset(self):
        return (
            Appointment.objects.filter(user=self.request.user)
            .select_related("service")
            .order_by("-start")[:60]
        )


class CancelMyAppointmentView(APIView):
    """POST /api/my/appointments/<id>/cancel/"""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        appointment = get_object_or_404(
            Appointment.objects.select_related("customer", "service"), pk=pk, user=request.user
        )
        if appointment.status not in (Appointment.Status.PENDING, Appointment.Status.CONFIRMED):
            return Response(
                {"detail": "Esta cita ya no se puede cancelar."}, status=status.HTTP_400_BAD_REQUEST
            )
        if not appointment.can_be_cancelled_by_client():
            hours = getattr(settings, "SALON_CANCEL_MIN_HOURS", 2)
            return Response(
                {"detail": f"Con menos de {hours} horas de anticipación no se puede cancelar aquí. "
                           "Escríbenos por WhatsApp."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        appointment.status = Appointment.Status.CANCELLED
        appointment.save(update_fields=["status"])
        transaction.on_commit(lambda: notify_cancellation(appointment))
        return Response(MyAppointmentSerializer(appointment).data)
