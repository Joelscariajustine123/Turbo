from account.models import CustomUser
from django.shortcuts import get_object_or_404, redirect,render
from django.contrib import messages
from account.forms import EditRiderForm
from django.contrib.auth.decorators import login_required   
# Create your views here.
@login_required
def home(request):
    return render(request,'adminpages/home.html')
@login_required
def dashboard(request):
    return render(request,'adminpages/dashboard.html')
@login_required
def booking(request):
    return render(request,'adminpages/booking.html')
@login_required
def payment(request):
    return render(request,'adminpages/payment.html')
@login_required
def report(request):
    return render(request,'adminpages/report.html')
@login_required
def rider(request):
    riders = CustomUser.objects.filter(role='rider')
    return render(request, 'adminpages/rider.html', {'riders': riders})

@login_required
def settings(request):
    user = request.user  # Get the currently logged-in user

    if request.method == 'POST':
        user.full_name = request.POST.get('name')
        user.email = request.POST.get('email')

        password = request.POST.get('password')
        if password:
            user.set_password(password)

        user.save()
        messages.success(request, "Account settings updated successfully.")
        return redirect('settings')  # Redirect to the same page

    return render(request, 'adminpages/settings.html', {
        'user': user
    })

@login_required
def delete_rider(request, rider_id):
    rider = get_object_or_404(CustomUser, id=rider_id, role='rider')
    if request.method == 'POST':
        rider.delete()
        messages.success(request, "Rider deleted successfully.")
    return redirect('rider')

@login_required
def edit_rider(request, rider_id):
    rider = get_object_or_404(CustomUser, id=rider_id, role='rider')
    if request.method == 'POST':
        form = EditRiderForm(request.POST, instance=rider)
        if form.is_valid():
            form.save()
            messages.success(request, "Rider updated successfully.")
            return redirect('adminpages:rider')
    else:
        form = EditRiderForm(instance=rider)
    return render(request, 'adminpages/edit_rider.html', {'form': form})