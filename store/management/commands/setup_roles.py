from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from store.models import Product, Category, Order, OrderItem, Supplier, Purchase


class Command(BaseCommand):
    help = 'Створює групи Cashiers та Managers і налаштовує їм права'

    def handle(self, *args, **kwargs):
        cashier_group, _ = Group.objects.get_or_create(name='Cashiers')
        manager_group, _ = Group.objects.get_or_create(name='Managers')

        # === Контент-тайпи (моделі) ===
        ct_product = ContentType.objects.get_for_model(Product)
        ct_category = ContentType.objects.get_for_model(Category)
        ct_order = ContentType.objects.get_for_model(Order)
        ct_order_item = ContentType.objects.get_for_model(OrderItem)
        ct_supplier = ContentType.objects.get_for_model(Supplier)
        ct_purchase = ContentType.objects.get_for_model(Purchase)

        # === КАСИР ===
        cashier_codenames = [
            'view_product',
            'view_category',
            'add_order',        # створювати чек
            'view_order',       # бачити свої чеки
            'add_orderitem',    # додавати позиції в чек
        ]
        cashier_perms = []
        for codename in cashier_codenames:
            perm = Permission.objects.filter(codename=codename, content_type__app_label='store').first()
            if perm:
                cashier_perms.append(perm)
            else:
                self.stdout.write(self.style.WARNING(f"Право {codename} не знайдено"))
        cashier_group.permissions.set(cashier_perms)
        self.stdout.write(self.style.SUCCESS('✅ Група Cashiers налаштована (тільки продаж)'))

        # === МЕНЕДЖЕР ===
        manager_codenames = [
            # товари/категорії
            'view_product', 'change_product', 'add_product',
            'view_category', 'add_category',
            # постачання
            'view_supplier', 'add_supplier', 'change_supplier',
            'view_purchase', 'add_purchase', 'change_purchase',
            # чеки (перегляд)
            'view_order',
        ]
        manager_perms = []
        for codename in manager_codenames:
            perm = Permission.objects.filter(codename=codename, content_type__app_label='store').first()
            if perm:
                manager_perms.append(perm)
        manager_group.permissions.set(manager_perms)
        self.stdout.write(self.style.SUCCESS('✅ Група Managers налаштована (склад + аналітика)'))
