from django.db import models
from django.core.validators import FileExtensionValidator
from cloudinary.models import CloudinaryField
from .validators import CloudinaryFileExtensionValidator
import cloudinary
from django.db.models.signals import post_delete
from django.dispatch import receiver

import logging
import traceback
logger = logging.getLogger(__name__)

class Store(models.Model):
    name = models.CharField(max_length=255, verbose_name="Nazwa sklepu")
    location = models.CharField(max_length=255, verbose_name="Lokalizacja")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Sklep"
        verbose_name_plural = "Sklepy"
    
    def __str__(self):
        return self.name

class Department(models.Model):
    name = models.CharField(max_length=255, verbose_name="Nazwa działu")
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="departments", verbose_name="Sklep")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Dział"
        verbose_name_plural = "Działy"
        
    def __str__(self):
        return f"{self.name} ({self.store.name})"

class Stand(models.Model):
    ANIMATION_CHOICES = (
        ('fade', 'Fade'),
        ('slide', 'Slide'),
        ('zoom', 'Zoom'),
        ('flip', 'Flip'),
        ('none', 'None'),
    )
    
    name = models.CharField(max_length=255, verbose_name="Nazwa stoiska")
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="stands", verbose_name="Dział")
    display_time = models.IntegerField(default=5, verbose_name="Czas wyświetlania (sekundy)")
    transition_animation = models.CharField(max_length=20, choices=ANIMATION_CHOICES, default='fade', verbose_name="Animacja przejścia")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Stoisko"
        verbose_name_plural = "Stoiska"
        
    def __str__(self):
        return f"{self.name} ({self.department.name}, {self.department.store.name})"

def advertisement_file_path(instance, filename):
    # Generate a file path for the advertisement material
    ext = filename.split('.')[-1]
    return f"advertisements/{instance.stand.id}/{instance.id}.{ext}"

class AdvertisementMaterial(models.Model):
    TYPE_CHOICES = (
        ('image', 'Obraz'),
        ('video', 'Film'),
    )
    
    STATUS_CHOICES = (
        ('active', 'Aktywny'),
        ('inactive', 'Nieaktywny'),
    )
    
    stand = models.ForeignKey(Stand, on_delete=models.CASCADE, related_name="materials", verbose_name="Stoisko")
    material_type = models.CharField(max_length=10, choices=TYPE_CHOICES, verbose_name="Typ materiału")
    file = CloudinaryField(
            'file',
            resource_type='auto',
            folder='advertisements/',
            transformation=[
                {'fetch_format': 'auto', 'quality': 'auto'}
            ],
            validators=[CloudinaryFileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'mp4', 'webm'])],
            help_text="Wybierz plik obrazu lub wideo. Obsługiwane formaty: jpg, jpeg, png, mp4, webm.",
        )
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Data wygaśnięcia")
    order = models.PositiveIntegerField(default=0, verbose_name="Kolejność")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active', verbose_name="Status")
    duration = models.IntegerField(default=5, verbose_name="Czas wyświetlania (sekundy)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Materiał reklamowy"
        verbose_name_plural = "Materiały reklamowe"
        ordering = ['order']

    @property
    def is_expired(self):
        """Sprawdza czy materiał wygasł i ustawia status na nieaktywny"""
        if self.expires_at is None:
            return False

        from django.utils import timezone
        if timezone.now() > self.expires_at:
            if self.status != 'inactive':
                self.status = 'inactive'
                try:
                    self.save(update_fields=["status"])
                except Exception as e:
                    logger.warning(f"Błąd podczas automatycznej zmiany statusu na 'inactive': {e}")
            return True
        return False
        
    def delete(self, *args, **kwargs):
        logger.debug(f"Wywołano delete() dla AdvertisementMaterial id={self.id}")
        file_id = None
        if self.file:
            file_id = self.file.public_id
            logger.debug(f"Znaleziono file_id: {file_id}")
        else:
            logger.debug("Brak pliku do usunięcia (self.file jest None lub puste)")

        super().delete(*args, **kwargs)
        logger.debug("Obiekt AdvertisementMaterial usunięty z bazy")

        if file_id:
            try:
                # Ustal właściwy resource_type
                if self.material_type == 'image':
                    resource_type = 'image'
                elif self.material_type == 'video':
                    resource_type = 'video'
                else:
                    resource_type = 'raw'

                logger.debug(f"Próba usunięcia pliku z Cloudinary: {file_id}, resource_type: {resource_type}")
                result = cloudinary.uploader.destroy(
                    file_id,
                    resource_type=resource_type,
                    invalidate=True
                )
                logger.info(f"Usunięto plik Cloudinary (przez metodę delete): {file_id}, rezultat: {result}")
            except Exception as e:
                logger.error(f"Błąd podczas usuwania pliku Cloudinary (przez metodę delete) ID={file_id}: {str(e)}")
                logger.error(traceback.format_exc())
        else:
            logger.debug("Nie znaleziono file_id, nie usuwam z Cloudinary")

    def __str__(self):
        return f"Materiał {self.id} ({self.get_material_type_display()}) - {self.stand.name}"
    

# Dodaj ten model na końcu pliku models.py
class PlayerStatus(models.Model):
    stand = models.OneToOneField(Stand, on_delete=models.CASCADE, related_name='player_status', verbose_name="Stoisko")
    is_online = models.BooleanField(default=False, verbose_name="Czy aktywny")
    last_seen = models.DateTimeField(null=True, blank=True, verbose_name="Ostatnia aktywność")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Adres IP")
    user_agent = models.TextField(blank=True, null=True, verbose_name="User Agent")
    screen_resolution = models.CharField(max_length=50, blank=True, null=True, verbose_name="Rozdzielczość ekranu")
    version = models.CharField(max_length=20, blank=True, null=True, verbose_name="Wersja odtwarzacza")
    errors = models.TextField(blank=True, null=True, verbose_name="Błędy")
    
    class Meta:
        verbose_name = "Status odtwarzacza"
        verbose_name_plural = "Statusy odtwarzaczy"
    
    def __str__(self):
        return f"Status odtwarzacza - {self.stand.name}"
    
    
class EmissionSchedule(models.Model):
    REPEAT_CHOICES = (
        ('none', 'Bez powtarzania'),
        ('daily', 'Codziennie'),
        ('weekly', 'Co tydzień'),
        ('monthly', 'Co miesiąc'),
        ('custom', 'Niestandardowy'),
    )

    DAY_CHOICES = (
        (0, 'Poniedziałek'),
        (1, 'Wtorek'),
        (2, 'Środa'),
        (3, 'Czwartek'),
        (4, 'Piątek'),
        (5, 'Sobota'),
        (6, 'Niedziela'),
    )

    materials = models.ManyToManyField(
        AdvertisementMaterial,
        related_name='schedules',
        verbose_name="Materiały"
    )
    name = models.CharField(max_length=100, verbose_name="Nazwa harmonogramu")
    start_date = models.DateField(verbose_name="Data rozpoczęcia")
    end_date = models.DateField(null=True, blank=True, verbose_name="Data zakończenia")
    start_time = models.TimeField(verbose_name="Czas rozpoczęcia")
    end_time = models.TimeField(verbose_name="Czas zakończenia")
    repeat_type = models.CharField(max_length=10, choices=REPEAT_CHOICES, default='none', verbose_name="Typ powtarzania")
    repeat_days = models.JSONField(null=True, blank=True, verbose_name="Dni powtarzania")
    priority = models.IntegerField(default=5, verbose_name="Priorytet")
    is_active = models.BooleanField(default=True, verbose_name="Aktywny")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Harmonogram emisji"
        verbose_name_plural = "Harmonogramy emisji"
        ordering = ['-priority', 'start_date', 'start_time']

    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date or 'brak końca'})"

    def is_scheduled_for_date(self, check_date):
        """Sprawdza czy harmonogram jest aktywny w podanym dniu"""
        # Sprawdź czy data jest w zakresie
        if check_date < self.start_date:
            return False
        if self.end_date and check_date > self.end_date:
            return False
            
        # Sprawdź typ powtarzania
        if self.repeat_type == 'none':
            # Dla jednorazowego wydarzenia - tylko w dniu rozpoczęcia
            return check_date == self.start_date
        elif self.repeat_type == 'daily':
            # Codziennie
            return True
        elif self.repeat_type == 'weekly':
            # Sprawdź czy dzień tygodnia jest w repeat_days
            weekday = check_date.weekday()
            return self.repeat_days and weekday in self.repeat_days
        elif self.repeat_type == 'monthly':
            # Ten sam dzień każdego miesiąca
            try:
                # Obsługa ostatniego dnia miesiąca
                if self.start_date.day >= 28:  # Potencjalnie ostatni dzień miesiąca
                    # Jeśli dzień rozpoczęcia to ostatni dzień miesiąca, sprawdź czy dziś też jest ostatni
                    import calendar
                    last_day = calendar.monthrange(check_date.year, check_date.month)[1]
                    if self.start_date.day == calendar.monthrange(self.start_date.year, 
                                                                self.start_date.month)[1]:
                        return check_date.day == last_day
                
                # Standardowe sprawdzenie - ten sam dzień miesiąca
                return check_date.day == self.start_date.day
            except:
                return False
        elif self.repeat_type == 'custom':
            # Implementacja dla niestandardowych powtórzeń (można rozszerzyć)
            return False
            
        return False

    def apply_schedule(self):
        """Sprawdza czy harmonogram jest aktywny w bieżącym momencie"""
        from django.utils import timezone
        
        # Użycie localtime do uzyskania czasu w strefie czasowej aplikacji
        now = timezone.localtime(timezone.now())
        today = now.date()
        current_time = now.time()
        
        if not self.is_active:
            # Jeśli harmonogram jest nieaktywny, zwróć False
            return False
        
        # Sprawdź, czy dzień jest zgodny z harmonogramem
        is_active_day = self.is_scheduled_for_date(today)
        if not is_active_day:
            return False
        
        # Sprawdź czas
        # Obsługa harmonogramów nocnych (przez północ)
        if self.start_time <= self.end_time:
            # Normalny zakres godzin (np. 8:00-20:00)
            is_active_time = self.start_time <= current_time <= self.end_time
        else:
            # Zakres przez północ (np. 22:00-6:00)
            is_active_time = self.start_time <= current_time or current_time <= self.end_time
        
        return is_active_time
    
    