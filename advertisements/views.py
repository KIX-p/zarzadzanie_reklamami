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
import io
import random
import colorsys
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from django.http import FileResponse, HttpResponse
import csv
import xlsxwriter

from .models import Store, Department, Stand, AdvertisementMaterial, EmissionSchedule
from accounts.permissions import SuperadminRequiredMixin, StoreAdminRequiredMixin, EditorRequiredMixin, StoreAccessMixin
from .forms import AdvertisementMaterialForm, StandAnimationForm, EmissionScheduleForm, MaterialReportForm
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


def get_random_color():
    """Generuje losowy kolor w formacie szesnastkowym."""
    # Użycie HSV dla lepszej różnorodności i czytelności kolorów
    h = random.random()
    s = 0.5 + random.random() * 0.5  # Saturation
    v = 0.5 + random.random() * 0.5  # Value
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


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
        # Pomijaj harmonogramy bez wymaganych dat/godzin
        if not schedule.start_date or not schedule.start_time:
            continue

        # Ustal wartości końcowe, jeśli brak to użyj startowych
        end_date_val = schedule.end_date or schedule.start_date
        end_time_val = schedule.end_time or schedule.start_time

        materials_data = []
        for material in schedule.materials.all():
            materials_data.append({
                'id': material.id,
                'type': material.get_material_type_display(),
            })

        event_start_time = schedule.start_time.isoformat() if schedule.start_time else "00:00:00"
        event_end_time = end_time_val.isoformat() if end_time_val else "23:59:59"

        event_title = f"{schedule.name} ({', '.join([mat['type'] for mat in materials_data])})"

        random_color = get_random_color()

        base_event = {
            'id': schedule.id,
            'title': event_title,
            'backgroundColor': random_color,
            'borderColor': random_color,
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
                'end': f"{end_date_val.isoformat()}T{event_end_time}",
            })
            events.append(base_event)

        elif schedule.repeat_type == 'daily':
            base_event.update({
                'daysOfWeek': [0, 1, 2, 3, 4, 5, 6],
                'startTime': event_start_time,
                'endTime': event_end_time,
                'startRecur': schedule.start_date.isoformat(),
                'endRecur': end_date_val.isoformat() if end_date_val else None
            })
            events.append(base_event)

        elif schedule.repeat_type == 'weekly' and schedule.repeat_days:
            base_event.update({
                'daysOfWeek': [int(day) for day in schedule.repeat_days],
                'startTime': event_start_time,
                'endTime': event_end_time,
                'startRecur': schedule.start_date.isoformat(),
                'endRecur': end_date_val.isoformat() if end_date_val else None
            })
            events.append(base_event)

        elif schedule.repeat_type == 'monthly':
            current_date = schedule.start_date
            end_limit = end_date_val or end.date()
            while current_date <= end_limit:
                if current_date.day == schedule.start_date.day:
                    monthly_event = base_event.copy()
                    monthly_event['start'] = f"{current_date.isoformat()}T{event_start_time}"
                    monthly_event['end'] = f"{current_date.isoformat()}T{event_end_time}"
                    events.append(monthly_event)

                # Obliczenie następnego miesiąca
                next_month = current_date.month + 1
                year = current_date.year + (next_month > 12)
                month = (next_month - 1) % 12 + 1

                try:
                    current_date = current_date.replace(year=year, month=month)
                except ValueError:
                    last_day_of_month = (current_date.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                    current_date = last_day_of_month.replace(year=year, month=month)

    return JsonResponse(events, safe=False)

@login_required
def generate_materials_report(request):
    """
    Widok do generowania zaawansowanych raportów materiałów reklamowych.
    """
    if request.method == 'POST':
        form = MaterialReportForm(request.POST, user=request.user)
        if form.is_valid():
            # Pobierz dane z formularza
            store = form.cleaned_data.get('store')
            department = form.cleaned_data.get('department')
            stand = form.cleaned_data.get('stand')
            material_type = form.cleaned_data.get('material_type')
            status = form.cleaned_data.get('status')
            start_date = form.cleaned_data.get('start_date')
            end_date = form.cleaned_data.get('end_date')
            report_format = form.cleaned_data.get('report_format')
            include_schedules = form.cleaned_data.get('include_schedules')
            include_analytics = form.cleaned_data.get('include_analytics')
            include_thumbnails = form.cleaned_data.get('include_thumbnails')

            # Buduj zapytanie
            materials_query = AdvertisementMaterial.objects.all()

            # Ogranicz dostęp w zależności od roli użytkownika
            if request.user.is_store_admin() and request.user.managed_store:
                materials_query = materials_query.filter(stand__department__store=request.user.managed_store)
            elif request.user.is_editor() and request.user.managed_stand:
                materials_query = materials_query.filter(stand=request.user.managed_stand)

            # Zastosuj filtry
            if store:
                materials_query = materials_query.filter(stand__department__store=store)
            if department:
                materials_query = materials_query.filter(stand__department=department)
            if stand:
                materials_query = materials_query.filter(stand=stand)
            if material_type:
                materials_query = materials_query.filter(material_type=material_type)
            if status:
                materials_query = materials_query.filter(status=status)
            if start_date:
                materials_query = materials_query.filter(created_at__gte=start_date)
            if end_date:
                materials_query = materials_query.filter(created_at__lte=end_date)

            materials = materials_query.select_related('stand__department__store').order_by('-created_at')

            if report_format == 'pdf':
                return generate_pdf_report(
                    materials,
                    include_schedules=include_schedules,
                    include_analytics=include_analytics,
                    include_thumbnails=include_thumbnails
                )
            elif report_format == 'excel':
                return generate_excel_report(
                    materials,
                    include_schedules=include_schedules,
                    include_analytics=include_analytics
                )
            elif report_format == 'csv':
                return generate_csv_report(materials)
    else:
        form = MaterialReportForm(user=request.user)

    return render(request, 'advertisements/materials_report_form.html', {'form': form})


def generate_pdf_report(materials, include_schedules=False, include_analytics=False, include_thumbnails=False):
    """Generuje raport PDF z materiałów reklamowych"""

    # Utwórz bufor do przechowywania PDF
    buffer = io.BytesIO()

    # Utwórz dokument PDF
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )

    # Styl dokumentu
    styles = getSampleStyleSheet()

    # Tworzenie elementów raportu
    elements = []

    # Tytuł
    title_style = styles['Heading1']
    title = Paragraph("Raport Materiałów Reklamowych", title_style)
    elements.append(title)
    elements.append(Spacer(1, 20))

    # Data wygenerowania
    date_style = styles['Normal']
    import datetime
    today = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    date_text = Paragraph(f"Data wygenerowania: {today}", date_style)
    elements.append(date_text)
    elements.append(Spacer(1, 20))

    # Przygotowanie danych do tabeli
    data = [['ID', 'Nazwa', 'Typ', 'Stoisko', 'Dział', 'Sklep', 'Status', 'Czas trwania', 'Data utworzenia']]

    for material in materials:
        row = [
            material.id,
            f"Materiał {material.id}",
            material.get_material_type_display(),
            material.stand.name,
            material.stand.department.name,
            material.stand.department.store.name,
            material.get_status_display(),
            f"{material.duration}s",
            material.created_at.strftime("%d.%m.%Y")
        ]
        data.append(row)

    # Tworzenie tabeli
    table = Table(data, repeatRows=1)

    # Style tabeli
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))

    elements.append(table)

    # Dodanie harmonogramów emisji, jeśli wybrano
    if include_schedules:
        elements.append(Spacer(1, 30))
        elements.append(Paragraph("Harmonogramy Emisji", styles['Heading2']))
        elements.append(Spacer(1, 10))

        schedule_data = [
            ['ID Materiału', 'Nazwa harmonogramu', 'Data rozpoczęcia', 'Data zakończenia', 'Czas emisji', 'Powtarzanie',
             'Priorytet']]

        for material in materials:
            schedules = material.schedules.all()
            for schedule in schedules:
                end_date = schedule.end_date.strftime("%d.%m.%Y") if schedule.end_date else "Bezterminowo"
                row = [
                    material.id,
                    schedule.name,
                    schedule.start_date.strftime("%d.%m.%Y"),
                    end_date,
                    f"{schedule.start_time.strftime('%H:%M')} - {schedule.end_time.strftime('%H:%M')}",
                    schedule.get_repeat_type_display(),
                    schedule.priority
                ]
                schedule_data.append(row)

        if len(schedule_data) > 1:
            schedule_table = Table(schedule_data, repeatRows=1)
            schedule_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ]))
            elements.append(schedule_table)
        else:
            elements.append(Paragraph("Brak harmonogramów dla wybranych materiałów.", styles['Normal']))

    # Dodanie analityki, jeśli wybrano
    if include_analytics:
        elements.append(Spacer(1, 30))
        elements.append(Paragraph("Statystyki Wyświetleń", styles['Heading2']))
        elements.append(Spacer(1, 10))

        # Tutaj można dodać kod do generowania statystyk wyświetleń
        # Na potrzeby przykładu dodajemy informację placeholder
        elements.append(Paragraph("Statystyki będą dostępne w przyszłej wersji systemu.", styles['Normal']))

    # Generowanie dokumentu PDF
    doc.build(elements)

    # Przygotowanie odpowiedzi
    buffer.seek(0)
    response = FileResponse(buffer, as_attachment=True, filename='raport_materialow.pdf')
    return response


def generate_excel_report(materials, include_schedules=False, include_analytics=False):
    """Generuje raport Excel z materiałów reklamowych"""

    # Utwórz bufor do przechowywania pliku Excel
    buffer = io.BytesIO()

    # Utwórz plik Excel
    workbook = xlsxwriter.Workbook(buffer)

    # Formaty
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#4472C4',
        'color': 'white',
        'border': 1
    })

    cell_format = workbook.add_format({
        'border': 1
    })

    # Arkusz materiałów
    materials_sheet = workbook.add_worksheet('Materiały')

    # Nagłówki
    headers = ['ID', 'Nazwa', 'Typ', 'Stoisko', 'Dział', 'Sklep', 'Status', 'Czas trwania (s)', 'Data utworzenia']
    for col, header in enumerate(headers):
        materials_sheet.write(0, col, header, header_format)

    # Dane materiałów
    for row, material in enumerate(materials, start=1):
        materials_sheet.write(row, 0, material.id, cell_format)
        materials_sheet.write(row, 1, f"Materiał {material.id}", cell_format)
        materials_sheet.write(row, 2, material.get_material_type_display(), cell_format)
        materials_sheet.write(row, 3, material.stand.name, cell_format)
        materials_sheet.write(row, 4, material.stand.department.name, cell_format)
        materials_sheet.write(row, 5, material.stand.department.store.name, cell_format)
        materials_sheet.write(row, 6, material.get_status_display(), cell_format)
        materials_sheet.write(row, 7, material.duration, cell_format)
        materials_sheet.write(row, 8, material.created_at.strftime("%d.%m.%Y"), cell_format)

    # Auto szerokość kolumn
    materials_sheet.autofit()

    # Arkusz harmonogramów, jeśli wybrano
    if include_schedules:
        schedules_sheet = workbook.add_worksheet('Harmonogramy')

        # Nagłówki harmonogramów
        schedule_headers = ['ID Materiału', 'Nazwa harmonogramu', 'Data rozpoczęcia', 'Data zakończenia',
                            'Czas rozpoczęcia', 'Czas zakończenia', 'Powtarzanie', 'Priorytet', 'Status']
        for col, header in enumerate(schedule_headers):
            schedules_sheet.write(0, col, header, header_format)

        # Dane harmonogramów
        row = 1
        for material in materials:
            schedules = material.schedules.all()
            for schedule in schedules:
                schedules_sheet.write(row, 0, material.id, cell_format)
                schedules_sheet.write(row, 1, schedule.name, cell_format)
                schedules_sheet.write(row, 2, schedule.start_date.strftime("%d.%m.%Y"), cell_format)
                if schedule.end_date:
                    schedules_sheet.write(row, 3, schedule.end_date.strftime("%d.%m.%Y"), cell_format)
                else:
                    schedules_sheet.write(row, 3, "Bezterminowo", cell_format)
                schedules_sheet.write(row, 4, schedule.start_time.strftime("%H:%M"), cell_format)
                schedules_sheet.write(row, 5, schedule.end_time.strftime("%H:%M"), cell_format)
                schedules_sheet.write(row, 6, schedule.get_repeat_type_display(), cell_format)
                schedules_sheet.write(row, 7, schedule.priority, cell_format)
                schedules_sheet.write(row, 8, "Aktywny" if schedule.is_active else "Nieaktywny", cell_format)
                row += 1

        # Auto szerokość kolumn
        schedules_sheet.autofit()

    # Arkusz analityki, jeśli wybrano
    if include_analytics:
        analytics_sheet = workbook.add_worksheet('Analityka')

        # Placeholder dla przyszłych funkcji analitycznych
        analytics_sheet.write(0, 0, "Analityka wyświetleń będzie dostępna w przyszłej wersji systemu.",
                              workbook.add_format({'bold': True}))

    # Zamknij plik i zwróć go
    workbook.close()
    buffer.seek(0)

    # Przygotowanie odpowiedzi
    response = HttpResponse(buffer.getvalue(),
                            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=raport_materialow.xlsx'
    return response


def generate_csv_report(materials):
    """Generuje raport CSV z materiałów reklamowych"""

    # Utwórz odpowiedź HTTP z typem pliku CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="raport_materialow.csv"'

    # Tworzenie pliku CSV
    writer = csv.writer(response, delimiter=';')

    # Nagłówki
    writer.writerow(
        ['ID', 'Nazwa', 'Typ', 'Stoisko', 'Dział', 'Sklep', 'Status', 'Czas trwania (s)', 'Data utworzenia'])

    # Dane materiałów
    for material in materials:
        writer.writerow([
            material.id,
            f"Materiał {material.id}",
            material.get_material_type_display(),
            material.stand.name,
            material.stand.department.name,
            material.stand.department.store.name,
            material.get_status_display(),
            material.duration,
            material.created_at.strftime("%d.%m.%Y")
        ])

    return response