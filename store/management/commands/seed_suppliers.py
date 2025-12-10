import random
from django.core.management.base import BaseCommand
from faker import Faker
from store.models import Supplier, Category

class Command(BaseCommand):
    help = "Генерує постачальників і прив'язує їх до категорій"

    def handle(self, *args, **options):
        fake = Faker('uk_UA')

        categories_data = {
            'Напої': [],
            'Снеки': [],
            'Молочка': [],
            'Бакалія': [],
            'Фрукти': [],
        }

        self.stdout.write(self.style.WARNING("⚠️ Видаляю старих постачальників..."))
        Supplier.objects.all().delete()

        # гарантуємо наявність категорій
        categories = {}
        for cat_name in categories_data.keys():
            category, _ = Category.objects.get_or_create(name=cat_name)
            categories[cat_name] = category

        created = 0
        self.stdout.write("Створюю постачальників...")

        for cat_name, category in categories.items():
            # по 2-3 постачальники на категорію
            for _ in range(random.randint(2, 3)):
                supplier = Supplier.objects.create(
                    name=fake.company(),
                    email=fake.email(),
                    phone=fake.phone_number(),
                    address=fake.address(),
                    notes=f"Спеціалізація: {cat_name}"
                )
                supplier.categories.add(category)
                # іноді додаємо другу категорію для перетину
                other_cats = [c for cname, c in categories.items() if cname != cat_name]
                if other_cats and random.random() < 0.3:
                    supplier.categories.add(random.choice(other_cats))
                created += 1

        self.stdout.write(self.style.SUCCESS(f"✅ Створено {created} постачальників"))
