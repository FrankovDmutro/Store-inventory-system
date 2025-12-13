from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', views.category_list, name='category_list'),
    # Редірект на manager dashboard
    path('manager/', RedirectView.as_view(pattern_name='manager_dashboard', permanent=False)),
    path('manager', RedirectView.as_view(pattern_name='manager_dashboard', permanent=False)),
    path('manager/dashboard/', views.manager_dashboard, name='manager_dashboard'),
    path('manager/receipts/', views.manager_receipts_list, name='manager_receipts_list'),
    path('manager/receipts', RedirectView.as_view(pattern_name='manager_receipts_list', permanent=False)),
    path('manager/products/', views.manager_products_list, name='manager_products_list'),
    path('manager/products', RedirectView.as_view(pattern_name='manager_products_list', permanent=False)),
    path('manager/suppliers/', views.suppliers_list, name='suppliers_list'),
    path('manager/suppliers', RedirectView.as_view(pattern_name='suppliers_list', permanent=False)),
    path('manager/stats/', views.stats_dashboard, name='stats_dashboard'),
    path('manager/stats', RedirectView.as_view(pattern_name='stats_dashboard', permanent=False)),
    
    # Списання
    path('manager/writeoffs/', views.writeoffs_list, name='writeoffs_list'),
    path('manager/writeoffs', RedirectView.as_view(pattern_name='writeoffs_list', permanent=False)),
    path('manager/writeoffs/create/', views.writeoff_create, name='writeoff_create'),
    path('manager/expired-products/', views.expired_products, name='expired_products'),
    
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
    
    # Чеки (Receipts)
    path('receipt/<int:order_id>/details/', views.receipt_details, name='receipt_details'),
    path('receipt/<int:order_id>/download-pdf/', views.receipt_download_pdf, name='receipt_download_pdf'),
    
    # Чеки для касира (перегляд та повернення)
    path('receipts/', views.receipts_list_cashier, name='receipts_list_cashier'),
    path('receipts', RedirectView.as_view(pattern_name='receipts_list_cashier', permanent=False)),
    path('receipts/<int:order_id>/', views.receipt_detail_cashier, name='receipt_detail_cashier'),
    path('receipts/<int:order_id>/return/', views.process_return, name='process_return'),
]