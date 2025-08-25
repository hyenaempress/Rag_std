
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
import json
import os
from .rag_engine import rag_engine
from .models import Document

def chatbot_view(request):
    doc_count = rag_engine.get_document_count()
    context = {
        'document_count': doc_count
    }
    return render(request, 'chatbot/chatbot.html', context)

@csrf_exempt
def chat_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '').strip()
            
            # 먼저 일반적인 대화 응답 시도
            general_response = get_general_response(user_message)
            
            if general_response:
                # 일반 대화 응답이 있으면 그것을 반환
                response = general_response
            elif rag_engine.get_document_count() > 0:
                # 문서가 있으면 RAG 검색 시도
                rag_response = rag_engine.get_rag_response(user_message)
                if "관련된 문서를 찾을 수 없습니다" in rag_response:
                    # RAG에서도 답을 못 찾으면 친근한 응답
                    response = f"'{user_message}'에 대해 업로드된 문서에서 관련 내용을 찾지 못했어요. 다른 질문을 해보시거나 관련 문서를 추가로 업로드해주세요!"
                else:
                    response = rag_response
            else:
                # 문서도 없고 일반 응답도 없으면
                response = get_no_document_response(user_message)
            
            return JsonResponse({
                'response': response,
                'status': 'success'
            })
            
        except Exception as e:
            return JsonResponse({
                'response': f'오류가 발생했습니다: {str(e)}',
                'status': 'error'
            })
    
    return JsonResponse({'status': 'error', 'message': 'POST 요청만 허용됩니다.'})

def get_general_response(message):
    """일반적인 대화나 기본 질문에 대한 응답"""
    message_lower = message.lower()
    
    # 인사말
    if any(word in message_lower for word in ['안녕', 'hello', 'hi', '반가워']):
        return "안녕하세요! 저는 RAG 챗봇입니다. 문서를 업로드하면 그 내용에 대해 질문할 수 있어요! 😊"
    
    # 자기소개 관련
    if any(word in message_lower for word in ['누구', '이름', 'name', '소개']):
        return "저는 문서 기반 질답을 도와주는 RAG(Retrieval-Augmented Generation) 챗봇입니다. 문서를 업로드하시면 그 내용을 바탕으로 정확한 답변을 드려요!"
    
    # 기능 설명
    if any(word in message_lower for word in ['기능', '뭐할', '뭐해', '도움', 'help']):
        doc_count = rag_engine.get_document_count()
        return f"""제가 할 수 있는 것들:
📚 문서 업로드 (텍스트, PDF, DOCX)
🔍 업로드된 문서에서 정보 검색
💬 문서 내용 기반 질의응답

현재 {doc_count}개의 문서가 업로드되어 있어요. 왼쪽에서 더 많은 문서를 추가할 수 있습니다!"""
    
    # 일반 대화
    if any(word in message_lower for word in ['대화', '채팅', '얘기']):
        return "네, 기본적인 대화는 가능해요! 하지만 제 주특기는 업로드하신 문서의 내용을 분석해서 정확한 답변을 드리는 거예요. 문서를 업로드해보시겠어요?"
    
    # ORM 관련 (기술 질문 예시)
    if 'orm' in message_lower:
        return """ORM(Object-Relational Mapping)은 객체와 관계형 데이터베이스 간의 매핑을 도와주는 기술입니다.

🔍 Django ORM의 특징:
• Python 객체로 데이터베이스 조작
• SQL을 직접 작성하지 않아도 됨
• 데이터베이스 독립적
• 보안 (SQL Injection 방지)

더 자세한 ORM 관련 정보가 필요하시면, 관련 문서를 업로드해주세요!"""
    
    # 시간 관련
    if any(word in message_lower for word in ['시간', 'time', '몇시']):
        from datetime import datetime
        now = datetime.now().strftime('%Y년 %m월 %d일 %H시 %M분')
        return f"현재 시간은 {now}입니다. ⏰"
    
    # 감사 인사
    if any(word in message_lower for word in ['고마워', '감사', 'thank']):
        return "천만에요! 더 궁금한 것이 있으시면 언제든 물어보세요. 😊"
    
    # 기타 간단한 응답들
    simple_responses = {
        ('좋아', '좋다', 'good'): "좋네요! 다른 궁금한 것이 있으시면 언제든 물어보세요!",
        ('나빠', '안좋아', 'bad'): "아, 그렇군요. 더 도움이 될 만한 것이 있을까요?",
        ('재미있어', '흥미로워'): "그렇게 생각해주셔서 기뻐요! 😊",
        ('어려워', '복잡해'): "이해하기 어려우시다면 더 자세히 설명해드릴게요. 구체적으로 어떤 부분이 어려우신가요?"
    }
    
    for keywords, response in simple_responses.items():
        if any(word in message_lower for word in keywords):
            return response
    
    return None  # 일반 응답이 없음

def get_no_document_response(message):
    """문서가 없을 때의 응답"""
    return """아직 업로드된 문서가 없어요. 📝

다음 단계를 따라해보세요:
1. 왼쪽 '문서 업로드' 섹션에서 텍스트를 입력하거나 파일을 업로드
2. 업로드가 완료되면 문서 내용에 대해 질문해보세요!

지원하는 파일 형식: PDF, TXT, DOCX"""

# 파일 업로드 관련 함수들은 기존과 동일...
@csrf_exempt
def upload_text_api(request):
    """텍스트 직접 업로드"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            text = data.get('text', '')
            title = data.get('title', '직접 입력 문서')
            
            if not text.strip():
                return JsonResponse({'status': 'error', 'message': '텍스트를 입력해주세요.'})
            
            # 데이터베이스에 저장
            doc = Document.objects.create(
                title=title,
                text_content=text,
                processed=False
            )
            
            # RAG 엔진에 추가
            chunk_count = rag_engine.add_text_document(text, title)
            
            # 처리 완료 표시
            doc.processed = True
            doc.chunk_count = chunk_count
            doc.save()
            
            return JsonResponse({
                'status': 'success', 
                'message': f'✅ 텍스트가 업로드되었습니다! ({chunk_count}개 청크 생성)',
                'document_count': rag_engine.get_document_count()
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

@csrf_exempt
def upload_file_api(request):
    """파일 업로드"""
    if request.method == 'POST' and request.FILES.get('file'):
        try:
            file = request.FILES['file']
            
            # 파일 크기 체크 (예: 10MB 제한)
            if file.size > 10 * 1024 * 1024:
                return JsonResponse({'status': 'error', 'message': '파일 크기는 10MB 이하여야 합니다.'})
            
            # 파일 확장자 체크
            allowed_extensions = ['.txt', '.pdf', '.docx']
            file_extension = os.path.splitext(file.name)[1].lower()
            if file_extension not in allowed_extensions:
                return JsonResponse({'status': 'error', 'message': 'TXT, PDF, DOCX 파일만 업로드 가능합니다.'})
            
            # 파일 저장
            file_path = default_storage.save(f'documents/{file.name}', file)
            full_path = default_storage.path(file_path)
            
            # 데이터베이스에 저장
            doc = Document.objects.create(
                title=file.name,
                file=file_path,
                processed=False
            )
            
            # RAG 엔진에 추가
            success, message = rag_engine.add_file_document(full_path)
            
            if success:
                doc.processed = True
                doc.save()
                return JsonResponse({
                    'status': 'success', 
                    'message': f'✅ 파일이 업로드되었습니다! {message}',
                    'document_count': rag_engine.get_document_count()
                })
            else:
                doc.delete()  # 실패시 DB에서 제거
                return JsonResponse({'status': 'error', 'message': message})
                
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'파일 업로드 중 오류: {str(e)}'})