from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, F, Sum, DecimalField
from django.db import transaction, models
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from decimal import Decimal, InvalidOperation
import json
import logging
from .models import Product, Category, Order, OrderItem, Supplier, Purchase, PurchaseItem
from .forms import SupplierForm, PurchaseItemForm, CartItemForm
from .services import PurchaseService, OrderService, SupplierService
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
@transaction.atomic
def create_purchase_draft(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Метод не дозволений'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'status': 'error', 'message': 'Невірний формат даних'}, status=400)

    supplier_id = payload.get('supplier_id')
    items = payload.get('items', []) or []
    expected_raw = payload.get('expected_date')

    if not supplier_id:
        return JsonResponse({'status': 'error', 'message': 'Оберіть постачальника'}, status=400)
    if not items:
        return JsonResponse({'status': 'error', 'message': 'Додайте товари до поставки'}, status=400)

    supplier = get_object_or_404(Supplier, id=supplier_id)

    expected_date = None
    if expected_raw:
        parsed = parse_datetime(expected_raw)
        if parsed:
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            expected_date = parsed

    purchase = Purchase.objects.create(
        supplier=supplier,
        status='draft',
        expected_date=expected_date,
    )

    total = Decimal('0')
    created_count = 0

    for item in items:
        pid = item.get('product_id')
        qty_raw = item.get('quantity')
        cost_raw = item.get('unit_cost')

        if not pid or qty_raw is None:
            continue

        try:
            product = Product.objects.get(id=int(pid))
            qty = Decimal(str(qty_raw))
            if qty <= 0:
                continue
            unit_cost = Decimal(str(cost_raw if cost_raw is not None else product.purchase_price))
        except (Product.DoesNotExist, InvalidOperation, ValueError):
            continue

        PurchaseItem.objects.create(
            purchase=purchase,
            product=product,
            quantity=qty,
            unit_cost=unit_cost,
        )
        created_count += 1
        total += qty * unit_cost

    if created_count == 0:
        purchase.delete()
        return JsonResponse({'status': 'error', 'message': 'Не вдалося додати жодну позицію'}, status=400)

    purchase.total_cost = total
    purchase.save(update_fields=['total_cost'])

    return JsonResponse({'status': 'success', 'purchase_id': purchase.id, 'total_cost': float(total)})


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


@login_required
@role_required(ROLE_MANAGER)
def suppliers_list(request):
    """Сторінка списку постачальників (використання сервісу)."""
    # Використовуємо сервіс для отримання даних
    suppliers_data = SupplierService.get_suppliers_with_stats()
    
    products = Product.objects.select_related('category', 'supplier').order_by('name')
    
    products_payload = []
    for p in products:
        try:
            products_payload.append({
                'id': p.id,
                'name': p.name,
                'sku': p.sku or '',
                'stock': float(p.quantity),
                'purchase_price': float(p.purchase_price),
                'supplier_id': p.supplier_id,
                'supplier_name': p.supplier.name if p.supplier else '',
                'category': p.category.name,
            })
        except (ValueError, InvalidOperation):
            continue
    
    return render(request, 'store/suppliers_list.html', {
        'suppliers': suppliers_data,
        'products_json': json.dumps(products_payload, ensure_ascii=False),
    })


@login_required
@role_required(ROLE_MANAGER)
def create_supplier(request):
    """Створення постачальника (Thin View - використання форми)."""
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save()
            messages.success(request, f'Постачальник "{supplier.name}" успішно додан')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    
    return redirect('suppliers_list')


@login_required
@role_required(ROLE_MANAGER)
def create_purchase(request):
    """Формування поставки (Thin View - використання сервісу)."""
    if request.method == 'POST':
        items_json = request.POST.get('items_json', '[]')
        expected_dates_json = request.POST.get('expected_dates_json', '{}')
        
        try:
            items_data = json.loads(items_json)
            expected_dates = json.loads(expected_dates_json)
        except json.JSONDecodeError:
            messages.error(request, 'Невірний формат даних')
            return redirect('suppliers_list')
        
        if not items_data:
            messages.error(request, 'Додайте товари до поставки')
            return redirect('suppliers_list')
        
        # Використовуємо сервіс для створення поставок
        try:
            created_purchases = PurchaseService.create_purchase_from_items(
                items_data=items_data,
                expected_dates_data=expected_dates
            )
            
            if not created_purchases:
                messages.error(request, 'Не вдалося обробити жодну позицію')
            elif len(created_purchases) == 1:
                p = created_purchases[0]
                messages.success(
                    request,
                    f'Створено поставку ID: {p["id"]}, '
                    f'постачальник: {p["supplier"]}, '
                    f'позицій: {p["items"]}, сума: {p["total"]} ₴'
                )
            else:
                details = [f'{p["supplier"]} (ID: {p["id"]}, {p["items"]} поз., {p["total"]} ₴)' 
                          for p in created_purchases]
                messages.success(
                    request,
                    f'Створено {len(created_purchases)} поставок: ' + '; '.join(details)
                )
        except Exception as e:
            logger.error(f"Purchase creation error: {e}")
            messages.error(request, f'Помилка створення поставки: {str(e)}')
        
        return redirect('suppliers_list')
    
    return redirect('suppliers_list')


@login_required
@role_required(ROLE_MANAGER)
def stats_dashboard(request):
    """Статистика продажів, прибутку та товарів."""
    from django.db.models import Sum, Count, Avg, Q
    
    # Загальні показники
    total_orders = Order.objects.count()
    total_sales = Order.objects.aggregate(Sum('total_price'))['total_price__sum'] or Decimal('0')
    total_profit = Order.objects.aggregate(Sum('total_profit'))['total_profit__sum'] or Decimal('0')
    avg_check = total_sales / total_orders if total_orders > 0 else Decimal('0')
    
    # Показники за сьогодні
    today = timezone.localdate()
    today_orders_qs = Order.objects.filter(created_at__date=today)
    today_orders_count = today_orders_qs.count()
    today_sales = today_orders_qs.aggregate(Sum('total_price'))['total_price__sum'] or Decimal('0')
    today_profit = today_orders_qs.aggregate(Sum('total_profit'))['total_profit__sum'] or Decimal('0')
    today_avg_check = today_sales / today_orders_count if today_orders_count > 0 else Decimal('0')
    
    # Топ товарів за продажами
    top_products = OrderItem.objects.values('product__name').annotate(
        qty_sold=Sum('quantity'),
        revenue=Sum(F('quantity') * F('price'), output_field=DecimalField())
    ).order_by('-revenue')[:10]
    
    # Стан товарів
    low_stock = Product.objects.filter(quantity__lte=5).count()
    out_of_stock = Product.objects.filter(quantity=0).count()
    total_products = Product.objects.count()
    good_stock = total_products - low_stock - out_of_stock
    total_stock_value = Product.objects.aggregate(
        value=Sum(F('quantity') * F('purchase_price'), output_field=DecimalField())
    )['value'] or Decimal('0')
    
    # Постачальники
    supplier_count = Supplier.objects.count()
    suppliers_active = Supplier.objects.filter(products__isnull=False).distinct().count()
    
    # Поставки
    purchases_draft = Purchase.objects.filter(status='draft').count()
    purchases_ordered = Purchase.objects.filter(status='ordered').count()
    purchases_received = Purchase.objects.filter(status='received').count()
    purchases_cancelled = Purchase.objects.filter(status='cancelled').count()
    purchases_total = Purchase.objects.count()
    
    # Категорії - найпопулярніші
    top_categories = OrderItem.objects.values('product__category__name').annotate(
        qty=Sum('quantity'),
        revenue=Sum(F('quantity') * F('price'), output_field=DecimalField())
    ).order_by('-revenue')[:5]
    
    return render(request, 'store/stats_dashboard.html', {
        'total_orders': total_orders,
        'total_sales': total_sales,
        'total_profit': total_profit,
        'avg_check': avg_check,
        'today_sales': today_sales,
        'today_profit': today_profit,
        'today_orders': today_orders_count,
        'today_avg_check': today_avg_check,
        'top_products': list(top_products),
        'low_stock': low_stock,
        'out_of_stock': out_of_stock,
        'good_stock': good_stock,
        'total_products': total_products,
        'total_stock_value': total_stock_value,
        'supplier_count': supplier_count,
        'suppliers_active': suppliers_active,
        'purchases_draft': purchases_draft,
        'purchases_ordered': purchases_ordered,
        'purchases_received': purchases_received,
        'purchases_cancelled': purchases_cancelled,
        'purchases_total': purchases_total,
        'top_categories': list(top_categories),
        'today': today,
    })