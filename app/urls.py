from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from app import views

urlpatterns = [

    path('home/', views.home, name='home'),
    path('product/<int:id>/', views.product_detail, name='product_detail'),
    path('register/', views.register_view, name='register'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('verify_otp/', views.verify_otp, name='verify_otp'),
    path('reset-password/', views.reset_password, name='reset_password'),
    path('product/<int:id>/', views.product_detail, name='product'),
    path('products/', views.product_list, name='product_list'),
    path('search/', views.search_results, name='search_results'),
   

    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit-email/', views.edit_email, name='edit_email'),
    path('profile/edit-username/', views.edit_username, name='edit_username'),
    path('profile/add-address/', views.add_address, name='add_address'),
    path('profile/edit-address/<int:address_id>/', views.edit_address, name='edit_address'),
    path('profile/delete-address/<int:address_id>/', views.delete_address, name='delete_address'),
    path('recommendations/', views.recommendations, name='recommendations'),
   
    path('dashboard/', views.first_page, name='firstpage'),
    path('dashboard/bookings/', views.admin_bookings, name='admin_bookings'),
    path('dashboard/add-product/', views.add_product, name='add_product'),
    path('dashboard/edit/<int:id>/', views.edit_g, name='edit_g'),
    path('dashboard/delete/<int:id>/', views.delete_g, name='delete_g'),
    path('update-order-status/<int:order_id>/', views.update_order_status, name='update_order_status'),
    # path('order/<int:product_id>/', views.order_product, name='order_product'),
    path('user/orders/', views.user_orders, name='user_orders'),
    path('order/<int:order_id>/', views.order_detail_view, name='order_detail'),
    path('order-success/', views.order_success, name='order_success'),
    path('order_track/', views.order_tracking, name='order_track'),
    path('track-order/', views.track_order, name='track_order'),
    path('cancel-order/<int:order_id>/', views.cancel_order, name='cancel_order'),
    path('return-order/<int:order_id>/', views.return_order, name='return_order'),
    # path('order/detail/<int:order_id>/', views.order_detail, name='order_detail'),
  
    # Add to cart, only accessible if logged in
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/increment/<int:id>/', views.increment_cart, name='increment_cart'),
    path('cart/decrement/<int:id>/', views.decrement_cart, name='decrement_cart'),
    path('cart/delete/<int:id>/', views.delete_cart_item, name='delete_cart_item'),

    # Cart view, only accessible if logged in
    
    path('cart/', views.cart, name='cart'),
    # Remove item from cart, only accessible if logged in
    path('cart/remove/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    # Update quantity in cart, only accessible if logged in
    path('terms', views.terms, name='terms'),
    path('privacy/', views.privacy, name='privacy'),
    path('contact/', views.contact, name='contact'),
    path('search/', views.search_products, name='search_products'),
    path('update_quantity/<int:product_id>/', views.update_quantity, name='update_quantity'),
    path('checkout/', views.checkout, name='checkout'),
    path('process-checkout/', views.process_checkout, name='process_checkout'),
    path('buy-now/<int:product_id>/', views.buy_now, name='buy_now'),
    path('payment-successful/', views.payment_successful, name='payment_successful'),
    path('order-confirmation/<int:order_id>/', views.contact, name='order_confirmation'),
     path('user-list/', views.user_list, name='user_list'),
    path('user/<int:user_id>/', views.user_detail, name='user_detail'),
    path('user/<int:user_id>/delete/', views.delete_user, name='delete_user'),

]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)