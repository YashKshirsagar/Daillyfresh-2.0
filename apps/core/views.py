import json
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from decimal import Decimal

from .models import *


# --- Main Home View ---
def home(request):
    slides = HomeHero.objects.order_by('order')
    products = Product.objects.all()
    partner_logos = PartnerLogo.objects.all()
    testimonials = Testimonial.objects.filter(is_active=True)
    return render(request, 'index.html', {'slides': slides, 'products': products, 'partner_logos': partner_logos, 'testimonials': testimonials})


# --- Authentication Views ---
def signup_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created successfully! Welcome to Daillyfresh.")
            return redirect('home')
    else:
        form = UserCreationForm()

    return render(request, 'accounts/signup.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {username}!")
                return redirect('home')
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect('home')


# ---------------------------------------------------------------
# Cart & Checkout Views
# ---------------------------------------------------------------

def cart_page(request):
    """
    Renders the cart/checkout page.
    Fetches user addresses and applied coupon from session.
    """
    addresses = []
    if request.user.is_authenticated:
        addresses = Address.objects.filter(user=request.user)

    applied_coupon_code = request.session.get('applied_coupon')
    coupon_data = None

    if applied_coupon_code:
        try:
            coupon = Coupon.objects.get(code=applied_coupon_code)
            if coupon.is_valid:
                coupon_data = {
                    'code': coupon.code,
                    'type': coupon.discount_type,
                    'value': float(coupon.discount_value),
                    'min_order_amount': float(coupon.min_order_amount),
                }
            else:
                del request.session['applied_coupon']
        except Coupon.DoesNotExist:
            del request.session['applied_coupon']

    coupon_json = json.dumps(coupon_data) if coupon_data else 'null'

    return render(request, 'cart.html', {
        'addresses': addresses,
        'coupon_data': coupon_json,
    })


def remove_coupon(request):
    """Session se coupon hata do."""
    if 'applied_coupon' in request.session:
        del request.session['applied_coupon']
        messages.info(request, "Coupon removed from your cart.")
    return redirect('cart_page')


def apply_coupon(request):
    """
    Manual coupon code entry ke liye AJAX endpoint.
    Cart page ka Alpine.js fetch() call karega — JSON response milega.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            code = data.get('code', '').strip()
            subtotal = Decimal(str(data.get('subtotal', 0)))

            if not code:
                return JsonResponse({
                    'success': False,
                    'message': 'Please enter a coupon code.'
                })

            coupon = Coupon.objects.get(code__iexact=code)

            if not coupon.is_valid:
                return JsonResponse({
                    'success': False,
                    'message': 'This coupon is expired or has reached its usage limit.'
                })

            if subtotal < coupon.min_order_amount:
                return JsonResponse({
                    'success': False,
                    'message': f'Minimum order of Rs.{coupon.min_order_amount:.0f} required to use this coupon.'
                })

            request.session['applied_coupon'] = coupon.code

            return JsonResponse({
                'success': True,
                'message': f"Coupon '{coupon.code}' applied successfully!",
                'coupon': {
                    'code': coupon.code,
                    'type': coupon.discount_type,
                    'value': float(coupon.discount_value),
                    'min_order_amount': float(coupon.min_order_amount),
                }
            })

        except Coupon.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Invalid coupon code. Please check and try again.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': 'Something went wrong. Please try again.'
            })

    return JsonResponse({'success': False, 'message': 'Invalid request method.'})


@login_required
def add_address(request):
    """
    'Add New Address' modal form ka submission handle karta hai.
    """
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        phone_number = request.POST.get('phone_number')
        street_address = request.POST.get('street_address')
        city = request.POST.get('city')
        state = request.POST.get('state')
        pincode = request.POST.get('pincode')
        is_default = request.POST.get('is_default') == 'on'

        Address.objects.create(
            user=request.user,
            full_name=full_name,
            phone_number=phone_number,
            street_address=street_address,
            city=city,
            state=state,
            pincode=pincode,
            is_default=is_default,
        )
        messages.success(request, "New delivery address added successfully.")
        return redirect('cart_page')

    return redirect('cart_page')


@login_required
def place_order(request):
    """
    Alpine.js se JSON data receive karta hai.
    Backend pe securely total calculate karta hai — frontend totals pe
    trust nahi karta.
    Coupon apply karta hai aur order create karta hai.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            cart_items = data.get('cart', [])
            address_id = data.get('address_id')
            coupon_code = data.get('coupon_code')

            shipping_address = Address.objects.get(id=address_id, user=request.user)

            # Backend pe actual subtotal calculate karo (DB prices se)
            actual_subtotal = Decimal('0.00')
            order_products = []
            for item in cart_items:
                product = Product.objects.get(id=item['id'])
                qty = int(item['quantity'])
                actual_subtotal += product.price * qty
                order_products.append((product, qty))

            # Delivery fee
            delivery_fee = Decimal('0.00') if actual_subtotal >= 500 else Decimal('40.00')

            # Coupon validate aur apply
            applied_coupon = None
            discount_amount = Decimal('0.00')

            if coupon_code:
                try:
                    coupon = Coupon.objects.get(code__iexact=coupon_code)
                    if coupon.is_valid and actual_subtotal >= coupon.min_order_amount:
                        applied_coupon = coupon
                        if coupon.discount_type == 'Percentage':
                            discount_amount = (actual_subtotal * coupon.discount_value) / Decimal('100.00')
                        else:
                            discount_amount = coupon.discount_value
                except Coupon.DoesNotExist:
                    pass

            # Final total
            total_amount = actual_subtotal + delivery_fee - discount_amount
            if total_amount < Decimal('0.00'):
                total_amount = Decimal('0.00')

            # Order create karo
            order = Order.objects.create(
                user=request.user,
                shipping_address=shipping_address,
                subtotal=actual_subtotal,
                delivery_fee=delivery_fee,
                coupon=applied_coupon,
                discount_amount=discount_amount,
                total_amount=total_amount,
                status='Pending',
            )

            # Order items
            for product, qty in order_products:
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    price=product.price,
                    quantity=qty,
                )

            # Coupon stats update
            if applied_coupon:
                applied_coupon.total_uses += 1
                if applied_coupon.is_affiliate:
                    applied_coupon.total_revenue_generated += total_amount
                applied_coupon.save()

            # Session cleanup
            request.session.pop('applied_coupon', None)

            return JsonResponse({
                'success': True,
                'message': 'Order placed successfully!',
                'order_id': order.id,
            })

        except Address.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Selected address not found.'})
        except Product.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'One or more products not found.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': 'Invalid request.'})


# ---------------------------------------------------------------
# Affiliate / Promo URL View
# ---------------------------------------------------------------

def apply_affiliate_coupon(request, code):
    """
    URL se coupon auto-apply karta hai (e.g. /ref/RAHUL20/).
    Customer ko manually enter nahi karna padta — direct discount milta hai.
    """
    try:
        coupon = Coupon.objects.get(code__iexact=code)

        if coupon.is_valid:
            request.session['applied_coupon'] = coupon.code

            if coupon.is_affiliate and coupon.affiliate_name:
                messages.success(
                    request,
                    f"Awesome! {coupon.affiliate_name}'s special discount ({coupon.code}) has been applied to your cart!"
                )
            else:
                messages.success(request, f"Coupon '{coupon.code}' applied successfully!")
        else:
            messages.error(
                request,
                "Sorry, this referral link or coupon is expired or has reached its usage limit."
            )

    except Coupon.DoesNotExist:
        messages.error(request, "Invalid referral link or coupon code.")

    return redirect('home')