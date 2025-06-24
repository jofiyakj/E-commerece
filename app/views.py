from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from .models import *
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.shortcuts import redirect
from django.http import HttpResponse
from .vectorize import vectorize_single_user, vectorize_product_with_reviews,combine_user_with_search_and_views,get_recommendations
from .models import Product, Cart, CartItem, Order, OrderItem, UserProfile, Address, users, ViewHistory, SearchHistory, reviews
import json
import pandas as pd
import re
import random
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from datetime import datetime, timedelta
from django.utils import timezone
import razorpay
from django.conf import settings
from .models import Product, Cart, CartItem
from django.views.decorators.csrf import csrf_exempt
from razorpay.errors import BadRequestError, ServerError, GatewayError



client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_home_view(request):
    return render(request, 'admin_home.html')

def admin_home(request):
    return render(request, 'admin_home.html')


def category_list(request):
    categories = Product.objects.values_list('category', flat=True).distinct()
    return render(request, 'category_list.html', {'categories': categories})


def home(request):
    query = request.GET.get('query')
    
    if query:
        # Check for exact match (case-insensitive)
        exact_matches = Product.objects.filter(name__iexact=query)
        
        if exact_matches.count() == 1:
            # Redirect to the product detail page
            return redirect('product_detail', product_id=exact_matches.first().id)
        
        # Else show partial matches
        products = Product.objects.filter(name__icontains=query)
    else:
        products = Product.objects.all()
        
    return render(request, 'home.html', {'products': products})


@login_required(login_url='login')
def recommendations(request):
    recommended_products = get_recommendations(request.user, top_n=5)
    return render(request, 'recommendations.html', {'recommended_products': recommended_products})



# def product_detail(request, product_id):
#     product = get_object_or_404(Product, id=product_id)
#     if request.method == 'POST':
#         return redirect('order_product', product_id=product.id)
#     return render(request, 'product_detail.html', {'product': product})


def update_product_vector(product):
    try:
        # Gather all review descriptions
        reviews_text = [review.description for review in product.reviews_set.all()]

        # Construct a single-row DataFrame
        product_data = [{
            "pro_id": product.id,
            "name": product.name,
            "rating": product.rating,
            "category": product.category,
            "description": product.description,
            "reviews": ', '.join(reviews_text)  # Combine review texts
        }]
        df = pd.DataFrame(product_data)

        # Generate vector
        product_vector = vectorize_product_with_reviews(df)

        # Save the vector as JSON
        if product_vector is not None and len(product_vector) > 0:
            product.vector_data = json.dumps(product_vector[0].tolist())
        else:
            product.vector_data = json.dumps([])

        product.save()

    except Exception as e:
        print(f"[Vector Error] Failed to vectorize product {product.id}: {e}")
        product.vector_data = json.dumps([])
        product.save()


def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart_item_ids = []
    product_reviews = product.reviews_set.all()  # Fetch all reviews for this product
    print(f"Reviews for product {product.id}: {product_reviews.count()}")  # Debugging line

    if request.user.is_authenticated:
        # Get or create cart
        cart = Cart.objects.filter(user=request.user).first()
        if cart:
            cart_item_ids = cart.items.values_list('product_id', flat=True)

        # Get or create user extension (users model)
        user_obj, created = users.objects.get_or_create(user=request.user)

        # Add to view history
        ViewHistory.objects.create(user=user_obj, product=product)
        vectorize_single_user(request.user)

        # Handle review submission
        if request.method == 'POST':
            rating = request.POST.get('rating')
            description = request.POST.get('description')

            if not rating or not description:
                messages.error(request, "Please provide both rating and description.", extra_tags='review')
            else:
                try:
                    rating = int(rating)
                    if 1 <= rating <= 5:
                        # Save new review
                        new_review = reviews.objects.create(
                            pname=product,
                            uname=user_obj,
                            rating=rating,
                            description=description
                        )
                        print(f"Created review ID {new_review.id} for product {product.id}")  # Debug

                        # Update product rating
                        all_reviews = product.reviews_set.all()
                        total_rating = sum(r.rating for r in all_reviews)
                        product.rating = round(total_rating / len(all_reviews), 1)
                        product.save()

                        # Update vector
                        update_product_vector(product)

                        messages.success(request, "Review added successfully!", extra_tags='review')
                        return redirect('product', product_id=product.id)
                    else:
                        messages.error(request, "Rating must be between 1 and 5.", extra_tags='review')
                except ValueError:
                    messages.error(request, "Invalid rating value.", extra_tags='review')
                except Exception as e:
                    messages.error(request, f"Error adding review: {str(e)}", extra_tags='review')
                    print(f"Review creation error: {str(e)}")  # Debug

    # Gather product images (main + additional)
    additional_images = [
        img for img in [
            product.image,
            product.additional_image1,
            product.additional_image2,
            product.additional_image3
        ] if img
    ]

    # Get similar products from the same category
    similar_products = Product.objects.filter(category=product.category).exclude(id=product.id)

    return render(request, 'product_detail.html', {
        'product': product,
        'cart_item_ids': cart_item_ids,
        'additional_images': additional_images,
        'similar_products': similar_products,
        'reviews': product_reviews,
    })



def is_valid_password(password):
    return (
        len(password) >= 8 and
        re.search(r"[A-Z]", password) and
        re.search(r"\d", password) and
        re.search(r"[!@#$%^&*(),.?\":{}|<>]", password)
    )
# def register(request):
#     if request.method == 'POST':
#         form = UserCreationForm(request.POST)
#         if form.is_valid():
#             user = form.save()
#             login(request, user)
#             return redirect('home')
#     else:
#         form = UserCreationForm()
#     return render(request, 'register.html', {'form': form})








def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confpassword = request.POST.get('confpassword', '')

        # Basic validation
        if not username or not email or not password or not confpassword:
            messages.error(request, "All fields are required.")
            return redirect('register')

        if password != confpassword:
            messages.error(request, "Passwords do not match.")
            return redirect('register')

        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Invalid email format.")
            return redirect('register')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect('register')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already in use.")
            return redirect('register')

        if not is_valid_password(password):
            messages.error(
                request,
                "Password must be at least 8 characters long, contain an uppercase letter, a number, and a special character."
            )
            return redirect('register')

        # Create user and profile
        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()

        user_profile = users.objects.create(user=user)

        # Safely generate and assign vector data
        user_vector = combine_user_with_search_and_views(user_profile)
        if user_vector is not None:
            try:
                user_profile.vector_data = json.dumps(user_vector.tolist())
                user_profile.save()
            except Exception as e:
                messages.warning(request, f"User registered, but vector data save failed: {e}")
        else:
            messages.warning(request, "User registered, but no vector data was generated.")

        messages.success(request, "Registration successful. Please login.")
        return redirect('login')

    messages.get_messages(request).used = True
    return render(request, 'register.html')






def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if user.is_superuser:
                return redirect('admin_home')  # Ensure 'admin_home' is mapped in urls.py
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

def forgot_password_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        otp = random.randint(100000, 999999)

        request.session['reset_email'] = email
        request.session['otp'] = otp

        send_mail(
            subject='Your OTP Code',
            message=f'Your OTP is {otp}',
            from_email='jofiyakj@gmail.com',
            recipient_list=[email],
            fail_silently=False,
        )

        messages.success(request, 'OTP has been sent to your email.')
        return redirect('verify_otp')

    return render(request, 'forgot_password.html')

def verify_otp(request):
    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        if str(request.session.get('otp')) == entered_otp:
            messages.success(request, 'OTP verified. You can now reset your password.')
            return redirect('reset_password')
        else:
            messages.error(request, 'Invalid OTP. Please try again.')

    return render(request, 'verify_otp.html')

def reset_password(request):
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        email = request.session.get('reset_email')

        user = User.objects.filter(email=email).first()
        if user:
            user.set_password(new_password)
            user.save()
            messages.success(request, "Password has been reset. You can now log in.")
            return redirect('login')
        else:
            messages.error(request, "Something went wrong. Please try again.")
            return redirect('forgot_password')

    return render(request, 'reset_password.html')


def first_page(request):
    products = Product.objects.all()
    return render(request, 'firstpage.html', {'products': products})

def delete_g(request, id):
    get_object_or_404(Product, pk=id).delete()
    return redirect('firstpage')

def edit_g(request, id):
    product = get_object_or_404(Product, id=id)

    if request.method == 'POST':
        product.name = request.POST.get('name')
        product.price = request.POST.get('price')
        product.offerprice = request.POST.get('offerprice')
        product.category = request.POST.get('category')
        product.warranty = request.POST.get('warranty')
        product.description = request.POST.get('description')
        product.stock = request.POST.get('stock')

        # Update images if provided
        if 'image' in request.FILES:
            product.image = request.FILES['image']
        if 'additional_image1' in request.FILES:
            product.additional_image1 = request.FILES['additional_image1']
        if 'additional_image2' in request.FILES:
            product.additional_image2 = request.FILES['additional_image2']
        if 'additional_image3' in request.FILES:
            product.additional_image3 = request.FILES['additional_image3']

        product.save()
        messages.success(request, 'Product updated successfully!')
        return redirect('firstpage')

    return render(request, 'add.html', {'data1': product})






# @login_required(login_url='login')  # Ensure user is logged in before proceeding
# def order_product(request, product_id):
#     product = get_object_or_404(Product, id=product_id)
#     if request.method == 'POST':
#         quantity = int(request.POST['quantity'])
#         order = Order.objects.create(user=request.user, product=product, quantity=quantity)
#         return redirect('order_detail', order_id=order.id)
#     return render(request, 'order_product.html', {'product': product})



# @login_required(login_url='login')  # Ensure user is logged in before proceeding
# def order_detail(request, order_id):
#     order = get_object_or_404(Order, id=order_id)
#     return render(request, 'order_detail.html', {'order': order})



@login_required(login_url='login')
def add_product(request):
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to access this page.")
        return redirect('login')

    if request.method == 'POST':
        name = request.POST.get('name')
        price = request.POST.get('price')
        offerprice = request.POST.get('offerprice')
        description = request.POST.get('description')
        category = request.POST.get('category')
        warranty = request.POST.get('warranty')
        stock = request.POST.get('stock')
        image = request.FILES.get('image')
        additional_image1 = request.FILES.get('additional_image1')
        additional_image2 = request.FILES.get('additional_image2')
        additional_image3 = request.FILES.get('additional_image3')

        if not all([name, price, description, category, stock]):
            messages.error(request, "Please fill in all required fields.")
            return render(request, 'add.html', {
                'name': name,
                'price': price,
                'offerprice': offerprice,
                'description': description,
                'category': category,
                'warranty': warranty,
                'stock': stock,
            })

        try:
            price = float(price)
            offerprice = float(offerprice) if offerprice else None
            stock = int(stock)
            if stock < 0:
                raise ValueError("Stock cannot be negative.")
        except ValueError:
            messages.error(request, "Invalid price or stock value.")
            return render(request, 'add.html', {
                'name': name,
                'price': price,
                'offerprice': offerprice,
                'description': description,
                'category': category,
                'warranty': warranty,
                'stock': stock,
            })

        product = Product.objects.create(
            name=name,
            price=price,
            offerprice=offerprice,
            description=description,
            category=category,
            warranty=warranty,
            stock=stock,
            image=image,
            additional_image1=additional_image1,
            additional_image2=additional_image2,
            additional_image3=additional_image3,
            rating=0,
        )

        # Add error handling for vectorization
        try:
            pro_data = [{
                "pro_id": product.id,
                "name": product.name,
                "rating": product.rating,
                "type": product.category,
                "description": product.description,
                "reviews": ''
            }]
            df = pd.DataFrame(pro_data)
            product_vector = vectorize_product_with_reviews(df)
            
            # Check if product_vector is not empty and has valid data
            if product_vector is not None and len(product_vector) > 0:
                product.vector_data = json.dumps(product_vector[0].tolist())
                product.save()
            else:
                # Handle case where vectorization fails
                print(f"Warning: Vectorization failed for product {product.id}")
                # You might want to set a default vector or leave it empty
                product.vector_data = json.dumps([])
                product.save()
                
        except Exception as e:
            # Log the error and continue without crashing
            print(f"Error during product vectorization: {str(e)}")
            # Set empty vector data as fallback
            product.vector_data = json.dumps([])
            product.save()

        messages.success(request, "Product added successfully!")
        return redirect('firstpage')

    return render(request, 'add.html', {
        'categories': Product.CATEGORY_CHOICES,
    })

@login_required(login_url='login')
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if product.stock <= 0:
        messages.error(request, "Product is out of stock.", extra_tags='stock')
        return redirect('product_detail', product_id=product_id)

    cart, _ = Cart.objects.get_or_create(user=request.user)
    cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)

    quantity = 1

    if request.method == 'POST':
        try:
            quantity = int(request.POST.get('quantity', 1))
            if quantity < 1:
                messages.error(request, "Quantity must be at least 1.", extra_tags='stock')
                return redirect('product_detail', product_id=product_id)
            if quantity > product.stock:
                messages.error(request, f"Only {product.stock} items available.", extra_tags='stock')
                return redirect('product_detail', product_id=product_id)
        except ValueError:
            messages.error(request, "Invalid quantity.", extra_tags='stock')
            return redirect('product_detail', product_id=product_id)

        if created:
            cart_item.quantity = quantity
        else:
            if cart_item.quantity + quantity > product.stock:
                messages.error(request, f"Adding this quantity exceeds stock. Only {product.stock} item(s) available.", extra_tags='stock')
                return redirect('product_detail', product_id=product_id)
            cart_item.quantity += quantity

        cart_item.save()
        messages.success(request, f"Added {quantity} × {product.name} to cart.")
        return redirect('cart')

    # Add a fallback return (in case it's a GET request or something goes wrong)
    return redirect('product_detail', product_id=product_id)

@login_required(login_url='login')
def increment_cart(request, id):
    if request.method == "POST":
        cart_item = get_object_or_404(CartItem, id=id, cart__user=request.user)
        product = cart_item.product

        if cart_item.quantity >= product.stock:
            messages.warning(request, f"Only {product.stock} items in stock.")
        else:
            cart_item.quantity += 1
            cart_item.save()
            messages.success(request, "Quantity increased.")

    return redirect('cart')

@login_required(login_url='login')
def decrement_cart(request, id):
    if request.method == "POST":
        cart_item = get_object_or_404(CartItem, id=id, cart__user=request.user)

        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
            messages.success(request, "Quantity decreased.")
        else:
            cart_item.delete()
            messages.info(request, "Item removed from cart.")

    return redirect('cart')# views.py (updated cart_view)

@login_required(login_url='login')
def buy_now(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    # Check if product is out of stock
    if product.stock <= 0:
        messages.error(request, "Product is out of stock.", extra_tags='stock')
        return redirect('product', id=product_id)

    # Default quantity
    quantity = 1
    if request.method == 'POST':
        try:
            quantity = int(request.POST.get('quantity', 1))
            if quantity < 1:
                messages.error(request, "Quantity must be at least 1.", extra_tags='stock')
                return redirect('product', id=product_id)
            if quantity > product.stock:
                messages.error(request, f"Only {product.stock} items available.", extra_tags='stock')
                return redirect('product', id=product_id)
        except ValueError:
            messages.error(request, "Invalid quantity.", extra_tags='stock')
            return redirect('product', id=product_id)

    # Get or create the user's cart
    cart, _ = Cart.objects.get_or_create(user=request.user)
    cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)

    # Update cart item quantity
    if not created:
        # Check if adding the new quantity exceeds stock
        if cart_item.quantity + quantity > product.stock:
            messages.error(request, f"Stock limit reached. Only {product.stock - cart_item.quantity} more items available.", extra_tags='stock')
            return redirect('product', id=product_id)
        cart_item.quantity += quantity
    else:
        cart_item.quantity = quantity

    cart_item.save()
    messages.success(request, f"{quantity} item(s) added for purchase.", extra_tags='stock')
    return redirect('checkout')


def remove_from_cart(request, product_id):
    try:
        cart = Cart.objects.get(user=request.user)
        cart_item = get_object_or_404(CartItem, cart=cart, product_id=product_id)
        cart_item.delete()
    except Cart.DoesNotExist:
        pass
    return redirect('checkout')

@login_required(login_url='login')
def delete_cart_item(request, id):
    cart_item = get_object_or_404(CartItem, id=id, cart__user=request.user)
    cart_item.delete()
    messages.success(request, 'Item removed.')
    return redirect('cart_view')
@login_required(login_url='login')
def cart_view(request):
    cart = Cart.objects.filter(user=request.user).first()
    cart_items = cart.items.all() if cart else []
    total_price = sum(item.get_total_price() for item in cart_items)  # Now uses offerprice
    # Prepare cart items with subtotals for the template
    cart_items_with_subtotals = [
        {'item': item, 'subtotal': item.get_total_price()}
        for item in cart_items
    ]
    return render(request, 'cart.html', {
        'cart_items_with_subtotals': cart_items_with_subtotals,
        'total_price': total_price
    })

def get_total_price(self):
    return self.product.offerprice * self.quantity


@login_required(login_url='login')
def checkout(request):
    cart_items = CartItem.objects.filter(cart__user=request.user)
    addresses = Address.objects.filter(user=request.user)

    total_price = sum(
        item.product.offerprice * item.quantity if item.product.offerprice
        else item.product.price * item.quantity
        for item in cart_items
    )

    if total_price <= 0:
        messages.error(request, "Invalid cart total. Please check your cart and try again.")
        return redirect('cart_view')

    razorpay_order = None
    if total_price > 0:
        try:
            razorpay_order = client.order.create({
                "amount": int(total_price * 100),
                "currency": "INR",
                "payment_capture": "1"
            })
        except BadRequestError:
            messages.error(request, "Invalid request to payment gateway. Please try again later.")
            return redirect('cart_view')
        except ServerError:
            messages.error(request, "Payment gateway server error. Please try again later.")
            return redirect('cart_view')
        except GatewayError:
            messages.error(request, "Payment gateway error. Please try again later.")
            return redirect('cart_view')
        except Exception:
            messages.error(request, "An unexpected error occurred. Please try again later.")
            return redirect('cart_view')

    context = {
        'cart_items': cart_items,
        'items_total': cart_items.count(),
        'total_price': total_price,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'razorpay_amount': total_price,
        'razorpay_order_id': razorpay_order['id'] if razorpay_order else '',
        'delivery_date': timezone.now() + timezone.timedelta(days=5),
        'addresses': addresses,
    }
    return render(request, 'checkout.html', context)

@csrf_exempt
@login_required(login_url='login')
def process_checkout(request):
    if request.method == 'POST':
        address_id = request.POST.get('billing_address')
        payment_method = request.POST.get('payment_method')
        razorpay_payment_id = request.POST.get('razorpay_payment_id', '')
        cart_items = CartItem.objects.filter(cart__user=request.user)
        
        if not cart_items.exists():
            messages.error(request, 'Your cart is empty.', extra_tags='stock')
            return redirect('cart_view')
        
        if not address_id:
            messages.error(request, 'Please select a billing address.', extra_tags='stock')
            return redirect('checkout')

        # Re-validate stock to prevent race conditions
        for cart_item in cart_items:
            # Refresh product from database to get latest stock
            product = Product.objects.get(id=cart_item.product.id)
            if product.stock < cart_item.quantity:
                messages.error(request, f'Insufficient stock for {product.name}. Only {product.stock} items left.', extra_tags='stock')
                return redirect('checkout')  # Stay in checkout

        selected_address = get_object_or_404(Address, id=address_id, user=request.user)
        total_price = sum(
            (item.product.offerprice or item.product.price) * item.quantity for item in cart_items
        )

        # Create order
        order = Order.objects.create(
            user=request.user,
            name=selected_address.name,
            phone=selected_address.phone,
            pincode=selected_address.pincode,
            address=selected_address.address,
            address_type='Home' if selected_address.is_default else 'Other',
            payment_method=payment_method,
            total_price=total_price,
            razorpay_payment_id=razorpay_payment_id if payment_method == 'razorpay' else '',
            status='Ordered'
        )

        # Create order items and reduce stock
        for cart_item in cart_items:
            # Refresh product again to ensure consistency
            product = Product.objects.get(id=cart_item.product.id)
            if product.stock < cart_item.quantity:
                # Roll back order if stock changed
                order.delete()
                messages.error(request, f'Insufficient stock for {product.name}. Please try again.', extra_tags='stock')
                return redirect('checkout')
            
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                quantity=cart_item.quantity,
                price=(cart_item.product.offerprice or cart_item.product.price)
            )
            # Reduce stock
            product.stock -= cart_item.quantity
            product.save()

        # Clear cart
        cart_items.delete()
     
        return redirect('payment_successful')

    return redirect('checkout')



def order_detail_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'order_detail.html', {'order': order})


@login_required(login_url='login')
def update_order_status(request, order_id):
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('index')

    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_statuses = [choice[0] for choice in Order.STATUS_CHOICES]
        
        if new_status in valid_statuses and new_status != 'Cancelled':  # Cancel is handled separately
            if order.status != new_status:
                order.status = new_status
                order.save()
                messages.success(request, f"Order #{order.id} status updated to {new_status}.")

                # Send email notification to the user
                try:
                    subject = f'Order #{order.id} Status Update'
                    message = (
                        f'Dear {order.user.username},\n\n'
                        f'Your order #{order.id} has been updated to the following status: {new_status}.\n'
                        f'Order Details:\n'
                        f'Total Price: ₹{order.total_price}\n'
                        f'Payment Method: {order.payment_method.title()}\n'
                        f'For more details, please check your order history on our website.\n\n'
                        f'Thank you for shopping with VaultGuard!'
                    )
                    send_mail(
                        subject=subject,
                        message=message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[order.user.email],
                        fail_silently=False,
                    )
                except Exception as e:
                    messages.error(request, f"Order status updated, but failed to send email notification: {str(e)}")

            else:
                messages.error(request, f"Order #{order.id} is already {new_status}.")
        else:
            messages.error(request, "Invalid status update.")
    
    return redirect('admin_bookings')



@login_required(login_url='login')
def update_quantity(request, product_id):
    cart = Cart.objects.get(user=request.user)
    cart_item = CartItem.objects.get(cart=cart, product_id=product_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        product = cart_item.product

        if action == 'increase':
            if cart_item.quantity + 1 > product.stock:
                
                return redirect('checkout')
            cart_item.quantity += 1
            cart_item.save()
          

        elif action == 'decrease' and cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
            

    return redirect('checkout')

def payment_successful(request):
    if request.user.is_superuser:
        return redirect('admin_bookings')
    order = Order.objects.filter(user=request.user).order_by('-created_at').first()
    if not order:
        messages.error(request, 'No recent order found.')
        return redirect('index')
    return render(request, 'payment_successful.html', {'order': order})

def order_tracking(request):
    return render(request, 'order_track.html')

def track_order(request):
    if request.method == 'POST':
        order_number = request.POST.get('order_number')
        try:
            order = Order.objects.get(id=order_number, user=request.user)
            context = {
                'order_status': order.status,
                'order': order,
                'items': order.items.all(),  # Pass all order items
            }
            return render(request, 'order_track.html', context)
        except Order.DoesNotExist:
            return render(request, 'order_track.html', {'error': 'Order not found or you do not have permission to view it'})
    
    return render(request, 'order_track.html')

@login_required
def user_list(request):
    if not request.user.is_superuser:
        return render(request, 'unauthorized.html')
    users = User.objects.all().order_by('-date_joined')  # <- newest first
    return render(request, 'user_list.html', {'users': users})

def user_detail(request, user_id):
    user_obj = User.objects.get(id=user_id)
    
    # Use the get_or_create_profile method to retrieve or create the profile for the user
    profile = UserProfile.get_or_create_profile(user_obj)
    
    # Retrieve the addresses and orders for the user
    addresses = Address.objects.filter(user=user_obj)
    orders = Order.objects.filter(user=user_obj)

    context = {
        'user_obj': user_obj,
        'profile': profile,
        'addresses': addresses,
        'orders': orders,
    }

    return render(request, 'user_detail.html', context)

@login_required
def delete_user(request, user_id):
    if not request.user.is_superuser:
        return render(request, 'unauthorized.html')

    user = get_object_or_404(User, id=user_id)
    user.delete()
    messages.success(request, "User deleted successfully.")
    return redirect('user_list') 





#NEW SINGLE ORDER VIEW
@login_required
def profile_view(request):
    addresses = Address.objects.filter(user=request.user)
    orders = Order.objects.filter(user=request.user).order_by('-created_at')

    # Calculate delivery date and return eligibility for each order
    for order in orders:
        order.delivery_date = order.created_at + timedelta(days=5)
        # Check if order is within 7 days for return eligibility
        order.can_return = (order.status == 'Delivered' and 
                           (timezone.now() - order.created_at).days < 7)

    editing_address = False
    address_to_edit = None
    name = phone = pincode = address = ''
    errors = {}

    # Check if editing an address
    address_id = request.GET.get('edit')
    if address_id:
        try:
            address_to_edit = Address.objects.get(id=address_id, user=request.user)
            editing_address = True
            name = address_to_edit.name
            phone = address_to_edit.phone
            pincode = address_to_edit.pincode
            address = address_to_edit.address
        except Address.DoesNotExist:
            pass

    context = {
        'addresses': addresses,
        'orders': orders,
        'editing_address': editing_address,
        'address_to_edit': address_to_edit,
        'name': name,
        'phone': phone,
        'pincode': pincode,
        'address': address,
        'errors': errors,
        'action': 'Edit',
    }
    return render(request, 'profile.html', context)


@login_required
def add_address(request):
    if request.method == 'POST':
        name = request.POST.get('name', '')
        address = request.POST.get('address', '')
        pincode = request.POST.get('pincode', '')
        phone = request.POST.get('phone', '')

        errors = {}
        if not name:
            errors['name'] = 'Name is required.'
        if not address:
            errors['address'] = 'Address is required.'
        if not pincode:
            errors['pincode'] = 'Pincode is required.'
        if not phone:
            errors['phone'] = 'Phone number is required.'

        if not errors:
            Address.objects.create(
                user=request.user,
                name=name,
                address=address,
                pincode=pincode,
                phone=phone
            )
            messages.success(request, 'Address added successfully!')
            return redirect('profile')
        else:
            return render(request, 'address_form.html', {
                'errors': errors,
                'name': name,
                'address': address,
                'pincode': pincode,
                'phone': phone,
                'action': 'Add'
            })

    return render(request, 'address_form.html', {
        'action': 'Add',
        'name': '',
        'address': '',
        'pincode': '',
        'phone': '',
        'errors': {}
    })

@login_required
def edit_address(request, address_id):
    address_obj = get_object_or_404(Address, id=address_id, user=request.user)

    if request.method == 'POST':
        name = request.POST.get('name', '')
        address = request.POST.get('address', '')
        pincode = request.POST.get('pincode', '')
        phone = request.POST.get('phone', '')

        errors = {}
        if not name:
            errors['name'] = 'Name is required.'
        if not address:
            errors['address'] = 'Address is required.'
        if not pincode:
            errors['pincode'] = 'Pincode is required.'
        if not phone:
            errors['phone'] = 'Phone number is required.'

        if not errors:
            address_obj.name = name
            address_obj.address = address
            address_obj.pincode = pincode
            address_obj.phone = phone
            address_obj.save()
            messages.success(request, 'Address updated successfully!')
            return redirect('profile')
        else:
            return render(request, 'address_form.html', {
                'errors': errors,
                'name': name,
                'address': address,
                'pincode': pincode,
                'phone': phone,
                'action': 'Edit'
            })

    return render(request, 'address_form.html', {
        'name': address_obj.name,
        'address': address_obj.address,
        'pincode': address_obj.pincode,
        'phone': address_obj.phone,
        'action': 'Edit',
        'errors': {}
    })

@login_required
def delete_address(request, address_id):
    address_obj = get_object_or_404(Address, id=address_id, user=request.user)
    address_obj.delete()
    messages.success(request, 'Address deleted successfully!')
    return redirect('profile')


@login_required
def edit_email(request):
    """View to edit user's email"""
    user = request.user
    
    if request.method == 'POST':
        email = request.POST.get('email', '')
        
        # Basic validation
        errors = {}
        if not email:
            errors['email'] = 'Email is required.'
        elif '@' not in email:
            errors['email'] = 'Please enter a valid email address.'
            
        if not errors:
            # Update email
            user.email = email
            user.save()
            messages.success(request, 'Email updated successfully!')
            return redirect('profile')
        else:
            # If there are errors, pass them to the template
            return render(request, 'email.html', {
                'errors': errors,
                'email': email
            })
    
    
    return render(request, 'email.html', {
        'email': user.email
    })



@login_required
def edit_username(request):
    """View to edit user's username"""
    user = request.user
    
    if request.method == 'POST':
        username = request.POST.get('username', '')
        
        # Basic validation
        errors = {}
        if not username:
            errors['username'] = 'Username is required.'
        elif len(username) < 4:
            errors['username'] = 'Username should be at least 4 characters long.'
        elif User.objects.filter(username=username).exists():
            errors['username'] = 'This username is already taken.'
            
        if not errors:
            # Update username
            user.username = username
            user.save()
            messages.success(request, 'Username updated successfully!')
            return redirect('profile')
        else:
            # If there are errors, pass them to the template
            return render(request, 'username.html', {
                'errors': errors,
                'username': username
            })
    
    # Pre-fill form with existing username
    return render(request, 'username.html', {
        'username': user.username
    }) 


@login_required
def admin_bookings(request):
    if not request.user.is_superuser:
        return redirect('index')
    orders = Order.objects.all().order_by('-created_at')
    
    # Calculate delivery date for each order (created_at + 5 days)
    for order in orders:
        order.delivery_date = order.created_at + timedelta(days=5)
    
    return render(request, 'bookings.html', {'orders': orders})

@login_required(login_url='login')
def confirm_order(request, order_id):
    # Ensure only admins can access this view
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('index')

    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        if order.status == 'Pending':
            order.status = 'Confirmed'
            order.save()
            messages.success(request, f"Order #{order.id} has been confirmed.")
        else:
            messages.error(request, f"Order #{order.id} cannot be confirmed as it is already {order.status}.")
    
    return redirect('admin_bookings')

def payment_successful(request):
    return render(request, 'payment_successful.html')



@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if request.method == "POST":
        if order.status in ['Ordered', 'Confirmed', 'Shipped']:
            order.status = 'Cancelled'
            order.save()
            
            # Restore stock for each item in the order
            for order_item in order.items.all():
                product = order_item.product
                product.stock += order_item.quantity
                product.save()
            
            messages.success(request, f"Order #{order.id} has been cancelled.")
    
    return redirect('profile')



def order_success(request):
    order = Order.objects.filter(user=request.user).order_by('-created_at').first()
    if not order:
        messages.error(request, 'No recent order found.')
        return redirect('index')
    return render(request, 'order_success.html', {'order': order})

@login_required
def return_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    if request.method == 'POST':
        # Check if the order is in 'Delivered' status and within 7 days
        if order.status == 'Delivered':
            order_age = timezone.now() - order.created_at
            if order_age.days <= 7:
                order.status = 'Returned'
                order.save()
                messages.success(request, f"Order #{order.id} has been marked for return.")
            else:
                messages.error(request, "Return period has expired (7 days).")
        else:
            messages.error(request, "Only delivered orders can be returned.")
        return redirect('profile')
    
    return redirect('profile')




# @login_required(login_url='login')
# def order_product(request, product_id):
#     product = get_object_or_404(Product, id=product_id)

#     if request.method == 'POST':
#         quantity = int(request.POST['quantity'])

#         # Create a new Order
#         order = Order.objects.create(user=request.user)

#         # Create a single OrderItem for the product
#         OrderItem.objects.create(
#             order=order,
#             product=product,
#             quantity=quantity
#         )

#         # Optionally update product stock
#         product.stock -= quantity
#         product.save()

#         return redirect('order_detail', order_id=order.id)

#     return render(request, 'order_product.html', {'product': product})



#NEW CART TO ORDER VIEW



# @login_required(login_url='login')

# def cart_to_order(request):
#     cart = get_object_or_404(Cart, user=request.user)
#     cart_items = cart.items.all()

#     if not cart_items.exists():
#         return HttpResponse("Your cart is empty.")


#     print("Checking",request.user)
#     # Create a new Order
#     order = Order.objects.create(user=request.user)

#     # Create OrderItems from CartItems
#     order_summary = ""
#     for item in cart_items:
#         if item.product.stock < item.quantity:
#             messages.error(
#                 request,
#                 f"Insufficient stock for {item.product.name}. Available: {item.product.stock}, Requested: {item.quantity}"
#             )
#             return redirect('view')
#         else:
#             OrderItem.objects.create(
#                 order=order,
#                 product=item.product,
#                 quantity=item.quantity
#             )
#             print("Checking",item.product.name)
#             print("Checking",item.quantity)
#             print("Checking",item.product.stock)
#             # Optionally decrease product stock
#             item.product.stock -= item.quantity
#             item.product.save()

#             # Build summary
#             order_summary += f"{item.product.name} - {item.quantity}\n"

#     # Clear cart
#     cart.items.all().delete()

#     # Send confirmation email
#     send_mail(
#         subject='Your Order Confirmation',
#         message=f"Hi {request.user},\n\nThank you for your order!\n\nOrder ID: {order.id}\nItems:\n{order_summary}",
#         from_email='jofiyakj@gmail.com',
#         recipient_list=[request.user.email],
#         fail_silently=False,
#     )

#     return redirect('order_detail', order_id=order.id)










@login_required(login_url='login')  # Ensure user is logged in before proceeding
def user_orders(request):
    orders = Order.objects.filter(user=request.user)
    return render(request, 'user_orders.html', {'orders': orders})

# @login_required(login_url='login')  # Ensure user is logged in before proceeding
# def add_to_cart(request, product_id):
#     product = get_object_or_404(Product, id=product_id)
#     cart, _ = Cart.objects.get_or_create(user=request.user)
#     cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
#     if not created:
#         cart_item.quantity += 1
#         cart_item.save()
#     return redirect('view_cart')















# @login_required(login_url='login')  # Ensure user is logged in before proceeding
# def view_cart(request):
#     cart, _ = Cart.objects.get_or_create(user=request.user)
#     cart_items = cart.items.all()
#     total_price = cart.get_total_price()
#     return render(request, 'view_cart.html', {'cart_items': cart_items, 'total_price': total_price})

# @login_required(login_url='login')  # Ensure user is logged in before proceeding
# def remove_from_cart(request, product_id):
#     cart = get_object_or_404(Cart, user=request.user)
#     product = get_object_or_404(Product, id=product_id)
#     cart_item = get_object_or_404(CartItem, cart=cart, product=product)
#     cart_item.delete()
#     return redirect('cart')



# @login_required(login_url='login')
# def update_quantity(request, product_id):
#     if request.method == "POST":
#         new_quantity = int(request.POST.get("quantity", 1))
#         cart = get_object_or_404(Cart, user=request.user)
#         cart_item = get_object_or_404(CartItem, cart=cart, product_id=product_id)

#         if new_quantity > 0:
#             cart_item.quantity = new_quantity
#             cart_item.save()
#         else:
#             cart_item.delete()

#     return redirect('cart')




def terms(request):
    return render(request, 'terms.html')

def privacy(request):
    return render(request, 'privacy.html')

def contact(request):
    return render(request, 'contact.html')

def search_products(request):
    query = request.GET.get('query', '')
    products = Product.objects.filter(name__icontains=query) if query else []
    return render(request, 'search_results.html', {'products': products, 'query': query})



# @login_required
# def initiate_payment(request):
#     client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

#     amount = 50000  # Amount in paise (₹500.00)
#     currency = 'INR'

#     payment = client.order.create({
#         'amount': amount,
#         'currency': currency,
#         'payment_capture': 1
#     })

#     context = {
#         'payment': payment,
#         'key_id': settings.RAZORPAY_KEY_ID,
#         'amount': amount,
#         'user': request.user
#     }
#     return render(request, 'payment.html', context)

# def payment_success(request):
#     payment_id = request.GET.get('payment_id')
#     # Optionally verify payment with Razorpay API
#     # Save order/payment in DB
#     return render(request, 'payment_success.html', {'payment_id': payment_id})
# @login_required(login_url='login')
