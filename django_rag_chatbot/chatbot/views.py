from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
import json
import os
from .rag_engine import rag_engine
from .models import Document

def chatbot_view(request):
    # 저장된 문서 개수 정보
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
            user_message = data.get('message', '')
            
            # RAG 응답 시도
            if rag_engine.get_document_count() > 0:
                bot_response = rag_engine.get_rag_response(user_message)
            else:
                bot_response = get_simple_response(user_message)
            
            return JsonResponse({
                'response': bot_response,
                'status': 'success'
            })
        except Exception as e:
            return JsonResponse({
                'response': f'오류가 발생했습니다: {str(e)}',
                'status': 'error'
            })
    
    return JsonResponse({'status': 'error', 'message': 'POST 요청만 허용됩니다.'})

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
                'message': f'텍스트가 업로드되었습니다. ({chunk_count}개 청크 생성)',
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
                    'message': f'파일이 업로드되었습니다. {message}',
                    'document_count': rag_engine.get_document_count()
                })
            else:
                doc.delete()  # 실패시 DB에서 제거
                return JsonResponse({'status': 'error', 'message': message})
                
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

def get_simple_response(message):
    """문서가 없을 때의 간단한 응답"""
    message = message.lower()
    
    if '안녕' in message:
        return "안녕하세요! 문서를 업로드하면 더 정확한 답변을 드릴 수 있어요."
    elif '문서' in message or '업로드' in message:
        return "아래 업로드 섹션에서 텍스트나 파일을 업로드해주세요!"
    else:
        return "아직 업로드된 문서가 없습니다. 먼저 문서를 업로드한 후 질문해주세요."