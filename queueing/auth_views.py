from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from django.contrib.auth import authenticate, logout
from django.contrib.auth.models import User
from .auth_serializers import (
    UserSerializer, LoginSerializer, 
    RegisterStaffSerializer, ChangePasswordSerializer
)
from .authentication import set_jwt_cookies, delete_jwt_cookies

@extend_schema(
    tags=['Authentication'],
    summary='Login to get JWT tokens',
    description="Login user and get JWT tokens in HTTP-only cookies.",
    request=LoginSerializer,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="✅ Login successful",
            examples=[
                OpenApiExample(
                    'Success Response',
                    value={
                        'success': True,
                        'message': 'Login Successfully',
                        'user': {
                            'id': 1,
                            'username': 'john',
                            'email': 'john@email.com',
                            'is_staff': False
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="❌ Login failed",
            examples=[
                OpenApiExample(
                    'Wrong Password',
                    value={
                        'success': False,
                        'message': 'Invalid Data',
                        'errors': {'non_field_errors': ['Invalid credentials']}
                    }
                ),
                OpenApiExample(
                    'Disabled Account',
                    value={
                        'success': False,
                        'message': 'Account is disabled'
                    }
                )
            ]
        )
    },
    examples=[
        OpenApiExample(
            'Example Request',
            value={'username': 'testuser', 'password': 'testpass123'}
        )
    ]
)
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if not user.is_active:
                return Response({'success': False, 'message':'Account is disabled'}, status=status.HTTP_400_BAD_REQUEST)
            
            user_data = UserSerializer(user).data
            response = Response({'success': True, 'message': 'Login Successfully', 'user':user_data})
            response = set_jwt_cookies(response, user)
            return response
        else:
            return Response({'success': False, 'message':'Invalid Data', 'errors': serializer.errors}, status=400)


@extend_schema(
    tags=['Authentication'],
    summary='Logout user',
    description="""Logout and clear JWT cookies.
    Clears: access_token and refresh_token cookies
    """,
    responses={
        200: OpenApiResponse(
            description="Logout successful",
            examples=[
                OpenApiExample(
                    'Success Response',
                    value={'success': True, 'message': 'Logout successfully'}
                )
            ]
        )
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def logout_view(request):
    logout(request)
    response = Response({'success': True, 'message':'Logout successfully'})
    response = delete_jwt_cookies(response)
    return response


@extend_schema(
    tags=['Authentication'],
    summary='Change password',
    description="""Change password for logged-in user.
    After changing password, user is automatically logged out.
    User must login again with new password.
    """,
    request=ChangePasswordSerializer,
    responses={
        200: OpenApiResponse(
            description="Password changed",
            examples=[
                OpenApiExample(
                    'Success Response',
                    value={
                        'success': True,
                        'message': 'Password changed successfully please login again'
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description="Change failed",
            examples=[
                OpenApiExample(
                    'Wrong old password',
                    value={
                        'success': False,
                        'message': 'old password is incorrect'
                    }
                )
            ]
        )
    },
    examples=[
        OpenApiExample(
            'Example Request',
            value={
                'old_password': 'oldpass123',
                'new_password': 'newpass456',
                'confirm_password': 'newpass456'
            }
        )
    ]
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    serializer = ChangePasswordSerializer(data=request.data)

    if serializer.is_valid():
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response({'success': False, 'message': 'old password is incorrect'}, status=status.HTTP_400_BAD_REQUEST)
        
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        logout(request)
        response = Response({'success': True, 'message': 'Password changed successfully please login again'})
        response = delete_jwt_cookies(response)
        return response
    return Response({'success': False, 'message': 'Invalid Data', 'errors': serializer.errors}, status=400)


@extend_schema(
    tags=['Authentication'],
    summary='Get current user info',
    description="Get information about currently logged-in user",
    responses={
        200: OpenApiResponse(
            description="✅ User information",
            examples=[
                OpenApiExample(
                    'Success Response',
                    value={
                        'success': True,
                        'user': {
                            'id': 1,
                            'username': 'john',
                            'email': 'john@email.com',
                            'first_name': 'John',
                            'last_name': 'Doe',
                            'is_staff': True,
                            'is_active': True
                        }
                    }
                )
            ]
        ),
        401: OpenApiResponse(
            description="❌ Not logged in",
            examples=[
                OpenApiExample(
                    'Unauthorized',
                    value={'detail': 'Authentication credentials were not provided.'}
                )
            ]
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user_view(request):
    user = request.user
    serializer = UserSerializer(user)
    return Response({'success': True, 'user': serializer.data})


@extend_schema(
    tags=['Authentication'],
    summary='Refresh access token',
    description="Get new access token using refresh token.",
    responses={
        200: OpenApiResponse(
            description="✅ Token refreshed",
            examples=[
                OpenApiExample(
                    'Success Response',
                    value={'success': True, 'message': 'Token refreshed'}
                )
            ]
        ),
        400: OpenApiResponse(
            description="❌ No refresh token",
            examples=[
                OpenApiExample(
                    'Missing Token',
                    value={'success': False, 'message': 'Refresh Token not found'}
                )
            ]
        ),
        401: OpenApiResponse(
            description="❌ Invalid refresh token",
            examples=[
                OpenApiExample(
                    'Invalid Token',
                    value={'success': False, 'message': 'Invalid refresh token'}
                )
            ]
        )
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def refresh_token_view(request):
    refresh_token = request.COOKIES.get('refresh_token')
    if not refresh_token:
        return Response({'success': False, 'message': 'Refresh Token not found'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken(refresh_token)
        user = User.objects.get(id=refresh.payload['user_id'])
        response = Response({'success': True, 'message': 'Token refreshed'})
        response = set_jwt_cookies(response, user)
        return response
    except Exception as e:
        return Response({
            'success': False,
            'message': 'Invalid refresh token'
        }, status=status.HTTP_401_UNAUTHORIZED)


# ==================== ADMIN ENDPOINTS ====================

@extend_schema(
    tags=['Admin'],
    summary='Create staff account (Admin only)',
    description="""Create new staff user. Requires admin privileges.  
    👑 **Permission:** Only users with `is_staff=True` can access
    """,
    request=RegisterStaffSerializer,
    responses={
        201: OpenApiResponse(
            description="Staff created",
            examples=[
                OpenApiExample(
                    'Success Response',
                    value={
                        'success': True,
                        'message': 'Staff account created for new_staff',
                        'user': {
                            'id': 2,
                            'username': 'new_staff',
                            'email': 'staff@email.com',
                            'is_staff': True,
                            'is_active': True
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description="Creation failed",
            examples=[
                OpenApiExample(
                    'Validation Error',
                    value={
                        'success': False,
                        'message': 'Account failed to create',
                        'errors': {
                            'username': ['This username already exists.']
                        }
                    }
                )
            ]
        ),
        403: OpenApiResponse(
            description="Not an admin",
            examples=[
                OpenApiExample(
                    'Forbidden',
                    value={'detail': 'You do not have permission to perform this action.'}
                )
            ]
        )
    },
    examples=[
        OpenApiExample(
            'Example Request',
            value={
                'username': 'new_staff',
                'email': 'staff@example.com',
                'password': 'staffpass123',
                'first_name': 'Jane',
                'last_name': 'Smith'
            }
        )
    ]
)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_staff_view(request):
    serializer = RegisterStaffSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response({'success': True, 'message': f'Staff account created for {user.username}', 'user': UserSerializer(user).data}, status=status.HTTP_201_CREATED)
    return Response({'success': False, 'message': 'Account failed to create', 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    tags=['Admin'],
    summary='List all staff (Admin only)',
    description="Get list of all staff users except yourself",
    responses={
        200: OpenApiResponse(
            description="Staff list",
            examples=[
                OpenApiExample(
                    'Success Response',
                    value={
                        'success': True,
                        'count': 2,
                        'staff': [
                            {
                                'id': 2,
                                'username': 'staff1',
                                'email': 'staff1@email.com',
                                'is_staff': True
                            },
                            {
                                'id': 3,
                                'username': 'staff2',
                                'email': 'staff2@email.com',
                                'is_staff': True
                            }
                        ]
                    }
                )
            ]
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_staff_view(request):
    staff_users = User.objects.filter(is_staff=True).exclude(id=request.user.id)
    serializer = UserSerializer(staff_users, many=True)
    return Response({'success': True, 'count': staff_users.count(), 'staff': serializer.data})


@extend_schema(
    tags=['Admin'],
    summary='Delete staff (Admin only)',
    description="Delete a staff user by ID.",
    responses={
        200: OpenApiResponse(
            description="Staff deleted",
            examples=[
                OpenApiExample(
                    'Success Response',
                    value={
                        'success': True,
                        'message': 'Staff account staff1 deleted'
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description="Self-deletion attempt",
            examples=[
                OpenApiExample(
                    'Error Response',
                    value={
                        'success': False,
                        'message': 'Cannot delete your own account'
                    }
                )
            ]
        ),
        404: OpenApiResponse(
            description="Staff not found",
            examples=[
                OpenApiExample(
                    'Error Response',
                    value={
                        'success': False,
                        'message': 'staff user not found'
                    }
                )
            ]
        )
    }
)
@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_staff_view(request, user_id):
    try:
        if request.user.id == user_id:
            return Response({'success': False, 'message':'Cannot delete your own account'}, status=status.HTTP_400_BAD_REQUEST)
        
        user = User.objects.get(id=user_id, is_staff=True)
        username = user.username
        user.delete()
        return Response({'success':True, 'message':f'Staff account {username} deleted'})
    except User.DoesNotExist:
        return Response({'success': False, 'message': 'staff user not found'}, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    tags=['Admin'],
    summary='Update staff (Admin only)',
    description="""Update staff user information.
    ⚠️ **Cannot update password here.** Use change password endpoint.
    """,
    responses={
        200: OpenApiResponse(
            description="Staff updated",
            examples=[
                OpenApiExample(
                    'Success Response',
                    value={
                        'success': True,
                        'message': 'Staff account staff1 updated',
                        'user': {
                            'id': 2,
                            'username': 'updated_staff',
                            'email': 'updated@email.com'
                        }
                    }
                )
            ]
        )
    },
    examples=[
        OpenApiExample(
            'Example Request',
            value={
                'email': 'updated@example.com',
                'first_name': 'Updated',
                'is_active': True
            }
        )
    ]
)
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAdminUser])
def update_staff_view(request, user_id):
    try:
        user = User.objects.get(id=user_id, is_staff=True)
        data = request.data.copy()
        if 'password' in data:
            data.pop('password')

        serializer = UserSerializer(user, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'success':True, 'message': f'Staff account {user.username} updated', 'user': serializer.data})
        return Response({'success':False, 'message':'Invalid data', 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    except User.DoesNotExist:
        return Response({'success': False, 'message':'Staff user not found'}, status=status.HTTP_404_NOT_FOUND)