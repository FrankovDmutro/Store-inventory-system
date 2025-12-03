from django.db import models
from django.utils import timezone

# =======================================================
# 1. МОДЕЛЬ КАТЕГОРІЇ
# Відповідає за групи товарів (Електроніка, Їжа тощо)
# =======================================================
class Category(models.Model):
    # CharField - для короткого тексту (назва)
    name = models.CharField(max_length=100, verbose_name="Назва категорії")

    # Цей метод каже Django, як показувати об'єкт текстом.
    # Замість "Category object (1)" ми побачимо реальну назву.
    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Категорія"
        verbose_name_plural = "Категорії"


# =======================================================
# 2. МОДЕЛЬ ТОВАРУ
# Це головна таблиця нашого складу
# =======================================================
class Product(models.Model):
    # СПИСОК ВАРІАНТІВ ВИМІРУ
    UNIT_CHOICES = [
        ('pcs', 'шт'),
        ('kg', 'кг'),
        ('g', 'г'),
        ('l', 'л'),
        ('ml', 'мл'),
    ]

    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name="Категорія")
    name = models.CharField(max_length=200, verbose_name="Назва товару")
    
    # --- НОВІ ПОЛЯ ---
    # 1. Саме число (напр. 0.5 або 100). DecimalField дозволяє дроби (1.5 кг)
    weight_value = models.DecimalField(
        max_digits=6, 
        decimal_places=3, 
        blank=True, 
        null=True, 
        verbose_name="Вага/Об'єм (число)"
    )
    
    # 2. Випадаючий список (кг, л, шт)
    weight_unit = models.CharField(
        max_length=10, 
        choices=UNIT_CHOICES, 
        default='pcs', 
        verbose_name="Одиниця виміру"
    )
    # -----------------

    description = models.TextField(blank=True, verbose_name="Опис")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Ціна (грн)")
    
    # Це залишок на складі (скільки у нас цих пляшок чи пачок)
    quantity = models.PositiveIntegerField(default=0, verbose_name="Кількість на складі")
    
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name="Фото товару")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата додавання")

    def __str__(self):
        # Якщо вказана вага, додаємо її до назви (напр. "Гречка 1.00 кг")
        if self.weight_value and self.weight_unit:
            # get_weight_unit_display() показує "кг" замість "kg"
            return f"{self.name} {self.weight_value:g} {self.get_weight_unit_display()}"
        return f"{self.name}"

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товари"


# =======================================================
# 3. МОДЕЛЬ ПРОДАЖУ (ЧЕК)
# Зберігає історію: що продали, скільки і коли
# =======================================================
class Sale(models.Model):
    # on_delete=models.PROTECT - ЗАХИСТ. 
    # Не дозволить видалити Товар, якщо він є в історії продажів (щоб не поламався звіт).
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="Товар")
    
    quantity = models.PositiveIntegerField(verbose_name="Продана кількість")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Загальна сума", blank=True)
    sale_date = models.DateTimeField(default=timezone.now, verbose_name="Час продажу")

    # === БІЗНЕС-ЛОГІКА ===
    # Ми переписуємо метод save(), щоб він автоматично рахував суму.
    def save(self, *args, **kwargs):
        # Якщо сума не вказана вручну -> рахуємо: Ціна товару * Кількість
        if not self.total_price:
            self.total_price = self.product.price * self.quantity
        
        # Викликаємо стандартне збереження Django
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Продаж {self.product.name} | {self.sale_date.strftime('%Y-%m-%d')}"

    class Meta:
        verbose_name = "Продаж"
        verbose_name_plural = "Продажі"