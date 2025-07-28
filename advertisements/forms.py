from django import forms
from .models import Store, Department, Stand, AdvertisementMaterial

class AdvertisementMaterialForm(forms.ModelForm):
    class Meta:
        model = AdvertisementMaterial
        fields = ['stand', 'material_type', 'file', 'status', 'duration']
        widgets = {
            'stand': forms.Select(attrs={'class': 'form-select'}),
            'material_type': forms.Select(attrs={'class': 'form-select'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'duration': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Jeżeli użytkownik jest przekazany, ogranicz wybór stanowiska
        if user:
            if user.is_superadmin():
                # Superadmin może wybierać wszystkie stanowiska
                pass
            elif user.is_store_admin() and user.managed_store:
                # Admin sklepu może wybierać tylko stanowiska w swoim sklepie
                departments = user.managed_store.departments.all()
                stands = Stand.objects.filter(department__in=departments)
                self.fields['stand'].queryset = stands
            elif user.is_editor() and user.managed_stand:
                # Edytor może wybierać tylko swoje stanowisko
                self.fields['stand'].queryset = Stand.objects.filter(id=user.managed_stand.id)
                self.fields['stand'].widget.attrs['disabled'] = 'disabled'
                self.fields['stand'].widget.attrs['readonly'] = True
                if not self.initial.get('stand'):
                    self.initial['stand'] = user.managed_stand