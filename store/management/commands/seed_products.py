import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from store.models import Product, Category
from faker import Faker

class Command(BaseCommand):
    help = 'Генерує тестові товари для магазину'

    def handle(self, *args, **kwargs):
        fake = Faker('uk_UA')  # Українська мова
        
        # 1. Створюємо базові категорії, якщо їх немає
        categories_data = {
            'Напої': ['Кола', 'Фанта', 'Спрайт', 'Сік', 'Вода', 'Енергетик', 'Чай', 'Кава'],
            'Снеки': ['Чіпси', 'Сухарики', 'Горішки', 'Попкорн', 'Шоколадка', 'Печиво'],
            'Молочка': ['Молоко', 'Кефір', 'Йогурт', 'Сирок', 'Масло', 'Сметана'],
            'Бакалія': ['Гречка', 'Рис', 'Макарони', 'Цукор', 'Сіль', 'Олія'],
            'Фрукти': ['Яблуко', 'Банан', 'Апельсин', 'Лимон', 'Груша']
        }

        self.stdout.write("Починаю генерацію...")
        total_created = 0

        for cat_name, product_names in categories_data.items():
            # get_or_create повертає кортеж (об'єкт, чи_створено)
            category, created = Category.objects.get_or_create(name=cat_name)
            
            if created:
                self.stdout.write(f"Створено категорію: {cat_name}")

            # Генеруємо по 1-3 різновидів кожного товару
            for prod_base_name in product_names:
                for _ in range(random.randint(1, 3)):
                    
                    # Випадкові параметри
                    if cat_name == 'Напої':
                        weight_opts = [
                            (Decimal('0.5'), 'l'),
                            (Decimal('1.0'), 'l'),
                            (Decimal('2.0'), 'l')
                        ]
                    elif cat_name == 'Фрукти':
                        weight_opts = [
                            (Decimal('0.5'), 'kg'),
                            (Decimal('1.0'), 'kg')
                        ]
                    else:
                        weight_opts = [
                            (Decimal('100'), 'g'),
                            (Decimal('200'), 'g'),
                            (Decimal('1'), 'kg')
                        ]
                    
                    w_val, w_unit = random.choice(weight_opts)
                    
                    full_name = f"{prod_base_name} {w_val}{w_unit} '{fake.company()}'"
                    
                    sku = fake.ean8()  # Штрихкод
                    purchase_price = Decimal(str(random.randint(10, 200)))
                    price = purchase_price * Decimal(str(random.uniform(1.2, 1.5)))  # Націнка 20-50%
                    quantity = Decimal(str(random.randint(0, 100)))

                    # Створюємо товар
                    Product.objects.create(
                        category=category,
                        name=full_name,
                        sku=sku,
                        weight_value=w_val,
                        weight_unit=w_unit,
                        purchase_price=purchase_price,
                        price=round(price, 2),
                        quantity=quantity,
                        description=fake.text(max_nb_chars=50)
                    )
                    total_created += 1
        
        self.stdout.write(self.style.SUCCESS(f'✅ Успішно додано {total_created} товарів!'))