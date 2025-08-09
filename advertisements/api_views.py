from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.utils import timezone
from .models import PlayerStatus, Store, Department


from .models import Stand, AdvertisementMaterial, EmissionSchedule
from .serializers import StandSerializer, AdvertisementMaterialSerializer
from accounts.models import User

class IsPlayerOrAdmin(permissions.BasePermission):
    """
    Permission to only allow players or admins to access the API
    """
    def has_permission(self, request, view):
        return request.user and (request.user.is_player() or 
                                request.user.is_editor() or
                                request.user.is_store_admin() or
                                request.user.is_superadmin())
    
    def has_object_permission(self, request, view, obj):
        # Admin has access to all
        if request.user.is_superadmin():
            return True
            
        # Store admin can access all stands in their store
        if request.user.is_store_admin():
            if hasattr(obj, 'department'):  # Is a Stand
                return obj.department.store == request.user.managed_store
                
        # Editor can only access their stand
        if request.user.is_editor():
            return obj == request.user.managed_stand
            
        # Player can only access their stand
        if request.user.is_player():
            return obj == request.user.managed_stand
            
        return False

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsPlayerOrAdmin])
def stand_materials(request, stand_id):
    """
    Get all materials for a specific stand.
    Used by the player to display the carousel.
    Uwzględnia harmonogram emisji.
    """
    try:
        stand = Stand.objects.get(pk=stand_id)
        
        # Check permissions
        if not IsPlayerOrAdmin().has_object_permission(request, None, stand):
            return Response({"error": "Nie masz uprawnień do tego stoiska"}, 
                          status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        current_time = now.time()
        current_date = now.date()
        current_weekday = now.weekday()

        # Pobierz wszystkie materiały dla stoiska
        materials = AdvertisementMaterial.objects.filter(stand=stand, status='active')

        # Pobierz aktywne harmonogramy dla stoiska
        schedules = EmissionSchedule.objects.filter(
            materials__stand=stand,  # Corrected from 'material__stand'
            is_active=True,
            start_time__lte=current_time,
            end_time__gte=current_time
        ).order_by('-priority')

        # Pobierz aktywne harmonogramy dla stoiska - dodajemy specjalną obsługę harmonogramów nocnych
        current_schedules = EmissionSchedule.objects.filter(
            materials__stand=stand, 
            is_active=True
        )
        
        # Filtruj harmonogramy według daty i czasu
        active_schedules = []
        for schedule in current_schedules:
            # Sprawdź czy harmonogram obowiązuje w bieżącym dniu
            if schedule.is_scheduled_for_date(current_date):
                # Sprawdź godziny
                if schedule.start_time <= schedule.end_time:
                    # Normalny harmonogram dzienny (np. 8:00-20:00)
                    if schedule.start_time <= current_time <= schedule.end_time:
                        active_schedules.append(schedule)
                else:
                    # Harmonogram nocny przechodzący przez północ (np. 22:00-6:00)
                    if schedule.start_time <= current_time or current_time <= schedule.end_time:
                        active_schedules.append(schedule)
        
        # Filtruj harmonogramy według daty i typu powtarzania
        active_schedules = []
        for schedule in schedules:
            if schedule.is_scheduled_for_date(current_date):
                active_schedules.append(schedule)
        
        # Jeśli są aktywne harmonogramy, używaj tylko materiałów z harmonogramów
        materials_ids = []
        # Jeśli są aktywne harmonogramy, używaj tylko materiałów z harmonogramów
        if active_schedules:
            # Grupuj materiały według priorytetów harmonogramów
            materials_by_priority = {}
            
            for schedule in active_schedules:
                priority = schedule.priority
                for material in schedule.materials.filter(status='active'):
                    # Zachowaj tylko najwyższy priorytet dla każdego materiału
                    if material.id not in materials_by_priority or priority > materials_by_priority[material.id]['priority']:
                        materials_by_priority[material.id] = {
                            'material': material,
                            'priority': priority
                        }
            
            # Konwertuj na listę i sortuj według priorytetu
            prioritized_materials = [item['material'] for item in sorted(
                materials_by_priority.values(), 
                key=lambda x: x['priority'], 
                reverse=True
            )]
            
            # Użyj tylko materiałów z aktywnych harmonogramów
            materials = prioritized_materials
        
        # Serializuj stoisko wraz z materiałami
        serializer = StandSerializer(stand, context={'request': request})
        data = serializer.data
        
        # Jeśli używamy harmonogramów, zastąp materiały tymi z harmonogramów w odpowiedniej kolejności
        if active_schedules:
            # Sortuj materiały według priorytetu harmonogramu
            priority_map = {s.material_id: s.priority for s in active_schedules}
            materials_data = []
            
            for material in materials:
                material_data = AdvertisementMaterialSerializer(material, context={'request': request}).data
                material_data['schedule_priority'] = priority_map.get(material.id, 0)
                materials_data.append(material_data)
                
            # Sortuj według priorytetu (wyższy najpierw)
            materials_data.sort(key=lambda x: x['schedule_priority'], reverse=True)
            data['materials'] = materials_data
        
        return Response(data)
    
    except Stand.DoesNotExist:
        return Response({"error": "Stoisko nie istnieje"}, 
                      status=status.HTTP_404_NOT_FOUND)
    

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def schedule_details(request, schedule_id):
    """
    Pobiera szczegóły harmonogramu
    """
    try:
        schedule = EmissionSchedule.objects.get(pk=schedule_id)
        
        # Sprawdź uprawnienia (ten sam kod co w innych widokach)
        materials = schedule.materials.all()
        if not materials.exists():
            return Response({"error": "Harmonogram nie zawiera materiałów"}, 
                          status=status.HTTP_404_NOT_FOUND)
            
        stand = materials.first().stand
        user = request.user
        
        if not (user.is_superadmin() or 
               (user.is_store_admin() and stand.department.store == user.managed_store) or
               (user.is_editor() and stand == user.managed_stand)):
            return Response({"error": "Brak uprawnień"}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        # Przygotuj dane
        material_data = []
        for material in materials:
            material_data.append({
                'id': material.id,
                'type': material.get_material_type_display(),
                'url': request.build_absolute_uri(material.file.url) if material.file else None,
                'duration': material.duration,
                'status': material.status
            })
        
        # Czy to harmonogram nocny
        is_overnight = schedule.start_time > schedule.end_time
        
        data = {
            'id': schedule.id,
            'name': schedule.name,
            'start_date': schedule.start_date.isoformat(),
            'end_date': schedule.end_date.isoformat() if schedule.end_date else None,
            'start_time': schedule.start_time.isoformat(),
            'end_time': schedule.end_time.isoformat(),
            'repeat_type': schedule.repeat_type,
            'repeat_days': schedule.repeat_days,
            'priority': schedule.priority,
            'is_active': schedule.is_active,
            'is_overnight': is_overnight,
            'materials': material_data
        }
        
        return Response(data)
        
    except EmissionSchedule.DoesNotExist:
        return Response({"error": "Harmonogram nie istnieje"}, 
                      status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def get_token(request):
    """
    Get or create a token for player authentication.
    Requires username and password.
    """
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response({"error": "Podaj nazwę użytkownika i hasło"}, 
                      status=status.HTTP_400_BAD_REQUEST)
    
    user = None
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return Response({"error": "Nieprawidłowa nazwa użytkownika lub hasło"}, 
                      status=status.HTTP_401_UNAUTHORIZED)
    
    if not user.check_password(password):
        return Response({"error": "Nieprawidłowa nazwa użytkownika lub hasło"}, 
                      status=status.HTTP_401_UNAUTHORIZED)
    
    if not user.is_player():
        return Response({"error": "Tylko konta typu Odtwarzacz mogą uzyskać token"}, 
                      status=status.HTTP_403_FORBIDDEN)
    
    # Get or create token
    token, created = Token.objects.get_or_create(user=user)
    
    # Get stand info if available
    stand_info = None
    if user.managed_stand:
        stand_info = {
            "id": user.managed_stand.id,
            "name": user.managed_stand.name,
        }
    
    return Response({
        "token": token.key,
        "stand": stand_info
    })
    
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsPlayerOrAdmin])
def report_player_status(request):
    """
    Report player status (heartbeat)
    """
    try:
        user = request.user
        if not (user.is_player() or user.is_superadmin() or user.is_editor()):
            return Response({"error": "Brak uprawnień"}, status=status.HTTP_403_FORBIDDEN)
        
        stand = getattr(user, 'managed_stand', None)
        if not stand:
            return Response({"error": "Brak przypisanego stoiska"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Pobierz lub utwórz obiekt PlayerStatus
        player_status, created = PlayerStatus.objects.get_or_create(stand=stand)
        
        # Aktualizuj informacje o statusie
        player_status.last_seen = timezone.now()
        player_status.is_online = True
        player_status.ip_address = request.META.get('REMOTE_ADDR')
        player_status.user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Aktualizacja opcjonalnych danych
        if 'screen_resolution' in request.data:
            player_status.screen_resolution = request.data['screen_resolution']
        if 'version' in request.data:
            player_status.version = request.data['version']
        if 'errors' in request.data:
            player_status.errors = request.data['errors']
            
        player_status.save()
        
        return Response({"status": "ok"})
        
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_player_status(request, stand_id):
    """
    Get player status
    """
    try:
        stand = Stand.objects.get(pk=stand_id)
        
        # Sprawdź uprawnienia
        user = request.user
        if not (user.is_superadmin() or 
                (user.is_store_admin() and stand.department.store == user.managed_store) or
                (user.is_editor() and stand == user.managed_stand)):
            return Response({"error": "Brak uprawnień"}, status=status.HTTP_403_FORBIDDEN)
            
        # Pobierz lub utwórz status odtwarzacza
        player_status, created = PlayerStatus.objects.get_or_create(stand=stand)
        
        # Sprawdź, czy status jest aktualny (ostatnia aktywność < 90 sekund)
        from datetime import timedelta
        is_online = False
        if player_status.last_seen:
            is_online = timezone.now() - player_status.last_seen <= timedelta(seconds=90)
            if player_status.is_online != is_online:
                player_status.is_online = is_online
                player_status.save(update_fields=['is_online'])
        
        return Response({
            "is_online": is_online,
            "last_seen": player_status.last_seen.isoformat() if player_status.last_seen else None,
            "ip_address": player_status.ip_address,
            "screen_resolution": player_status.screen_resolution,
            "version": player_status.version,
        })
    
    except Stand.DoesNotExist:
        return Response({"error": "Stoisko nie istnieje"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_departments_for_store(request, store_id):
    """API do pobierania działów dla sklepu"""
    try:
        user = request.user
        store = Store.objects.get(pk=store_id)
        
        # Sprawdź uprawnienia użytkownika
        if user.is_store_admin() and user.managed_store != store:
            return Response({"error": "Brak uprawnień"}, status=status.HTTP_403_FORBIDDEN)
        
        departments = Department.objects.filter(store=store)
        data = [{"id": dept.id, "name": dept.name} for dept in departments]
        return Response(data)
    except Store.DoesNotExist:
        return Response({"error": "Sklep nie istnieje"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_stands_for_department(request, department_id):
    """API do pobierania stoisk dla działu"""
    try:
        user = request.user
        department = Department.objects.get(pk=department_id)
        
        # Sprawdź uprawnienia użytkownika
        if user.is_store_admin() and user.managed_store != department.store:
            return Response({"error": "Brak uprawnień"}, status=status.HTTP_403_FORBIDDEN)
        
        stands = Stand.objects.filter(department=department)
        data = [{"id": stand.id, "name": stand.name} for stand in stands]
        return Response(data)
    except Department.DoesNotExist:
        return Response({"error": "Dział nie istnieje"}, status=status.HTTP_404_NOT_FOUND)
    
    
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsPlayerOrAdmin])
def reset_player_token(request):
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Wywołano reset_player_token")
    user = request.user
    logger.info(f"Użytkownik: {user} ({user.role})")

    # Edytor resetuje swój własny token
    if user.is_editor():
        Token.objects.filter(user=user).delete()
        new_token = Token.objects.create(user=user)
        logger.info(f"Nowy token dla edytora {user.username}: {new_token.key}")
        return Response({'token': new_token.key})

    # Odtwarzacz może zresetować swój token
    if user.is_player():
        Token.objects.filter(user=user).delete()
        new_token = Token.objects.create(user=user)
        logger.info(f"Nowy token dla playera {user.username}: {new_token.key}")
        return Response({'token': new_token.key})

    logger.warning("Brak uprawnień do resetu tokenu.")
    return Response({'error': 'Brak uprawnień'}, status=status.HTTP_403_FORBIDDEN)