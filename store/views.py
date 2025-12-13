from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, F, Sum
from django.db import transaction
from django.utils import timezone
from decimal import Decimal, InvalidOperation
import logging
from .models import Product, Category, Order, OrderItem
from .utils import role_required, ROLE_CASHIER, ROLE_MANAGER

logger = logging.getLogger(__name__)

@login_required
@role_required(ROLE_CASHIER)
def category_list(request):
    categories = Category.objects.all()
    return render(request, 'store/category_list.html', {'categories': categories})

@login_required
@role_required(ROLE_CASHIER)
def category_detail(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    
    # Розділяємо товари на наявні та відсутні
    products_in_stock = Product.objects.filter(
        category=category, quantity__gt=0
    ).select_related('category').order_by('name')
    
    products_out_of_stock = Product.objects.filter(
        category=category, quantity__lte=0
    ).select_related('category').order_by('name')
    
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
        'products_in_stock': products_in_stock,
        'products_out_of_stock': products_out_of_stock,
        'cart_items': cart_items,
        'cart_total_price': cart_total_price
    })

# === ГІБРИДНА ФУНКЦІЯ ДОДАВАННЯ (AJAX + звичайна) ===
@login_required
@role_required(ROLE_CASHIER)
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
@role_required(ROLE_CASHIER)
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
@role_required(ROLE_CASHIER)
def cart_clear(request, category_id):
    if 'cart' in request.session:
        del request.session['cart']
        request.session.modified = True
        messages.info(request, 'Кошик очищено.')
    return redirect('category_detail', category_id=category_id)

@login_required
@role_required(ROLE_CASHIER)
def cart_checkout(request, category_id):
    cart = request.session.get('cart', {})
    if not cart:
        if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Кошик порожній!'}, status=400)
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
            
            # Відповідь залежить від типу запиту
            if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'order_id': order.id,
                    'total': float(total)
                })
            
            # Для звичайного запиту - редірект без messages
            return redirect('category_list')
            
    except Exception as e:
        logger.error(f"Error in cart_checkout: {e}")
        messages.error(request, 'Виникла помилка при оформленні чеку. Спробуйте ще раз.')
        return redirect('category_detail', category_id=category_id)


@login_required
@role_required(ROLE_MANAGER)
def manager_dashboard(request):

    today = timezone.localdate()

    orders_today = Order.objects.filter(created_at__date=today)
    agg = orders_today.aggregate(
        cash=Sum('total_price'),
        profit=Sum('total_profit')
    )

    cash_today = agg['cash'] or Decimal('0')
    profit_today = agg['profit'] or Decimal('0')

    low_stock = Product.objects.filter(quantity__lte=5).select_related('category').order_by('quantity', 'name')[:20]
    latest_orders = Order.objects.order_by('-created_at').prefetch_related('items__product')[:10]

    return render(request, 'store/manager_dashboard.html', {
        'cash_today': cash_today,
        'profit_today': profit_today,
        'low_stock': low_stock,
        'latest_orders': latest_orders,
        'today': today,
    })


@login_required
@role_required(ROLE_MANAGER)
def manager_receipts_list(request):
    """Сторінка списку всіх чеків з фільтром за датою та сортуванням."""
    from .models import Order
    qs = Order.objects.all()

    # Фільтр за датою: ?date=YYYY-MM-DD
    date_str = request.GET.get('date')
    if date_str:
        try:
            target = timezone.datetime.fromisoformat(date_str)
            qs = qs.filter(created_at__date=target.date())
        except Exception:
            pass

    # Сортування: ?sort=id|date|total|profit
    sort = request.GET.get('sort', 'date')
    order = request.GET.get('order', 'desc')

    if sort == 'id':
        qs = qs.order_by('id' if order == 'asc' else '-id')
    elif sort == 'total':
        qs = qs.order_by('total_price' if order == 'asc' else '-total_price')
    elif sort == 'profit':
        qs = qs.order_by('total_profit' if order == 'asc' else '-total_profit')
    else:  # date
        qs = qs.order_by('created_at' if order == 'asc' else '-created_at')

    # Пагінація проста: ?page=1
    page = request.GET.get('page')
    try:
        page = int(page) if page else 1
    except ValueError:
        page = 1
    page_size = 50
    start = (page - 1) * page_size
    end = start + page_size

    orders = qs[start:end]

    return render(request, 'store/manager_receipts_list.html', {
        'orders': orders,
        'page': page,
        'date': date_str or '',
        'current_sort': sort,
        'current_order': order,
    })


@login_required
@role_required(ROLE_MANAGER)
def manager_products_list(request):
    """Сторінка списку товарів з сортуванням та фільтром по категорії."""
    from .models import Product, Category

    qs = Product.objects.select_related('category').all()

    # Фільтр за категорією: ?category=<id>
    category_id = request.GET.get('category')
    if category_id:
        try:
            qs = qs.filter(category_id=int(category_id))
        except ValueError:
            pass

    # Сортування: ?sort=quantity|name|price|profit
    sort = request.GET.get('sort', 'name')
    order = request.GET.get('order', 'asc')

    if sort == 'quantity':
        qs = qs.order_by('quantity' if order == 'asc' else '-quantity')
    elif sort == 'price':
        qs = qs.order_by('price' if order == 'asc' else '-price')
    elif sort == 'profit':
        # маржа = price - purchase_price (сортуємо за нею)
        from django.db.models import F, ExpressionWrapper, DecimalField
        margin = ExpressionWrapper(F('price') - F('purchase_price'), output_field=DecimalField(max_digits=10, decimal_places=2))
        qs = qs.annotate(margin=margin).order_by('margin' if order == 'asc' else '-margin')
    elif sort == 'category':
        qs = qs.order_by('category__name' if order == 'asc' else '-category__name')
    elif sort == 'sku':
        qs = qs.order_by('sku' if order == 'asc' else '-sku')
    else:
        qs = qs.order_by('name' if order == 'asc' else '-name')

    categories = Category.objects.all().order_by('name')

    return render(request, 'store/manager_products_list.html', {
        'products': qs[:500],
        'categories': categories,
        'current_category': category_id,
        'current_sort': sort,
        'current_order': order,
    })