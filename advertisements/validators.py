from django.core.validators import ValidationError
from django.utils.translation import gettext_lazy as _
import os

class CloudinaryFileExtensionValidator:
    """
    Validator sprawdzający rozszerzenie pliku dla pól CloudinaryField.
    """
    
    def __init__(self, allowed_extensions=None, message=None, code=None):
        self.allowed_extensions = [ext.lower() for ext in allowed_extensions] if allowed_extensions else []
        self.message = message or _(
            "Rozszerzenie pliku '%(extension)s' nie jest dozwolone. Dozwolone rozszerzenia: '%(allowed_extensions)s'."
        )
        self.code = code or 'invalid_extension'
    
    def __call__(self, value):
        # Pomijamy walidację, jeśli wartość jest None (brak pliku)
        if not value:
            return
            
        # Sprawdzamy, czy mamy do czynienia z nowym plikiem czy istniejącym zasobem Cloudinary
        if hasattr(value, 'name'):
            # Standardowy plik (nowy upload)
            extension = os.path.splitext(value.name)[1][1:].lower()
        elif hasattr(value, 'public_id'):
            # Istniejący zasób Cloudinary
            # Wyciągamy rozszerzenie z public_id lub URL
            if hasattr(value, 'url') and value.url:
                extension = os.path.splitext(value.url.split('?')[0])[1][1:].lower()
            else:
                # Jeśli nie możemy określić rozszerzenia, pomijamy walidację
                return
        else:
            # Nie możemy określić typu pliku, pomijamy walidację
            return
            
        if self.allowed_extensions and extension not in self.allowed_extensions:
            raise ValidationError(
                self.message,
                code=self.code,
                params={'extension': extension, 'allowed_extensions': ', '.join(self.allowed_extensions)}
            )
            
    def __eq__(self, other):
        if isinstance(other, CloudinaryFileExtensionValidator):
            return (
                self.allowed_extensions == other.allowed_extensions and
                self.message == other.message and
                self.code == other.code
            )
        return False
        
    def deconstruct(self):
        return (
            'advertisements.validators.CloudinaryFileExtensionValidator',  # ścieżka do klasy
            [self.allowed_extensions],  # argumenty pozycyjne
            {  # argumenty nazwane
                'message': self.message,
                'code': self.code,
            },
        )