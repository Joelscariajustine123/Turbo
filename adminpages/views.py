from django.shortcuts import render

# Create your views here.
def home(request):
    return render(request,'adminpages/home.html')