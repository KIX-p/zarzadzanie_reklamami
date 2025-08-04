from django import forms
from .models import Store, Department, Stand, AdvertisementMaterial
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
        
        # Ukryj pole expires_at początkowo, jeśli jest nowy materiał lub ma nieokreślony termin
        if self.instance.pk is None or self.instance.expires_at is None:
            self.fields['never_expires'].initial = True
        else:
            self.fields['never_expires'].initial = False
            
        # Ustaw minimalną datę na jutro
        tomorrow = datetime.datetime.now()
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

        # Możesz dodać ewentualne sprawdzenie dostępu do stoiska
        if user and user.is_editor() and user.managed_stand:
            # Edytor może edytować tylko swoje stanowisko
            if self.instance != user.managed_stand:
                self.fields['transition_animation'].disabled = True