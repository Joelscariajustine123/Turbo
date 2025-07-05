from django.shortcuts import render

# Create your views here.
def first(request):
    return render(request,'account/usertype.html')

def riderlogin(request):
    return render(request,'account/riderlogin.html')

def dirverlogin(request):
    return render(request,'account/driverlogin.html')

def adminlogin(request):
    return render(request,'account/adminlogin.html')

def ridersignup(request):
    return render(request,'account/ridersignup.html')

def driversignup(request):
    return render(request,'account/driversignup.html')

def adminsignup(request):
    return render(request,'account/adminsignup.html')