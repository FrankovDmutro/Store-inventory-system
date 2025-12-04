from django.urls import path
from . import views

urlpatterns = [
    # Головна (список категорій)
    path('', views.category_list, name='category_list'),
    
    # Екран каси (товари + кошик)
    path('category/<int:category_id>/', views.category_detail, name='category_detail'),
    
    # Кнопки кошика (вони не відкривають сторінок, просто виконують дію і повертають назад)
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/clear/<int:category_id>/', views.cart_clear, name='cart_clear'),
    path('cart/checkout/<int:category_id>/', views.cart_checkout, name='cart_checkout'),
]