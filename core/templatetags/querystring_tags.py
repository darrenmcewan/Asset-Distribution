from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    """Build a query string preserving current GET params with overrides.

    Usage: {% querystring sort='name' dir='asc' page='' %}
    Empty string values remove that parameter.
    """
    request = context['request']
    params = request.GET.copy()
    for key, value in kwargs.items():
        if value == '':
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode()
