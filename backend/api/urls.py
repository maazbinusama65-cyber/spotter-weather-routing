from django.urls import path

from . import views

urlpatterns = [
    path("health", views.health, name="health"),
    path("analyze", views.analyze, name="analyze"),
    path("geocode", views.geocode, name="geocode"),
]
