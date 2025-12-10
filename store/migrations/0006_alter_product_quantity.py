# Generated migration for changing quantity field to DecimalField
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0005_category_image'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='quantity',
            field=models.DecimalField(decimal_places=3, default=0, max_digits=10, verbose_name='Кількість на складі'),
        ),
    ]
