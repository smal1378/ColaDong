from django.urls import path

from . import views

app_name = "dong"

urlpatterns = [
    path("balances/", views.BalancesView.as_view(), name="balances"),
    path("add-record/", views.AddRecordView.as_view(), name="add_record"),
    path("records/", views.RecordsView.as_view(), name="records"),
    path("records.csv", views.RecordsCsvView.as_view(), name="records_csv"),
    path("group-buy/", views.GroupBuyView.as_view(), name="group_buy"),
]
