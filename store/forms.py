from django import forms

class SaleForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, label="Кількість")