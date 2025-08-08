from django import forms
from .models import Store, Department, Stand, AdvertisementMaterial, EmissionSchedule
import datetime


class AdvertisementMaterialForm(forms.ModelForm):
    never_expires = forms.BooleanField(
        label="Bezterminowy",
        required=False,
        initial=True,
        help_text="Zaznacz, jeśli materiał nie powinien automatycznie wygasać"
    )

    class Meta:
        model = AdvertisementMaterial
        fields = ['stand', 'material_type', 'file', 'status', 'duration', 'expires_at']
        widgets = {
            'stand': forms.Select(attrs={'class': 'form-select'}),
            'material_type': forms.Select(attrs={'class': 'form-select'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'duration': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'expires_at': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk is None or self.instance.expires_at is None:
            self.fields['never_expires'].initial = True
        else:
            self.fields['never_expires'].initial = False

        tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
        self.fields['expires_at'].widget.attrs['min'] = tomorrow.strftime('%Y-%m-%dT%H:%M')

    def clean(self):
        cleaned_data = super().clean()
        never_expires = cleaned_data.get('never_expires')
        expires_at = cleaned_data.get('expires_at')

        if never_expires:
            cleaned_data['expires_at'] = None
        elif not expires_at:
            self.add_error('expires_at', 'Wybierz datę wygaśnięcia lub zaznacz "Bezterminowy"')

        return cleaned_data


class StandAnimationForm(forms.ModelForm):
    class Meta:
        model = Stand
        fields = ['transition_animation']
        labels = {
            'transition_animation': 'Animacja przejścia między materiałami',
        }
        widgets = {
            'transition_animation': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and user.is_editor() and user.managed_stand:
            if self.instance != user.managed_stand:
                self.fields['transition_animation'].disabled = True


class EmissionScheduleForm(forms.ModelForm):
    repeat_days_display = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple,
        choices=EmissionSchedule.DAY_CHOICES,
        label="Dni tygodnia"
    )
    
    is_overnight = forms.BooleanField(
        required=False, 
        label="Emisja przez północ",
        help_text="Zaznacz, jeśli harmonogram trwa przez północ (np. od 22:00 do 06:00)"
    )

    class Meta:
        model = EmissionSchedule
        fields = ['name', 'start_date', 'end_date', 'start_time', 'end_time',
                  'repeat_type', 'priority', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'repeat_type': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '10'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Ustaw początkowe wartości dla dni tygodnia (jeśli jest to edycja)
        if self.instance.pk and self.instance.repeat_days:
            self.fields['repeat_days_display'].initial = [str(day) for day in self.instance.repeat_days]
        
        # Ustaw wartość dla is_overnight
        if self.instance.pk and self.instance.start_time and self.instance.end_time:
            self.fields['is_overnight'].initial = self.instance.start_time > self.instance.end_time

    def clean(self):
        cleaned_data = super().clean()
        repeat_type = cleaned_data.get('repeat_type')
        repeat_days = self.cleaned_data.get('repeat_days_display')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        is_overnight = cleaned_data.get('is_overnight')
        
        if repeat_type == 'weekly' and not repeat_days:
            self.add_error('repeat_days_display', 'Wybierz co najmniej jeden dzień tygodnia')

        if not is_overnight and start_time and end_time and start_time >= end_time:
            self.add_error('end_time', 'Godzina zakończenia musi być późniejsza niż godzina rozpoczęcia')
            
        if repeat_days:
            cleaned_data['repeat_days'] = [int(day) for day in repeat_days]
        else:
            cleaned_data['repeat_days'] = []

        return cleaned_data
    
    
# Dodaj nową klasę formularza na końcu pliku

class MaterialReportForm(forms.Form):
    REPORT_FORMAT_CHOICES = (
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
    )
    
    store = forms.ModelChoiceField(
        queryset=Store.objects.all(),
        required=False,
        empty_label="Wszystkie sklepy",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.none(),
        required=False,
        empty_label="Wszystkie działy",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    stand = forms.ModelChoiceField(
        queryset=Stand.objects.none(),
        required=False,
        empty_label="Wszystkie stoiska",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    material_type = forms.ChoiceField(
        choices=(('', 'Wszystkie typy'),) + AdvertisementMaterial.TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    status = forms.ChoiceField(
        choices=(('', 'Wszystkie statusy'),) + AdvertisementMaterial.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    report_format = forms.ChoiceField(
        choices=REPORT_FORMAT_CHOICES,
        initial='pdf',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    include_schedules = forms.BooleanField(
        required=False, 
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    include_analytics = forms.BooleanField(
        required=False, 
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    include_thumbnails = forms.BooleanField(
        required=False, 
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter queryset based on user permissions
        if user:
            if user.is_superadmin():
                pass  # Superadmin sees all
            elif user.is_store_admin() and user.managed_store:
                self.fields['store'].queryset = Store.objects.filter(id=user.managed_store.id)
                self.fields['department'].queryset = Department.objects.filter(store=user.managed_store)
                self.fields['stand'].queryset = Stand.objects.filter(department__store=user.managed_store)
            elif user.is_editor() and user.managed_stand:
                self.fields['store'].queryset = Store.objects.filter(departments__stands=user.managed_stand)
                self.fields['department'].queryset = Department.objects.filter(stands=user.managed_stand)
                self.fields['stand'].queryset = Stand.objects.filter(id=user.managed_stand.id)
