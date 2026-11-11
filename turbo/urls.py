from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('', include('account.urls')),
    path('adminpages/', include('adminpages.urls')),
    path('driverpages/', include('driverpages.urls')),
    path('riderpages/', include('riderpages.urls')),
]

# Static files are served by runserver automatically; uploaded media needs this
# in development (static() returns nothing when DEBUG is False).
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
