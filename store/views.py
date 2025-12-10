from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Product, Category, Order, OrderItem

# === 1. ГОЛОВНА: СПИСОК КАТЕГОРІЙ ===
def category_list(request):
    categories = Category.objects.all()
    return render(request, 'store/category_list.html', {'categories': categories})

# === 2. ЕКРАН КАСИРА (ТОВАРИ + КОШИК) ===
def category_detail(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    products = Product.objects.filter(category=category)

    # Отримуємо кошик із сесії (якщо його немає - буде пустий словник)
    cart = request.session.get('cart', {}) 
    
    # Підготовка даних для відображення кошика справа
    cart_items = []
    cart_total_price = 0
    
    for product_id, quantity in cart.items():
        # Шукаємо товар, якщо його раптом видалили - пропускаємо
        try:
            product = Product.objects.get(id=product_id)
            total = product.price * quantity
            cart_total_price += total
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'total': total
            })
        except Product.DoesNotExist:
            continue

    context = {
        'category': category,
        'products': products,
        'cart_items': cart_items,
        'cart_total_price': cart_total_price
    }
    # Використовуємо новий шаблон POS-терміналу
    return render(request, 'store/pos_screen.html', context)

# === 3. ДОДАТИ В КОШИК (КЛІК ПО ТОВАРУ) ===
def cart_add(request, product_id):
    # Отримуємо кошик
    cart = request.session.get('cart', {})
    
    # JSON у сесіях працює з ключами-стрічками, тому ID переводимо в str
    str_id = str(product_id)
    
    product = get_object_or_404(Product, id=product_id)
    
    # Скільки вже в кошику?
    current_in_cart = cart.get(str_id, 0)
    
    # Перевірка: чи не хочемо ми продати більше, ніж є на складі?
    if current_in_cart + 1 <= product.quantity:
        cart[str_id] = current_in_cart + 1
        request.session['cart'] = cart # Зберігаємо зміни в браузері
    else:
        messages.error(request, f"На складі всього {product.quantity} шт. товару {product.name}!")

    # Повертаємось на ту саму сторінку
    return redirect('category_detail', category_id=product.category.id)

# === 4. ОЧИСТИТИ КОШИК ===
def cart_clear(request, category_id):
    if 'cart' in request.session:
        del request.session['cart']
    return redirect('category_detail', category_id=category_id)

# === 5. ОФОРМИТИ ЧЕК (ВЕЛИКА КНОПКА "ОПЛАТИТИ") ===
def cart_checkout(request, category_id):
    cart = request.session.get('cart', {})
    
    if not cart:
        messages.error(request, "Кошик пустий!")
        return redirect('category_detail', category_id=category_id)

    # 1. Створюємо "Шапку" чека
    order = Order.objects.create()
    
    final_price = 0
    final_profit = 0
    
    # 2. Проходимо по кошику і переносимо товари в базу
    for product_id, quantity in cart.items():
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            continue
        
        # Фінальна перевірка наявності (раптом хтось вкрав товар, поки ми думали)
        if product.quantity >= quantity:
            item_total = product.price * quantity
            # Рахуємо прибуток: (Ціна продажу - Собівартість) * Кількість
            # purchase_price ми додали в модель Product минулого кроку
            item_profit = (product.price - product.purchase_price) * quantity
            
            # Створюємо рядок у чеку
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=product.price,
                purchase_price=product.purchase_price
            )
            
            # Списуємо зі складу
            product.quantity -= quantity
            product.save()
            
            # Плюсуємо загальну касу
            final_price += item_total
            final_profit += item_profit
        else:
            messages.error(request, f"Товар {product.name} закінчився під час оформлення!")
    
    # 3. Записуємо підсумки в чек
    order.total_price = final_price
    order.total_profit = final_profit
    order.save()
    
    # 4. Очищаємо кошик після успішного продажу
    del request.session['cart']
    
    messages.success(request, f"✅ Чек №{order.id} закрито! Сума: {final_price} грн")
    return redirect('category_detail', category_id=category_id)