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

        if self.instance.pk and self.instance.repeat_days:
            self.fields['repeat_days_display'].initial = [str(day) for day in self.instance.repeat_days]

    def clean(self):
        cleaned_data = super().clean()
        repeat_type = cleaned_data.get('repeat_type')
        repeat_days = self.cleaned_data.get('repeat_days_display')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')

        if repeat_type == 'weekly' and not repeat_days:
            self.add_error('repeat_days_display', 'Wybierz co najmniej jeden dzień tygodnia')

        if repeat_days:
            cleaned_data['repeat_days'] = [int(day) for day in repeat_days]
        else:
            cleaned_data['repeat_days'] = []

        return cleaned_data
