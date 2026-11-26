from django.urls import path

from . import views

app_name = 'resources'

urlpatterns = [
    path('', views.DocumentListView.as_view(), name='list'),
    path('upload/', views.DocumentCreateView.as_view(), name='create'),
    path('<int:pk>/', views.DocumentDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.DocumentUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.DocumentDeleteView.as_view(), name='delete'),
    path('<int:pk>/download/', views.DocumentFileView.as_view(), name='download'),
    path('<int:pk>/preview/', views.DocumentPreviewView.as_view(), name='preview'),
]
