from django.shortcuts import render
# Create your views here.
def homepage(request):
    return render(request,'driverpages/homepage.html')

def earnings(request):
    return render(request,'driverpages/earning.html')

def profile(request):
    return render(request,'driverpages/profile.html')

def setting(request):
    return render(request,'driverpages/settings.html')