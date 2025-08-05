from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from rest_framework.authtoken.models import Token
from django.contrib.auth.mixins import LoginRequiredMixin

from datetime import datetime, timedelta

from .models import Store, Department, Stand, AdvertisementMaterial, EmissionSchedule
from accounts.permissions import SuperadminRequiredMixin, StoreAdminRequiredMixin, EditorRequiredMixin, StoreAccessMixin
from .forms import AdvertisementMaterialForm, StandAnimationForm, EmissionScheduleForm
from django.utils.timezone import now


class PlayerView(TemplateView):
    template_name = 'player/player.html'

    def dispatch(self, request, *args, **kwargs):
        # Aktualizacja harmonogramów
        from advertisements.models import EmissionSchedule
        schedules = EmissionSchedule.objects.filter(is_active=True)
        for schedule in schedules:
            schedule.apply_schedule()
        return super().dispatch(request, *args, **kwargs)


class StandMaterialsView(LoginRequiredMixin, DetailView):
    model = Stand
    template_name = 'advertisements/stand_materials.html'
    context_object_name = 'stand'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['materials'] = self.object.materials.all().order_by('order')
        context['form'] = AdvertisementMaterialForm(initial={'stand': self.object})
        token, created = Token.objects.get_or_create(user=self.request.user)
        context['token'] = token.key
        return context


@require_POST
@login_required
def update_material_order(request, stand_id):
    stand = get_object_or_404(Stand, pk=stand_id)
    user = request.user

    if not (user.is_superadmin() or
            (user.is_store_admin() and user.managed_store == stand.department.store) or
            (user.is_editor() and user.managed_stand == stand)):
        return JsonResponse({'status': 'error', 'message': 'Brak uprawnień'}, status=403)

    try:
        materials_order = request.POST.getlist('materials[]')
        for idx, material_id in enumerate(materials_order):
            material = AdvertisementMaterial.objects.get(pk=material_id)
            if material.stand != stand:
                return JsonResponse({'status': 'error', 'message': 'Niedozwolona operacja'}, status=400)
            material.order = idx
            material.save()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


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
        form.instance.order = AdvertisementMaterial.objects.filter(stand=form.instance.stand).count()
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
        return reverse('stand-materials', kwargs={'pk': self.object.stand.pk})

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        messages.success(self.request, "Materiał został usunięty.")
        return response


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


class DepartmentCreateView(StoreAdminRequiredMixin, CreateView):
    model = Department
    fields = ['name', 'store']
    template_name = 'advertisements/department_form.html'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        user = self.request.user
        if user.is_store_admin() and not user.is_superadmin():
            form.fields['store'].queryset = Store.objects.filter(id=user.managed_store.id)
            form.fields['store'].initial = user.managed_store
            form.fields['store'].widget.attrs['disabled'] = True
        return form

    def form_valid(self, form):
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
        messages.success(self.request, f"Dział '{department.name}' został usunięty.")
        return super().delete(request, *args, **kwargs)


class StandCreateView(StoreAdminRequiredMixin, CreateView):
    model = Stand
    fields = ['name', 'department', 'display_time', 'transition_animation']
    template_name = 'advertisements/stand_form.html'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        user = self.request.user
        if user.is_superadmin():
            pass
        elif user.is_store_admin() and user.managed_store:
            form.fields['department'].queryset = Department.objects.filter(store=user.managed_store)

        department_id = self.kwargs.get('department_id')
        if department_id:
            form.fields['department'].initial = Department.objects.get(id=department_id)

        return form

    def get_success_url(self):
        return reverse('stand-materials', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
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
        return reverse('store-detail', kwargs={'pk': self.object.department.store.pk})

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


class ScheduleCalendarView(LoginRequiredMixin, TemplateView):
    template_name = 'advertisements/schedule_calendar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stand_id = self.kwargs.get('stand_id')
        stand = get_object_or_404(Stand, id=stand_id)
        context['stand'] = stand
        context['materials'] = stand.materials.all()
        return context


class ScheduleCreateView(EditorRequiredMixin, StoreAccessMixin, CreateView):
    model = EmissionSchedule
    form_class = EmissionScheduleForm
    template_name = 'advertisements/schedule_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stand_id = self.kwargs.get('stand_id')
        if stand_id:
            context['materials'] = get_object_or_404(Stand, pk=stand_id).materials.all()

        selected_material_ids = self.request.GET.getlist('material_ids')
        context['selected_material_ids'] = selected_material_ids
        return context

    def form_valid(self, form):
        self.object = form.save()
        material_ids = self.request.POST.getlist('materials')
        if material_ids:
            materials = AdvertisementMaterial.objects.filter(pk__in=material_ids)
            self.object.materials.set(materials)
        return super().form_valid(form)

    def get_success_url(self):
        stand_id = self.kwargs.get('stand_id')
        return reverse('schedule-calendar', kwargs={'stand_id': stand_id})


class ScheduleUpdateView(EditorRequiredMixin, StoreAccessMixin, UpdateView):
    model = EmissionSchedule
    form_class = EmissionScheduleForm
    template_name = 'advertisements/schedule_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.object:
            first_material = self.object.materials.first()
            if first_material:
                context['materials'] = first_material.stand.materials.all()
            else:
                context['materials'] = AdvertisementMaterial.objects.none()

        # Pobierz ID materiałów przypisanych do tego harmonogramu, aby zaznaczyć je w formularzu
        context['selected_material_ids'] = [str(m.id) for m in self.object.materials.all()]
        return context

    def get_success_url(self):
        # Pobierz stand_id przed zapisaniem zmian, aby poprawnie przekierować
        stand_id = self.object.materials.first().stand.id if self.object.materials.first() else None
        if stand_id:
            return reverse('schedule-calendar', kwargs={'stand_id': stand_id})
        # W przypadku braku materiałów, przekieruj do listy sklepów
        return reverse('store-list')


class ScheduleDeleteView(EditorRequiredMixin, StoreAccessMixin, DeleteView):
    model = EmissionSchedule
    template_name = 'advertisements/schedule_confirm_delete.html'

    def get_success_url(self):
        # Pobierz stand_id przed usunięciem harmonogramu, ponieważ obiekt zostanie zniszczony
        stand = self.object.materials.first().stand if self.object.materials.first() else None
        if stand:
            return reverse('schedule-calendar', kwargs={'stand_id': stand.id})
        return reverse_lazy('store-list')


def get_schedule_events(request, stand_id):
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')

    if start_date and end_date:
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    else:
        today = datetime.today()
        start = datetime(today.year, today.month, 1)
        end = start + timedelta(days=42)

    schedules = EmissionSchedule.objects.filter(materials__stand_id=stand_id).distinct()

    events = []
    for schedule in schedules:
        materials_data = []
        for material in schedule.materials.all():
            materials_data.append({
                'id': material.id,
                'type': material.get_material_type_display(),
            })

        event_start_time = schedule.start_time.isoformat()
        event_end_time = schedule.end_time.isoformat()

        # Zmodyfikowany kod do obsługi eventów z wieloma materiałami
        event_title = f"{schedule.name} ({', '.join([mat['type'] for mat in materials_data])})"

        base_event = {
            'id': schedule.id,
            'title': event_title,
            'backgroundColor': '#3788d8',  # Domyślny kolor
            'borderColor': '#3788d8',
            'textColor': '#ffffff',
            'extendedProps': {
                'materials': materials_data,
                'repeat_type': schedule.repeat_type,
                'priority': schedule.priority,
                'stand_id': stand_id,
            }
        }

        if schedule.repeat_type == 'none':
            base_event.update({
                'start': f"{schedule.start_date.isoformat()}T{event_start_time}",
                'end': f"{schedule.start_date.isoformat()}T{event_end_time}",
            })
            events.append(base_event)

        elif schedule.repeat_type == 'daily':
            base_event.update({
                'daysOfWeek': [0, 1, 2, 3, 4, 5, 6],
                'startTime': event_start_time,
                'endTime': event_end_time,
                'startRecur': schedule.start_date.isoformat(),
                'endRecur': schedule.end_date.isoformat() if schedule.end_date else None
            })
            events.append(base_event)

        elif schedule.repeat_type == 'weekly' and schedule.repeat_days:
            base_event.update({
                'daysOfWeek': [int(day) for day in schedule.repeat_days],
                'startTime': event_start_time,
                'endTime': event_end_time,
                'startRecur': schedule.start_date.isoformat(),
                'endRecur': schedule.end_date.isoformat() if schedule.end_date else None
            })
            events.append(base_event)

        elif schedule.repeat_type == 'monthly':
            current_date = schedule.start_date
            while current_date <= (schedule.end_date or end.date()):
                if current_date.day == schedule.start_date.day and current_date >= start.date():
                    monthly_event = base_event.copy()
                    monthly_event['start'] = f"{current_date.isoformat()}T{event_start_time}"
                    monthly_event['end'] = f"{current_date.isoformat()}T{event_end_time}"
                    events.append(monthly_event)

                next_month = current_date.month + 1
                year = current_date.year + (next_month > 12)
                month = (next_month - 1) % 12 + 1

                try:
                    current_date = current_date.replace(year=year, month=month)
                except ValueError:
                    # Obsługa błędów, gdy miesiąc nie ma danego dnia (np. 31 lutego)
                    last_day_of_month = (current_date.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(
                        days=1)
                    current_date = last_day_of_month.replace(year=year, month=month)

    return JsonResponse(events, safe=False)