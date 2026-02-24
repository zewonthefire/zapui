from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy


class AccountLoginView(LoginView):
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True


class AccountLogoutView(LogoutView):
    next_page = reverse_lazy('login')
