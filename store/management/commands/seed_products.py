import random
from django.core.management.base import BaseCommand
from store.models import Product, Category
from faker import Faker

class Command(BaseCommand):
    help = 'Генерує тестові товари для магазину'

    def handle(self, *args, **kwargs):
        fake = Faker('uk_UA') # Українська мова
        
        # 1. Створюємо базові категорії, якщо їх немає
        categories_data = {
            'Напої': ['Кола', 'Фанта', 'Спрайт', 'Сік', 'Вода', 'Енергетик', 'Чай', 'Кава'],
            'Снеки': ['Чіпси', 'Сухарики', 'Горішки', 'Попкорн', 'Шоколадка', 'Печиво'],
            'Молочка': ['Молоко', 'Кефір', 'Йогурт', 'Сирок', 'Масло', 'Сметана'],
            'Бакалія': ['Гречка', 'Рис', 'Макарони', 'Цукор', 'Сіль', 'Олія'],
            'Фрукти': ['Яблуко', 'Банан', 'Апельсин', 'Лимон', 'Груша']
        }

        self.stdout.write("Починаю генерацію...")

        for cat_name, product_names in categories_data.items():
            # get_or_create повертає кортеж (об'єкт, чи_створено)
            category, created = Category.objects.get_or_create(name=cat_name)
            
            if created:
                self.stdout.write(f"Створено категорію: {cat_name}")

            # Генеруємо по 5-10 різновидів кожного товару
            for prod_base_name in product_names:
                for _ in range(random.randint(1, 3)): # 1-3 варіанти кожного (напр. Кола 0.5, Кола 1л)
                    
                    # Випадкові параметри
                    weight_opts = [('0.5', 'l'), ('1.0', 'l'), ('2.0', 'l')] if cat_name == 'Напої' else [('100', 'g'), ('200', 'g'), ('1', 'kg')]
                    w_val, w_unit = random.choice(weight_opts)
                    
                    full_name = f"{prod_base_name} '{fake.company()}'" # Наприклад: Гречка 'ТОВ Роги і Копита'
                    
                    sku = fake.ean8() # Штрихкод
                    purchase_price = random.randint(10, 200)
                    price = purchase_price * random.uniform(1.2, 1.5) # Націнка 20-50%
                    quantity = random.randint(0, 100)

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
        
        self.stdout.write(self.style.SUCCESS('✅ Успішно додано купу товарів!'))