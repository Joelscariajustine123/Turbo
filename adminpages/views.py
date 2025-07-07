from django.shortcuts import render

# Create your views here.
def home(request):
    return render(request,'adminpages/home.html')

def dashboard(request):
    return render(request,'adminpages/dashboard.html')

def booking(request):
    return render(request,'adminpages/booking.html')

def payment(request):
    return render(request,'adminpages/payment.html')

def report(request):
    return render(request,'adminpages/report.html')

def rider(request):
    return render(request,'adminpages/rider.html')

def settings(request):
    return render(request,'adminpages/settings.html')