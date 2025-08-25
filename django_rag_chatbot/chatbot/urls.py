from django.urls import path
from . import views

urlpatterns = [
    path('', views.chatbot_view, name='chatbot'),
    path('api/chat/', views.chat_api, name='chat_api'),  # API 엔드포인트 추가
]