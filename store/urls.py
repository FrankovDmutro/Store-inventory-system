from django.urls import path
from . import views

urlpatterns = [
    path('', views.category_list, name='category_list'),
    path('manager/', views.manager_dashboard, name='manager_dashboard'),
    path('category/<int:category_id>/', views.category_detail, name='category_detail'),
    
    # API для пошуку
    path('api/search/', views.search_products, name='search_products'),

    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/clear/<int:category_id>/', views.cart_clear, name='cart_clear'),
    path('cart/checkout/<int:category_id>/', views.cart_checkout, name='cart_checkout'),
]