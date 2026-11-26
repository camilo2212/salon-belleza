from datetime import date

from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .availability import available_slots
from .models import Product, Service
from .serializers import (
    AppointmentConfirmationSerializer,
    BookingSerializer,
    ProductSerializer,
    ServiceSerializer,
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
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        appointment = serializer.save()
        return Response(
            AppointmentConfirmationSerializer(appointment).data, status=status.HTTP_201_CREATED
        )
