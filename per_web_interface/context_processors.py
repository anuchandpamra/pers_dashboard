"""
Context processors for Django templates.
"""


def base_path(request):
    """
    Context processor to make base path available in all templates.
    The base path is set by BasePathMiddleware from:
    1. X-Forwarded-Prefix header (priority)
    2. DJANGO_BASE_PATH environment variable (fallback)
    3. Empty string (direct access)
    
    Usage in templates:
        {{ BASE_PATH }}{% static 'css/style.css' %}
        {{ BASE_PATH }}{% url 'index' %}
    """
    return {
        'BASE_PATH': request.META.get('SCRIPT_NAME', '')
    }

