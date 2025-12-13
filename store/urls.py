from django.urls import path
from django.shortcuts import redirect
from . import views

urlpatterns = [
    path('', views.category_list, name='category_list'),
    # Тримай сумісність: старий шлях редіректить на новий /manager
    path('manager/', lambda request: redirect('manager_dashboard')),
    path('manager', lambda request: redirect('manager_dashboard')),
    path('manager/dashboard/', views.manager_dashboard, name='manager_dashboard'),
    path('manager/receipts/', views.manager_receipts_list, name='manager_receipts_list'),
    path('manager/receipts', lambda request: redirect('manager_receipts_list')),
    path('manager/products/', views.manager_products_list, name='manager_products_list'),
    path('manager/products', lambda request: redirect('manager_products_list')),
    path('manager/suppliers/', views.suppliers_list, name='suppliers_list'),
    path('manager/suppliers', lambda request: redirect('suppliers_list')),
    path('manager/stats/', views.stats_dashboard, name='stats_dashboard'),
    path('manager/stats', lambda request: redirect('stats_dashboard')),
    path('category/<int:category_id>/', views.category_detail, name='category_detail'),
    
    # API для пошуку
    path('api/search/', views.search_products, name='search_products'),
    path('api/purchases/draft/', views.create_purchase_draft, name='create_purchase_draft'),
    
    # Постачальники та поставки
    path('supplier/create/', views.create_supplier, name='create_supplier'),
    path('purchase/create/', views.create_purchase, name='create_purchase'),

    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/clear/<int:category_id>/', views.cart_clear, name='cart_clear'),
    path('cart/checkout/<int:category_id>/', views.cart_checkout, name='cart_checkout'),
]