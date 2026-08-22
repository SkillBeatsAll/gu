from django.urls import path
from . import views
from .utils import cache_except_staff
from django.views.decorators.cache import cache_page
from . import  settings

urlpatterns = [
    path('donations/', views.page, name='donation.page'),
    path('payfast/', views.payment_view, name='make_payment'),
    path('donations/payment-success/', views.payment_success, name='payment_success'),
    path('donations/payment-cancel/', views.payment_cancel, name='payment_cancel'),
    path('donations/payment-notify/', views.payfast_ipn, name='payment_notify'),
    path('donations/donor-access/', views.donor_access_view, name='donor_access'),
    path('donations/donor-dashboard/<str:token>/', views.donor_dashboard_view, name='donor_dashboard'),
    path('donations/cancel-subscription/<str:token>/', views.cancel_subscription, name='cancel_subscription'),
    path('donations/donor-logout/', views.donor_dashboard_logout, name='donor_dashboard_logout'),

    # s18a tax certificates - donor facing (tokenised, no login)
    path('donations/certificate/request/<str:token>/',
         views.certificate_request_view, name='certificate_request'),
    path('donations/certificate/<int:pk>/pdf/<str:token>/',
         views.donor_certificate_pdf, name='certificate_pdf'),

    # s18a tax certificates - staff (login + permission required)
    path('donations/certificates/', views.staff_certificate_list,
         name='s18a.staff.list'),
    path('donations/certificates/new/', views.staff_certificate_create,
         name='s18a.staff.create'),
    path('donations/certificates/export.csv', views.staff_certificate_csv,
         name='s18a.staff.csv'),
    path('donations/certificates/<int:pk>/', views.staff_certificate_detail,
         name='s18a.staff.detail'),
    path('donations/certificates/<int:pk>/pdf/', views.staff_certificate_pdf,
         name='s18a.staff.pdf'),
    path('donations/certificates/<int:pk>/approve/',
         views.staff_certificate_approve, name='s18a.staff.approve'),
    path('donations/certificates/<int:pk>/reject/',
         views.staff_certificate_reject, name='s18a.staff.reject'),
    path('donations/certificates/<int:pk>/email/',
         views.staff_certificate_email, name='s18a.staff.email'),

]
