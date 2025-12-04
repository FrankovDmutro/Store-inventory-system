from django.contrib import admin
from .models import Category, Product, Order, OrderItem

# Цей клас дозволяє бачити товари прямо всередині Чека
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ['product'] # Щоб був зручний пошук товару, а не довгий список
    readonly_fields = ['price', 'purchase_price'] # Забороняємо міняти ціни заднім числом
    extra = 0 # Не показувати пусті рядки

class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'created_at', 'total_price', 'total_profit']
    list_filter = ['created_at']
    inlines = [OrderItemInline] # <--- ВСТАВЛЯЄМО ТОВАРИ В ЧЕК

admin.site.register(Category)
admin.site.register(Product)
admin.site.register(Order, OrderAdmin)
# OrderItem реєструвати окремо не треба, він буде всередині Order