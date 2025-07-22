from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request,'riderpages/index.html')
def safety(request):
    return render(request,'riderpages/Safety.html')
def outstation(request):
    return render(request,'riderpages/outstation.html')
def contact(request):
    return render(request,'riderpages/contact.html')
def services(request):
    return render(request,'riderpages/services.html')