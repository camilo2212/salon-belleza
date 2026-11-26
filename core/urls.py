from django.urls import path

from . import views

urlpatterns = [
    path("services/", views.ServiceListView.as_view()),
    path("products/", views.ProductListView.as_view()),
    path("availability/", views.AvailabilityView.as_view()),
    path("appointments/", views.BookingView.as_view()),
]
