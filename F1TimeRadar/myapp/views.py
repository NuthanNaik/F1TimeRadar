from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from .models import Time
from myapp.utils.classes import SignalRClient
import threading, logging

def run_req():
  log = logging.getLogger()
  log.setLevel(logging.DEBUG)
  connect = SignalRClient(logger=log)
  connect.start()

# def data(request):
#   return JsonResponse({'time': Time.objects().all()})

# Create your views here.
def home(request):
  process_thread = threading.Thread(target=run_req, daemon=True)
  process_thread.start()
  return render(request, 'home.html')

def timings(request):
  return render(request, 'timings.html', {'time': Time.objects.all()})