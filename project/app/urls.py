from django.urls import path
from . import views

urlpatterns = [
    path('admin-home/', views.admin_home, name='admin_home'),
    path('', views.home, name='home'),
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('order/<int:product_id>/', views.order_product, name='order_product'),
    path('order/detail/<int:order_id>/', views.order_detail, name='order_detail'),
    path('user/orders/', views.user_orders, name='user_orders'),
    # Add to cart, only accessible if logged in
    path('product/<int:product_id>/add-to-cart/', views.add_to_cart, name='add_to_cart'),
    # Cart view, only accessible if logged in
    path('cart/', views.view_cart, name='view_cart'),
    # Remove item from cart, only accessible if logged in
    path('cart/remove/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    # Update quantity in cart, only accessible if logged in
    path('cart/update/<int:product_id>/<int:quantity>/', views.update_quantity, name='update_quantity'),
    path('terms', views.terms, name='terms'),
    path('privacy/', views.privacy, name='privacy'),
    path('contact/', views.contact, name='contact'),
    path('search/', views.search_products, name='search_products'),
    path('cart/update/<int:product_id>/<int:quantity>/', views.update_quantity, name='update_quantity'),

]
