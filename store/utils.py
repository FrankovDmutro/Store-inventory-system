from functools import wraps
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

# Чітка відповідність ролей: кожен має свою зону
ROLE_NONE = 0
ROLE_CASHIER = 1
ROLE_MANAGER = 2
ROLE_ADMIN = 3


def get_role_level(user):
    if not user.is_authenticated:
        return ROLE_NONE
    if user.is_superuser:
        return ROLE_ADMIN
    if user.groups.filter(name='Managers').exists() or user.is_staff:
        return ROLE_MANAGER
    if user.groups.filter(name='Cashiers').exists():
        return ROLE_CASHIER
    # За замовчуванням відносимо до касирів, щоб не блокувати користувача без групи
    return ROLE_CASHIER


def role_home_url(role_level):
    if role_level == ROLE_ADMIN:
        return reverse('admin:index')
    if role_level == ROLE_MANAGER:
        return reverse('manager_dashboard')
    if role_level == ROLE_CASHIER:
        return reverse('category_list')
    return settings.LOGIN_URL


def role_required(required_role_level):
    """Декоратор: пускає тільки точну роль, інших тихо переспрямовує додому."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user_level = get_role_level(request.user)

            if user_level != required_role_level:
                return redirect(role_home_url(user_level))

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator
