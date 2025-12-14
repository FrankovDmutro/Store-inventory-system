from django import template

register = template.Library()

@register.filter
def mul(value, arg):
    """Множення двох значень"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def has_group(user, group_name):
    """Перевіряє чи користувач в групі"""
    return user.groups.filter(name=group_name).exists()