"""
Middleware for handling base path when Django is served behind a reverse proxy.

This middleware dynamically sets SCRIPT_NAME based on priority:
1. X-Forwarded-Prefix header (from Nginx reverse proxy)
2. DJANGO_BASE_PATH environment variable (manual override)
3. Empty string (direct access, no base path)
"""
import os


class BasePathMiddleware:
    """
    Middleware to dynamically set SCRIPT_NAME based on priority:
    1. X-Forwarded-Prefix header (from Nginx reverse proxy)
    2. DJANGO_BASE_PATH environment variable (manual override)
    3. Empty string (direct access, no base path)
    
    This allows Django to work behind reverse proxies automatically
    while still supporting direct access and manual configuration.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # Cache environment variable at startup
        self.env_base_path = os.environ.get('DJANGO_BASE_PATH', '').rstrip('/')

    def __call__(self, request):
        # Priority 1: Check X-Forwarded-Prefix header (set by Nginx)
        # Django converts HTTP headers: X-Forwarded-Prefix -> HTTP_X_FORWARDED_PREFIX
        forwarded_prefix = request.META.get('HTTP_X_FORWARDED_PREFIX', '')
        
        # Priority 2: Fall back to environment variable
        if not forwarded_prefix and self.env_base_path:
            forwarded_prefix = self.env_base_path
        
        # Priority 3: If still empty, assume direct access (no base path)
        # Set SCRIPT_NAME in request.META for Django's URL generation
        if forwarded_prefix:
            request.META['SCRIPT_NAME'] = forwarded_prefix.rstrip('/')
        
        response = self.get_response(request)
        return response

