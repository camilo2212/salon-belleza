from django.urls import path

from . import views

urlpatterns = [
    path("services/", views.ServiceListView.as_view()),
    path("products/", views.ProductListView.as_view()),
    path("availability/", views.AvailabilityView.as_view()),
    path("appointments/", views.BookingView.as_view()),
    path("auth/register/", views.RegisterView.as_view()),
    path("auth/login/", views.LoginView.as_view()),
    path("auth/logout/", views.LogoutView.as_view()),
    path("auth/me/", views.MeView.as_view()),
    path("my/appointments/", views.MyAppointmentsView.as_view()),
    path("my/appointments/<int:pk>/cancel/", views.CancelMyAppointmentView.as_view()),
]
