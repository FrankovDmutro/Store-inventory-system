from django.core.management.base import BaseCommand
from django.db import transaction, connection
from django.utils import timezone
from django.core.files.base import ContentFile
from decimal import Decimal
from datetime import timedelta
from store.models import Category, Product, Supplier, Order, OrderItem, WriteOff, Return, ReturnItem, Purchase, PurchaseItem
from django.contrib.auth.models import User
import random
import requests

class Command(BaseCommand):
    help = 'Seed database with demo data (categories, products, orders, writeoffs)'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Clear all data except users and groups first')
        parser.add_argument('--with-images', action='store_true', help='Download product images from LoremFlickr')

    def download_product_image(self, product, category_name):
        """Завантажує картинку для товару з LoremFlickr"""
        # Словник для пошуку картинок (UA -> EN)
        cat_translation = {
            'Молочні продукти': 'dairy',
            'Хлібобулочні вироби': 'bread',
            'Напої': 'drink',
            'Снеки та цукерки': 'snacks',
            'Фрукти': 'fruit',
            'Овочі': 'vegetable',
        }
        
        search_keyword = cat_translation.get(category_name, 'food')
        
        try:
            # Запитуємо випадкову картинку 320x240 по темі категорії
            image_url = f"https://loremflickr.com/320/240/{search_keyword}/all"
            response = requests.get(image_url, timeout=5)
            
            if response.status_code == 200:
                # Зберігаємо файл у поле image
                file_name = f"{product.sku}.jpg"
                product.image.save(file_name, ContentFile(response.content), save=True)
                return True
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"    ⚠️ Помилка при завантаженні фото: {str(e)[:50]}"))
        
        return False

    @transaction.atomic
    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write(self.style.WARNING('Очищення бази іданих...'))
            # Видаляємо всі пов'язані дані
            ReturnItem.objects.all().delete()
            Return.objects.all().delete()
            PurchaseItem.objects.all().delete()
            Purchase.objects.all().delete()
            WriteOff.objects.all().delete()
            OrderItem.objects.all().delete()
            Order.objects.all().delete()
            Product.objects.all().delete()
            Supplier.objects.all().delete()
            Category.objects.all().delete()
            
            self.stdout.write(self.style.SUCCESS('База даних очищена'))

        # === КАТЕГОРІЇ ===
        self.stdout.write(self.style.SUCCESS('Створення категорій...'))
        categories_data = [
            {'name': 'Молочні продукти', 'id': 1},
            {'name': 'Хлібобулочні вироби', 'id': 2},
            {'name': 'Напої', 'id': 3},
            {'name': 'Снеки та цукерки', 'id': 4},
            {'name': 'Фрукти', 'id': 5},
            {'name': 'Овочі', 'id': 6},
        ]

        categories = {}
        for cat_data in categories_data:
            cat, created = Category.objects.get_or_create(
                id=cat_data['id'],
                defaults={'name': cat_data['name']}
            )
            categories[cat_data['name']] = cat
            status = 'Створено' if created else 'Існує'
            self.stdout.write(f"  {status}: {cat.name}")

        # === ПОСТАЧАЛЬНИКИ ===
        self.stdout.write(self.style.SUCCESS('Створення постачальників...'))
        suppliers_data = [
            {'name': 'ТОВ "Молочна Україна"', 'phone': '+380501234567'},
            {'name': 'ЗАО "Хлібобулочна фабрика №1"', 'phone': '+380502234567'},
            {'name': 'ФОП "Постачання напоїв"', 'phone': '+380503234567'},
            {'name': 'ООО "Гурман"', 'phone': '+380504234567'},
            {'name': 'ПП "Свіжі фрукти"', 'phone': '+380505234567'},
            {'name': 'СПД "Овочева база"', 'phone': '+380506234567'},
        ]

        suppliers = {}
        for sup_data in suppliers_data:
            supplier, created = Supplier.objects.get_or_create(
                name=sup_data['name'],
                defaults={'phone': sup_data['phone']}
            )
            suppliers[sup_data['name']] = supplier
            status = 'Створено' if created else 'Існує'
            self.stdout.write(f"  {status}: {supplier.name}")

        # === ТОВАРИ ===
        self.stdout.write(self.style.SUCCESS('Створення товарів...'))
        products_data = [
            # Молочні продукти
            {
                'category': 'Молочні продукти',
                'supplier': 'ТОВ "Молочна Україна"',
                'name': 'Молоко коровине 2.5%',
                'sku': 'MILK001',
                'price': Decimal('45.00'),
                'purchase_price': Decimal('28.00'),
                'quantity': 50,
            },
            {
                'category': 'Молочні продукти',
                'supplier': 'ТОВ "Молочна Україна"',
                'name': 'Йогурт натуральний 500г',
                'sku': 'YOGURT001',
                'price': Decimal('35.00'),
                'purchase_price': Decimal('18.00'),
                'quantity': 40,
            },
            {
                'category': 'Молочні продукти',
                'supplier': 'ТОВ "Молочна Україна"',
                'name': 'Сир "Голландія" 200г',
                'sku': 'CHEESE001',
                'price': Decimal('120.00'),
                'purchase_price': Decimal('65.00'),
                'quantity': 25,
            },
            {
                'category': 'Молочні продукти',
                'supplier': 'ТОВ "Молочна Україна"',
                'name': 'Масло вершкове 200г',
                'sku': 'BUTTER001',
                'price': Decimal('85.00'),
                'purchase_price': Decimal('50.00'),
                'quantity': 35,
            },
            {
                'category': 'Молочні продукти',
                'supplier': 'ТОВ "Молочна Україна"',
                'name': 'Сметана 20% 300мл',
                'sku': 'SOUR001',
                'price': Decimal('42.00'),
                'purchase_price': Decimal('22.00'),
                'quantity': 30,
            },
            {
                'category': 'Молочні продукти',
                'supplier': 'ТОВ "Молочна Україна"',
                'name': 'Кефір 1л',
                'sku': 'KEFIR001',
                'price': Decimal('38.00'),
                'purchase_price': Decimal('20.00'),
                'quantity': 45,
            },
            {
                'category': 'Молочні продукти',
                'supplier': 'ТОВ "Молочна Україна"',
                'name': 'Творог "Українець" 400г',
                'sku': 'COTTAGE001',
                'price': Decimal('55.00'),
                'purchase_price': Decimal('30.00'),
                'quantity': 25,
            },
            {
                'category': 'Молочні продукти',
                'supplier': 'ТОВ "Молочна Україна"',
                'name': 'Молоко згущене 370г',
                'sku': 'CONDMILK001',
                'price': Decimal('48.00'),
                'purchase_price': Decimal('26.00'),
                'quantity': 40,
            },
            # Хлібобулочні
            {
                'category': 'Хлібобулочні вироби',
                'supplier': 'ЗАО "Хлібобулочна фабрика №1"',
                'name': 'Хліб білий нарізний 500г',
                'sku': 'BREAD001',
                'price': Decimal('22.00'),
                'purchase_price': Decimal('12.00'),
                'quantity': 60,
            },
            {
                'category': 'Хлібобулочні вироби',
                'supplier': 'ЗАО "Хлібобулочна фабрика №1"',
                'name': 'Хліб чорний 500г',
                'sku': 'BREAD002',
                'price': Decimal('25.00'),
                'purchase_price': Decimal('13.00'),
                'quantity': 50,
            },
            {
                'category': 'Хлібобулочні вироби',
                'supplier': 'ЗАО "Хлібобулочна фабрика №1"',
                'name': 'Булка молочна 80г',
                'sku': 'BUN001',
                'price': Decimal('8.00'),
                'purchase_price': Decimal('3.50'),
                'quantity': 80,
            },
            {
                'category': 'Хлібобулочні вироби',
                'supplier': 'ЗАО "Хлібобулочна фабрика №1"',
                'name': 'Круасан шоколадний 100г',
                'sku': 'CROISSANT001',
                'price': Decimal('28.00'),
                'purchase_price': Decimal('14.00'),
                'quantity': 40,
            },
            {
                'category': 'Хлібобулочні вироби',
                'supplier': 'ЗАО "Хлібобулочна фабрика №1"',
                'name': 'Лаваш вірменський 250г',
                'sku': 'LAVASH001',
                'price': Decimal('15.00'),
                'purchase_price': Decimal('7.00'),
                'quantity': 70,
            },
            {
                'category': 'Хлібобулочні вироби',
                'supplier': 'ЗАО "Хлібобулочна фабрика №1"',
                'name': 'Батон білий 500г',
                'sku': 'BATON001',
                'price': Decimal('24.00'),
                'purchase_price': Decimal('13.00'),
                'quantity': 45,
            },
            {
                'category': 'Хлібобулочні вироби',
                'supplier': 'ЗАО "Хлібобулочна фабрика №1"',
                'name': 'Булочка з родзинками 100г',
                'sku': 'RBUN001',
                'price': Decimal('12.00'),
                'purchase_price': Decimal('5.00'),
                'quantity': 65,
            },
            # Напої
            {
                'category': 'Напої',
                'supplier': 'ФОП "Постачання напоїв"',
                'name': 'Вода мінеральна "Бортяна" 1.5л',
                'sku': 'WATER001',
                'price': Decimal('18.00'),
                'purchase_price': Decimal('8.00'),
                'quantity': 100,
            },
            {
                'category': 'Напої',
                'supplier': 'ФОП "Постачання напоїв"',
                'name': 'Сік апельсиновий 1л',
                'sku': 'JUICE001',
                'price': Decimal('42.00'),
                'purchase_price': Decimal('22.00'),
                'quantity': 50,
            },
            {
                'category': 'Напої',
                'supplier': 'ФОП "Постачання напоїв"',
                'name': 'Кава мелена "Львів" 250г',
                'sku': 'COFFEE001',
                'price': Decimal('95.00'),
                'purchase_price': Decimal('55.00'),
                'quantity': 30,
            },
            {
                'category': 'Напої',
                'supplier': 'ФОП "Постачання напоїв"',
                'name': 'Чай чорний "Брісбем" 100г',
                'sku': 'TEA001',
                'price': Decimal('75.00'),
                'purchase_price': Decimal('40.00'),
                'quantity': 35,
            },
            {
                'category': 'Напої',
                'supplier': 'ФОП "Постачання напоїв"',
                'name': 'Какао "Несквік" 400г',
                'sku': 'COCOA001',
                'price': Decimal('85.00'),
                'purchase_price': Decimal('48.00'),
                'quantity': 25,
            },
            {
                'category': 'Напої',
                'supplier': 'ФОП "Постачання напоїв"',
                'name': 'Компот "Фрукти" 1л',
                'sku': 'COMPOTE001',
                'price': Decimal('32.00'),
                'purchase_price': Decimal('16.00'),
                'quantity': 60,
            },
            {
                'category': 'Напої',
                'supplier': 'ФОП "Постачання напоїв"',
                'name': 'Морс журавлинний 1л',
                'sku': 'MORSE001',
                'price': Decimal('48.00'),
                'purchase_price': Decimal('26.00'),
                'quantity': 40,
            },
            # Снеки та цукерки
            {
                'category': 'Снеки та цукерки',
                'supplier': 'ООО "Гурман"',
                'name': 'Чіпси "Лейс" 150г',
                'sku': 'CHIPS001',
                'price': Decimal('35.00'),
                'purchase_price': Decimal('18.00'),
                'quantity': 50,
            },
            {
                'category': 'Снеки та цукерки',
                'supplier': 'ООО "Гурман"',
                'name': 'Печиво "Юнісон" 200г',
                'sku': 'COOKIES001',
                'price': Decimal('28.00'),
                'purchase_price': Decimal('14.00'),
                'quantity': 60,
            },
            {
                'category': 'Снеки та цукерки',
                'supplier': 'ООО "Гурман"',
                'name': 'Орішки солені 150г',
                'sku': 'NUTS001',
                'price': Decimal('55.00'),
                'purchase_price': Decimal('32.00'),
                'quantity': 35,
            },
            {
                'category': 'Снеки та цукерки',
                'supplier': 'ООО "Гурман"',
                'name': 'Шоколад "Алпін" 100г',
                'sku': 'CHOCO001',
                'price': Decimal('42.00'),
                'purchase_price': Decimal('24.00'),
                'quantity': 45,
            },
            {
                'category': 'Снеки та цукерки',
                'supplier': 'ООО "Гурман"',
                'name': 'Конфети "Сладур" 250г',
                'sku': 'CANDY001',
                'price': Decimal('65.00'),
                'purchase_price': Decimal('38.00'),
                'quantity': 40,
            },
            {
                'category': 'Снеки та цукерки',
                'supplier': 'ООО "Гурман"',
                'name': 'Попкорн карамельний 100г',
                'sku': 'POPCORN001',
                'price': Decimal('32.00'),
                'purchase_price': Decimal('16.00'),
                'quantity': 50,
            },
            {
                'category': 'Снеки та цукерки',
                'supplier': 'ООО "Гурман"',
                'name': 'Вафлі "Бомба" 200г',
                'sku': 'WAFFLE001',
                'price': Decimal('38.00'),
                'purchase_price': Decimal('20.00'),
                'quantity': 45,
            },
            {
                'category': 'Снеки та цукерки',
                'supplier': 'ООО "Гурман"',
                'name': 'Халва "Ласощі" 300г',
                'sku': 'HALVA001',
                'price': Decimal('58.00'),
                'purchase_price': Decimal('34.00'),
                'quantity': 30,
            },
            # Фрукти
            {
                'category': 'Фрукти',
                'supplier': 'ПП "Свіжі фрукти"',
                'name': 'Яблуко Гала за кг',
                'sku': 'APPLE001',
                'price': Decimal('35.00'),
                'purchase_price': Decimal('18.00'),
                'quantity': 80,
                'weight_value': Decimal('1.0'),
                'weight_unit': 'kg',
            },
            {
                'category': 'Фрукти',
                'supplier': 'ПП "Свіжі фрукти"',
                'name': 'Банан за кг',
                'sku': 'BANANA001',
                'price': Decimal('45.00'),
                'purchase_price': Decimal('24.00'),
                'quantity': 70,
                'weight_value': Decimal('1.0'),
                'weight_unit': 'kg',
            },
            {
                'category': 'Фрукти',
                'supplier': 'ПП "Свіжі фрукти"',
                'name': 'Апельсин за кг',
                'sku': 'ORANGE001',
                'price': Decimal('42.00'),
                'purchase_price': Decimal('22.00'),
                'quantity': 65,
                'weight_value': Decimal('1.0'),
                'weight_unit': 'kg',
            },
            {
                'category': 'Фрукти',
                'supplier': 'ПП "Свіжі фрукти"',
                'name': 'Груша за кг',
                'sku': 'PEAR001',
                'price': Decimal('48.00'),
                'purchase_price': Decimal('26.00'),
                'quantity': 55,
                'weight_value': Decimal('1.0'),
                'weight_unit': 'kg',
            },
            {
                'category': 'Фрукти',
                'supplier': 'ПП "Свіжі фрукти"',
                'name': 'Виноград за кг',
                'sku': 'GRAPE001',
                'price': Decimal('85.00'),
                'purchase_price': Decimal('48.00'),
                'quantity': 40,
                'weight_value': Decimal('1.0'),
                'weight_unit': 'kg',
            },
            {
                'category': 'Фрукти',
                'supplier': 'ПП "Свіжі фрукти"',
                'name': 'Лимон за кг',
                'sku': 'LEMON001',
                'price': Decimal('55.00'),
                'purchase_price': Decimal('30.00'),
                'quantity': 50,
                'weight_value': Decimal('1.0'),
                'weight_unit': 'kg',
            },
            {
                'category': 'Фрукти',
                'supplier': 'ПП "Свіжі фрукти"',
                'name': 'Киви за кг',
                'sku': 'KIWI001',
                'price': Decimal('75.00'),
                'purchase_price': Decimal('42.00'),
                'quantity': 35,
                'weight_value': Decimal('1.0'),
                'weight_unit': 'kg',
            },
            {
                'category': 'Фрукти',
                'supplier': 'ПП "Свіжі фрукти"',
                'name': 'Мандарин за кг',
                'sku': 'MAND001',
                'price': Decimal('58.00'),
                'purchase_price': Decimal('32.00'),
                'quantity': 60,
                'weight_value': Decimal('1.0'),
                'weight_unit': 'kg',
            },
            # Овочі
            {
                'category': 'Овочі',
                'supplier': 'СПД "Овочева база"',
                'name': 'Помідор за кг',
                'sku': 'TOMATO001',
                'price': Decimal('48.00'),
                'purchase_price': Decimal('26.00'),
                'quantity': 90,
                'weight_value': Decimal('1.0'),
                'weight_unit': 'kg',
            },
            {
                'category': 'Овочі',
                'supplier': 'СПД "Овочева база"',
                'name': 'Огірок за кг',
                'sku': 'CUCUMBER001',
                'price': Decimal('38.00'),
                'purchase_price': Decimal('20.00'),
                'quantity': 85,
                'weight_value': Decimal('1.0'),
                'weight_unit': 'kg',
            },
            {
                'category': 'Овочі',
                'supplier': 'СПД "Овочева база"',
                'name': 'Морква за кг',
                'sku': 'CARROT001',
                'price': Decimal('25.00'),
                'purchase_price': Decimal('12.00'),
                'quantity': 100,
                'weight_value': Decimal('1.0'),
                'weight_unit': 'kg',
            },
            {
                'category': 'Овочі',
                'supplier': 'СПД "Овочева база"',
                'name': 'Цибуля за кг',
                'sku': 'ONION001',
                'price': Decimal('22.00'),
                'purchase_price': Decimal('10.00'),
                'quantity': 110,
                'weight_value': Decimal('1.0'),
                'weight_unit': 'kg',
            },
            {
                'category': 'Овочі',
                'supplier': 'СПД "Овочева база"',
                'name': 'Картопля за кг',
                'sku': 'POTATO001',
                'price': Decimal('18.00'),
                'purchase_price': Decimal('8.00'),
                'quantity': 150,
                'weight_value': Decimal('1.0'),
                'weight_unit': 'kg',
            },
            {
                'category': 'Овочі',
                'supplier': 'СПД "Овочева база"',
                'name': 'Перець сладкий за кг',
                'sku': 'PEPPER001',
                'price': Decimal('65.00'),
                'purchase_price': Decimal('36.00'),
                'quantity': 60,
                'weight_value': Decimal('1.0'),
                'weight_unit': 'kg',
            },
            {
                'category': 'Овочі',
                'supplier': 'СПД "Овочева база"',
                'name': 'Капуста за кг',
                'sku': 'CABBAGE001',
                'price': Decimal('28.00'),
                'purchase_price': Decimal('14.00'),
                'quantity': 75,
                'weight_value': Decimal('1.0'),
                'weight_unit': 'kg',
            },
            {
                'category': 'Овочі',
                'supplier': 'СПД "Овочева база"',
                'name': 'Чеснок за кг',
                'sku': 'GARLIC001',
                'price': Decimal('95.00'),
                'purchase_price': Decimal('52.00'),
                'quantity': 40,
                'weight_value': Decimal('1.0'),
                'weight_unit': 'kg',
            },
        ]

        created_count = 0
        for prod_data in products_data:
            category = categories[prod_data['category']]
            supplier = suppliers[prod_data['supplier']]
            
            prod, created = Product.objects.get_or_create(
                sku=prod_data['sku'],
                defaults={
                    'category': category,
                    'supplier': supplier,
                    'name': prod_data['name'],
                    'price': prod_data['price'],
                    'purchase_price': prod_data['purchase_price'],
                    'quantity': prod_data['quantity'],
                    'weight_value': prod_data.get('weight_value'),
                    'weight_unit': prod_data.get('weight_unit', 'pcs'),
                }
            )
            if created:
                created_count += 1
                status = f"  ✓ {prod.name}"
                
                # Завантажуємо картинку якщо запущено з --with-images
                if options.get('with_images'):
                    if self.download_product_image(prod, prod_data['category']):
                        status += " 🖼️"
                
                self.stdout.write(status)

        self.stdout.write(self.style.SUCCESS(f'Створено товарів: {created_count}'))

        # === ЗАМОВЛЕННЯ (ЧЕКИ) ===
        self.stdout.write(self.style.SUCCESS('Створення чеків за останній місяць...'))
        products_list = list(Product.objects.all())
        
        orders_created = 0
        # Починаємо з 30 днів тому
        start_date = timezone.now() - timedelta(days=30)
        
        for day_offset in range(30):  # За 30 днів
            orders_per_day = random.randint(3, 8)
            current_day = start_date + timedelta(days=day_offset)
            
            for order_idx in range(orders_per_day):
                # Встановлюємо випадковий час від 8:00 до 20:00
                hour = random.randint(8, 20)
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                order_time = current_day.replace(hour=hour, minute=minute, second=second)
                
                order = Order.objects.create(created_at=order_time)
                total_price = Decimal('0')
                total_profit = Decimal('0')
                
                # 2-5 товарів у замовленні
                items_count = random.randint(2, 5)
                selected_products = random.sample(products_list, min(items_count, len(products_list)))
                
                for product in selected_products:
                    quantity = random.randint(1, 5)
                    item_total = product.price * quantity
                    item_profit = (product.price - product.purchase_price) * quantity
                    
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=quantity,
                        price=product.price,
                        purchase_price=product.purchase_price
                    )
                    
                    total_price += item_total
                    total_profit += item_profit
                
                order.total_price = total_price
                order.total_profit = total_profit
                order.save()
                orders_created += 1

        self.stdout.write(self.style.SUCCESS(f'Створено чеків: {orders_created}'))

        # === СПИСАННЯ ===
        self.stdout.write(self.style.SUCCESS('Створення записів списання...'))
        writeoffs_created = 0
        
        # Отримуємо менеджера для списань
        manager = User.objects.filter(groups__name='Managers').first()
        if not manager:
            manager = User.objects.first()  # Fallback на першого користувача
        
        reasons = ['damage', 'defect', 'expiry', 'other']
        
        for day_offset in range(5, 31, 5):  # Кожні 5 днів
            writeoff_time = timezone.now() - timedelta(days=day_offset)
            
            # 1-3 товари у списанні
            items_count = random.randint(1, 3)
            selected_products = random.sample(products_list, min(items_count, len(products_list)))
            
            for product in selected_products:
                quantity = random.randint(1, 3)
                reason = random.choice(reasons)
                
                WriteOff.objects.create(
                    product=product,
                    quantity=quantity,
                    reason=reason,
                    manager=manager,
                    created_at=writeoff_time,
                    comment='Демо запис'
                )
                writeoffs_created += 1

        self.stdout.write(self.style.SUCCESS(f'Створено записів списання: {WriteOff.objects.count()}'))

        self.stdout.write(self.style.SUCCESS('\n✅ Seed завершено!'))
        self.stdout.write(f'  Категорій: {len(categories)}')
        self.stdout.write(f'  Товарів: {Product.objects.count()}')
        self.stdout.write(f'  Чеків: {Order.objects.count()}')
        self.stdout.write(f'  Списань: {WriteOff.objects.count()}')
