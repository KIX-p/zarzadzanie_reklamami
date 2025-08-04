from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from rest_framework.authtoken.models import Token

from .models import Store, Department, Stand, AdvertisementMaterial
from accounts.permissions import SuperadminRequiredMixin, StoreAdminRequiredMixin, EditorRequiredMixin, StoreAccessMixin
from .forms import AdvertisementMaterialForm, StandAnimationForm

# Istniejący widok PlayerView
class PlayerView(TemplateView):
    """Simple player view to display advertisements"""
    template_name = 'player/player.html'

# Nowe widoki zarządzania materiałami
class StandMaterialsView(EditorRequiredMixin, StoreAccessMixin, DetailView):
    """
    View for managing stand materials with drag & drop interface
    """
    model = Stand
    template_name = 'advertisements/stand_materials.html'
    context_object_name = 'stand'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['materials'] = self.object.materials.all().order_by('order')
        context['form'] = AdvertisementMaterialForm(initial={'stand': self.object})

        # Tutaj mamy dostęp do self.request
        token, created = Token.objects.get_or_create(user=self.request.user)
        context['token'] = token.key
        return context
@require_POST
@login_required
def update_material_order(request, stand_id):
    """
    AJAX endpoint for updating material order via drag & drop
    """
    # Check permissions
    stand = get_object_or_404(Stand, pk=stand_id)
    user = request.user
    
    # Permission check
    if not (user.is_superadmin() or 
           (user.is_store_admin() and user.managed_store == stand.department.store) or
           (user.is_editor() and user.managed_stand == stand)):
        return JsonResponse({'status': 'error', 'message': 'Brak uprawnień'}, status=403)
    
    # Get the new order from the request
    try:
        materials_order = request.POST.getlist('materials[]')
        
        # Update the order for each material
        for idx, material_id in enumerate(materials_order):
            material = AdvertisementMaterial.objects.get(pk=material_id)
            # Check if material belongs to this stand
            if material.stand != stand:
                return JsonResponse({
                    'status': 'error', 
                    'message': 'Niedozwolona operacja'
                }, status=400)
                
            material.order = idx
            material.save()
        
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

# Material CRUD views
class MaterialCreateView(EditorRequiredMixin, StoreAccessMixin, CreateView):
    model = AdvertisementMaterial
    form_class = AdvertisementMaterialForm
    template_name = 'advertisements/material_form.html'
    
    def get_initial(self):
        initial = super().get_initial()
        stand_id = self.kwargs.get('stand_id')
        if stand_id:
            initial['stand'] = get_object_or_404(Stand, pk=stand_id)
        return initial
    
    def form_valid(self, form):
        form.instance.order = AdvertisementMaterial.objects.filter(
            stand=form.instance.stand).count()
        response = super().form_valid(form)
        messages.success(self.request, "Materiał został dodany pomyślnie.")
        return response
    
    def get_success_url(self):
        return reverse('stand-materials', kwargs={'pk': self.object.stand.pk})

class MaterialUpdateView(EditorRequiredMixin, StoreAccessMixin, UpdateView):
    model = AdvertisementMaterial
    form_class = AdvertisementMaterialForm
    template_name = 'advertisements/material_form.html'
    context_object_name = 'material'
    
    def get_success_url(self):
        return reverse('stand-materials', kwargs={'pk': self.object.stand.pk})
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Materiał został zaktualizowany.")
        return response

class MaterialDeleteView(EditorRequiredMixin, StoreAccessMixin, DeleteView):
    model = AdvertisementMaterial
    template_name = 'advertisements/material_confirm_delete.html'
    context_object_name = 'material'
    
    def get_success_url(self):
        stand_id = self.object.stand.id
        return reverse('stand-materials', kwargs={'pk': stand_id})
    
    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        messages.success(self.request, "Materiał został usunięty.")
        return response


# Dodaj te widoki do istniejącego pliku

# Store views
class StoreListView(SuperadminRequiredMixin, ListView):
    model = Store
    template_name = 'advertisements/store_list.html'
    context_object_name = 'stores'
    ordering = ['name']

class StoreCreateView(SuperadminRequiredMixin, CreateView):
    model = Store
    fields = ['name', 'location']
    template_name = 'advertisements/store_form.html'
    success_url = reverse_lazy('store-list')
    
    def form_valid(self, form):
        messages.success(self.request, f"Sklep '{form.instance.name}' został utworzony.")
        return super().form_valid(form)

class StoreUpdateView(SuperadminRequiredMixin, UpdateView):
    model = Store
    fields = ['name', 'location']
    template_name = 'advertisements/store_form.html'
    
    def get_success_url(self):
        return reverse('store-detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, f"Sklep '{form.instance.name}' został zaktualizowany.")
        return super().form_valid(form)

class StoreDetailView(StoreAdminRequiredMixin, DetailView):
    model = Store
    template_name = 'advertisements/store_detail.html'
    context_object_name = 'store'
    
    def test_func(self):
        obj = self.get_object()
        return (self.request.user.is_superadmin() or 
                (self.request.user.is_store_admin() and self.request.user.managed_store == obj))

class StoreDeleteView(SuperadminRequiredMixin, DeleteView):
    model = Store
    template_name = 'advertisements/store_confirm_delete.html'
    success_url = reverse_lazy('store-list')
    context_object_name = 'store'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['department_count'] = self.object.departments.count()
        return context
    
    def delete(self, request, *args, **kwargs):
        store = self.get_object()
        result = super().delete(request, *args, **kwargs)
        messages.success(self.request, f"Sklep '{store.name}' został usunięty.")
        return result

# Department views
class DepartmentCreateView(StoreAdminRequiredMixin, CreateView):
    model = Department
    fields = ['name', 'store']
    template_name = 'advertisements/department_form.html'
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Ogranicz wybór sklepów
        user = self.request.user
        if user.is_store_admin() and not user.is_superadmin():
            form.fields['store'].queryset = Store.objects.filter(id=user.managed_store.id)
            form.fields['store'].initial = user.managed_store
            form.fields['store'].widget.attrs['disabled'] = True
        return form
    
    def form_valid(self, form):
        # Zapewnij, że admin sklepu może dodać dział tylko do swojego sklepu
        user = self.request.user
        if user.is_store_admin() and not user.is_superadmin():
            form.instance.store = user.managed_store
            
        messages.success(self.request, f"Dział '{form.instance.name}' został utworzony.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('store-detail', kwargs={'pk': self.object.store.pk})

class DepartmentUpdateView(StoreAdminRequiredMixin, StoreAccessMixin, UpdateView):
    model = Department
    fields = ['name']
    template_name = 'advertisements/department_form.html'
    
    def get_success_url(self):
        return reverse('store-detail', kwargs={'pk': self.object.store.pk})
    
    def form_valid(self, form):
        messages.success(self.request, f"Dział '{form.instance.name}' został zaktualizowany.")
        return super().form_valid(form)

class DepartmentDeleteView(StoreAdminRequiredMixin, StoreAccessMixin, DeleteView):
    model = Department
    template_name = 'advertisements/department_confirm_delete.html'
    context_object_name = 'department'
    
    def get_success_url(self):
        return reverse('store-detail', kwargs={'pk': self.object.store.pk})
    
    def delete(self, request, *args, **kwargs):
        department = self.get_object()
        store_id = department.store.id
        messages.success(self.request, f"Dział '{department.name}' został usunięty.")
        return super().delete(request, *args, **kwargs)

# Stand views
class StandCreateView(StoreAdminRequiredMixin, CreateView):
    model = Stand
    fields = ['name', 'department', 'display_time', 'transition_animation']
    template_name = 'advertisements/stand_form.html'
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Ogranicz wybór działów
        user = self.request.user
        if user.is_superadmin():
            pass  # Superadmin widzi wszystko
        elif user.is_store_admin() and user.managed_store:
            form.fields['department'].queryset = Department.objects.filter(store=user.managed_store)
        
        # Predefiniowany dział z URL
        department_id = self.kwargs.get('department_id')
        if department_id:
            form.fields['department'].initial = Department.objects.get(id=department_id)
            
        return form
    
    def get_success_url(self):
        return reverse('stand-materials', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        # Sprawdź, czy użytkownik ma dostęp do wybranego działu
        user = self.request.user
        department = form.cleaned_data['department']
        
        if user.is_store_admin() and department.store != user.managed_store and not user.is_superadmin():
            form.add_error('department', 'Nie masz uprawnień do tego działu.')
            return self.form_invalid(form)
            
        messages.success(self.request, f"Stoisko '{form.instance.name}' zostało utworzone.")
        return super().form_valid(form)

class StandUpdateView(EditorRequiredMixin, StoreAccessMixin, UpdateView):
    model = Stand
    fields = ['name', 'display_time', 'transition_animation']
    template_name = 'advertisements/stand_form.html'
    
    def get_success_url(self):
        return reverse('stand-materials', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, f"Stoisko '{form.instance.name}' zostało zaktualizowane.")
        return super().form_valid(form)

class StandDeleteView(StoreAdminRequiredMixin, StoreAccessMixin, DeleteView):
    model = Stand
    template_name = 'advertisements/stand_confirm_delete.html'
    context_object_name = 'stand'
    
    def get_success_url(self):
        department_id = self.object.department.id
        store_id = self.object.department.store.id
        return reverse('store-detail', kwargs={'pk': store_id})
    
    def delete(self, request, *args, **kwargs):
        stand = self.get_object()
        messages.success(self.request, f"Stoisko '{stand.name}' zostało usunięte.")
        return super().delete(request, *args, **kwargs)


class StandAnimationUpdateView(EditorRequiredMixin, StoreAccessMixin, UpdateView):
    model = Stand
    form_class = StandAnimationForm
    template_name = 'advertisements/stand_animation_form.html'

    def get_success_url(self):
        messages.success(self.request, "Animacja została zaktualizowana.")
        return reverse('stand-materials', kwargs={'pk': self.object.pk})