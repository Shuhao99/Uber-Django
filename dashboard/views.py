from django.shortcuts import get_object_or_404, redirect, render, render
from .forms import RegisterForm, ProfileForm, RideRequestForm
from .models import User, Profile, Ride, Group
# from django.urls import reverse
from django.utils import timezone
from datetime import datetime
from django.views import generic
from django.contrib.auth.models import User
from django.http import Http404
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from .backend import VehicleInfo
#TODO: Success 页面, edit删除ride所有共享成员
#TODO: 检查非法输入

def require_ride(request):
    if not request.session.get('is_login', None):
        return redirect('/login')

    if request.method == "POST":
        form = RideRequestForm(request.POST)
        curr_user = get_object_or_404(User, id=request.session['user_id'])
        if form.is_valid():
            ride = form.save(commit=False)
            ride.owner = curr_user
            try:
                group = Group.objects.get(user=curr_user, groupNum=ride.passengerNum)
            except Group.DoesNotExist:
                group = Group(user=curr_user, groupNum=ride.passengerNum)
                group.save()
            ride.save()
            ride.shared_by_user.add(group)
            messages.success(request, 'Request successfully.')
            return redirect("/")
        else:
            print("form not valid:"+str(form.errors))
    else:
        form = RideRequestForm()

    context = {'form': form}
    return render(request, 'dashboard/require_ride.html', context)

def started_ride(request):
    if not request.session.get('is_login', None):
        return redirect('/login')
    else:
        curr_user = get_object_or_404(User, id = request.session['user_id'])
        open_ride = Ride.objects.filter(
            confirmed=False,
            completed=False,
            owner = curr_user
        ).order_by("arrive_time")
        confirmed_ride = Ride.objects.filter(
            confirmed=True,
            completed=False,
            owner = curr_user
        ).order_by("arrive_time")
        completed_ride = Ride.objects.filter(
            confirmed=True,
            completed=True,
            owner = curr_user
        ).order_by("arrive_time")
        context = {"open_rides": open_ride,
                   "confirmed_rides": confirmed_ride,
                   "completed_rides": completed_ride,
                   "user":curr_user
                   }
        return render(request, 'dashboard/started_ride.html', context)

def register(request):
    if request.method == 'POST':
        user_form = RegisterForm(request.POST)
        profile_form = ProfileForm(request.POST)
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()
            profile = profile_form.save(commit=False)
            profile.user = user
            profile.save()
            return redirect('/login')
    else:
        user_form = RegisterForm()
        profile_form = ProfileForm()
    return render(request, 'registration/register.html', context={'form': user_form,
                                                                  'profile_form': profile_form})

def ride_cancel(request, pk):
    if not request.session.get('is_login', None):
        return redirect('/login')
    ride = get_object_or_404(Ride, pk = pk)
    if not ride.owner == request.user:
        raise Http404
    ride.delete()

    return redirect('/')

def ride_detail(request, pk):
    if not request.session.get('is_login', None):
        return redirect('/login')
    gender = ['female', 'male', 'NG']
    vehicle_info = ['Sedan', 'SUV', 'Coupe', 'Hatchback', 'Mini van']
    ride = get_object_or_404(Ride, pk=pk)
    curr_user = get_object_or_404(User, id=request.session['user_id'])
    if curr_user != ride.owner:
        raise Http404
    # status
    if ride.completed:
        status = "Completed"
    elif ride.confirmed:
        status = "Confirmed"
    else:
        status = "Open"
    # driver
    if ride.vehicle:
        driver = ride.vehicle.owner.first_name + ride.vehicle.owner.last_name
        plate = ride.vehicle.plateNumber
        driver_phone = ride.vehicle.owner.profile.mobile
        driver_email = ride.vehicle.owner.email
    else:
        driver = "Not assigned yet"
        plate = "Unknown"
        driver_phone = "Unknown"
        driver_email = "Unknown"

    shared_by = ride.shared_by_user.exclude(
        user=curr_user,
    )
    context = {
        "dest" : ride.dest,
        "arrive_time" : ride.arrive_time,
        "v_type": vehicle_info[ride.vehicleType],
        "shared_by": shared_by,
        "owner" : ride.owner,
        "status" : status,
        "driver" : driver,
        "plate" : plate,
        "driver_phone": driver_phone,
        "driver_Email": driver_email,
        "gender": gender,
        "curr_user": curr_user,
        "ride": ride
    }
    return render(request, 'dashboard/ride_detail.html',context)

class EditRide(SuccessMessageMixin, generic.UpdateView):
    model = Ride
    form_class = RideRequestForm
    template_name = 'dashboard/edit_ride.html'
    # redirect to this url after success
    success_url = "/"
    success_message = "Changes successfully saved."

    # Check if the user is qualified for edit
    def get_object(self, *args, **kwargs):
        if not self.request.session.get('is_login', None):
            return redirect('/login')
        ride = self.model.objects.get_object_or_404(pk=self.kwargs['pk'])
        if not ride.owner == self.request.user:
            raise Http404
        return ride

def search_ride(request):
    if not request.session.get('is_login', None):
        return redirect('/login')
    if request.method == 'POST':
        addr = request.POST.get('address')
        start = request.POST.get('start')
        end = request.POST.get('end')
        number = int(request.POST.get('PassengerNum'))

        #format time
        start = datetime.strptime(start, "%Y-%m-%dT%H:%M").astimezone(timezone.utc)
        end = datetime.strptime(end, "%Y-%m-%dT%H:%M").astimezone(timezone.utc)

        rides = Ride.objects.filter(
            completed=False,
            confirmed=False,
            if_share=True,
            arrive_time__gte=start,
            arrive_time__lte=end
        ).exclude(owner=request.user).order_by("arrive_time")
        addr = str(addr).lower().split()
        groups = Group.objects.filter(user=request.user)
        for group in groups:
            rides = [ride for ride in rides if group not in ride.shared_by_user.all()]
        for word in addr:
            rides = [ride for ride in rides if word in str(ride.dest).lower()]
        rides = [ride for ride in rides if \
                 number + ride.get_passenger_num() + 1 <= \
                 ride.get_capacity()]
        message = "{number} orders found: ".format(number = str(len(rides)))
    else:
        rides = []
        message = "Results will be displayed below. "

    context = {
        "rides" : rides,
        "msg" : message,
    }
    return render(request, 'dashboard/search_rides.html', context=context)