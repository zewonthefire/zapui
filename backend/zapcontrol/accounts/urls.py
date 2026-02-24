from django.urls import path

from .views import AccountLoginView, AccountLogoutView

urlpatterns = [
    path('login', AccountLoginView.as_view(), name='login'),
    path('logout', AccountLogoutView.as_view(), name='logout'),
]
