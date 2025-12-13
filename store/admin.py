from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Product, Order, OrderItem, Supplier, Purchase, PurchaseItem, WriteOff, Return, ReturnItem

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
    
    def total_profit(self, obj):
        return f"{obj.get_total_profit():.2f} ₴"
    total_profit.short_description = "Прибуток"


# 3. ТОВАРИ (Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'purchase_price', 'quantity', 'expiry_date']
    list_filter = ['category']
    search_fields = ['name', 'sku']


# === ПОСТАЧАЛЬНИКИ ТА ПОСТАВКИ ===
class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    raw_id_fields = ['product']
    extra = 1
    
    def get_readonly_fields(self, request, obj=None):
        # Блокуємо редагування тільки після збереження
        if obj and obj.received_applied:
            return ['product', 'quantity', 'unit_cost']
        return []


class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'email']
    search_fields = ['name', 'phone', 'email']


class PurchaseAdmin(admin.ModelAdmin):
    list_display = ['id', 'supplier', 'status', 'total_cost', 'created_at']
    list_filter = ['status', 'created_at']
    date_hierarchy = 'created_at'
    inlines = [PurchaseItemInline]
    readonly_fields = ['total_cost']

    def get_readonly_fields(self, request, obj=None):
        # Блокуємо редагування supplier після збереження
        base_readonly = ['total_cost']
        if obj and obj.id:
            base_readonly.append('supplier')
        return base_readonly

    def save_model(self, request, obj, form, change):
        # При зміні статусу на "received" — зараховуємо товар у базу
        super().save_model(request, obj, form, change)
        purchase = obj
        if purchase.status == 'received' and not purchase.received_applied:
            purchase.apply_to_stock_once()

    def save_formset(self, request, form, formset, change):
        formset.save()
        # Після збереження позицій — перераховуємо total_cost
        purchase = form.instance
        purchase.recalc_total()
        purchase.save(update_fields=['total_cost'])
        # миттєве зарахування при статусі "Отримано"
        if purchase.status == 'received' and not purchase.received_applied:
            purchase.apply_to_stock_once()


admin.site.register(Supplier, SupplierAdmin)
admin.site.register(Purchase, PurchaseAdmin)


# === СПИСАННЯ ===
class WriteOffAdmin(admin.ModelAdmin):
    list_display = ['id', 'product', 'quantity', 'reason', 'manager', 'created_at', 'total_loss_display']
    list_filter = ['reason', 'created_at', 'manager']
    date_hierarchy = 'created_at'
    search_fields = ['product__name', 'comment']
    readonly_fields = ['created_at', 'purchase_price', 'total_loss_display']
    
    def total_loss_display(self, obj):
        if obj.pk is None:
            return "-"
        return f"{obj.get_total_loss():.2f} грн"
    total_loss_display.short_description = 'Збитки'
    
    def has_delete_permission(self, request, obj=None):
        # Тільки суперюзер може видаляти списання
        return request.user.is_superuser

admin.site.register(WriteOff, WriteOffAdmin)


# === ПОВЕРНЕННЯ ===
class ReturnItemInline(admin.TabularInline):
    model = ReturnItem
    readonly_fields = ['product', 'quantity', 'unit_price', 'purchase_price', 'line_total_display', 'line_loss_display']
    can_delete = False
    max_num = 0
    extra = 0
    
    def line_total_display(self, obj):
        if obj.id:
            return f"{obj.get_line_total():.2f} грн"
        return "-"
    line_total_display.short_description = "Сума повернення"
    
    def line_loss_display(self, obj):
        if obj.id:
            return f"{obj.get_line_loss():.2f} грн"
        return "-"
    line_loss_display.short_description = "Збиток"


class ReturnAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'reason', 'processed_by', 'created_at', 'refund_display', 'loss_display']
    list_filter = ['reason', 'created_at', 'processed_by']
    date_hierarchy = 'created_at'
    search_fields = ['order__id', 'comment']
    readonly_fields = ['order', 'created_at', 'processed_by', 'refund_display', 'loss_display']
    inlines = [ReturnItemInline]
    
    def has_add_permission(self, request):
        # Повернення створюються тільки через інтерфейс касира
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Тільки суперюзер може видаляти повернення
        return request.user.is_superuser
    
    def refund_display(self, obj):
        if obj.pk is None:
            return "-"
        return f"{obj.get_total_refund():.2f} грн"
    refund_display.short_description = 'Повернено клієнту'
    
    def loss_display(self, obj):
        if obj.pk is None:
            return "-"
        return f"{obj.get_total_loss():.2f} грн"
    loss_display.short_description = 'Втрачений прибуток'

admin.site.register(Return, ReturnAdmin)


# Реєстрація базових моделей
admin.site.register(Category, CategoryAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Order, OrderAdmin)
