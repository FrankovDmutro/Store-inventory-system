from django import template

register = template.Library()

@register.filter
def mul(value, arg):
    """Множення двох значень"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
