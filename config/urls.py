"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from accounts import views as accounts
from study import pages, submissions
from study.access import StudyLoginView
from study.views import dashboard, presentation, presentation_live, presentation_pptx, slideshow

admin.site.site_header = 'DIMENSION Study administration'
admin.site.site_title = 'DIMENSION admin'
admin.site.index_title = 'Data management'

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('clinics/', pages.clinics, name='clinics'),
    path('study-periods/', pages.periods, name='periods'),
    path('study-periods/add/', pages.period_edit, name='period-add'),
    path('study-periods/<int:number>/edit/', pages.period_edit, name='period-edit'),
    path('submissions/', submissions.submissions, name='submissions'),
    path('submissions/<int:pk>/', submissions.submission_detail, name='submission'),
    path('users/', pages.users, name='users'),
    path('users/add/', pages.user_edit, name='user-add'),
    path('users/<int:pk>/edit/', pages.user_edit, name='user-edit'),
    path('users/<int:pk>/password/', pages.user_password, name='user-password'),
    path('users/<int:pk>/<str:action>/', pages.user_status, name='user-status'),
    path('profile/', accounts.profile, name='profile'),
    path('profile/phone/send/', accounts.phone_send, name='phone-send'),
    path('profile/phone/verify/', accounts.phone_verify, name='phone-verify'),
    path('activate/<uidb64>/<token>/', accounts.activate, name='activate'),
    path('password/forgot/', accounts.PasswordResetView.as_view(), name='password-reset'),
    path('password/forgot/sent/', accounts.PasswordResetDoneView.as_view(), name='password-reset-done'),
    path('password/reset/<uidb64>/<token>/', accounts.PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('password/reset/done/', accounts.PasswordResetCompleteView.as_view(), name='password-reset-complete'),
    path('password/', pages.password_change, name='password-change'),
    path('presentation/', presentation, name='presentation'),
    path('presentation/live/', presentation_live, name='presentation-live'),
    path('presentation/live/download.pptx', presentation_pptx, name='presentation-pptx'),
    path('presentation/<slug:key>/', slideshow, name='slideshow'),
    path('login/', StudyLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('resources/', include('resources.urls')),
    path('admin/', admin.site.urls),
]
