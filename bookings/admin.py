from django.contrib import admin
from .models import Resource, Booking

@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'price', 'source_url')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'resource', 'checkin_date', 'checkout_date', 'total_price', 'status')
    list_filter = ('status', 'checkin_date', 'checkout_date')
    search_fields = ('user__email', 'resource_title')
