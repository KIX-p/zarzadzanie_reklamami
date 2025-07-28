from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    USER_ROLE_CHOICES = (
        ('superadmin', 'Superadministrator'),
        ('store_admin', 'Administrator sklepu'),
        ('editor', 'Edytor stanowiska'),
        ('player', 'Odtwarzacz'),
    )
    
    role = models.CharField(max_length=20, choices=USER_ROLE_CHOICES, default='editor')
    
    # For store admins
    managed_store = models.ForeignKey('advertisements.Store', on_delete=models.SET_NULL, 
                                     null=True, blank=True, related_name='administrators')
    
    # For stand editors
    managed_stand = models.ForeignKey('advertisements.Stand', on_delete=models.SET_NULL, 
                                     null=True, blank=True, related_name='editors')
    
    # For player
    access_token = models.CharField(max_length=64, blank=True, null=True)
    
    def is_superadmin(self):
        return self.role == 'superadmin'
    
    def is_store_admin(self):
        return self.role == 'store_admin'
    
    def is_editor(self):
        return self.role == 'editor'
    
    def is_player(self):
        return self.role == 'player'