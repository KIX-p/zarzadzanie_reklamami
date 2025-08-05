from django.core.management.base import BaseCommand
from django.utils import timezone
from advertisements.models import EmissionSchedule, AdvertisementMaterial
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Aktualizuje statusy materiałów na podstawie harmonogramów emisji'
    
    def handle(self, *args, **options):
        now = timezone.now()
        active_schedules = EmissionSchedule.objects.filter(is_active=True)
        
        self.stdout.write(f'Przetwarzanie {active_schedules.count()} aktywnych harmonogramów')
        
        # Najpierw dezaktywuj wszystkie materiały bez aktywnych harmonogramów
        materials_with_schedules = AdvertisementMaterial.objects.filter(
            schedules__in=active_schedules
        ).distinct()
        
        materials_without_schedules = AdvertisementMaterial.objects.exclude(
            id__in=materials_with_schedules.values_list('id', flat=True)
        )
        
        # Nie dezaktywuj materiałów bezterminowych (bez harmonogramów)
        # Zamiast tego, sprawdź tylko te z harmonogramami
        
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