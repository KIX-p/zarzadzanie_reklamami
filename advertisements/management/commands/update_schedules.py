from django.core.management.base import BaseCommand
from django.utils import timezone
from advertisements.models import EmissionSchedule, AdvertisementMaterial
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Aktualizuje statusy materiałów na podstawie harmonogramów emisji'
    
    def handle(self, *args, **options):
        now = timezone.localtime(timezone.now())  # Konwertuje UTC na lokalny czas
        current_time = now.time()
        self.stdout.write(f'DEBUG: Aktualny czas lokalny: {now.strftime("%H:%M:%S")}')
        self.stdout.write(f'DEBUG: Aktualny czas: {now.strftime("%H:%M:%S")}')
        active_schedules = EmissionSchedule.objects.filter(is_active=True)
        
        self.stdout.write(f'Przetwarzanie {active_schedules.count()} aktywnych harmonogramów')
        
         # Sprawdź harmonogramy, które się zakończyły
        expired_schedules = []
        for schedule in active_schedules:
            # Harmonogramy bezterminowe (bez end_date) nie wygasają
            self.stdout.write(f"DEBUG: Sprawdzam harmonogram {schedule.id} ({schedule.name})")
            self.stdout.write(f"DEBUG: start_date={schedule.start_date}, end_date={schedule.end_date}, end_time={schedule.end_time}")
            
            if schedule.end_date:
                # Sprawdź, czy minęła data zakończenia
                if schedule.end_date < now.date():
                    self.stdout.write(f"DEBUG: Harmonogram {schedule.id} wygasł (end_date < dzisiaj)")
                    expired_schedules.append(schedule.id)
                # Sprawdź, czy to ostatni dzień i minęła godzina zakończenia
                elif schedule.end_date == now.date():
                    if schedule.end_time:
                        # Wypisz szczegóły dla lepszego debugowania
                        self.stdout.write(f"DEBUG: Porównanie czasów: end_time={schedule.end_time}, current_time={current_time}")
                        if schedule.end_time < current_time:
                            self.stdout.write(f"DEBUG: Harmonogram {schedule.id} wygasł (end_time < current_time)")
                            expired_schedules.append(schedule.id)
                        else:
                            self.stdout.write(f"DEBUG: Harmonogram {schedule.id} nadal aktywny (end_time >= current_time)")
                    else:
                        self.stdout.write(f"DEBUG: Harmonogram {schedule.id} nie ma określonego end_time")
                else:
                    self.stdout.write(f"DEBUG: Harmonogram {schedule.id} nadal aktywny (end_date > dzisiaj)")
            else:
                self.stdout.write(f"DEBUG: Harmonogram {schedule.id} jest bezterminowy")
        
        # Dezaktywuj wygasłe harmonogramy
        if expired_schedules:
            count = EmissionSchedule.objects.filter(id__in=expired_schedules).update(is_active=False)
            self.stdout.write(self.style.SUCCESS(f'Dezaktywowano {count} wygasłych harmonogramów: {expired_schedules}'))
        else:
            self.stdout.write("DEBUG: Brak harmonogramów do dezaktywacji")
        
        # Najpierw dezaktywuj wszystkie materiały bez aktywnych harmonogramów
        materials_with_schedules = AdvertisementMaterial.objects.filter(
            schedules__in=active_schedules
        ).distinct()
        
        materials_without_schedules = AdvertisementMaterial.objects.exclude(
            id__in=materials_with_schedules.values_list('id', flat=True)
        )
            
        # Zbuduj słownik priorytetów dla materiałów z aktywnymi harmonogramami
        material_priorities = {}
        activated_materials = set()
        
        for schedule in active_schedules:
            is_active = schedule.apply_schedule()
            
            if is_active:
                for material in schedule.materials.all():
                    # Zachowaj najwyższy priorytet dla każdego materiału
                    current_priority = material_priorities.get(material.id, 0)
                    if schedule.priority > current_priority:
                        material_priorities[material.id] = schedule.priority
                        activated_materials.add(material.id)
        
        # Aktywuj materiały z aktywnymi harmonogramami
        if activated_materials:
            AdvertisementMaterial.objects.filter(id__in=activated_materials).update(status='active')
            self.stdout.write(f'Aktywowano {len(activated_materials)} materiałów')
        
        # Dezaktywuj materiały z harmonogramami, które nie są teraz aktywne
        materials_to_deactivate = materials_with_schedules.exclude(
            id__in=activated_materials
        )
        
        if materials_to_deactivate:
            materials_to_deactivate.update(status='inactive')
            self.stdout.write(f'Dezaktywowano {materials_to_deactivate.count()} materiałów')
        
        self.stdout.write(self.style.SUCCESS('Zakończono aktualizację statusów materiałów'))