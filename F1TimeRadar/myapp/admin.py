from django.contrib import admin
from .models import Time

# Register your models here.
# class TimeAdmin(admin.ModelAdmin):
#   list_display = ('master_time', 'master_delay')

admin.site.register(Time)