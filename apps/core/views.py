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
    combos = Combo.objects.all()
    process_steps = ProcessStep.objects.all()
    return render(request, 'index.html', {'slides': slides, 'products': products, 'partner_logos': partner_logos, 'testimonials': testimonials, 'combos': combos, 'process_steps': process_steps})


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
                actual_subtotal += product.current_price * qty
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
                    price=product.current_price,
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


# --- Policy Pages ---
def terms_and_conditions(request):
    return render(request, 'terms.html')


def refund_policy(request):
    return render(request, 'refund-policy.html')


# --- Orders Views ---
@login_required(login_url='login')
def my_orders(request):
    """Display user's orders"""
    orders = Order.objects.filter(user=request.user)
    return render(request, 'orders.html', {'orders': orders})


@login_required(login_url='login')
def get_user_orders(request):
    """AJAX endpoint to fetch user orders"""
    orders = Order.objects.filter(user=request.user).select_related('shipping_address', 'coupon').prefetch_related('items__product')
    
    orders_data = []
    for order in orders:
        items_data = []
        for item in order.items.all():
            items_data.append({
                'id': item.id,
                'product_name': item.product.name if item.product else 'Deleted Product',
                'product_id': item.product.id if item.product else None,
                'quantity': item.quantity,
                'price': float(item.price),
                'total': float(item.get_cost()),
            })
        
        orders_data.append({
            'id': order.id,
            'status': order.status,
            'created_at': order.created_at.strftime('%B %d, %Y'),
            'created_at_iso': order.created_at.isoformat(),
            'subtotal': float(order.subtotal),
            'delivery_fee': float(order.delivery_fee),
            'discount_amount': float(order.discount_amount),
            'total_amount': float(order.total_amount),
            'coupon_code': order.coupon.code if order.coupon else None,
            'items': items_data,
            'shipping_address': {
                'full_name': order.shipping_address.full_name if order.shipping_address else 'N/A',
                'phone': order.shipping_address.phone_number if order.shipping_address else 'N/A',
                'address': order.shipping_address.street_address if order.shipping_address else 'N/A',
                'city': order.shipping_address.city if order.shipping_address else 'N/A',
            } if order.shipping_address else None
        })
    
    return JsonResponse({'orders': orders_data})


@login_required(login_url='login')
def repeat_order(request):
    """Repeat a previous order"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)
    
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        
        # Get the original order
        original_order = Order.objects.get(id=order_id, user=request.user)
        
        # Create new order with same items
        new_order = Order.objects.create(
            user=request.user,
            shipping_address=original_order.shipping_address,
            subtotal=original_order.subtotal,
            delivery_fee=original_order.delivery_fee,
            coupon=original_order.coupon,
            discount_amount=original_order.discount_amount,
            total_amount=original_order.total_amount,
            status='Pending'
        )
        
        # Copy order items
        for item in original_order.items.all():
            OrderItem.objects.create(
                order=new_order,
                product=item.product,
                price=item.price,
                quantity=item.quantity
            )
        
        return JsonResponse({
            'success': True,
            'message': 'Order repeated successfully!',
            'order_id': new_order.id
        })
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Order not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


# --- Profile Views ---
@login_required(login_url='login')
def get_user_profile(request):
    """AJAX endpoint to get user profile data"""
    user = request.user
    addresses = Address.objects.filter(user=user)
    
    profile_data = {
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'addresses': [
            {
                'id': addr.id,
                'full_name': addr.full_name,
                'phone_number': addr.phone_number,
                'street_address': addr.street_address,
                'city': addr.city,
                'state': addr.state,
                'pincode': addr.pincode,
                'is_default': addr.is_default,
            }
            for addr in addresses
        ]
    }
    
    return JsonResponse(profile_data)


@login_required(login_url='login')
def update_user_profile(request):
    """AJAX endpoint to update user profile"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)
    
    try:
        data = json.loads(request.body)
        user = request.user
        
        # Update user info
        if 'first_name' in data:
            user.first_name = data['first_name'].strip()
        if 'last_name' in data:
            user.last_name = data['last_name'].strip()
        if 'email' in data:
            user.email = data['email'].strip()
        
        # Validate email uniqueness
        if 'email' in data and User.objects.filter(email=data['email']).exclude(id=user.id).exists():
            return JsonResponse({'success': False, 'message': 'Email already in use'}, status=400)
        
        user.save()
        return JsonResponse({'success': True, 'message': 'Profile updated successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@login_required(login_url='login')
def update_address(request):
    """AJAX endpoint to add/update address"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)
    
    try:
        data = json.loads(request.body)
        user = request.user
        address_id = data.get('id')
        
        if address_id:
            # Update existing address
            address = Address.objects.get(id=address_id, user=user)
        else:
            # Create new address
            address = Address(user=user)
        
        address.full_name = data.get('full_name', '').strip()
        address.phone_number = data.get('phone_number', '').strip()
        address.street_address = data.get('street_address', '').strip()
        address.city = data.get('city', '').strip()
        address.state = data.get('state', '').strip()
        address.pincode = data.get('pincode', '').strip()
        address.is_default = data.get('is_default', False)
        
        if not all([address.full_name, address.phone_number, address.street_address, address.city, address.state, address.pincode]):
            return JsonResponse({'success': False, 'message': 'All fields are required'}, status=400)
        
        address.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Address saved successfully',
            'address': {
                'id': address.id,
                'full_name': address.full_name,
                'phone_number': address.phone_number,
                'street_address': address.street_address,
                'city': address.city,
                'state': address.state,
                'pincode': address.pincode,
                'is_default': address.is_default,
            }
        })
    except Address.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Address not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@login_required(login_url='login')
def delete_address(request):
    """AJAX endpoint to delete address"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)
    
    try:
        data = json.loads(request.body)
        address_id = data.get('id')
        user = request.user
        
        address = Address.objects.get(id=address_id, user=user)
        address.delete()
        
        return JsonResponse({'success': True, 'message': 'Address deleted successfully'})
    except Address.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Address not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)