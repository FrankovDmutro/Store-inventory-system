from django.shortcuts import redirect
from .utils import get_role_level, role_home_url, ROLE_ADMIN


class RoleBasedAccessMiddleware:
    """Middleware: блокує доступ до /admin/ для неадмінів."""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Перевіряємо чи це запит до адмінки
        if request.path.startswith('/admin/') and not request.path.startswith('/admin/login/'):
            if request.user.is_authenticated:
                user_level = get_role_level(request.user)
                # Якщо це не адмін - тихо редіректимо на домашню сторінку
                if user_level != ROLE_ADMIN:
                    return redirect(role_home_url(user_level))
        
        response = self.get_response(request)
        return response
