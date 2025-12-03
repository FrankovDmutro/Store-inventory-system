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
    # Зв'язок "Один до багатьох" з категорією.
    # on_delete=models.CASCADE означає: якщо видалити Категорію, видаляться всі її Товари.
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name="Категорія")
    
    name = models.CharField(max_length=200, verbose_name="Назва товару")
    description = models.TextField(blank=True, verbose_name="Опис")
    
    # DecimalField - обов'язковий для цін! FloatField використовувати не можна через похибки округлення.
    # max_digits=10 (всього цифр), decimal_places=2 (цифри після коми).
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Ціна (грн)")
    
    # PositiveIntegerField - щоб кількість не могла бути від'ємною (-5 шт).
    quantity = models.PositiveIntegerField(default=0, verbose_name="Кількість на складі")
    
    # Поле для картинки. upload_to вказує папку всередині /media/
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name="Фото товару")
    
    # Дата додавання ставиться автоматично (auto_now_add)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")

    def __str__(self):
        return f"{self.name} ({self.quantity} шт.)"

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