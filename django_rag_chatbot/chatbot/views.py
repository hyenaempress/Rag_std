from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
import json
import os
import logging
from datetime import datetime
from .rag_engine import rag_engine
from .models import Document

# 로거 설정
logger = logging.getLogger(__name__)

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
            
            if not user_message:
                return JsonResponse({
                    'response': '메시지를 입력해주세요.',
                    'status': 'error'
                })
            
            # 응답 생성 로직
            response = generate_response(user_message)
            
            # 로깅
            logger.info(f"사용자 질문: {user_message[:50]}... | 응답 길이: {len(response)}")
            
            return JsonResponse({
                'response': response,
                'status': 'success'
            })
            
        except json.JSONDecodeError:
            logger.error("Invalid JSON in chat request")
            return JsonResponse({
                'response': '잘못된 요청 형식입니다.',
                'status': 'error'
            })
        except Exception as e:
            logger.error(f"Chat API error: {str(e)}")
            return JsonResponse({
                'response': '죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
                'status': 'error'
            })
    
    return JsonResponse({'status': 'error', 'message': 'POST 요청만 허용됩니다.'})

def generate_response(user_message):
    """통합 응답 생성 함수"""
    
    # 1. 먼저 일반적인 대화 응답 확인
    general_response = get_general_response(user_message)
    if general_response:
        return general_response
    
    # 2. 문서가 있으면 RAG 검색 시도
    if rag_engine.get_document_count() > 0:
        rag_response = rag_engine.get_rag_response(user_message)
        
        # RAG 응답 개선
        if "관련된 문서를 찾을 수 없습니다" in rag_response:
            return format_no_result_response(user_message)
        else:
            return format_rag_response(user_message, rag_response)
    
    # 3. 문서가 없는 경우
    return get_no_document_response(user_message)

def format_rag_response(query, raw_response):
    """RAG 응답을 더 읽기 좋게 포맷팅"""
    try:
        # 원본 응답에서 "검색된 관련 내용:" 부분 제거
        content = raw_response.replace("검색된 관련 내용:", "").strip()
        
        # 너무 긴 내용은 줄바꿈으로 분할
        if len(content) > 500:
            # 문장 단위로 분할 시도
            sentences = content.replace('. ', '.\n').split('\n')
            formatted_sentences = []
            
            for sentence in sentences[:3]:  # 처음 3문장만
                if sentence.strip():
                    formatted_sentences.append(f"• {sentence.strip()}")
            
            formatted_content = '\n'.join(formatted_sentences)
            
            return f"""💡 **"{query}"**에 대한 답변:

{formatted_content}

📚 더 자세한 내용이 필요하시면 구체적인 질문을 해주세요!"""
        
        return f"""💡 **"{query}"**에 대한 답변:

{content}"""
        
    except Exception as e:
        logger.error(f"RAG response formatting error: {str(e)}")
        return raw_response

def format_no_result_response(query):
    """검색 결과가 없을 때의 응답"""
    doc_count = rag_engine.get_document_count()
    
    return f"""🤔 **"{query}"**에 대한 정보를 찾지 못했어요.

📝 현재 {doc_count}개의 문서가 업로드되어 있습니다.

💡 다음을 시도해보세요:
• 다른 키워드로 질문해보기
• 관련 문서를 추가로 업로드하기
• 더 구체적인 질문하기

예시: "Django ORM이란?" → "Django에서 데이터베이스 모델 정의하는 방법은?"
"""

def get_general_response(message):
    """일반적인 대화나 기본 질문에 대한 응답 (개선된 버전)"""
    message_lower = message.lower()
    
    # 인사말 - 더 자연스럽게
    greetings = ['안녕', 'hello', 'hi', '반가워', 'hey', '좋은아침', '좋은오후']
    if any(word in message_lower for word in greetings):
        return "안녕하세요! 👋 저는 RAG 챗봇입니다.\n문서를 업로드하면 그 내용에 대해 질문할 수 있어요!"
    
    # 자기소개 관련
    identity_keywords = ['누구', '이름', 'name', '소개', '너는', '당신은']
    if any(word in message_lower for word in identity_keywords):
        return """🤖 **저는 RAG 챗봇입니다!**

**RAG**란? Retrieval-Augmented Generation
• 문서에서 관련 정보를 검색
• 찾은 정보를 바탕으로 정확한 답변 생성

**제가 도와드릴 수 있는 것:**
📚 문서 분석 및 요약
🔍 정보 검색 및 질의응답
💡 내용 기반 추천"""
    
    # 기능 설명
    function_keywords = ['기능', '뭐할', '뭐해', '도움', 'help', '사용법']
    if any(word in message_lower for word in function_keywords):
        doc_count = rag_engine.get_document_count()
        return f"""🛠️ **제가 할 수 있는 것들:**

📤 **문서 업로드**
• 텍스트 직접 입력
• PDF, TXT, DOCX 파일 업로드

🔍 **스마트 검색**
• 키워드 기반 문서 검색
• 관련 내용 자동 추출

💬 **질의응답**
• 문서 내용 기반 답변
• 요약 및 설명 제공

📊 **현재 상태:** {doc_count}개 문서 업로드됨
➡️ 왼쪽에서 더 많은 문서를 추가해보세요!"""
    
    # RAG 관련 질문
    if 'rag' in message_lower:
        return """🔍 **RAG (Retrieval-Augmented Generation)**

**개념:**
• Retrieval: 관련 문서/정보 검색
• Augmented: 검색된 정보로 강화
• Generation: 정확한 답변 생성

**장점:**
✅ 최신 정보 활용
✅ 환각(Hallucination) 감소  
✅ 출처 기반 신뢰성
✅ 도메인 특화 가능

**동작 과정:**
1. 문서를 작은 청크로 분할
2. 질문과 관련된 청크 검색
3. 검색된 내용을 바탕으로 답변 생성"""
    
    # 시간 관련
    time_keywords = ['시간', 'time', '몇시', '날짜', 'date']
    if any(word in message_lower for word in time_keywords):
        now = datetime.now()
        formatted_time = now.strftime('%Y년 %m월 %d일 (%A) %H시 %M분')
        return f"⏰ **현재 시간:** {formatted_time}"
    
    # 감사 인사
    thanks_keywords = ['고마워', '감사', 'thank', '고맙다', '땡큐']
    if any(word in message_lower for word in thanks_keywords):
        return "😊 천만에요! 더 궁금한 것이 있으시면 언제든 물어보세요."
    
    # 기술 관련 질문들
    tech_responses = {
        'django': """🐍 **Django는 Python 웹 프레임워크입니다**

**주요 특징:**
• MTV 패턴 (Model-Template-View)
• ORM (Object-Relational Mapping)  
• Admin 인터페이스 자동 생성
• 보안 기능 내장

Django 관련 문서를 업로드하시면 더 자세한 답변을 드릴 수 있어요!""",

        'python': """🐍 **Python**

**특징:**
• 읽기 쉬운 문법
• 풍부한 라이브러리
• 다양한 용도 (웹, AI, 데이터분석 등)
• 활발한 커뮤니티

Python 관련 문서를 업로드해보세요!""",
        
        'ai': """🤖 **AI (Artificial Intelligence)**

**분야:**
• 머신러닝 (Machine Learning)
• 딥러닝 (Deep Learning)
• 자연어처리 (NLP)
• 컴퓨터 비전 (Computer Vision)

AI 관련 자료를 업로드하시면 더 전문적인 답변을 드려요!"""
    }
    
    for keyword, response in tech_responses.items():
        if keyword in message_lower:
            return response
    
    return None  # 일반 응답이 없음

def get_no_document_response(message):
    """문서가 없을 때의 응답 (개선된 버전)"""
    return f"""📝 **문서를 업로드해주세요!**

**"{message}"**에 대해 답변드리려면 관련 문서가 필요해요.

🚀 **빠른 시작 가이드:**
1️⃣ 왼쪽 '📁 문서 업로드' 클릭
2️⃣ 텍스트 입력 또는 파일 선택  
3️⃣ 업로드 후 질문하기

📋 **지원 파일:** PDF, TXT, DOCX
💡 **팁:** 구체적이고 상세한 문서일수록 더 정확한 답변을 받을 수 있어요!"""

# 파일 업로드 함수들 (보안 강화)
@csrf_exempt  
def upload_text_api(request):
    """텍스트 직접 업로드 (보안 강화)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            text = data.get('text', '').strip()
            title = data.get('title', '').strip() or '직접 입력 문서'
            
            # 입력 검증
            if not text:
                return JsonResponse({'status': 'error', 'message': '텍스트를 입력해주세요.'})
            
            if len(text) < 10:
                return JsonResponse({'status': 'error', 'message': '최소 10자 이상 입력해주세요.'})
            
            if len(text) > 100000:  # 100KB 제한
                return JsonResponse({'status': 'error', 'message': '텍스트가 너무 깁니다. (최대 100,000자)'})
            
            # 제목 길이 제한
            if len(title) > 200:
                title = title[:200] + "..."
            
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
            
            logger.info(f"Text document uploaded: {title} ({chunk_count} chunks)")
            
            return JsonResponse({
                'status': 'success', 
                'message': f'✅ "{title}" 업로드 완료! ({chunk_count}개 청크)',
                'document_count': rag_engine.get_document_count()
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': '잘못된 요청 형식입니다.'})
        except Exception as e:
            logger.error(f"Text upload error: {str(e)}")
            return JsonResponse({'status': 'error', 'message': '업로드 중 오류가 발생했습니다.'})

@csrf_exempt
def upload_file_api(request):
    """파일 업로드 (보안 강화)"""
    if request.method == 'POST' and request.FILES.get('file'):
        try:
            file = request.FILES['file']
            
            # 파일 크기 체크 (10MB 제한)
            max_size = 10 * 1024 * 1024
            if file.size > max_size:
                return JsonResponse({
                    'status': 'error', 
                    'message': f'파일 크기는 {max_size//1024//1024}MB 이하여야 합니다.'
                })
            
            # 파일 확장자 및 MIME 타입 검증
            allowed_extensions = {'.txt', '.pdf', '.docx'}
            allowed_mime_types = {
                'text/plain',
                'application/pdf', 
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            }
            
            file_extension = os.path.splitext(file.name)[1].lower()
            mime_type = file.content_type
            
            if file_extension not in allowed_extensions:
                return JsonResponse({
                    'status': 'error', 
                    'message': 'TXT, PDF, DOCX 파일만 업로드 가능합니다.'
                })
            
            if mime_type not in allowed_mime_types:
                return JsonResponse({
                    'status': 'error', 
                    'message': f'지원하지 않는 파일 형식입니다. ({mime_type})'
                })
            
            # 파일명 안전하게 처리
            safe_filename = os.path.basename(file.name)
            if len(safe_filename) > 255:
                name, ext = os.path.splitext(safe_filename)
                safe_filename = name[:250] + ext
            
            # 파일 저장
            file_path = default_storage.save(f'documents/{safe_filename}', file)
            full_path = default_storage.path(file_path)
            
            # 데이터베이스에 저장
            doc = Document.objects.create(
                title=safe_filename,
                file=file_path,
                processed=False
            )
            
            # RAG 엔진에 추가
            success, message = rag_engine.add_file_document(full_path)
            
            if success:
                doc.processed = True
                doc.save()
                
                logger.info(f"File uploaded successfully: {safe_filename}")
                
                return JsonResponse({
                    'status': 'success', 
                    'message': f'✅ "{safe_filename}" 업로드 완료! {message}',
                    'document_count': rag_engine.get_document_count()
                })
            else:
                doc.delete()
                logger.error(f"File processing failed: {safe_filename} - {message}")
                return JsonResponse({'status': 'error', 'message': f'파일 처리 실패: {message}'})
                
        except Exception as e:
            logger.error(f"File upload error: {str(e)}")
            return JsonResponse({
                'status': 'error', 
                'message': '파일 업로드 중 오류가 발생했습니다.'
            })
    
    return JsonResponse({'status': 'error', 'message': '파일을 선택해주세요.'})