from django.contrib import admin
from .models import Product

class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'offerprice', 'stock']

admin.site.register(Product, ProductAdmin)


