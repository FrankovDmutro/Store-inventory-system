from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, F
from django.db import transaction
from decimal import Decimal, InvalidOperation
import logging
from .models import Product, Category, Order, OrderItem

logger = logging.getLogger(__name__)

@login_required
def category_list(request):
    categories = Category.objects.all()
    return render(request, 'store/category_list.html', {'categories': categories})

@login_required
def category_detail(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    products = Product.objects.filter(category=category).select_related('category')
    
    # Отримуємо кошик для початкового завантаження
    cart = request.session.get('cart', {})
    cart_items = []
    cart_total_price = Decimal('0')
    
    for pid, qty in cart.items():
        try:
            p = Product.objects.get(id=pid)
            qty_decimal = Decimal(str(qty))
            total = p.price * qty_decimal
            cart_total_price += total
            cart_items.append({'product': p, 'quantity': float(qty_decimal), 'total': total})
        except (Product.DoesNotExist, ValueError, InvalidOperation):
            continue

    return render(request, 'store/pos_screen.html', {
        'category': category,
        'products': products,
        'cart_items': cart_items,
        'cart_total_price': cart_total_price
    })

# === ГІБРИДНА ФУНКЦІЯ ДОДАВАННЯ (AJAX + звичайна) ===
@login_required
def cart_add(request, product_id):
    try:
        cart = request.session.get('cart', {})
        str_id = str(product_id)
        product = get_object_or_404(Product, id=product_id)
        
        # Конвертуємо в Decimal для точних обчислень
        current_qty = Decimal(str(cart.get(str_id, 0)))
        
        # Перевірка наявності товару
        if current_qty + 1 <= product.quantity:
            cart[str_id] = float(current_qty + 1)
            request.session['cart'] = cart
            request.session.modified = True
            status = 'success'
            message = f"Додано: {product.name}"
        else:
            status = 'error'
            message = "Недостатньо товару на складі!"

        # Якщо це AJAX-запит (від JavaScript) -> повертаємо JSON
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # Перераховуємо кошик
            items_data = []
            total_price = Decimal('0')
            for pid, qty in cart.items():
                try:
                    p = Product.objects.get(id=pid)
                    qty_decimal = Decimal(str(qty))
                    t = p.price * qty_decimal
                    total_price += t
                    items_data.append({
                        'id': p.id,
                        'name': p.name,
                        'price': float(p.price),
                        'qty': float(qty_decimal),
                        'total': float(t)
                    })
                except (Product.DoesNotExist, ValueError, InvalidOperation) as e:
                    logger.warning(f"Error processing cart item {pid}: {e}")
                    continue
                
            return JsonResponse({
                'status': status,
                'message': message,
                'added_id': int(product_id),
                'cart_total': float(total_price),
                'cart_count': len(items_data),
                'cart_items': items_data
            })

        # Якщо JS вимкнено -> звичайний редірект
        if status == 'error':
            messages.error(request, message)
        return redirect('category_detail', category_id=product.category.id)
    except Exception as e:
        logger.error(f"Error in cart_add: {e}")
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Виникла помилка. Спробуйте ще раз.'})
        messages.error(request, 'Виникла помилка при додаванні товару.')
        return redirect('category_list')

# === ПОШУК ===
@login_required
def search_products(request):
    query = request.GET.get('q', '').strip()
    cat_id = request.GET.get('category_id')
    
    if len(query) < 1:
        return JsonResponse({'here': [], 'others': []})

    try:
        products = Product.objects.filter(
            Q(name__icontains=query) | Q(sku__icontains=query)
        ).select_related('category')[:50]  # Обмежуємо результати
        
        res_here = []
        res_others = []

        for p in products:
            weight_display = ""
            if p.weight_value:
                weight_display = f"{p.weight_value:g} {p.get_weight_unit_display()}"
            
            item = {
                'id': p.id,
                'name': p.name,
                'price': float(p.price),
                'quantity': float(p.quantity),
                'sku': p.sku or '',
                'image_url': p.image.url if p.image else None,
                'weight': weight_display,
                'category_name': p.category.name
            }
            if str(p.category.id) == str(cat_id):
                res_here.append(item)
            else:
                res_others.append(item)

        return JsonResponse({'here': res_here, 'others': res_others})
    except Exception as e:
        logger.error(f"Error in search_products: {e}")
        return JsonResponse({'here': [], 'others': [], 'error': 'Помилка пошуку'})

@login_required
def cart_clear(request, category_id):
    if 'cart' in request.session:
        del request.session['cart']
        request.session.modified = True
        messages.info(request, 'Кошик очищено.')
    return redirect('category_detail', category_id=category_id)

@login_required
def cart_checkout(request, category_id):
    cart = request.session.get('cart', {})
    if not cart:
        messages.warning(request, 'Кошик порожній!')
        return redirect('category_detail', category_id=category_id)

    try:
        with transaction.atomic():
            order = Order.objects.create()
            total = Decimal('0')
            profit = Decimal('0')
            
            for pid, qty in cart.items():
                try:
                    # Блокування рядка для запобігання конкурентних оновлень
                    p = Product.objects.select_for_update().get(id=pid)
                    qty_decimal = Decimal(str(qty))
                    
                    # Перевірка наявності
                    if p.quantity >= qty_decimal:
                        OrderItem.objects.create(
                            order=order,
                            product=p,
                            quantity=qty_decimal,
                            price=p.price,
                            purchase_price=p.purchase_price
                        )
                        # Використання F() для атомарного оновлення
                        Product.objects.filter(id=p.id).update(
                            quantity=F('quantity') - qty_decimal
                        )
                        total += p.price * qty_decimal
                        profit += (p.price - p.purchase_price) * qty_decimal
                    else:
                        logger.warning(f"Insufficient quantity for product {p.id}: {p.quantity} < {qty_decimal}")
                        messages.warning(request, f"Товар '{p.name}' відсутній у потрібній кількості")
                except (Product.DoesNotExist, ValueError, InvalidOperation) as e:
                    logger.error(f"Error processing product {pid}: {e}")
                    continue
            
            order.total_price = total
            order.total_profit = profit
            order.save()
            
            # Очищення кошика
            del request.session['cart']
            request.session.modified = True
            
            messages.success(request, f"Чек №{order.id} успішно закрито! Сума: {total} ₴")
            return redirect('category_detail', category_id=category_id)
            
    except Exception as e:
        logger.error(f"Error in cart_checkout: {e}")
        messages.error(request, 'Виникла помилка при оформленні чеку. Спробуйте ще раз.')
        return redirect('category_detail', category_id=category_id)