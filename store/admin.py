from django.contrib import admin
from .models import Category, Product, Order, OrderItem

# 1. ТОВАРИ В ЧЕКУ (Таблиця всередині)
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ['product']
    # Робимо ВСІ поля неактивними для редагування
    readonly_fields = ['product', 'quantity', 'price', 'purchase_price']
    # Забороняємо видаляти рядки
    can_delete = False
    # Забороняємо додавати нові пусті рядки
    max_num = 0
    extra = 0

# 2. САМ ЧЕК (Шапка)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'created_at', 'total_price', 'total_profit']
    list_filter = ['created_at']
    # Забороняємо міняти ці поля
    readonly_fields = ['created_at', 'total_price', 'total_profit']
    inlines = [OrderItemInline]

    # Ця функція прибирає кнопку "Додати чек" в адмінці.
    # Чеки мають створюватися ТІЛЬКИ касиром через POS-термінал.
    def has_add_permission(self, request):
        return False

    # Забороняємо видаляти чеки (опціонально, можна залишити True, якщо адміну треба чистити помилки)
    # def has_delete_permission(self, request, obj=None):
    #     return False

# Налаштування Товарів (залишаємо як було)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'purchase_price', 'price', 'margin', 'quantity')
    search_fields = ('name', 'sku')
    list_filter = ('category',)
    # Дозволяємо редагувати ціну, але показуємо прибуток
    readonly_fields = ('margin',) 

admin.site.register(Category)
admin.site.register(Product, ProductAdmin)
admin.site.register(Order, OrderAdmin)