from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

# === ФУНКЦІЯ-РЕГУЛЮВАЛЬНИК ===
def root_dispatcher(request):
    # 1. Якщо не увійшов -> на Логін
    if not request.user.is_authenticated:
        return redirect('login')
    
    # 2. Якщо це Адмін (Superuser) -> в Адмінку Django
    if request.user.is_superuser:
        return redirect('/admin/')
    
    # 3. Всі інші (Касири) -> на POS-термінал
    return redirect('category_list')

urlpatterns = [
    # Головна сторінка ('') викликає нашого регулювальника
    path('', root_dispatcher, name='root'),
    
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('store/', include('store.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)