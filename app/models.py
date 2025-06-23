from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone



class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    offerprice=models.DecimalField(max_digits=10,decimal_places=2)
    stock = models.IntegerField()
    image = models.ImageField(upload_to='products/')
    category = models.CharField(max_length=100)
    additional_image1 = models.ImageField(upload_to='products/', blank=True, null=True)
    additional_image2 = models.ImageField(upload_to='products/', blank=True, null=True)
    additional_image3 = models.ImageField(upload_to='products/', blank=True, null=True)
    rating = models.FloatField(default=0)
    vector_data = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class users(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    vector_data = models.TextField(null=True)
    
    def _str_(self):
        return self.user.username 

class ViewHistory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    user = models.ForeignKey(users, on_delete=models.CASCADE)
    
class SearchHistory(models.Model):
    query = models.CharField(max_length=255)
    user = models.ForeignKey(users, on_delete=models.CASCADE)

class reviews(models.Model):
    rating = models.IntegerField()
    description = models.TextField()
    uname = models.ForeignKey(users, on_delete=models.CASCADE)
    pname = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews_set')



class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cart for {self.user.username}"

    def get_total_price(self):
        return sum(item.get_total_price() for item in self.items.all())

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} of {self.product.name}"

    def get_total_price(self):
        return self.product.price * self.quantity
    

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def _str_(self):
        return f"Profile of {self.user.username}"

    @classmethod
    def get_or_create_profile(cls, user):
        profile, created = cls.objects.get_or_create(user=user)
        return profile

class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=225)
    address = models.TextField()
    pincode = models.CharField(max_length=6)
    phone = models.CharField(max_length=12)
    is_default = models.BooleanField(default=False)

    def _str_(self):
        return f"{self.name} - {self.address[:30]}"
    

from django.db import models
from django.contrib.auth.models import User

class Order(models.Model):
    STATUS_CHOICES = [
        ('Ordered', 'Ordered'),
        ('Confirmed', 'Confirmed'),
        ('Packed', 'Packed'),
        ('Shipped', 'Shipped'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
        ('Returned', 'Returned'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ordered_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    pincode = models.CharField(max_length=10)
    address = models.TextField()

    # FIX: use choices and set default from the choices
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Ordered')

    def __str__(self):
        return f"Order #{self.id} by {self.user.username}"

    def get_total_price(self):
        return sum(item.get_total_price() for item in self.items.all())


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey('Product', on_delete=models.CASCADE)  # make sure Product model exists
    quantity = models.IntegerField()

    def __str__(self):
        return f"{self.quantity} of {self.product.name}"

    def get_total_price(self):
        return self.product.price * self.quantity

    

class UserExtension(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    vector_data = models.TextField(null=True)

    def __str__(self):
        return self.user.username


#wishlist
# class Wishlist(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     product = models.ForeignKey(Product, on_delete=models.CASCADE)