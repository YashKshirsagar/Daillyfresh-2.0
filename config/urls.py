from django.contrib import admin
from django.urls import path, include
from core.views import (
    home, signup_view, login_view, logout_view,
    cart_page, add_address, place_order,
    apply_affiliate_coupon, remove_coupon, apply_coupon,
    terms_and_conditions, refund_policy
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('home/', home, name='home_redirect'),

    # Auth URLs
    path('signup/', signup_view, name='signup'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),

    # Cart & Checkout URLs
    path('cart/', cart_page, name='cart_page'),
    path('add-address/', add_address, name='add_address'),
    path('place-order/', place_order, name='place_order'),
    path('apply-coupon/', apply_coupon, name='apply_coupon'),
    path('remove-coupon/', remove_coupon, name='remove_coupon'),

    # Policy Pages
    path('terms-and-conditions/', terms_and_conditions, name='terms_and_conditions'),
    path('refund-policy/', refund_policy, name='refund_policy'),

    # Affiliate / Promo URL — freelancer/YouTuber ke liye
    path('ref/<str:code>/', apply_affiliate_coupon, name='apply_affiliate_coupon'),

    path("__reload__/", include("django_browser_reload.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)