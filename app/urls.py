from django.urls import path
from . import views

urlpatterns = [
    path('admin-home/', views.admin_home, name='admin_home'),
    path('', views.home, name='home'),
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    path('register/', views.register_view, name='register'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('verify_otp/', views.verify_otp, name='verify_otp'),
    path('reset-password/', views.reset_password, name='reset_password'),
    path('checkout/', views.cart_to_order, name='cart_to_order'),

    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('order/<int:product_id>/', views.order_product, name='order_product'),
    path('order_track/', views.order_tracking, name='order_track'),
    path('track-order/', views.track_order, name='track_order'),
    path('order/detail/<int:order_id>/', views.order_detail, name='order_detail'),
    path('user/orders/', views.user_orders, name='user_orders'),
    # Add to cart, only accessible if logged in
    path('product/<int:product_id>/add-to-cart/', views.add_to_cart, name='add_to_cart'),
    # Cart view, only accessible if logged in
    path('cart/', views.view_cart, name='view_cart'),
    # Remove item from cart, only accessible if logged in
    path('cart/remove/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    # Update quantity in cart, only accessible if logged in
    path('terms', views.terms, name='terms'),
    path('privacy/', views.privacy, name='privacy'),
    path('contact/', views.contact, name='contact'),
    path('search/', views.search_products, name='search_products'),
    path('cart/update/<int:product_id>/', views.update_quantity, name='update_quantity')

]
