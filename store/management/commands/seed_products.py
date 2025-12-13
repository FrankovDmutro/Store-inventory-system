import random
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from store.models import Product, Category, Supplier, Order, OrderItem, Purchase, PurchaseItem, WriteOff
from faker import Faker


class Command(BaseCommand):
    help = 'Очищає старі товари і генерує нові тестові товари по категоріях'

    def handle(self, *args, **kwargs):
        fake = Faker('uk_UA')

        categories_data = {
            'Напої': ['Кола', 'Фанта', 'Спрайт', 'Сік', 'Вода', 'Енергетик', 'Чай', 'Кава'],
            'Снеки': ['Чіпси', 'Сухарики', 'Горішки', 'Попкорн', 'Шоколадка', 'Печиво'],
            'Молочка': ['Молоко', 'Кефір', 'Йогурт', 'Сирок', 'Масло', 'Сметана'],
            'Бакалія': ['Гречка', 'Рис', 'Макарони', 'Цукор', 'Сіль', 'Олія'],
            'Фрукти': ['Яблуко', 'Банан', 'Апельсин', 'Лимон', 'Груша']
        }

        self.stdout.write(self.style.WARNING("⚠️ Видаляю старі дані (чеки, списання, поставки, товари)..."))
        OrderItem.objects.all().delete()
        Order.objects.all().delete()
        WriteOff.objects.all().delete()
        PurchaseItem.objects.all().delete()
        Purchase.objects.all().delete()
        Product.objects.all().delete()

        self.stdout.write("Починаю генерацію категорій і товарів...")
        total_created = 0

        for cat_name, product_names in categories_data.items():
            category, _ = Category.objects.get_or_create(name=cat_name)

            # Підтягнемо постачальників, що прив’язані до цієї категорії (може бути порожньо)
            cat_suppliers = list(category.suppliers.all())

            for prod_base_name in product_names:
                for _ in range(random.randint(2, 4)):
                    if cat_name == 'Напої':
                        weight_opts = [(Decimal('0.5'), 'l'), (Decimal('1.0'), 'l'), (Decimal('2.0'), 'l')]
                    elif cat_name == 'Фрукти':
                        weight_opts = [(Decimal('0.5'), 'kg'), (Decimal('1.0'), 'kg')]
                    else:
                        weight_opts = [(Decimal('100'), 'g'), (Decimal('200'), 'g'), (Decimal('1'), 'kg')]

                    w_val, w_unit = random.choice(weight_opts)
                    full_name = f"{prod_base_name} {w_val}{w_unit} '{fake.company()}""'"
                    sku = fake.ean8()

                    purchase_price = Decimal(random.randint(10, 200)).quantize(Decimal('0.01'))
                    price = (purchase_price * Decimal(str(random.uniform(1.20, 1.50)))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    if price < purchase_price:
                        price = (purchase_price * Decimal('1.25')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                    quantity = Decimal(random.randint(0, 120))

                    supplier = random.choice(cat_suppliers) if cat_suppliers else None
                    
                    # Додаємо термін придатності для певних категорій
                    expiry_date = None
                    if cat_name in ['Напої', 'Молочка', 'Фрукти']:
                        # Для скоропсувних продуктів - від 7 до 90 днів
                        days_until_expiry = random.randint(7, 90)
                        expiry_date = (timezone.now() + timedelta(days=days_until_expiry)).date()
                    elif cat_name == 'Снеки':
                        # Для снеків - від 30 до 180 днів
                        days_until_expiry = random.randint(30, 180)
                        expiry_date = (timezone.now() + timedelta(days=days_until_expiry)).date()
                    # Для бакалії термін не ставимо (або дуже довгий)

                    Product.objects.create(
                        category=category,
                        supplier=supplier,
                        name=full_name,
                        sku=sku,
                        weight_value=w_val,
                        weight_unit=w_unit,
                        purchase_price=purchase_price,
                        price=price,
                        quantity=quantity,
                        expiry_date=expiry_date,
                        description=fake.text(max_nb_chars=60)
                    )
                    total_created += 1

        self.stdout.write(self.style.SUCCESS(f'✅ Успішно додано {total_created} товарів!'))