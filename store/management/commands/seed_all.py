import random
from decimal import Decimal, ROUND_HALF_UP
from django.core.management.base import BaseCommand
from faker import Faker
from store.models import (
    Category,
    Supplier,
    Product,
    Order,
    OrderItem,
    Purchase,
    PurchaseItem,
)

class Command(BaseCommand):
    help = "Повне перегенерування: категорії, постачальники, товари (видаляє старі дані)"

    def handle(self, *args, **options):
        fake = Faker('uk_UA')

        categories_data = {
            'Напої': ['Кола', 'Фанта', 'Спрайт', 'Сік', 'Вода', 'Енергетик', 'Чай', 'Кава'],
            'Снеки': ['Чіпси', 'Сухарики', 'Горішки', 'Попкорн', 'Шоколадка', 'Печиво'],
            'Набіл': ['Молоко', 'Кефір', 'Йогурт', 'Сирок', 'Масло', 'Сметана'],
            'Бакалія': ['Гречка', 'Рис', 'Макарони', 'Цукор', 'Сіль', 'Олія'],
            'Фрукти': ['Яблуко', 'Банан', 'Апельсин', 'Лимон', 'Груша'],
        }

        self.stdout.write(self.style.WARNING("⚠️ Очищаю дані (чеки, поставки, товари, постачальники, категорії)..."))
        OrderItem.objects.all().delete()
        Order.objects.all().delete()
        PurchaseItem.objects.all().delete()
        Purchase.objects.all().delete()
        Product.objects.all().delete()
        Supplier.objects.all().delete()
        Category.objects.all().delete()

        # Створюємо категорії
        self.stdout.write("Створюю категорії...")
        categories = {}
        for cat_name in categories_data.keys():
            category = Category.objects.create(name=cat_name)
            categories[cat_name] = category
        self.stdout.write(self.style.SUCCESS(f"✅ Створено {len(categories)} категорій"))

        # Створюємо постачальників
        self.stdout.write("Створюю постачальників...")
        suppliers_by_cat = {name: [] for name in categories.keys()}
        total_suppliers = 0
        for cat_name, category in categories.items():
            for _ in range(random.randint(2, 3)):
                supplier = Supplier.objects.create(
                    name=fake.company(),
                    email=fake.email(),
                    phone=fake.phone_number(),
                    address=fake.address(),
                    notes=f"Спеціалізація: {cat_name}",
                )
                supplier.categories.add(category)
                other_categories = [c for cname, c in categories.items() if cname != cat_name]
                if other_categories and random.random() < 0.3:
                    supplier.categories.add(random.choice(other_categories))
                suppliers_by_cat[cat_name].append(supplier)
                total_suppliers += 1
        self.stdout.write(self.style.SUCCESS(f"✅ Створено {total_suppliers} постачальників"))

        # Створюємо товари
        self.stdout.write("Створюю товари...")
        total_products = 0
        for cat_name, product_names in categories_data.items():
            category = categories[cat_name]
            cat_suppliers = suppliers_by_cat.get(cat_name, [])

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
                        description=fake.text(max_nb_chars=60),
                    )
                    total_products += 1

        self.stdout.write(self.style.SUCCESS(f"✅ Створено {total_products} товарів"))
        self.stdout.write(self.style.SUCCESS("Готово!"))
