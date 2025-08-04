from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.utils import timezone
from .models import PlayerStatus


from .models import Stand, AdvertisementMaterial
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
    """
    try:
        stand = Stand.objects.get(pk=stand_id)
        print(stand)
        
        # Check permissions
        if not IsPlayerOrAdmin().has_object_permission(request, None, stand):
            return Response({"error": "Nie masz uprawnień do tego stoiska"}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        serializer = StandSerializer(stand, context={'request': request})
        print(serializer)
        return Response(serializer.data)
    
    except Stand.DoesNotExist:
        return Response({"error": "Stoisko nie istnieje"}, 
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
        
        if not user.is_player() and not user.is_superadmin():
            return Response({"error": "Tylko odtwarzacz może raportować status"}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        if not user.managed_stand:
            return Response({"error": "Brak przypisanego stoiska"}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Pobierz lub stwórz status dla tego stoiska
        player_status, created = PlayerStatus.objects.get_or_create(stand=user.managed_stand)
        
        # Aktualizuj informacje o statusie
        player_status.is_online = True
        player_status.last_seen = timezone.now()
        player_status.ip_address = request.META.get('REMOTE_ADDR')
        player_status.user_agent = request.META.get('HTTP_USER_AGENT')
        
        # Opcjonalne pola z request
        if 'screen_resolution' in request.data:
            player_status.screen_resolution = request.data['screen_resolution']
        
        if 'version' in request.data:
            player_status.version = request.data['version']
        
        if 'errors' in request.data:
            player_status.errors = request.data['errors']
        
        player_status.save()
        
        return Response({"status": "success"})
    
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_player_status(request, stand_id):
    """
    Get player status
    """
    try:
        user = request.user
        stand = Stand.objects.get(pk=stand_id)
        
        # Sprawdź uprawnienia
        if not (user.is_superadmin() or 
               (user.is_store_admin() and stand.department.store == user.managed_store) or
               (user.is_editor() and stand == user.managed_stand) or
               (user.is_player() and stand == user.managed_stand)):
            return Response({"error": "Brak uprawnień"}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        try:
            player_status = PlayerStatus.objects.get(stand=stand)
            
            # Jeśli ostatnia aktywność była ponad 5 minut temu, uznaj za offline
            if player_status.last_seen:
                if (timezone.now() - player_status.last_seen).total_seconds() > 300:
                    player_status.is_online = False
                    player_status.save()
            
            data = {
                "is_online": player_status.is_online,
                "last_seen": player_status.last_seen,
                "ip_address": player_status.ip_address,
                "screen_resolution": player_status.screen_resolution,
                "version": player_status.version
            }
            
            return Response(data)
        
        except PlayerStatus.DoesNotExist:
            return Response({
                "is_online": False,
                "last_seen": None,
                "ip_address": None,
                "screen_resolution": None,
                "version": None
            })
    
    except Stand.DoesNotExist:
        return Response({"error": "Stoisko nie istnieje"}, 
                      status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)