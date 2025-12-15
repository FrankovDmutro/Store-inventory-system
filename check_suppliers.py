import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shop_core.settings')
django.setup()

from store.models import Product, Supplier

products_without_supplier = Product.objects.filter(supplier__isnull=True).count()
print(f'Товарів без постачальника: {products_without_supplier}')

suppliers = Supplier.objects.all()
print(f'Всього постачальників: {suppliers.count()}')

for s in suppliers:
    print(f'{s.name}: {s.products.count()} товарів')

print("\nПриклади товарів без постачальника:")
for p in Product.objects.filter(supplier__isnull=True)[:5]:
    print(f"  - {p.name} (ID: {p.id})")
