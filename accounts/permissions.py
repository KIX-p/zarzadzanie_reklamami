from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect
from django.contrib import messages

class SuperadminRequiredMixin(UserPassesTestMixin):
    """Mixin that requires the user to be a superadmin."""
    
    def test_func(self):
        return self.request.user.is_superadmin()
    
    def handle_no_permission(self):
        messages.error(self.request, "Wymagane uprawnienia administratora głównego.")
        return redirect('dashboard')

class StoreAdminRequiredMixin(UserPassesTestMixin):
    """Mixin that requires the user to be a store admin."""
    
    def test_func(self):
        return self.request.user.is_store_admin() or self.request.user.is_superadmin()
    
    def handle_no_permission(self):
        messages.error(self.request, "Wymagane uprawnienia administratora sklepu.")
        return redirect('dashboard')

class EditorRequiredMixin(UserPassesTestMixin):
    """Mixin that requires the user to be an editor."""
    
    def test_func(self):
        return (self.request.user.is_editor() or 
                self.request.user.is_store_admin() or 
                self.request.user.is_superadmin())
    
    def handle_no_permission(self):
        messages.error(self.request, "Wymagane uprawnienia edytora.")
        return redirect('dashboard')

class StoreAccessMixin(UserPassesTestMixin):
    """
    Mixin to check if user has access to a specific store.
    Must be used with views that have self.get_object() returning a Store or an object with a store attribute.
    """
    
    def test_func(self):
        # Try to get the store object
        if hasattr(self, 'get_object'):
            obj = self.get_object()
            
            # Check if object is a store
            if hasattr(obj, 'departments'):
                store = obj
            # Check if object has a store attribute
            elif hasattr(obj, 'store'):
                store = obj.store
            # Check if object has a department that has a store
            elif hasattr(obj, 'department'):
                store = obj.department.store
            else:
                return False
            
            # Check permissions
            if self.request.user.is_superadmin():
                return True
            elif self.request.user.is_store_admin():
                return self.request.user.managed_store == store
            elif self.request.user.is_editor() and hasattr(obj, 'id'):
                # Editors can only access their own stand
                return self.request.user.managed_stand == obj
            
            return False
        
        return False
    
    def handle_no_permission(self):
        messages.error(self.request, "Brak uprawnień do dostępu do tego zasobu.")
        return redirect('dashboard')