from django.db import models
from datetime import datetime

# Create your models here.
class Time(models.Model):
  master_time = models.DateTimeField(default=datetime.now())
  master_delay = models.DateTimeField()

