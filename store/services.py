"""
Сервісний шар для бізнес-логіки.
Thin Views, Fat Services - складна логіка виноситься сюди.
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.template.loader import render_to_string
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
from .models import Product, Supplier, Purchase, PurchaseItem, Order, OrderItem


class PurchaseService:
    """Сервіс для роботи з поставками."""
    
    @staticmethod
    @transaction.atomic
    def create_purchase_from_items(items_data, expected_dates_data=None):
        """
        Створює поставки, групуючи товари по постачальниках.
        
        Args:
            items_data: list[dict] - [{product_id, quantity, unit_cost}, ...]
            expected_dates_data: dict - {supplier_id: datetime_string, ...}
            
        Returns:
            list[dict] - Інформація про створені поставки
        """
        if not items_data:
            return []
        
        # Групуємо товари по постачальниках
        supplier_groups = {}
        for item in items_data:
            try:
                product = Product.objects.select_related('supplier').get(id=item['product_id'])
                supplier_id = product.supplier_id
                
                if supplier_id not in supplier_groups:
                    supplier_groups[supplier_id] = {
                        'supplier': product.supplier,
                        'items': []
                    }
                
                supplier_groups[supplier_id]['items'].append({
                    'product': product,
                    'quantity': int(item['quantity']),
                    'unit_cost': Decimal(str(item['unit_cost']))
                })
            except (Product.DoesNotExist, KeyError, ValueError):
                continue
        
        # Створюємо поставки для кожного постачальника
        created_purchases = []
        for supplier_id, group_data in supplier_groups.items():
            supplier = group_data['supplier']
            items = group_data['items']
            
            # Очікувана дата для цього постачальника
            expected_date = None
            if expected_dates_data and str(supplier_id) in expected_dates_data:
                try:
                    expected_date = timezone.datetime.fromisoformat(
                        expected_dates_data[str(supplier_id)].replace('Z', '+00:00')
                    )
                except (ValueError, AttributeError):
                    pass
            
            # Створюємо поставку
            purchase = Purchase.objects.create(
                supplier=supplier,
                expected_date=expected_date,
                status='draft'
            )
            
            # Додаємо позиції
            total_cost = Decimal('0')
            for item_data in items:
                PurchaseItem.objects.create(
                    purchase=purchase,
                    product=item_data['product'],
                    quantity=item_data['quantity'],
                    unit_cost=item_data['unit_cost']
                )
                total_cost += item_data['quantity'] * item_data['unit_cost']
            
            purchase.total_cost = total_cost
            purchase.save(update_fields=['total_cost'])
            
            created_purchases.append({
                'id': purchase.id,
                'supplier': supplier.name,
                'items': len(items),
                'total': float(total_cost)
            })
        
        return created_purchases


class OrderService:
    """Сервіс для роботи з чеками (замовленнями)."""
    
    @staticmethod
    @transaction.atomic
    def create_order_from_cart(cart_items):
        """
        Створює чек з кошика, списує товар зі складу.
        
        Args:
            cart_items: list[dict] - [{product_id, quantity}, ...]
            
        Returns:
            Order - Створений чек
            
        Raises:
            ValueError - Якщо недостатньо товару
        """
        if not cart_items:
            raise ValueError("Кошик порожній")
        
        order = Order.objects.create()
        total_price = Decimal('0')
        total_profit = Decimal('0')
        
        for item in cart_items:
            try:
                product = Product.objects.select_for_update().get(id=item['product_id'])
                quantity = int(item['quantity'])
                
                # Перевірка залишку
                if product.quantity < quantity:
                    raise ValueError(
                        f"Недостатньо товару '{product.name}'. "
                        f"На складі: {product.quantity}, потрібно: {quantity}"
                    )
                
                # Створюємо позицію чека
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    price=product.price,
                    purchase_price=product.purchase_price
                )
                
                # Списуємо товар
                product.quantity -= quantity
                product.save(update_fields=['quantity'])
                
                # Рахуємо суми
                item_total = quantity * product.price
                item_profit = quantity * (product.price - product.purchase_price)
                total_price += item_total
                total_profit += item_profit
                
            except Product.DoesNotExist:
                raise ValueError(f"Товар з ID {item['product_id']} не знайдено")
        
        # Оновлюємо підсумки чека
        order.total_price = total_price
        order.total_profit = total_profit
        order.save(update_fields=['total_price', 'total_profit'])
        
        return order


class SupplierService:
    """Сервіс для роботи з постачальниками."""
    
    @staticmethod
    def get_suppliers_with_stats():
        """
        Повертає список постачальників зі статистикою товарів.
        
        Returns:
            list[dict] - Постачальники з кількістю товарів та низьким залишком
        """
        suppliers = Supplier.objects.all().order_by('name')
        result = []
        
        for supplier in suppliers:
            products = supplier.products.all()
            products_count = products.count()
            low_stock_count = products.filter(quantity__lte=5).count()
            
            result.append({
                'id': supplier.id,
                'name': supplier.name,
                'email': supplier.email or '',
                'phone': supplier.phone or '',
                'products_count': products_count,
                'low_stock_count': low_stock_count
            })
        
        return result


class ReceiptService:
    """Сервіс для генерування чеків у HTML та PDF форматі."""
    
    @staticmethod
    def _register_unicode_fonts():
        """
        Реєструємо Unicode шрифти для PDF.
        Використовуємо вбудовані системні шрифти.
        """
        try:
            # Спробуємо знайти системні шрифти Windows для Unicode підтримки
            font_paths = [
                r"C:\Windows\Fonts\arial.ttf",
                r"C:\Windows\Fonts\Calibri.ttf",
                r"C:\Windows\Fonts\Tahoma.ttf",
            ]
            
            for font_path in font_paths:
                if os.path.exists(font_path):
                    # Реєструємо шрифт
                    font_name = os.path.basename(font_path).replace('.ttf', '')
                    try:
                        pdfmetrics.registerFont(TTFont(font_name, font_path))
                        return font_name
                    except Exception:
                        continue
        except Exception:
            pass
        
        # Якщо не вдалось зареєструвати, повертаємо ім'я стандартного шрифту
        return 'Helvetica'
    
    @staticmethod
    def generate_receipt_html(order):
        """
        Генерує HTML чека для відображення у модальному вікні.
        
        Args:
            order: Order - об'єкт замовлення
            
        Returns:
            str - HTML розмітка чека
        """
        from django.utils.html import escape
        
        items = order.items.select_related('product')
        
        html_content = f"""
        <div class="receipt-container" style="font-family: monospace; line-height: 1.4; max-width: 400px;">
            <div style="text-align: center; border-bottom: 1px dashed #333; padding-bottom: 10px;">
                <h3 style="margin: 5px 0; font-size: 1.2em;">🏪 КАССА</h3>
                <p style="margin: 2px 0; font-size: 0.9em;">Чек №{order.id}</p>
                <p style="margin: 2px 0; font-size: 0.85em;">{order.created_at.strftime('%d.%m.%Y %H:%M:%S')}</p>
            </div>
            
            <table style="width: 100%; margin-top: 10px; font-size: 0.95em;">
                <thead>
                    <tr style="border-bottom: 1px dashed #333;">
                        <th style="text-align: left; padding: 5px 0;">Товар</th>
                        <th style="text-align: center; padding: 5px 0;">К-во</th>
                        <th style="text-align: right; padding: 5px 0;">Сума</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for item in items:
            product_name = escape(item.product.name)
            item_total = item.quantity * item.price
            html_content += f"""
                    <tr>
                        <td style="text-align: left; padding: 5px 0;">{product_name}</td>
                        <td style="text-align: center; padding: 5px 0;">{item.quantity}</td>
                        <td style="text-align: right; padding: 5px 0;">{item.price * item.quantity:.2f} ₴</td>
                    </tr>
            """
        
        html_content += """
                </tbody>
            </table>
            
            <div style="border-top: 1px dashed #333; border-bottom: 1px dashed #333; margin-top: 10px; padding: 10px 0; text-align: right;">
                <strong>РАЗОМ: """ + f"{order.total_price:.2f} ₴" + """</strong>
            </div>
            
            <div style="text-align: center; margin-top: 10px; font-size: 0.9em; color: #666;">
                <p>Дякуємо за покупку! 😊</p>
            </div>
        </div>
        """
        
        return html_content
    
    @staticmethod
    def generate_receipt_pdf(order):
        """
        Генерує PDF чека з підтримкою Unicode символів.
        
        Args:
            order: Order - об'єкт замовлення
            
        Returns:
            BytesIO - PDF файл у вигляді байтів
        """
        from reportlab.pdfbase.pdfmetrics import registerFont
        from reportlab.lib.styles import ParagraphStyle
        
        # Реєструємо шрифт для Unicode
        font_name = ReceiptService._register_unicode_fonts()
        
        # Визначаємо розміри для чека (як для теплового принтера)
        width = 80 * mm
        height = 200 * mm
        
        # Створюємо PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=(width, height),
            rightMargin=5*mm,
            leftMargin=5*mm,
            topMargin=5*mm,
            bottomMargin=5*mm
        )
        
        # Стилі з Unicode підтримкою
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=12,
            textColor=colors.black,
            alignment=1,  # центрування
            spaceAfter=5,
            fontName=font_name
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=8,
            leading=10,
            alignment=1,
            fontName=font_name
        )
        
        # Елементи для PDF
        elements = []
        
        # Заголовок (без emoji для сумісності з шрифтами)
        elements.append(Paragraph("КАССА", title_style))
        elements.append(Paragraph(f"Чек №{order.id}", normal_style))
        elements.append(Paragraph(
            order.created_at.strftime('%d.%m.%Y %H:%M:%S'),
            normal_style
        ))
        elements.append(Spacer(1, 0.3*cm))
        
        # Таблиця товарів
        items = order.items.select_related('product')
        table_data = [['Товар', 'К-во', 'Ціна', 'Сума']]
        
        for item in items:
            item_total = item.quantity * item.price
            # Обрізаємо довгі назви для вмісту в PDF
            product_name = item.product.name[:20]
            table_data.append([
                product_name,
                str(item.quantity),
                f"{item.price:.2f}",
                f"{item_total:.2f}"
            ])
        
        # Додаємо рядок з сумою (без символу ₴ для сумісності)
        table_data.append(['', '', 'РАЗОМ:', f"{order.total_price:.2f} грн"])
        
        # Стиль таблиці
        table = Table(table_data, colWidths=[2.5*cm, 1*cm, 1.2*cm, 1.2*cm])
        table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.black),
            ('LINEBELOW', (0, -1), (-1, -1), 0.5, colors.black),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.3*cm))
        
        # Нижній текст (без emoji для сумісності з шрифтами)
        elements.append(Paragraph("Дякуємо за покупку!", normal_style))
        
        # Будуємо PDF
        try:
            doc.build(elements)
        except Exception as e:
            # Якщо виникла помилка, спробуємо без кастомного шрифту
            doc = SimpleDocTemplate(
                buffer,
                pagesize=(width, height),
                rightMargin=5*mm,
                leftMargin=5*mm,
                topMargin=5*mm,
                bottomMargin=5*mm
            )
            
            # Переробляємо стилі зі стандартним шрифтом
            title_style.fontName = 'Helvetica'
            normal_style.fontName = 'Helvetica'
            
            doc.build(elements)
        
        # Повертаємо буфер на початок
        buffer.seek(0)
        return buffer


