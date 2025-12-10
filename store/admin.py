from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Product, Order, OrderItem

# === КАТЕГОРІЇ ===
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'image_preview']
    search_fields = ['name']
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover;" />', obj.image.url)
        return '-'
    image_preview.short_description = 'Зображення'

# 1. ТОВАРИ В ЧЕКУ (Таблиця всередині)
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ['product']
    # Робимо ВСІ поля неактивними для редагування
    readonly_fields = ['product', 'quantity', 'price', 'purchase_price', 'item_profit']
    # Забороняємо видаляти рядки
    can_delete = False
    # Забороняємо додавати нові пусті рядки
    max_num = 0
    extra = 0
    
    def item_profit(self, obj):
        if obj.id:
            return f"{obj.get_profit():.2f} ₴"
        return "-"
    item_profit.short_description = "Прибуток"

# 2. САМ ЧЕК (Шапка)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'created_at', 'total_price', 'total_profit', 'items_count']
    list_filter = ['created_at']
    date_hierarchy = 'created_at'
    # Забороняємо міняти ці поля
    readonly_fields = ['created_at', 'total_price', 'total_profit']
    inlines = [OrderItemInline]

    # Ця функція прибирає кнопку "Додати чек" в адмінці.
    # Чеки мають створюватися ТІЛЬКИ касиром через POS-термінал.
    def has_add_permission(self, request):
        return False
    
    def items_count(self, obj):
        return obj.items.count()
    items_count.short_description = "К-сть товарів"

    # Забороняємо видаляти чеки (опціонально, можна залишити True, якщо адміну треба чистити помилки)
    # def has_delete_permission(self, request, obj=None):
    #     return False

# Налаштування Товарів (залишаємо як було)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'category', 'purchase_price', 'price', 'margin', 'quantity_display', 'image_preview')
    search_fields = ('name', 'sku')
    list_filter = ('category',)
    # Дозволяємо редагувати ціну, але показуємо прибуток
    readonly_fields = ('margin', 'created_at')
    
    def quantity_display(self, obj):
        """Відображає кількість без зайвих нулів"""
        if obj.quantity % 1 == 0:
            return int(obj.quantity)
        return f"{obj.quantity:g}"
    quantity_display.short_description = 'Кількість на складі'
    quantity_display.admin_order_field = 'quantity'
    fieldsets = (
        ('Основна інформація', {
            'fields': ('category', 'sku', 'name', 'description', 'image')
        }),
        ('Вага/Об\'єм', {
            'fields': ('weight_value', 'weight_unit')
        }),
        ('Ціноутворення', {
            'fields': ('purchase_price', 'price', 'margin')
        }),
        ('Залишки', {
            'fields': ('quantity',)
        }),
        ('Системна інформація', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover;" />', obj.image.url)
        return '-'
    image_preview.short_description = 'Фото'

admin.site.register(Category, CategoryAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Order, OrderAdmin)