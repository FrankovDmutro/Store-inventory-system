from django.db import models
from django.utils import timezone

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
    
    # --- НОВЕ ПОЛЕ: АРТИКУЛ ---
    sku = models.CharField(max_length=20, verbose_name="Артикул/Код", blank=True, null=True)
    
    name = models.CharField(max_length=200, verbose_name="Назва товару")
    
    weight_value = models.DecimalField(max_digits=6, decimal_places=3, blank=True, null=True, verbose_name="Вага/Об'єм")
    weight_unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='pcs', verbose_name="Одиниця виміру")

    description = models.TextField(blank=True, verbose_name="Опис")
    
    # --- НОВЕ ПОЛЕ: ЦІНА ЗАКУПІВЛІ ---
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Ціна закупівлі (грн)")
    
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Ціна продажу (грн)")
    
    quantity = models.PositiveIntegerField(default=0, verbose_name="Кількість на складі")
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name="Фото товару")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата додавання")

    def __str__(self):
        return f"{self.name}"

    # Метод, щоб в адмінці показувати маржу (націнку)
    def margin(self):
        if self.price and self.purchase_price:
            return self.price - self.purchase_price
        return 0
    margin.short_description = "Прибуток з одиниці"

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товари"


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
    
    quantity = models.DecimalField(max_digits=10, decimal_places=3, verbose_name="Кількість")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Ціна продажу (за од.)")
    
    # Зберігаємо собівартість на момент продажу (щоб якщо ціна зміниться, історія не поламалася)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Ціна закупівлі")
    
    def get_cost(self):
        return self.price * self.quantity

    def get_profit(self):
        return (self.price - self.purchase_price) * self.quantity

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"