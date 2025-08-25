from django.urls import path
from . import views

urlpatterns = [
    path('', views.chatbot_view, name='chatbot'),
    path('api/chat/', views.chat_api, name='chat_api'),
    path('api/upload-text/', views.upload_text_api, name='upload_text'),
    path('api/upload-file/', views.upload_file_api, name='upload_file'),
]