from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.contrib.auth.views import LoginView
from store import views as store_views
from store.utils import get_role_level, role_home_url

# === ФУНКЦІЯ-РЕГУЛЮВАЛЬНИК ===
def root_redirect(request):
    # 1. Якщо не авторизований -> на сторінку входу
    if not request.user.is_authenticated:
        return redirect('login')
    
    return redirect(role_home_url(get_role_level(request.user)))

# Кастомний LoginView - редіректить авторизованих
class CustomLoginView(LoginView):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(role_home_url(get_role_level(request.user)))
        return super().dispatch(request, *args, **kwargs)

urlpatterns = [
    # Головна сторінка ('') викликає нашу функцію
    path('', root_redirect, name='root'),
    
    path('admin/', admin.site.urls),

    # Дашборд менеджера
    path('manager/', store_views.manager_dashboard, name='manager_dashboard'),
    
    # Кастомний Login (перевіряє чи юзер вже залогінений)
    path('login/', CustomLoginView.as_view(template_name='registration/login.html'), name='login'),
    
    # Інші auth URLs (logout, etc.)
    path('accounts/', include('django.contrib.auth.urls')),
    
    # Наш магазин
    path('store/', include('store.urls')), 
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)