from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

def chatbot_view(request):
    return render(request, 'chatbot/chatbot.html')

@csrf_exempt  # 개발용 - 나중에 CSRF 토큰 사용하는게 좋음
def chat_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            
            # 간단한 키워드 응답 로직
            bot_response = get_bot_response(user_message)
            
            return JsonResponse({
                'response': bot_response,
                'status': 'success'
            })
        except Exception as e:
            return JsonResponse({
                'response': '오류가 발생했습니다.',
                'status': 'error'
            })
    
    return JsonResponse({'status': 'error', 'message': 'POST 요청만 허용됩니다.'})

def get_bot_response(message):
    """간단한 키워드 기반 응답"""
    message = message.lower()
    
    if '안녕' in message or 'hello' in message:
        return "안녕하세요! 무엇을 도와드릴까요?"
    elif '이름' in message:
        return "저는 RAG 챗봇입니다!"
    elif '날씨' in message:
        return "죄송합니다. 아직 날씨 정보는 제공하지 않습니다."
    elif '시간' in message:
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return f"현재 시간은 {now}입니다."
    elif 'rag' in message:
        return "RAG는 Retrieval-Augmented Generation의 줄임말로, 문서 검색 기반 생성 AI입니다!"
    elif '도움' in message or 'help' in message:
        return "저는 문서 기반 질문에 답변할 수 있습니다. 궁금한 것을 물어보세요!"
    else:
        return f"'{message}'에 대해 더 구체적으로 알려주시면 도움을 드릴 수 있어요!"