from django.urls import path
from . import api_views, views

urlpatterns = [
    # API endpoints
    path('api/stand/<int:stand_id>/', api_views.stand_materials, name='api-stand-materials'),
    path('api/token/', api_views.get_token, name='api-get-token'),
    path('api/player/status/', api_views.report_player_status, name='api-player-status'),
    path('api/player/status/<int:stand_id>/', api_views.get_player_status, name='api-get-player-status'),

    # Player view
    path('player/', views.PlayerView.as_view(), name='player-view'),

    # Material management
    path('stand/<int:pk>/materials/', views.StandMaterialsView.as_view(), name='stand-materials'),
    path('stand/<int:stand_id>/materials/order/', views.update_material_order, name='update-material-order'),
    path('material/create/', views.MaterialCreateView.as_view(), name='material-create'),
    path('material/create/<int:stand_id>/', views.MaterialCreateView.as_view(), name='material-create'),
    path('material/<int:pk>/update/', views.MaterialUpdateView.as_view(), name='material-update'),
    path('material/<int:pk>/delete/', views.MaterialDeleteView.as_view(), name='material-delete'),

    # Store management
    path('stores/', views.StoreListView.as_view(), name='store-list'),
    path('store/create/', views.StoreCreateView.as_view(), name='store-create'),
    path('store/<int:pk>/', views.StoreDetailView.as_view(), name='store-detail'),
    path('store/<int:pk>/update/', views.StoreUpdateView.as_view(), name='store-update'),
    path('store/<int:pk>/delete/', views.StoreDeleteView.as_view(), name='store-delete'),

    # Department management
    path('department/create/', views.DepartmentCreateView.as_view(), name='department-create'),
    path('department/<int:pk>/update/', views.DepartmentUpdateView.as_view(), name='department-update'),
    path('department/<int:pk>/delete/', views.DepartmentDeleteView.as_view(), name='department-delete'),

    # Stand management
    path('stand/create/', views.StandCreateView.as_view(), name='stand-create'),
    path('stand/create/<int:department_id>/', views.StandCreateView.as_view(), name='stand-create'),
    path('stand/<int:pk>/update/', views.StandUpdateView.as_view(), name='stand-update'),
    path('stand/<int:pk>/delete/', views.StandDeleteView.as_view(), name='stand-delete'),

    path('stands/<int:pk>/animation/', views.StandAnimationUpdateView.as_view(), name='stand-animation-update'),

    # Kalendarz emisji
    path('stand/<int:stand_id>/schedule/', views.ScheduleCalendarView.as_view(), name='schedule-calendar'),
    path('stand/<int:stand_id>/schedule/create/', views.ScheduleCreateView.as_view(), name='schedule-create'),
    path('schedule/<int:pk>/update/', views.ScheduleUpdateView.as_view(), name='schedule-update'),
    path('schedule/<int:pk>/delete/', views.ScheduleDeleteView.as_view(), name='schedule-delete'),
    path('api/stand/<int:stand_id>/schedule/events/', views.get_schedule_events, name='api-schedule-events'),

]