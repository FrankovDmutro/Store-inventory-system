"""
Django Forms для валідації даних.
Thin Views, Fat Forms - валідація виноситься у форми.
"""
from django import forms
from django.core.exceptions import ValidationError
from .models import Supplier, Product, WriteOff


class SupplierForm(forms.ModelForm):
    """Форма для створення/редагування постачальника."""
    
    class Meta:
        model = Supplier
        fields = ['name', 'email', 'phone', 'address', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Назва постачальника'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+380XXXXXXXXX'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Адреса'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Нотатки (необов\'язково)'})
        }
        labels = {
            'name': 'Назва',
            'email': 'Email',
            'phone': 'Телефон',
            'address': 'Адреса',
            'notes': 'Нотатки'
        }
    
    def clean_name(self):
        """Перевірка унікальності назви."""
        name = self.cleaned_data.get('name')
        if name:
            # Якщо редагуємо існуючого постачальника, виключаємо його з перевірки
            qs = Supplier.objects.filter(name__iexact=name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                raise ValidationError(f'Постачальник з назвою "{name}" вже існує.')
        return name


class PurchaseItemForm(forms.Form):
    """Форма для однієї позиції поставки."""
    
    product_id = forms.IntegerField(min_value=1, error_messages={
        'required': 'Не вказано товар',
        'invalid': 'Некоректний ID товару'
    })
    quantity = forms.IntegerField(min_value=1, error_messages={
        'required': 'Не вказано кількість',
        'min_value': 'Кількість має бути більше 0'
    })
    unit_cost = forms.DecimalField(min_value=0, decimal_places=2, error_messages={
        'required': 'Не вказано ціну',
        'min_value': 'Ціна не може бути від\'ємною'
    })
    
    def clean_product_id(self):
        """Перевірка існування товару."""
        product_id = self.cleaned_data.get('product_id')
        if product_id:
            if not Product.objects.filter(id=product_id).exists():
                raise ValidationError(f'Товар з ID {product_id} не існує.')
        return product_id


class WriteOffForm(forms.ModelForm):
    """Форма для списання товарів."""
    
    class Meta:
        model = WriteOff
        fields = ['product', 'quantity', 'reason', 'comment']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'reason': forms.Select(attrs={'class': 'form-select'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Додатковий коментар (необов\'язково)'}),
        }
        labels = {
            'product': 'Товар',
            'quantity': 'Кількість для списання',
            'reason': 'Причина списання',
            'comment': 'Коментар'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Показуємо тільки товари, які є на складі
        products = Product.objects.filter(quantity__gt=0).select_related('category').order_by('name')
        # Додаємо кількість до label
        choices = [(p.id, f"{p.name} ({p.quantity} шт)") for p in products]
        self.fields['product'].choices = [('', '---------')] + choices
    
    def clean(self):
        """Валідація наявності товару перед списанням."""
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        quantity = cleaned_data.get('quantity')
        
        if product and quantity:
            if product.quantity < quantity:
                raise ValidationError({
                    'quantity': f'Недостатньо товару на складі. Доступно: {product.quantity} шт.'
                })
        
        return cleaned_data