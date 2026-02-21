from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework.validators import UniqueValidator

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'is_staff', 'is_superuser']
        read_only_fields = ['id', 'is_staff']

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True, error_messages={'required': 'Username is required','blank': 'Username cannot be empty'})
    password = serializers.CharField(required=True, write_only = True, style={'input_type': 'password'},
                                     error_messages={'required': 'Password is required','blank': 'Password cannot be empty'})

class RegisterStaffSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    service_id = serializers.IntegerField(required=True, write_only=True) 

    class Meta:
        model = User
        fields = ['username', 'password', 'password2', 'service_id']  

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        
        from .models import Service
        service_id = attrs.get('service_id')
        if not Service.objects.filter(id=service_id).exists():
            raise serializers.ValidationError({"service_id": "Service does not exist"})
        
        return attrs
    
    def create(self, validated_data):
        service_id = validated_data.pop('service_id')
        validated_data.pop('password2')
        
        user = User.objects.create(username=validated_data['username'], is_staff=True)
        user.set_password(validated_data['password'])
        user.save()
        
        # Assign to service immediately
        from .models import StaffProfile, Service
        service = Service.objects.get(id=service_id)
        StaffProfile.objects.create(user=user, assigned_service=service, role='staff', can_manage_queue=True)
        
        return user
    
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    confirm_password = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"new_password": "New passwords don't match."})
        return attrs

class CreateAdminSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['username', 'password', 'password2']

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs
    
    def create(self, validated_data):
        user = User.objects.create(
            username=validated_data['username'],
            is_staff=True,
            is_superuser=True
        )
        user.set_password(validated_data['password'])
        user.save()

        from .models import StaffProfile
        StaffProfile.objects.create(
            user=user,
            role='admin',
            can_manage_queue=True
        )
        
        return user