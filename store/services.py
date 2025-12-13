"""
Сервісний шар для бізнес-логіки.
Thin Views, Fat Services - складна логіка виноситься сюди.
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .models import Product, Supplier, Purchase, PurchaseItem, Order, OrderItem


class PurchaseService:
    """Сервіс для роботи з поставками."""
    
    @staticmethod
    @transaction.atomic
    def create_purchase_from_items(items_data, expected_dates_data=None):
        """
        Створює поставки, групуючи товари по постачальниках.
        
        Args:
            items_data: list[dict] - [{product_id, quantity, unit_cost}, ...]
            expected_dates_data: dict - {supplier_id: datetime_string, ...}
            
        Returns:
            list[dict] - Інформація про створені поставки
        """
        if not items_data:
            return []
        
        # Групуємо товари по постачальниках
        supplier_groups = {}
        for item in items_data:
            try:
                product = Product.objects.select_related('supplier').get(id=item['product_id'])
                supplier_id = product.supplier_id
                
                if supplier_id not in supplier_groups:
                    supplier_groups[supplier_id] = {
                        'supplier': product.supplier,
                        'items': []
                    }
                
                supplier_groups[supplier_id]['items'].append({
                    'product': product,
                    'quantity': int(item['quantity']),
                    'unit_cost': Decimal(str(item['unit_cost']))
                })
            except (Product.DoesNotExist, KeyError, ValueError):
                continue
        
        # Створюємо поставки для кожного постачальника
        created_purchases = []
        for supplier_id, group_data in supplier_groups.items():
            supplier = group_data['supplier']
            items = group_data['items']
            
            # Очікувана дата для цього постачальника
            expected_date = None
            if expected_dates_data and str(supplier_id) in expected_dates_data:
                try:
                    expected_date = timezone.datetime.fromisoformat(
                        expected_dates_data[str(supplier_id)].replace('Z', '+00:00')
                    )
                except (ValueError, AttributeError):
                    pass
            
            # Створюємо поставку
            purchase = Purchase.objects.create(
                supplier=supplier,
                expected_date=expected_date,
                status='draft'
            )
            
            # Додаємо позиції
            total_cost = Decimal('0')
            for item_data in items:
                PurchaseItem.objects.create(
                    purchase=purchase,
                    product=item_data['product'],
                    quantity=item_data['quantity'],
                    unit_cost=item_data['unit_cost']
                )
                total_cost += item_data['quantity'] * item_data['unit_cost']
            
            purchase.total_cost = total_cost
            purchase.save(update_fields=['total_cost'])
            
            created_purchases.append({
                'id': purchase.id,
                'supplier': supplier.name,
                'items': len(items),
                'total': float(total_cost)
            })
        
        return created_purchases


class OrderService:
    """Сервіс для роботи з чеками (замовленнями)."""
    
    @staticmethod
    @transaction.atomic
    def create_order_from_cart(cart_items):
        """
        Створює чек з кошика, списує товар зі складу.
        
        Args:
            cart_items: list[dict] - [{product_id, quantity}, ...]
            
        Returns:
            Order - Створений чек
            
        Raises:
            ValueError - Якщо недостатньо товару
        """
        if not cart_items:
            raise ValueError("Кошик порожній")
        
        order = Order.objects.create()
        total_price = Decimal('0')
        total_profit = Decimal('0')
        
        for item in cart_items:
            try:
                product = Product.objects.select_for_update().get(id=item['product_id'])
                quantity = int(item['quantity'])
                
                # Перевірка залишку
                if product.quantity < quantity:
                    raise ValueError(
                        f"Недостатньо товару '{product.name}'. "
                        f"На складі: {product.quantity}, потрібно: {quantity}"
                    )
                
                # Створюємо позицію чека
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    price=product.price,
                    purchase_price=product.purchase_price
                )
                
                # Списуємо товар
                product.quantity -= quantity
                product.save(update_fields=['quantity'])
                
                # Рахуємо суми
                item_total = quantity * product.price
                item_profit = quantity * (product.price - product.purchase_price)
                total_price += item_total
                total_profit += item_profit
                
            except Product.DoesNotExist:
                raise ValueError(f"Товар з ID {item['product_id']} не знайдено")
        
        # Оновлюємо підсумки чека
        order.total_price = total_price
        order.total_profit = total_profit
        order.save(update_fields=['total_price', 'total_profit'])
        
        return order


class SupplierService:
    """Сервіс для роботи з постачальниками."""
    
    @staticmethod
    def get_suppliers_with_stats():
        """
        Повертає список постачальників зі статистикою товарів.
        
        Returns:
            list[dict] - Постачальники з кількістю товарів та низьким залишком
        """
        suppliers = Supplier.objects.all().order_by('name')
        result = []
        
        for supplier in suppliers:
            products = supplier.products.all()
            products_count = products.count()
            low_stock_count = products.filter(quantity__lte=5).count()
            
            result.append({
                'id': supplier.id,
                'name': supplier.name,
                'email': supplier.email or '',
                'phone': supplier.phone or '',
                'products_count': products_count,
                'low_stock_count': low_stock_count
            })
        
        return result
