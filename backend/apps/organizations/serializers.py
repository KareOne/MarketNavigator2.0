"""
Organization serializers.
"""
from rest_framework import serializers
from .models import Organization, OrganizationMember
from apps.users.serializers import UserSerializer


class OrganizationSerializer(serializers.ModelSerializer):
    """Organization serializer."""
    
    class Meta:
        model = Organization
        fields = ['id', 'name', 'slug', 'plan_tier', 'created_at']
        read_only_fields = ['id', 'slug', 'created_at']
    
    def create(self, validated_data):
        # Auto-generate slug from name
        from django.utils.text import slugify
        import uuid
        base_slug = slugify(validated_data['name'])
        validated_data['slug'] = f"{base_slug}-{str(uuid.uuid4())[:8]}"
        return super().create(validated_data)


class OrganizationMemberSerializer(serializers.ModelSerializer):
    """Organization member serializer."""
    
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = OrganizationMember
        fields = ['id', 'user', 'role', 'permissions', 'joined_at']
        read_only_fields = ['id', 'joined_at']


class CreateOrganizationSerializer(serializers.Serializer):
    """Serializer for creating organization with owner."""
    
    name = serializers.CharField(max_length=255)
    
    def create(self, validated_data):
        user = self.context['request'].user
        
        # Create organization
        from django.utils.text import slugify
        import uuid
        base_slug = slugify(validated_data['name'])
        slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"
        
        org = Organization.objects.create(
            name=validated_data['name'],
            slug=slug
        )
        
        # Add user as owner
        OrganizationMember.objects.create(
            organization=org,
            user=user,
            role='owner'
        )
        
        return org
