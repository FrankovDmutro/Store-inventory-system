from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

# === ФУНКЦІЯ-РЕГУЛЮВАЛЬНИК ===
def root_redirect(request):
    # 1. Якщо не авторизований -> на сторінку входу
    if not request.user.is_authenticated:
        return redirect('login')
    
    # 2. Якщо це Суперюзер (Власник) -> в Адмінку
    if request.user.is_superuser:
        return redirect('/admin/')
    
    # 3. Всі інші (Касири) -> на сторінку категорій
    return redirect('category_list')

urlpatterns = [
    # Головна сторінка ('') викликає нашу функцію
    path('', root_redirect, name='root'),
    
    path('admin/', admin.site.urls),
    
    # Система акаунтів (Login/Logout) - ОБОВ'ЯЗКОВО!
    path('accounts/', include('django.contrib.auth.urls')),
    
    # Наш магазин
    path('store/', include('store.urls')), 
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)