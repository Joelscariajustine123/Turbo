from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, Http404, HttpResponse
from django.urls import include, path, re_path
from django.views.static import serve as serve_file


def react_app(request, *args, **kwargs):
    """Return the React app's index.html for any /app/... route (client-side routing).

    The JS/CSS files themselves are served by WhiteNoise before this view runs.
    """
    index = settings.REACT_BUILD_DIR / 'app' / 'index.html'
    if not index.is_file():
        raise Http404('React app not built. Run "npm run build" in frontend/.')
    response = FileResponse(index.open('rb'), content_type='text/html')
    response['Cache-Control'] = 'no-cache'
    return response


def google_site_verification(request, filename):
    """Search Console HTML-file ownership check: serve exactly the line Google expects."""
    if filename not in settings.GOOGLE_SITE_VERIFICATION_FILES:
        raise Http404()
    return HttpResponse(f'google-site-verification: {filename}', content_type='text/html; charset=utf-8')


urlpatterns = [
    re_path(r'^(?P<filename>google[0-9a-f]{8,}\.html)$', google_site_verification, name='google-site-verification'),
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    re_path(r'^app(?:/.*)?$', react_app, name='react-app'),
    path('', include('account.urls')),
    path('adminpages/', include('adminpages.urls')),
    path('driverpages/', include('driverpages.urls')),
    path('riderpages/', include('riderpages.urls')),
]

# Uploaded files (driver photos). Fine for a small deployment; use object
# storage (S3/Cloudinary) if traffic grows.
if settings.SERVE_MEDIA:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve_file, {'document_root': settings.MEDIA_ROOT}),
    ]
