import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
	Category,
	Order,
	OrderItem,
	Product,
	Purchase,
	PurchaseItem,
	Return,
	Supplier,
	WriteOff,
	GROUP_CASHIER,
	GROUP_MANAGER,
)
from .forms import SupplierForm, WriteOffForm
from .services import OrderService, PurchaseService, ReceiptService


class BaseStoreTestCase(TestCase):
	def setUp(self):
		# Roles used by the role_required decorator in views
		self.cashiers_group, _ = Group.objects.get_or_create(name=GROUP_CASHIER)
		self.managers_group, _ = Group.objects.get_or_create(name=GROUP_MANAGER)

		self.cashier = User.objects.create_user(username="cashier", password="pass")
		self.cashier.groups.add(self.cashiers_group)

		self.manager = User.objects.create_user(username="manager", password="pass")
		self.manager.groups.add(self.managers_group)

		self.category = Category.objects.create(name="Food")
		self.supplier = Supplier.objects.create(name="ACME")

	def make_product(self, **kwargs):
		defaults = {
			"category": self.category,
			"supplier": self.supplier,
			"name": "Apple",
			"price": Decimal("10.00"),
			"purchase_price": Decimal("5.00"),
			"quantity": 10,
		}
		defaults.update(kwargs)
		return Product.objects.create(**defaults)


class ModelValidationTests(BaseStoreTestCase):
	def test_product_price_not_below_purchase_price(self):
		product = self.make_product(price=Decimal("4.00"), purchase_price=Decimal("5.00"))
		with self.assertRaises(ValidationError):
			product.clean()

	def test_purchase_apply_to_stock_is_idempotent(self):
		product = self.make_product(quantity=1)
		purchase = Purchase.objects.create(supplier=self.supplier, status="received")
		PurchaseItem.objects.create(purchase=purchase, product=product, quantity=3, unit_cost=Decimal("2.00"))

		purchase.apply_to_stock_once()
		product.refresh_from_db()
		self.assertEqual(product.quantity, 4)

		# Second call should not change stock
		purchase.apply_to_stock_once()
		product.refresh_from_db()
		self.assertEqual(product.quantity, 4)


class ServiceTests(BaseStoreTestCase):
	def test_order_service_creates_order_and_updates_stock(self):
		product = self.make_product(quantity=5, price=Decimal("12.00"), purchase_price=Decimal("7.00"))

		order = OrderService.create_order_from_cart([
			{"product_id": product.id, "quantity": 2},
		])

		product.refresh_from_db()
		self.assertEqual(product.quantity, 3)
		self.assertEqual(order.total_price, Decimal("24.00"))
		self.assertEqual(order.total_profit, Decimal("10.00"))
		self.assertEqual(order.items.count(), 1)

	def test_order_service_raises_on_insufficient_stock(self):
		product = self.make_product(quantity=1)

		with self.assertRaises(ValueError):
			OrderService.create_order_from_cart([
				{"product_id": product.id, "quantity": 3},
			])

		product.refresh_from_db()
		self.assertEqual(product.quantity, 1)
		self.assertEqual(Order.objects.count(), 0)

	def test_purchase_service_groups_by_supplier_and_skips_missing(self):
		supplier_b = Supplier.objects.create(name="Beta")
		product_a = self.make_product(name="A", supplier=self.supplier)
		product_b = self.make_product(name="B", supplier=supplier_b)
		product_no_supplier = self.make_product(name="C", supplier=None)

		created = PurchaseService.create_purchase_from_items([
			{"product_id": product_a.id, "quantity": 2, "unit_cost": "1.50"},
			{"product_id": product_b.id, "quantity": 1, "unit_cost": "2.00"},
			{"product_id": product_no_supplier.id, "quantity": 1, "unit_cost": "3.00"},
		])

		self.assertEqual(Purchase.objects.count(), 2)
		self.assertEqual(PurchaseItem.objects.count(), 2)
		self.assertEqual(len(created), 3)  # two purchases + skipped info
		self.assertTrue(any(entry.get("skipped") for entry in created))


class ViewTests(BaseStoreTestCase):
	def setUp(self):
		super().setUp()
		self.client = Client()

	def login_cashier(self):
		self.client.login(username="cashier", password="pass")

	def login_manager(self):
		self.client.login(username="manager", password="pass")

	def test_cart_checkout_consumes_cart_and_updates_stock(self):
		product = self.make_product(quantity=4, price=Decimal("11.00"), purchase_price=Decimal("6.00"))
		self.login_cashier()

		session = self.client.session
		session["cart"] = {str(product.id): 2}
		session.save()

		url = reverse("cart_checkout", args=[self.category.id])
		response = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["status"], "success")

		product.refresh_from_db()
		self.assertEqual(product.quantity, 2)
		self.assertEqual(Order.objects.count(), 1)

	def test_process_return_creates_records_and_restocks(self):
		product = self.make_product(quantity=5, price=Decimal("10.00"), purchase_price=Decimal("4.00"))
		order = Order.objects.create(total_price=Decimal("10.00"), total_profit=Decimal("6.00"))
		OrderItem.objects.create(order=order, product=product, quantity=2, price=product.price, purchase_price=product.purchase_price)

		self.login_cashier()
		payload = {
			"reason": "defective",
			"comment": "Damaged",
			"items": [{"product_id": product.id, "quantity": 1}],
		}
		url = reverse("process_return", args=[order.id])
		response = self.client.post(url, data=json.dumps(payload), content_type="application/json")

		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["status"], "success")
		self.assertEqual(Return.objects.count(), 1)
		product.refresh_from_db()
		self.assertEqual(product.quantity, 6)  # restocked by 1

	def test_process_return_rejects_over_returning(self):
		product = self.make_product(quantity=3)
		order = Order.objects.create(total_price=Decimal("5.00"), total_profit=Decimal("2.00"))
		OrderItem.objects.create(order=order, product=product, quantity=1, price=product.price, purchase_price=product.purchase_price)

		self.login_cashier()
		payload = {"reason": "other", "items": [{"product_id": product.id, "quantity": 2}]}
		url = reverse("process_return", args=[order.id])
		response = self.client.post(url, data=json.dumps(payload), content_type="application/json")

		self.assertEqual(response.status_code, 400)
		self.assertEqual(Return.objects.count(), 0)

	def test_search_products_splits_by_category(self):
		other_category = Category.objects.create(name="Drinks")
		product_here = self.make_product(name="Milk")
		product_other = self.make_product(name="Milkshake", category=other_category)

		self.login_cashier()
		url = reverse("search_products") + f"?q=Milk&category_id={self.category.id}"
		response = self.client.get(url)

		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(len(data.get("here", [])), 1)
		self.assertEqual(len(data.get("others", [])), 1)

	def test_create_purchase_draft_creates_items(self):
		p = self.make_product(name="Bulk", supplier=self.supplier)
		self.login_manager()
		url = reverse("create_purchase_draft")
		payload = {
			"supplier_id": self.supplier.id,
			"items": [{"product_id": p.id, "quantity": 2, "unit_cost": "3.50"}],
		}
		response = self.client.post(url, data=json.dumps(payload), content_type="application/json")
		self.assertEqual(response.status_code, 200)
		self.assertEqual(Purchase.objects.count(), 1)
		self.assertEqual(PurchaseItem.objects.count(), 1)

	def test_writeoff_create_reduces_stock(self):
		product = self.make_product(quantity=5)
		self.login_manager()
		url = reverse("writeoff_create")
		response = self.client.post(url, data={
			"product": product.id,
			"quantity": 2,
			"reason": WriteOff.Reason.DAMAGE,
			"comment": "Broken",
		})
		self.assertEqual(response.status_code, 302)
		product.refresh_from_db()
		self.assertEqual(product.quantity, 3)
		self.assertEqual(WriteOff.objects.count(), 1)

	def test_expired_products_view_lists_expired_and_soon(self):
		today = timezone.localdate()
		expired = self.make_product(name="Old", quantity=2, expiry_date=today - timedelta(days=1))
		soon = self.make_product(name="Soon", quantity=3, expiry_date=today + timedelta(days=3))
		self.login_manager()
		url = reverse("expired_products")
		response = self.client.get(url)
		self.assertEqual(response.status_code, 200)
		ctx = response.context
		self.assertIn(expired, list(ctx["expired"]))
		self.assertIn(soon, list(ctx["expiring_soon"]))

	def test_stats_dashboard_aggregates(self):
		product = self.make_product(quantity=5, price=Decimal("15.00"), purchase_price=Decimal("5.00"))
		order = Order.objects.create(total_price=Decimal("30.00"), total_profit=Decimal("20.00"))
		OrderItem.objects.create(order=order, product=product, quantity=2, price=product.price, purchase_price=product.purchase_price)
		Return.objects.create(order=order, reason="other", processed_by=self.manager)

		self.login_manager()
		response = self.client.get(reverse("stats_dashboard"))
		self.assertEqual(response.status_code, 200)
		ctx = response.context
		self.assertGreaterEqual(ctx["total_orders"], 1)
		self.assertGreater(ctx["total_sales"], 0)
		self.assertGreaterEqual(ctx["returns_count"], 1)

	def test_api_charts_endpoints(self):
		product = self.make_product(price=Decimal("8.00"), purchase_price=Decimal("3.00"))
		order = Order.objects.create()
		OrderItem.objects.create(order=order, product=product, quantity=1, price=product.price, purchase_price=product.purchase_price)
		order.created_at = timezone.now()
		order.total_price = product.price
		order.total_profit = product.price - product.purchase_price
		order.save()

		self.login_manager()
		sales = self.client.get(reverse("api_sales_chart_data"))
		self.assertEqual(sales.status_code, 200)
		self.assertEqual(len(sales.json().get("labels", [])), 30)

		categories = self.client.get(reverse("api_category_chart_data"))
		self.assertEqual(categories.status_code, 200)
		self.assertGreaterEqual(len(categories.json().get("labels", [])), 1)

		profit = self.client.get(reverse("api_profit_chart_data"))
		self.assertEqual(profit.status_code, 200)


class ReceiptServiceTests(BaseStoreTestCase):
	def test_generate_receipt_html_contains_totals(self):
		product = self.make_product(quantity=2, price=Decimal("9.00"), purchase_price=Decimal("4.00"))
		order = Order.objects.create(total_price=Decimal("18.00"), total_profit=Decimal("10.00"))
		OrderItem.objects.create(order=order, product=product, quantity=2, price=product.price, purchase_price=product.purchase_price)

		html = ReceiptService.generate_receipt_html(order)

		self.assertIn(f"Чек №{order.id}", html)
		self.assertIn("18.00", html)


class FormTests(BaseStoreTestCase):
	def test_supplier_form_unique_name(self):
		Supplier.objects.create(name="ACME2")
		form = SupplierForm(data={"name": "ACME2", "email": "a@a.com"})
		self.assertFalse(form.is_valid())

	def test_writeoff_form_prevents_overdraw(self):
		product = self.make_product(quantity=1)
		form = WriteOffForm(data={"product": product.id, "quantity": 5, "reason": WriteOff.Reason.DAMAGE})
		self.assertFalse(form.is_valid())
