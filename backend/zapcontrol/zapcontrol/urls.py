from django.contrib import admin
from django.urls import path

from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health', views.health, name='health'),
    path('setup', views.setup, name='setup'),
    path('', views.index, name='index'),
]
