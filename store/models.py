from django.db import models, transaction
from django.db.models import F
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal


class Supplier(models.Model):
    name = models.CharField(max_length=200, verbose_name="Постачальник")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    phone = models.CharField(max_length=30, blank=True, null=True, verbose_name="Телефон")
    address = models.CharField(max_length=255, blank=True, null=True, verbose_name="Адреса")
    notes = models.TextField(blank=True, null=True, verbose_name="Нотатки")

    # Які категорії товарів зазвичай постачає
    categories = models.ManyToManyField('Category', blank=True, related_name='suppliers', verbose_name="Категорії")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Постачальник"
        verbose_name_plural = "Постачальники"

class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="Назва категорії")
    image = models.ImageField(upload_to='categories/', blank=True, null=True, verbose_name="Зображення")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Категорія"
        verbose_name_plural = "Категорії"


class Product(models.Model):
    UNIT_CHOICES = [
        ('pcs', 'шт'),
        ('kg', 'кг'),
        ('g', 'г'),
        ('l', 'л'),
        ('ml', 'мл'),
    ]

    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name="Категорія")
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, blank=True, null=True, related_name='products', verbose_name="Постачальник")
    
    # --- НОВЕ ПОЛЕ: АРТИКУЛ ---
    sku = models.CharField(max_length=20, verbose_name="Артикул/Код", blank=True, null=True)
    
    name = models.CharField(max_length=200, verbose_name="Назва товару")
    
    weight_value = models.DecimalField(max_digits=6, decimal_places=3, blank=True, null=True, verbose_name="Вага/Об'єм")
    weight_unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='pcs', verbose_name="Одиниця виміру")

    description = models.TextField(blank=True, verbose_name="Опис")
    
    # --- НОВЕ ПОЛЕ: ЦІНА ЗАКУПІВЛІ ---
    purchase_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Ціна закупівлі (грн)"
    )
    
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Ціна продажу (грн)"
    )
    
    # Кількість на складі - тільки цілі числа
    quantity = models.PositiveIntegerField(
        default=0,
        verbose_name="Кількість на складі"
    )
    
    # Термін придатності
    expiry_date = models.DateField(
        blank=True,
        null=True,
        verbose_name="Термін придатності"
    )
    
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name="Фото товару")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата додавання")

    def __str__(self):
        return f"{self.name}"
    
    def clean(self):
        """Валідація даних перед збереженням"""
        super().clean()
        if self.price and self.purchase_price and self.price < self.purchase_price:
            raise ValidationError({
                'price': 'Ціна продажу не може бути меншою за ціну закупівлі!'
            })
        if self.quantity and self.quantity < 0:
            raise ValidationError({
                'quantity': 'Кількість не може бути від\'ємною!'
            })

    # Метод, щоб в адмінці показувати маржу (націнку)
    def margin(self):
        if self.price and self.purchase_price:
            return self.price - self.purchase_price
        return 0
    margin.short_description = "Прибуток з одиниці"

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товари"


class Purchase(models.Model):
    """Модель поставки товарів від постачальника."""
    
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Чернетка'
        ORDERED = 'ordered', 'Замовлено'
        RECEIVED = 'received', 'Отримано'
        CANCELLED = 'cancelled', 'Скасовано'

    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchases', verbose_name="Постачальник")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, verbose_name="Статус")
    expected_date = models.DateTimeField(blank=True, null=True, verbose_name="Очікувана дата")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0.00'))], verbose_name="Загальна сума")
    received_applied = models.BooleanField(default=False, verbose_name="Проведено на склад")

    def __str__(self):
        return f"Поставка #{self.id} від {self.supplier.name}"

    def recalc_total(self):
        total = Decimal('0')
        for item in self.items.all():
            total += item.quantity * item.unit_cost
        self.total_cost = total
        return total

    def apply_to_stock_once(self):
        """Якщо статус 'received' і ще не проведено — додаємо залишки по товарах."""
        if self.received_applied:
            return
        with transaction.atomic():
            for item in self.items.select_related('product'):
                Product.objects.filter(id=item.product_id).update(quantity=F('quantity') + item.quantity)
            self.received_applied = True
            self.save(update_fields=['received_applied'])

    class Meta:
        verbose_name = "Поставка"
        verbose_name_plural = "Поставки"


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='items', verbose_name="Поставка")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="Товар")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name="Кількість")
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))], verbose_name="Ціна за од.")

    def line_total(self):
        return self.quantity * self.unit_cost

    def clean(self):
        super().clean()
        if self.quantity <= 0:
            raise ValidationError({'quantity': 'Кількість має бути більшою за 0'})

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    class Meta:
        verbose_name = "Позиція поставки"
        verbose_name_plural = "Позиції поставки"


# 1. ГОЛОВНИЙ ЧЕК (Шапка)
class Order(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Загальна сума")
    total_profit = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Загальний прибуток")

    def __str__(self):
        return f"Чек №{self.id} від {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        verbose_name = "Чек"
        verbose_name_plural = "Чеки"


# 2. ТОВАР У ЧЕКУ (Рядок)
class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE, verbose_name="Чек")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="Товар")
    
    quantity = models.PositiveIntegerField(verbose_name="Кількість")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Ціна продажу (за од.)")
    
    # Зберігаємо собівартість на момент продажу (щоб якщо ціна зміниться, історія не поламалася)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Ціна закупівлі")
    
    def get_cost(self):
        return self.price * self.quantity

    def get_profit(self):
        return (self.price - self.purchase_price) * self.quantity

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    class Meta:
        verbose_name = "Позиція чека"
        verbose_name_plural = "Позиції чека"


# 3. СПИСАННЯ ТОВАРІВ
class WriteOff(models.Model):
    """Модель для списання товарів (бій, брак, термін придатності)"""
    
    class Reason(models.TextChoices):
        DAMAGE = 'damage', 'Бій/Пошкодження'
        DEFECT = 'defect', 'Брак'
        EXPIRY = 'expiry', 'Термін придатності'
        OTHER = 'other', 'Інше'
    
    product = models.ForeignKey(
        Product, 
        on_delete=models.PROTECT, 
        related_name='writeoffs',
        verbose_name="Товар"
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Кількість"
    )
    reason = models.CharField(
        max_length=20,
        choices=Reason.choices,
        default=Reason.OTHER,
        verbose_name="Причина списання"
    )
    comment = models.TextField(
        blank=True,
        null=True,
        verbose_name="Коментар"
    )
    manager = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Менеджер"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата списання"
    )
    
    # Зберігаємо собівартість на момент списання для статистики
    purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Собівартість на момент списання"
    )
    
    def get_total_loss(self):
        """Загальна сума збитків від списання"""
        if self.quantity is None or self.purchase_price is None:
            return 0
        return self.quantity * self.purchase_price
    
    def save(self, *args, **kwargs):
        # Зберігаємо собівартість при створенні
        if not self.pk and not self.purchase_price:
            self.purchase_price = self.product.purchase_price
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Списання: {self.product.name} x {self.quantity} ({self.get_reason_display()})"
    
    class Meta:
        verbose_name = "Списання"
        verbose_name_plural = "Списання"
        ordering = ['-created_at']