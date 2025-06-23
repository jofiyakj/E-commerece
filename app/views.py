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
from .vectorize import vectorize_single_user, vectorize_product_with_reviews,combine_user_with_search_and_views
from .models import Product, Cart, CartItem, Order, OrderItem, UserProfile, Address, users, ViewHistory, SearchHistory, reviews
import json
import pandas as pd
import re
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from datetime import datetime, timedelta
from django.utils import timezone


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
        username = request.POST['username'].strip()
        email = request.POST['email'].strip()
        password = request.POST['password']
        confpassword = request.POST['confpassword']

        # Check if passwords match
        if password != confpassword:
            messages.error(request, "Passwords do not match.")
            return redirect('register')

        # Validate email format
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Invalid email format.")
            return redirect('register')

        # Check if username already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect('register')

        # Check if email already exists
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already in use.")
            return redirect('register')

        # Validate password strength
        if not is_valid_password(password):
            messages.error(
                request,
                "Password must be at least 8 characters long, contain an uppercase letter, a number, and a special character."
            )
            return redirect('register')

        # Create user
        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()

        user_profile = users.objects.create(user=user)
        user_vector = combine_user_with_search_and_views(user_profile)
        user_profile.vector_data = json.dumps(user_vector.tolist())
        user_profile.save()

        messages.success(request, "Registration successful. Please login.")
        return redirect('login')

    # Clear messages for GET request
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
            from_email='youremail@example.com',
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

@login_required(login_url='login')  # Ensure user is logged in before proceeding
def order_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        quantity = int(request.POST['quantity'])
        order = Order.objects.create(user=request.user, product=product, quantity=quantity)
        return redirect('order_detail', order_id=order.id)
    return render(request, 'order_product.html', {'product': product})

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

@login_required(login_url='login')
def order_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        quantity = int(request.POST['quantity'])

        # Create a new Order
        order = Order.objects.create(user=request.user)

        # Create a single OrderItem for the product
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity
        )

        # Optionally update product stock
        product.stock -= quantity
        product.save()

        return redirect('order_detail', order_id=order.id)

    return render(request, 'order_product.html', {'product': product})



#NEW CART TO ORDER VIEW



@login_required(login_url='login')

def cart_to_order(request):
    cart = get_object_or_404(Cart, user=request.user)
    cart_items = cart.items.all()

    if not cart_items.exists():
        return HttpResponse("Your cart is empty.")


    print("Checking",request.user)
    # Create a new Order
    order = Order.objects.create(user=request.user)

    # Create OrderItems from CartItems
    order_summary = ""
    for item in cart_items:
        if item.product.stock < item.quantity:
            messages.error(
                request,
                f"Insufficient stock for {item.product.name}. Available: {item.product.stock}, Requested: {item.quantity}"
            )
            return redirect('cart_view')
        else:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity
            )
            print("Checking",item.product.name)
            print("Checking",item.quantity)
            print("Checking",item.product.stock)
            # Optionally decrease product stock
            item.product.stock -= item.quantity
            item.product.save()

            # Build summary
            order_summary += f"{item.product.name} - {item.quantity}\n"

    # Clear cart
    cart.items.all().delete()

    # Send confirmation email
    send_mail(
        subject='Your Order Confirmation',
        message=f"Hi {request.user},\n\nThank you for your order!\n\nOrder ID: {order.id}\nItems:\n{order_summary}",
        from_email='tsgjr2126@gmail.com',
        recipient_list=[request.user],
        fail_silently=False,
    )

    return redirect('order_detail', order_id=order.id)



@login_required(login_url='login')  # Ensure user is logged in before proceeding
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'order_detail.html', {'order': order})

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

@login_required(login_url='login')  # Ensure user is logged in before proceeding
def user_orders(request):
    orders = Order.objects.filter(user=request.user)
    return render(request, 'user_orders.html', {'orders': orders})

@login_required(login_url='login')  # Ensure user is logged in before proceeding
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart, _ = Cart.objects.get_or_create(user=request.user)
    cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    return redirect('view_cart')

@login_required(login_url='login')  # Ensure user is logged in before proceeding
def view_cart(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    cart_items = cart.items.all()
    total_price = cart.get_total_price()
    return render(request, 'view_cart.html', {'cart_items': cart_items, 'total_price': total_price})

@login_required(login_url='login')  # Ensure user is logged in before proceeding
def remove_from_cart(request, product_id):
    cart = get_object_or_404(Cart, user=request.user)
    product = get_object_or_404(Product, id=product_id)
    cart_item = get_object_or_404(CartItem, cart=cart, product=product)
    cart_item.delete()
    return redirect('view_cart')

@login_required(login_url='login')
def update_quantity(request, product_id):
    if request.method == "POST":
        new_quantity = int(request.POST.get("quantity", 1))
        cart = get_object_or_404(Cart, user=request.user)
        cart_item = get_object_or_404(CartItem, cart=cart, product_id=product_id)

        if new_quantity > 0:
            cart_item.quantity = new_quantity
            cart_item.save()
        else:
            cart_item.delete()

    return redirect('view_cart')



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


