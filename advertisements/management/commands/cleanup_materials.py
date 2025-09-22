from django.core.management.base import BaseCommand
from django.utils import timezone
from advertisements.models import AdvertisementMaterial
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Usuwa wygasłe materiały reklamowe'
    
    def handle(self, *args, **options):
        logger.info('Rozpoczynam czyszczenie wygasłych materiałów')
        now = timezone.now()
        expired_materials = AdvertisementMaterial.objects.filter(
            expires_at__isnull=False,
            expires_at__lt=now
        )
        
        logger.debug(f'Pobrano {expired_materials.count()} wygasłych materiałów z bazy')
        if not expired_materials:
            self.stdout.write(self.style.SUCCESS('Brak wygasłych materiałów do usunięcia'))
            logger.info('Brak wygasłych materiałów do usunięcia')
            return
            
        count = expired_materials.count()
        self.stdout.write(f'Znaleziono {count} wygasłych materiałów do usunięcia')
        logger.info(f'Znaleziono {count} wygasłych materiałów do usunięcia')
        
        for material in expired_materials:
            try:
                material_id = material.id
                stand_name = material.stand.name
                logger.info(f"Usuwanie wygasłego materiału ID={material_id} ze stoiska '{stand_name}'")
                material.delete()  # Ta metoda już obsługuje usuwanie plików z Cloudinary
                self.stdout.write(f'- Usunięto materiał ID={material_id}')
                logger.debug(f'Usunięto materiał ID={material_id}')
            except Exception as e:
                logger.error(f"Błąd podczas usuwania materiału ID={material.id}: {str(e)}")
                
        self.stdout.write(self.style.SUCCESS(f'Pomyślnie usunięto {count} wygasłych materiałów'))
        logger.info(f'Pomyślnie usunięto {count} wygasłych materiałów')