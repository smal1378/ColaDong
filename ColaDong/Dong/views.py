from django.shortcuts import render
from django.views import View


# Create your views here.
class LoginView(View):
    def post(self, request, *args, **kwargs):
        pass

    def get(self, request):
        return render(request,'login.html')


class BalancesView(View):
    def get(self, request):
        return render(request,'balances.html')

class RecordsView(View):
    def get(self, request):
        return render(request,'records.html')
