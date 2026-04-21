from django.contrib import admin
from django.db import models as db_models
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.conf import settings
from django.urls import reverse
from .models import (
    HomeHero, Product, Address, Order, OrderItem, Coupon,
    PartnerLogo, Testimonial, Combo, ProcessStep, Customer, Feedback,
    LocalPincode,
)

admin.site.register(HomeHero)
admin.site.register(Product)


# ─── Order Items inline (used inside OrderAdmin) ───
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'price', 'quantity', 'item_total']
    fields = ['product', 'quantity', 'price', 'item_total']

    def item_total(self, obj):
        return f"₹{obj.get_cost()}"
    item_total.short_description = 'Total'

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ─── Order Admin ───
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer_id_display', 'user', 'status', 'delivery_zone', 'total_amount', 'created_at']
    list_filter = ['status', 'delivery_zone', 'created_at']
    search_fields = ['id', 'user__username', 'user__email', 'customer__customer_id']
    readonly_fields = [
        'user', 'customer_link', 'shipping_address',
        'subtotal', 'delivery_fee', 'coupon', 'discount_amount', 'total_amount',
        'created_at', 'updated_at',
    ]
    list_editable = ['status']
    inlines = [OrderItemInline]

    fieldsets = (
        ('Customer', {
            'fields': ('user', 'customer_link', 'shipping_address'),
        }),
        ('Pricing', {
            'fields': ('subtotal', 'delivery_fee', 'coupon', 'discount_amount', 'total_amount'),
        }),
        ('Status & Dates', {
            'fields': ('status', 'delivery_zone', 'created_at', 'updated_at'),
        }),
    )

    def customer_id_display(self, obj):
        if obj.customer:
            url = reverse('admin:core_customer_change', args=[obj.customer.pk])
            return format_html('<a href="{}">{}</a>', url, obj.customer.customer_id)
        return '-'
    customer_id_display.short_description = 'Customer ID'

    def customer_link(self, obj):
        if obj.customer:
            url = reverse('admin:core_customer_change', args=[obj.customer.pk])
            return format_html('<a href="{}">{}</a>', url, obj.customer)
        return '-'
    customer_link.short_description = 'Customer'


# ─── Order inline (used inside CustomerAdmin) ───
class OrderInline(admin.TabularInline):
    model = Order
    extra = 0
    fields = ['order_link', 'status', 'total_amount', 'created_at']
    readonly_fields = ['order_link', 'status', 'total_amount', 'created_at']
    ordering = ['-created_at']
    show_change_link = False

    def order_link(self, obj):
        url = reverse('admin:core_order_change', args=[obj.pk])
        return format_html('<a href="{}">Order #{}</a>', url, obj.id)
    order_link.short_description = 'Order'

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ─── Customer Admin ───
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['customer_id', 'full_name', 'email', 'total_orders', 'created_at']
    search_fields = ['customer_id', 'user__username', 'user__first_name', 'user__last_name', 'user__email']
    readonly_fields = [
        'customer_id', 'username', 'full_name', 'email',
        'date_joined', 'last_login', 'total_orders', 'total_spent',
    ]
    inlines = [OrderInline]

    fieldsets = (
        ('Customer ID', {
            'fields': ('customer_id',),
        }),
        ('Profile Info', {
            'fields': ('username', 'full_name', 'email', 'date_joined', 'last_login'),
        }),
        ('Order Summary', {
            'fields': ('total_orders', 'total_spent'),
        }),
    )

    def username(self, obj):
        return obj.user.username
    username.short_description = 'Username'

    def full_name(self, obj):
        return obj.user.get_full_name() or '-'
    full_name.short_description = 'Full Name'

    def email(self, obj):
        return obj.user.email or '-'
    email.short_description = 'Email'

    def date_joined(self, obj):
        return obj.user.date_joined
    date_joined.short_description = 'Date Joined'

    def last_login(self, obj):
        return obj.user.last_login
    last_login.short_description = 'Last Login'

    def total_orders(self, obj):
        return obj.orders.count()
    total_orders.short_description = 'Total Orders'

    def total_spent(self, obj):
        total = obj.orders.aggregate(total=db_models.Sum('total_amount'))['total']
        return f"₹{total or 0}"
    total_spent.short_description = 'Total Spent'

    def has_add_permission(self, request):
        # Customers are auto-created via User signal
        return False


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'user', 'city', 'pincode', 'is_default']
    search_fields = ['full_name', 'user__username', 'city', 'pincode']
    list_filter = ['is_default', 'city']


@admin.register(LocalPincode)
class LocalPincodeAdmin(admin.ModelAdmin):
    list_display = ['pincode', 'label', 'is_active']
    list_editable = ['label', 'is_active']
    search_fields = ['pincode', 'label']
    list_filter = ['is_active']


@admin.register(ProcessStep)
class ProcessStepAdmin(admin.ModelAdmin):
    list_display = ['order', 'title_line1', 'title_line2']
    list_display_links = ['title_line1']
    list_editable = ['order']
    ordering = ['order']


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'discount_type', 'discount_value',
        'is_active', 'valid_to', 'total_uses',
        'is_affiliate', 'affiliate_name',
        'promo_url_display',
    ]
    list_filter = ['is_active', 'is_affiliate', 'discount_type']
    search_fields = ['code', 'affiliate_name']
    readonly_fields = ['total_uses', 'total_revenue_generated', 'promo_url_display']

    fieldsets = (
        ('Coupon Details', {
            'fields': ('code', 'discount_type', 'discount_value', 'min_order_amount')
        }),
        ('Validity & Limits', {
            'fields': ('is_active', 'valid_from', 'valid_to', 'max_uses', 'total_uses')
        }),
        ('Affiliate / Freelancer Info', {
            'fields': (
                'is_affiliate',
                'affiliate_name',
                'total_revenue_generated',
                'promo_url_display',
            ),
            'description': (
                "Agar ye coupon kisi YouTuber ya Freelancer ko dena hai toh "
                "'Is Affiliate' checkbox ON karo aur naam likho. "
                "Promo URL automatically generate hoga — use copy karke freelancer ko bhejo."
            ),
        }),
    )

    def promo_url_display(self, obj):
        """
        Affiliate coupon ka shareable URL generate karta hai.
        Admin list aur detail dono jagah dikhega.
        Sirf tab show hoga jab is_affiliate=True ho.
        """
        if not obj.is_affiliate or not obj.code:
            return mark_safe(
                '<span style="color:#9ca3af; font-size:0.85rem;">'
                'Is Affiliate checkbox ON karo aur save karo — URL yahan dikhega.'
                '</span>'
            )

        base_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        promo_url = f"{base_url}/ref/{obj.code}/"

        return format_html(
            '''
            <div style="
                background: #f0fdf4;
                border: 1.5px solid #bbf7d0;
                border-radius: 8px;
                padding: 10px 14px;
                margin-top: 4px;
                max-width: 520px;
            ">
                <p style="
                    font-size: 0.72rem;
                    font-weight: 700;
                    color: #6b7280;
                    text-transform: uppercase;
                    letter-spacing: 0.08em;
                    margin: 0 0 6px 0;
                ">
                    Shareable Promo URL
                </p>
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                    <code style="
                        background: white;
                        border: 1px solid #d1fae5;
                        border-radius: 6px;
                        padding: 6px 10px;
                        font-size: 0.88rem;
                        color: #1a6b3c;
                        font-weight: 600;
                        word-break: break-all;
                        flex: 1;
                    ">{url}</code>
                    <button
                        type="button"
                        onclick="
                            navigator.clipboard.writeText('{url}');
                            this.textContent = 'Copied!';
                            this.style.background = '#16a34a';
                            setTimeout(() => {{
                                this.textContent = 'Copy';
                                this.style.background = '#0a2f15';
                            }}, 2000);
                        "
                        style="
                            background: #0a2f15;
                            color: white;
                            border: none;
                            padding: 7px 16px;
                            border-radius: 6px;
                            font-weight: 700;
                            font-size: 0.82rem;
                            cursor: pointer;
                            white-space: nowrap;
                            transition: background 0.2s;
                        "
                    >Copy</button>
                </div>
                <p style="
                    font-size: 0.75rem;
                    color: #6b7280;
                    margin: 8px 0 0 0;
                ">
                    Ye URL freelancer/YouTuber ko bhejo.
                    Customer jab is link se aayega, coupon automatically apply ho jayega.
                </p>
            </div>
            ''',
            url=promo_url,
        )

    promo_url_display.short_description = 'Promo URL (Copy & Share)'
    promo_url_display.allow_tags = True
    

@admin.register(PartnerLogo)
class PartnerLogoAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'image')
    list_editable = ('order',)

@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('name', 'occupation', 'stars', 'is_dark_card', 'order', 'is_active')
    list_editable = ('order', 'is_dark_card', 'is_active')

@admin.register(Combo)
class ComboAdmin(admin.ModelAdmin):
    list_display = ['name', 'current_price', 'original_price', 'unit', 'badge']


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'message')
    readonly_fields = ('user', 'message', 'created_at')