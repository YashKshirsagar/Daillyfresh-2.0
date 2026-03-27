from django.contrib import admin
from django.utils.html import format_html
from django.conf import settings
from .models import HomeHero, Product, Address, Order, OrderItem, Coupon, PartnerLogo, Testimonial

admin.site.register(HomeHero)
admin.site.register(Product)
admin.site.register(Address)
admin.site.register(Order)
admin.site.register(OrderItem)


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
            return format_html(
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