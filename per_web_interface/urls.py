"""
URL configuration for per_web_interface project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('results_viewer.urls')),
]