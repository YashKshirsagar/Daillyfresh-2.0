import uuid

from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings

# Choose image field based on environment
if 'cloudinary_storage' in settings.INSTALLED_APPS:
    from cloudinary.models import CloudinaryField
    def ImageField(upload_to='', **kwargs):
        # Pass through blank, null, help_text, etc. so admin labels/fields stay correct
        allowed = {k: v for k, v in kwargs.items() if k in ('blank', 'null', 'default', 'help_text', 'verbose_name')}
        return CloudinaryField(folder=upload_to.strip('/'), **allowed)
else:
    def ImageField(upload_to='', **kwargs):
        return models.ImageField(upload_to=upload_to, **kwargs)


def _generate_customer_id():
    """Generate a unique sequential 4-digit customer ID starting from 1111."""
    from django.db.models import IntegerField
    from django.db.models.functions import Cast
    last = (
        Customer.objects
        .annotate(id_int=Cast('customer_id', IntegerField()))
        .order_by('-id_int')
        .values_list('id_int', flat=True)
        .first()
    )
    return str((last or 1110) + 1)


class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer')
    customer_id = models.CharField(
        max_length=20, unique=True, editable=False, db_index=True,
        help_text="Auto-generated unique Customer ID",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'

    def __str__(self):
        return f"{self.customer_id} — {self.user.get_full_name() or self.user.username}"

    def save(self, *args, **kwargs):
        if not self.customer_id:
            from django.db import IntegrityError
            for _ in range(5):  # retry up to 5 times on race condition
                self.customer_id = _generate_customer_id()
                try:
                    super().save(*args, **kwargs)
                    return
                except IntegrityError:
                    continue
            raise IntegrityError("Could not generate a unique customer ID after 5 attempts")
        super().save(*args, **kwargs)


@receiver(post_save, sender=User)
def create_customer_profile(sender, instance, created, **kwargs):
    """Auto-create a Customer profile whenever a new User is created."""
    if created:
        Customer.objects.get_or_create(user=instance)


# Create your models here.
class HomeHero(models.Model):
    title = models.CharField(max_length=200, blank=True, default='')
    subtitle = models.CharField(max_length=300, blank=True, default='')
    image = ImageField(upload_to='hero/')
    show_button = models.BooleanField(default=True)
    order = models.IntegerField(default=0)


# @receiver(post_delete, sender=HomeHero)
# def delete_image_file(sender, instance, **kwargs):
#     if instance.image:
#         instance.image.delete(save=False)


# Products model
class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    original_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="MRP / original price (shown as strikethrough)")
    current_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Selling price (shown as current price)")
    unit = models.CharField(max_length=50, help_text="e.g., 1000 ml, 500 gm")
    image = ImageField(upload_to='products/')
    modal_image = ImageField(upload_to='products/modal/', blank=True, null=True, help_text="Image shown in quick-view modal (leave blank to use main image)")
    modal_description = models.TextField(blank=True, default='', help_text="Detailed description shown in quick-view modal (leave blank to use main description)")
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.0)
    # is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviews_count = models.IntegerField(default=5)
    badge = models.CharField(max_length=50, blank=True, null=True, help_text="e.g., 'Best Seller', 'New Arrival'")
    badge_color = models.CharField(max_length=7, blank=True, null=True, help_text="Hex color e.g. #FFC107")
    badge_text_color = models.CharField(max_length=7, blank=True, null=True, help_text="Hex color e.g. #000000")
    sku = models.CharField(max_length=100, blank=True, default='', help_text="Stock Keeping Unit code for Shiprocket")
    weight = models.DecimalField(max_digits=6, decimal_places=2, default=0.5, help_text="Weight in KG")
    # updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
    
    def __str__(self):
        return self.name

class Combo(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    original_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="MRP / original price (shown as strikethrough)")
    current_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Selling price (shown as current price)")
    unit = models.CharField(max_length=50, help_text="e.g., 1 Pack, 2 Bottles")
    image = ImageField(upload_to='combos/')
    modal_image = ImageField(upload_to='combos/modal/', blank=True, null=True, help_text="Image shown in quick-view modal (leave blank to use main image)")
    modal_description = models.TextField(blank=True, default='', help_text="Detailed description shown in quick-view modal (leave blank to use main description)")
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.0)
    reviews_count = models.IntegerField(default=5)
    badge = models.CharField(max_length=50, blank=True, null=True)
    badge_color = models.CharField(max_length=7, blank=True, null=True)
    badge_text_color = models.CharField(max_length=7, blank=True, null=True)
    sku = models.CharField(max_length=100, blank=True, default='', help_text="Stock Keeping Unit code for Shiprocket")
    weight = models.DecimalField(max_digits=6, decimal_places=2, default=0.5, help_text="Weight in KG")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Combo'
        verbose_name_plural = 'Combos'

    def __str__(self):
        return self.name

class PartnerLogo(models.Model):
    image = ImageField(upload_to='partners/')
    order = models.PositiveIntegerField(default=0, help_text="Display order")

    class Meta:
        ordering = ['order']
        verbose_name = "Partner Logo"
        verbose_name_plural = "Partner Logos"

    def __str__(self):
        return f"Partner #{self.order}" 
    
class Testimonial(models.Model):
    name = models.CharField(max_length=100)
    occupation = models.CharField(max_length=150)
    feedback = models.TextField(max_length=300, help_text="Max 300 characters (~50 words)")
    image = ImageField(upload_to='testimonials/')
    stars = models.PositiveSmallIntegerField(default=5, choices=[(i, i) for i in range(1, 6)])
    is_dark_card = models.BooleanField(default=False, help_text="Dark green background card")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.name} — {self.occupation}"

# --- Process Step Model ---
class ProcessStep(models.Model):
    title_line1 = models.CharField(max_length=200, help_text="First line of the title, e.g. 'Sourced from Healthy,'")
    title_line2 = models.CharField(max_length=200, blank=True, default='', help_text="Second line of the title, e.g. 'Well-Cared Cattle'")
    image = ImageField(upload_to='process/')
    order = models.PositiveIntegerField(default=0, help_text="Display order (lower = first)")

    class Meta:
        ordering = ['order']
        verbose_name = 'Process Step'
        verbose_name_plural = 'Process Steps'

    def __str__(self):
        return self.title_line1


# --- Address Model ---
class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=15)
    street_address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Addresses'
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.full_name} - {self.city} ({self.pincode})"

    def save(self, *args, **kwargs):
        # Ensure only one default address exists per user
        if self.is_default:
            Address.objects.filter(user=self.user).update(is_default=False)
        super().save(*args, **kwargs)


# --- Local Pincode Model ---
class LocalPincode(models.Model):
    """Pincodes served locally — orders for these skip Shiprocket."""
    pincode = models.CharField(max_length=10, unique=True, db_index=True)
    label = models.CharField(max_length=100, blank=True, default='', help_text="Optional label, e.g. 'Sector 12, Noida'")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['pincode']
        verbose_name = 'Local Pincode'
        verbose_name_plural = 'Local Pincodes'

    def __str__(self):
        return f"{self.pincode}{' — ' + self.label if self.label else ''}"


# --- Order Model ---
class Order(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Processing', 'Processing'),
        ('Shipped', 'Shipped'),
        ('In Transit', 'In Transit'),
        ('Out for Delivery', 'Out for Delivery'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
        ('RTO', 'Returned to Origin'),
        ('Completed', 'Completed'),
    )

    PAYMENT_CHOICES = (
        ('COD', 'Cash on Delivery'),
        ('Prepaid', 'Prepaid'),
    )

    DELIVERY_ZONE_CHOICES = (
        ('local', 'Local'),
        ('shiprocket', 'Shiprocket'),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    customer = models.ForeignKey('Customer', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    shipping_address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Pricing
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    coupon = models.ForeignKey('Coupon', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Payment & Status
    payment_mode = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='COD')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    delivery_zone = models.CharField(
        max_length=20, choices=DELIVERY_ZONE_CHOICES, default='shiprocket',
        help_text="'Local' orders are handled in-house and not pushed to Shiprocket."
    )

    # Shiprocket fields
    shiprocket_order_id = models.CharField(max_length=50, blank=True, null=True)
    shipment_id = models.CharField(max_length=50, blank=True, null=True)
    awb_code = models.CharField(max_length=50, blank=True, null=True, help_text="Airway Bill number for tracking")
    courier_name = models.CharField(max_length=100, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.id} - {self.user.username if self.user else 'Guest'}"

    def save(self, *args, **kwargs):
        # Auto-link order to customer profile
        if self.user and not self.customer:
            self.customer = getattr(self.user, 'customer', None)
        super().save(*args, **kwargs)


# --- Order Item Model ---
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('Product', on_delete=models.SET_NULL, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2) 
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity}x {self.product.name if self.product else 'Deleted Product'} (Order #{self.order.id})"
    
    def get_cost(self):
        return self.price * self.quantity
    
# --- Coupon & Affiliate Model ---
class Coupon(models.Model):
    DISCOUNT_TYPES = (
        ('Fixed', 'Fixed Amount'),
        ('Percentage', 'Percentage (%)'),
    )

    code = models.CharField(max_length=50, unique=True, help_text="e.g., DIWALI50 or RAHUL10")
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES, default='Percentage')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount in ₹ or %")
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Validity
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField()
    
    # Usage Tracking
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text="Leave blank for unlimited")
    total_uses = models.PositiveIntegerField(default=0)

    # Affiliate / Freelancer Tracking
    is_affiliate = models.BooleanField(default=False, help_text="Check this if given to a YouTuber/Freelancer")
    affiliate_name = models.CharField(max_length=100, null=True, blank=True)
    total_revenue_generated = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return self.code

    @property
    def is_valid(self):
        now = timezone.now()
        if self.is_active and self.valid_from <= now <= self.valid_to:
            if self.max_uses is None or self.total_uses < self.max_uses:
                return True
        return False


class Feedback(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedbacks')
    message = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Feedback'
        verbose_name_plural = 'Feedbacks'

    def __str__(self):
        return f"Feedback by {self.user.username} on {self.created_at:%Y-%m-%d %H:%M}"