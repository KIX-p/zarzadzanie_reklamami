from rest_framework import serializers
from .models import Store, Department, Stand, AdvertisementMaterial

class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ['id', 'name', 'location']

class DepartmentSerializer(serializers.ModelSerializer):
    store = StoreSerializer(read_only=True)
    
    class Meta:
        model = Department
        fields = ['id', 'name', 'store']

class AdvertisementMaterialSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = AdvertisementMaterial
        fields = ['id', 'material_type', 'file_url', 'order', 'duration']
    
    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and hasattr(obj.file, 'url'):
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

class StandSerializer(serializers.ModelSerializer):
    department = DepartmentSerializer(read_only=True)
    materials = serializers.SerializerMethodField()
    
    class Meta:
        model = Stand
        fields = ['id', 'name', 'department', 'display_time', 'transition_animation', 'materials']
    
    def get_materials(self, obj):
        # Only return active materials, ordered by the order field
        materials = obj.materials.filter(status='active').order_by('order')
        return AdvertisementMaterialSerializer(materials, many=True, context=self.context).data