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



def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        return redirect('order_product', product_id=product.id)
    return render(request, 'product_detail.html', {'product': product})

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})



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

@login_required(login_url='login')  # Ensure user is logged in before proceeding
def order_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        quantity = int(request.POST['quantity'])
        order = Order.objects.create(user=request.user, product=product, quantity=quantity)
        return redirect('order_detail', order_id=order.id)
    return render(request, 'order_product.html', {'product': product})

#NEW SINGLE ORDER VIEW
from .models import Order, OrderItem  # Ensure OrderItem is imported

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


