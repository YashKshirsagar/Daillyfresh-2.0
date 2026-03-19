from django.db import models
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from cloudinary.models import CloudinaryField

# Create your models here.
class HomeHero(models.Model):
    title = models.CharField(max_length=200, blank=True, default='')
    subtitle = models.CharField(max_length=300, blank=True, default='')
    # image = models.ImageField(upload_to='hero/')
    image = CloudinaryField('image')
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
    price = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=50, help_text="e.g., 1000 ml, 500 gm")
    # image = models.ImageField(upload_to='products/')
    image = CloudinaryField('image')
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.0)
    # is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviews_count = models.IntegerField(default=5)
    badge = models.CharField(max_length=50, blank=True, null=True, help_text="e.g., 'Best Seller', 'New Arrival'")
    badge_color = models.CharField(max_length=7, blank=True, null=True, help_text="Hex color e.g. #FFC107")
    badge_text_color = models.CharField(max_length=7, blank=True, null=True, help_text="Hex color e.g. #000000")
    # updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
    
    def __str__(self):
        return self.name

class PartnerLogo(models.Model):
    # image = models.ImageField(upload_to='partners/')
    image = CloudinaryField('image')
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
    feedback = models.TextField()
    image = CloudinaryField('image')
    # image = models.ImageField(upload_to='partners/')
    stars = models.PositiveSmallIntegerField(default=5, choices=[(i, i) for i in range(1, 6)])
    is_dark_card = models.BooleanField(default=False, help_text="Dark green background card")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.name} — {self.occupation}"

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


# --- Order Model ---
class Order(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Processing', 'Processing'),
        ('Out for Delivery', 'Out for Delivery'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    shipping_address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Pricing
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    coupon = models.ForeignKey('Coupon', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.id} - {self.user.username if self.user else 'Guest'}"


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