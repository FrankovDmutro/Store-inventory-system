from django.shortcuts import render
from .models import Product

def product_list(request):
    # 1. Дістаємо всі товари з бази даних
    products = Product.objects.all()
    
    # 2. Віддаємо їх у файл дизайну (шаблон)
    return render(request, 'store/product_list.html', {'products': products})