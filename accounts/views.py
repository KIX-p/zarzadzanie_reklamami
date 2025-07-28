from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib import messages
from rest_framework.authtoken.models import Token

from .forms import LoginForm, RegistrationForm
from .models import User

class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    form_class = LoginForm
    redirect_authenticated_user = True
    
    def get_success_url(self):
        return reverse_lazy('dashboard')
    
    def form_invalid(self, form):
        messages.error(self.request, "Nieprawidłowa nazwa użytkownika lub hasło.")
        return super().form_invalid(form)

class RegisterView(CreateView):
    model = User
    template_name = 'accounts/register.html'
    form_class = RegistrationForm
    success_url = reverse_lazy('login')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Rejestracja zakończona sukcesem. Możesz się teraz zalogować.")
        return response
    
    def form_invalid(self, form):
        messages.error(self.request, "Wystąpił błąd podczas rejestracji.")
        return super().form_invalid(form)

class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('login')

@login_required
def dashboard(request):
    """
    Main dashboard view for logged in users.
    Content depends on user role.
    """
    user = request.user
    context = {'user': user}
    
    # W funkcji dashboard, w sekcji dla superadmina:
    if user.is_superadmin():
        # Superadmin sees all stores
        from advertisements.models import Store, Stand, PlayerStatus
        from django.db.models import Count
        
        stores = Store.objects.all()
        context['stores'] = stores
        
        # Count stats
        stands_count = Stand.objects.count()
        users_count = User.objects.count()
        
        # Count active players
        active_players = PlayerStatus.objects.filter(is_online=True).count()
        
        context['stands_count'] = stands_count
        context['users_count'] = users_count
        context['active_players'] = active_players
        
        return render(request, 'accounts/dashboard_superadmin.html', context)
        
    elif user.is_store_admin():
        # Store admin sees only their store
        context['store'] = user.managed_store
        
        if user.managed_store:
            # Get departments and stands
            departments = user.managed_store.departments.all()
            
            # Count stands and materials
            stands_count = 0
            materials_count = 0
            for dept in departments:
                stands = dept.stands.all()
                stands_count += stands.count()
                for stand in stands:
                    materials_count += stand.materials.count()
            
            context['departments'] = departments
            context['stands_count'] = stands_count
            context['materials_count'] = materials_count
        
        return render(request, 'accounts/dashboard_store_admin.html', context)
        
    elif user.is_editor():
        # Editor sees only their stand
        stand = user.managed_stand
        context['stand'] = stand
        
        if stand:
            context['materials'] = stand.materials.all().order_by('order')
            context['active_materials'] = stand.materials.filter(status='active').count()
            context['inactive_materials'] = stand.materials.filter(status='inactive').count()
        
        return render(request, 'accounts/dashboard_editor.html', context)
        
    elif user.is_player():
        # Player sees minimal interface with token and QR code
        stand = user.managed_stand
        context['stand'] = stand
        
        
        token, created = Token.objects.get_or_create(user=user)
        context['token'] = token.key
        
        return render(request, 'accounts/dashboard_player.html', context)
        
    # Fallback for users without specific role
    return render(request, 'accounts/dashboard.html', context)