import json
import logging
import os
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from decimal import Decimal

from .models import *

logger = logging.getLogger(__name__)


def health_check(request):
    return JsonResponse({'status': 'ok'})


def _resolve_cart_item(item):
    item_id = str(item.get('id', ''))
    quantity = int(item.get('quantity', 0))
    if quantity <= 0:
        raise ValueError('Invalid quantity.')

    if item_id.startswith('combo-'):
        combo_id = int(item_id.split('-', 1)[1])
        combo = Combo.objects.get(id=combo_id)
        return {
            'kind': 'combo',
            'object': combo,
            'quantity': quantity,
            'price': combo.current_price,
        }

    product = Product.objects.get(id=int(item_id))
    return {
        'kind': 'product',
        'object': product,
        'quantity': quantity,
        'price': product.current_price,
    }


def _order_item_cart_payload(order_item):
    combo = order_item.combo
    product = order_item.product
    if combo:
        return {
            'id': f'combo-{combo.id}',
            'name': combo.name,
            'price': str(combo.current_price),
            'image': combo.image.url if combo.image else '',
            'unit': combo.unit,
            'quantity': order_item.quantity,
        }
    if product:
        return {
            'id': product.id,
            'name': product.name,
            'price': str(product.current_price),
            'image': product.image.url if product.image else '',
            'unit': product.unit,
            'quantity': order_item.quantity,
        }
    return None


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
            order_lines = []
            for item in cart_items:
                resolved_item = _resolve_cart_item(item)
                actual_subtotal += resolved_item['price'] * resolved_item['quantity']
                order_lines.append(resolved_item)

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
            for line in order_lines:
                OrderItem.objects.create(
                    order=order,
                    product=line['object'] if line['kind'] == 'product' else None,
                    combo=line['object'] if line['kind'] == 'combo' else None,
                    price=line['price'],
                    quantity=line['quantity'],
                )

            # Coupon stats update
            if applied_coupon:
                applied_coupon.total_uses += 1
                if applied_coupon.is_affiliate:
                    applied_coupon.total_revenue_generated += total_amount
                applied_coupon.save()

            # Session cleanup
            request.session.pop('applied_coupon', None)

            # Determine delivery zone based on pincode
            is_local = LocalPincode.objects.filter(
                pincode=shipping_address.pincode, is_active=True
            ).exists()
            order.delivery_zone = 'local' if is_local else 'shiprocket'
            if is_local:
                order.shiprocket_sync_status = 'not_required'
                order.shiprocket_sync_error = ''
                order.shiprocket_synced_at = None
                order.save(update_fields=['delivery_zone', 'shiprocket_sync_status', 'shiprocket_sync_error', 'shiprocket_synced_at'])
            else:
                order.save(update_fields=['delivery_zone'])

            # Push order to Shiprocket (only for non-local zones)
            if not is_local and getattr(settings, 'SHIPROCKET_ENABLED', False):
                from core.shiprocket import shiprocket
                result = shiprocket.sync_order(order)
                if not result.get('success'):
                    logger.error(f"Shiprocket push failed for Order #{order.id}: {result.get('message', 'Unknown error')}")

            return JsonResponse({
                'success': True,
                'message': 'Order placed successfully!',
                'order_id': order.id,
                'order_ref': order.order_ref,
            })

        except Address.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Selected address not found.'})
        except (Product.DoesNotExist, Combo.DoesNotExist):
            return JsonResponse({'success': False, 'message': 'One or more cart items were not found.'})
        except ValueError as e:
            return JsonResponse({'success': False, 'message': str(e) or 'Invalid cart item.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': 'Invalid request.'})


# ---------------------------------------------------------------
# Razorpay — Create Order (no DB order yet)
# ---------------------------------------------------------------

@login_required
def create_razorpay_order(request):
    """
    Step 1 of online payment flow.
    Validates cart server-side, creates a Razorpay order, returns the
    razorpay_order_id + key_id to the frontend so it can open the modal.
    No DB Order is created here — only after payment is verified.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request.'})

    try:
        import razorpay
        data = json.loads(request.body)
        cart_items = data.get('cart', [])
        address_id = data.get('address_id')
        coupon_code = data.get('coupon_code')

        Address.objects.get(id=address_id, user=request.user)  # validate ownership

        # Recalculate totals server-side
        actual_subtotal = Decimal('0.00')
        for item in cart_items:
            resolved_item = _resolve_cart_item(item)
            actual_subtotal += resolved_item['price'] * resolved_item['quantity']

        delivery_fee = Decimal('0.00') if actual_subtotal >= 500 else Decimal('40.00')
        discount_amount = Decimal('0.00')

        if coupon_code:
            try:
                coupon = Coupon.objects.get(code__iexact=coupon_code)
                if coupon.is_valid and actual_subtotal >= coupon.min_order_amount:
                    if coupon.discount_type == 'Percentage':
                        discount_amount = (actual_subtotal * coupon.discount_value) / Decimal('100.00')
                    else:
                        discount_amount = coupon.discount_value
            except Coupon.DoesNotExist:
                pass

        total_amount = max(actual_subtotal + delivery_fee - discount_amount, Decimal('0.00'))

        # Razorpay expects amount in paise (1 INR = 100 paise)
        amount_paise = int(total_amount * 100)

        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            logger.error("create_razorpay_order error: Razorpay credentials are missing")
            return JsonResponse({
                'success': False,
                'message': 'Online payment is temporarily unavailable. Please contact support.'
            })

        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        rz_order = client.order.create({
            'amount': amount_paise,
            'currency': 'INR',
            'receipt': f'cart-{request.user.id}',
            'payment_capture': 1,
        })

        return JsonResponse({
            'success': True,
            'razorpay_order_id': rz_order['id'],
            'amount': amount_paise,
            'key_id': settings.RAZORPAY_KEY_ID,
        })

    except Address.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Selected address not found.'})
    except (Product.DoesNotExist, Combo.DoesNotExist):
        return JsonResponse({'success': False, 'message': 'One or more cart items were not found.'})
    except ValueError as e:
        return JsonResponse({'success': False, 'message': str(e) or 'Invalid cart item.'})
    except razorpay.errors.BadRequestError as e:
        key_prefix = settings.RAZORPAY_KEY_ID.split('_', 1)[0] if settings.RAZORPAY_KEY_ID else 'missing'
        logger.error(
            "create_razorpay_order Razorpay bad request: %s (key_prefix=%s, key_present=%s, secret_present=%s)",
            e,
            key_prefix,
            bool(settings.RAZORPAY_KEY_ID),
            bool(settings.RAZORPAY_KEY_SECRET),
        )
        return JsonResponse({
            'success': False,
            'message': 'Online payment is temporarily unavailable. Please contact support.'
        })
    except razorpay.errors.ServerError as e:
        logger.error("create_razorpay_order Razorpay server error: %s", e)
        return JsonResponse({
            'success': False,
            'message': 'Payment gateway is temporarily unavailable. Please try again.'
        })
    except Exception as e:
        logger.error(f"create_razorpay_order error: {e}")
        return JsonResponse({'success': False, 'message': 'Could not initiate payment. Please try again.'})


# ---------------------------------------------------------------
# Razorpay — Verify Payment & Create DB Order
# ---------------------------------------------------------------

@login_required
def verify_payment(request):
    """
    Step 2 of online payment flow.
    Verifies Razorpay HMAC signature — if valid, creates the DB Order
    with payment_mode='Prepaid' and pushes to Shiprocket.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request.'})

    try:
        import razorpay
        data = json.loads(request.body)

        razorpay_order_id = data.get('razorpay_order_id', '')
        razorpay_payment_id = data.get('razorpay_payment_id', '')
        razorpay_signature = data.get('razorpay_signature', '')
        cart_items = data.get('cart', [])
        address_id = data.get('address_id')
        coupon_code = data.get('coupon_code')

        # 1. Verify HMAC signature
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        try:
            client.utility.verify_payment_signature({
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature,
            })
        except razorpay.errors.SignatureVerificationError:
            logger.warning(f"Razorpay signature verification failed for {razorpay_order_id}")
            return JsonResponse({'success': False, 'message': 'Payment verification failed. Contact support.'})

        # 2. Recalculate totals server-side (never trust frontend)
        shipping_address = Address.objects.get(id=address_id, user=request.user)
        actual_subtotal = Decimal('0.00')
        order_lines = []
        for item in cart_items:
            resolved_item = _resolve_cart_item(item)
            actual_subtotal += resolved_item['price'] * resolved_item['quantity']
            order_lines.append(resolved_item)

        delivery_fee = Decimal('0.00') if actual_subtotal >= 500 else Decimal('40.00')
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

        total_amount = max(actual_subtotal + delivery_fee - discount_amount, Decimal('0.00'))

        # 3. Create DB Order
        order = Order.objects.create(
            user=request.user,
            shipping_address=shipping_address,
            subtotal=actual_subtotal,
            delivery_fee=delivery_fee,
            coupon=applied_coupon,
            discount_amount=discount_amount,
            total_amount=total_amount,
            payment_mode='Prepaid',
            status='Processing',
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
        )

        for line in order_lines:
            OrderItem.objects.create(
                order=order,
                product=line['object'] if line['kind'] == 'product' else None,
                combo=line['object'] if line['kind'] == 'combo' else None,
                price=line['price'],
                quantity=line['quantity'],
            )

        if applied_coupon:
            applied_coupon.total_uses += 1
            if applied_coupon.is_affiliate:
                applied_coupon.total_revenue_generated += total_amount
            applied_coupon.save()

        request.session.pop('applied_coupon', None)

        # 4. Determine delivery zone & push to Shiprocket as Prepaid
        is_local = LocalPincode.objects.filter(
            pincode=shipping_address.pincode, is_active=True
        ).exists()
        order.delivery_zone = 'local' if is_local else 'shiprocket'
        if is_local:
            order.shiprocket_sync_status = 'not_required'
            order.shiprocket_sync_error = ''
            order.shiprocket_synced_at = None
            order.save(update_fields=['delivery_zone', 'shiprocket_sync_status', 'shiprocket_sync_error', 'shiprocket_synced_at'])
        else:
            order.save(update_fields=['delivery_zone'])

        if not is_local and getattr(settings, 'SHIPROCKET_ENABLED', False):
            from core.shiprocket import shiprocket
            result = shiprocket.sync_order(order)
            if not result.get('success'):
                logger.error(f"Shiprocket push failed for Order #{order.id}: {result.get('message', 'Unknown error')}")

        return JsonResponse({
            'success': True,
            'message': 'Payment successful! Order placed.',
            'order_ref': order.order_ref,
        })

    except Address.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Selected address not found.'})
    except (Product.DoesNotExist, Combo.DoesNotExist):
        return JsonResponse({'success': False, 'message': 'One or more cart items were not found.'})
    except ValueError as e:
        return JsonResponse({'success': False, 'message': str(e) or 'Invalid cart item.'})
    except Exception as e:
        logger.error(f"verify_payment error: {e}")
        return JsonResponse({'success': False, 'message': str(e)})


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
    orders = Order.objects.filter(user=request.user).select_related('shipping_address', 'coupon').prefetch_related('items__product', 'items__combo')

    # Optional status filter
    status = request.GET.get('status')
    if status in ('Pending', 'Completed'):
        orders = orders.filter(status=status)
    
    orders_data = []
    # Count total orders for this user to assign user-specific order numbers
    total_user_orders = orders.count()
    for idx, order in enumerate(orders):
        # Orders are newest-first, so the first item gets the highest number
        user_order_number = total_user_orders - idx
        items_data = []
        for item in order.items.all():
            item_name = item.product.name if item.product else item.combo.name if item.combo else 'Deleted Item'
            item_identifier = item.product.id if item.product else f"combo-{item.combo.id}" if item.combo else None
            items_data.append({
                'id': item.id,
                'product_name': item_name,
                'product_id': item_identifier,
                'quantity': item.quantity,
                'price': float(item.price),
                'total': float(item.get_cost()),
            })
        
        orders_data.append({
            'id': order.id,
            'customer_id': order.customer.customer_id if order.customer else None,
            'user_order_number': user_order_number,
            'order_ref': order.order_ref,
            'status': order.status,
            'payment_mode': order.payment_mode,
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
    """Prepare cart items from a previous order for the standard checkout flow."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)
    
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        
        original_order = Order.objects.get(id=order_id, user=request.user)

        cart_items = []
        skipped_items = []

        for item in original_order.items.select_related('product', 'combo'):
            cart_payload = _order_item_cart_payload(item)
            if not cart_payload:
                skipped_items.append(item.id)
                continue

            cart_items.append(cart_payload)

        if not cart_items:
            return JsonResponse({
                'success': False,
                'message': 'This order cannot be repeated because its products are no longer available.',
            }, status=400)
        
        return JsonResponse({
            'success': True,
            'message': 'Items added to cart. Please confirm your address and payment method.',
            'cart_items': cart_items,
            'skipped_items': skipped_items,
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


# ---------------------------------------------------------------
# Quick Feedback View
# ---------------------------------------------------------------

@login_required(login_url='login')
def submit_feedback(request):
    """AJAX endpoint to submit quick feedback and email it to the site owner."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid request data.'}, status=400)

    import re
    from django.core.mail import send_mail
    from django.conf import settings as django_settings

    message = data.get('message', '').strip()

    # Strip HTML tags for sanitization
    message = re.sub(r'<[^>]+>', '', message)

    # Validation
    if not message:
        return JsonResponse({'success': False, 'message': 'Feedback cannot be empty.'}, status=400)
    if len(message) < 10:
        return JsonResponse({'success': False, 'message': 'Feedback must be at least 10 characters.'}, status=400)
    if len(message) > 500:
        return JsonResponse({'success': False, 'message': 'Feedback must not exceed 500 characters.'}, status=400)

    # Rate limiting: max 3 per user per hour
    one_hour_ago = timezone.now() - timezone.timedelta(hours=1)
    recent_count = Feedback.objects.filter(user=request.user, created_at__gte=one_hour_ago).count()
    if recent_count >= 3:
        return JsonResponse({'success': False, 'message': 'You can only submit 3 feedbacks per hour. Please try again later.'}, status=429)

    # Save feedback
    Feedback.objects.create(user=request.user, message=message)

    # Send email
    feedback_email = os.environ.get('FEEDBACK_EMAIL', '')
    if feedback_email:
        try:
            customer_id = getattr(request.user, 'customer', None)
            customer_id = customer_id.customer_id if customer_id else 'N/A'
            send_mail(
                subject=f"Quick Feedback from {request.user.get_full_name() or request.user.username} (ID: {customer_id})",
                message=(
                    f"Customer ID: {customer_id}\n"
                    f"Username: {request.user.username}\n"
                    f"Name: {request.user.get_full_name()}\n"
                    f"Email: {request.user.email}\n\n"
                    f"Feedback:\n{message}"
                ),
                from_email=django_settings.DEFAULT_FROM_EMAIL,
                recipient_list=[feedback_email],
                fail_silently=not django_settings.DEBUG,
            )
        except Exception as e:
            if django_settings.DEBUG:
                return JsonResponse({'success': False, 'message': f'Email error: {e}'}, status=500)

    return JsonResponse({'success': True, 'message': 'Thank you for your feedback!'})


# ---------------------------------------------------------------
# Shiprocket Webhook
# ---------------------------------------------------------------

@csrf_exempt
def shiprocket_webhook(request):
    """
    Receive tracking updates from Shiprocket.
    Shiprocket sends a POST with JSON body on every tracking event.
    """
    if request.method != "POST":
        return JsonResponse({"status": "error"}, status=405)

    # Optional token verification — set SHIPROCKET_WEBHOOK_TOKEN in env to enable
    webhook_token = getattr(settings, 'SHIPROCKET_WEBHOOK_TOKEN', '')
    if webhook_token:
        incoming = request.headers.get('x-api-key', '')
        if incoming != webhook_token:
            logger.warning("Shiprocket webhook: invalid token received")
            return JsonResponse({"status": "unauthorized"}, status=401)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "bad request"}, status=400)

    try:
        from core.shiprocket import shiprocket
        identifiers = shiprocket.extract_order_reference(data)
        event = shiprocket.extract_tracking_event(data)

        order = None
        sr_order_id = identifiers.get('shiprocket_order_id', '')
        shipment_id = identifiers.get('shipment_id', '')
        order_ref = identifiers.get('order_ref', '')

        if sr_order_id:
            order = Order.objects.filter(shiprocket_order_id=sr_order_id).first()
        if not order and shipment_id:
            order = Order.objects.filter(shipment_id=shipment_id).first()
        if not order and order_ref:
            order = Order.objects.filter(order_ref=order_ref).first()
        if not order:
            raise Order.DoesNotExist()

        new_status = shiprocket.apply_tracking_update(
            order,
            current_status=event.get('current_status', ''),
            awb=event.get('awb', ''),
            courier_name=event.get('courier_name', ''),
        )
        logger.info(
            "Webhook updated Order #%s → %s (sr_order_id=%s, shipment_id=%s)",
            order.id,
            event.get('current_status', ''),
            sr_order_id,
            shipment_id,
        )
    except Order.DoesNotExist:
        logger.warning("Webhook: No order found for payload=%s", data)

    return JsonResponse({"status": "ok"})