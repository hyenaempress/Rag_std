# Django RAG 챗봇 개발 과정 가이드

Django를 사용해서 RAG(Retrieval-Augmented Generation) 챗봇을 만든 전체 과정을 단계별로 정리한 문서입니다.

## 🎯 프로젝트 개요

- **목표**: 문서 업로드 후 질문-답변이 가능한 RAG 시스템
- **기술 스택**: Django, LangChain, 키워드 기반 검색
- **주요 기능**: 텍스트/파일 업로드, 실시간 채팅, 문서 검색

## 📁 1단계: 프로젝트 초기 설정

### 1.1 프로젝트 구조 생성
```bash
# 작업 디렉토리 생성
mkdir django_rag_chatbot
cd django_rag_chatbot

# Django 프로젝트 생성 (현재 폴더에)
django-admin startproject mainapp .

# Django 앱 생성
python manage.py startapp chatbot

# 템플릿 디렉토리 생성
mkdir templates
mkdir templates\chatbot
```

### 1.2 최종 프로젝트 구조
```
django_rag_chatbot/
├── manage.py
├── mainapp/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── chatbot/
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── rag_engine.py
│   └── migrations/
├── templates/
│   └── chatbot/
│       └── chatbot.html
├── media/
│   └── documents/
├── requirements.txt
└── README.md
```

## ⚙️ 2단계: Django 기본 설정

### 2.1 settings.py 수정
```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'chatbot',  # 추가
]

# 템플릿 경로 설정
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # 수정
        'APP_DIRS': True,
        # ... 기타 설정
    },
]

# 미디어 파일 설정
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
```

### 2.2 URL 라우팅 설정
**mainapp/urls.py**
```python
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('chatbot.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

**chatbot/urls.py (새로 생성)**
```python
from django.urls import path
from . import views

urlpatterns = [
    path('', views.chatbot_view, name='chatbot'),
    path('api/chat/', views.chat_api, name='chat_api'),
    path('api/upload-text/', views.upload_text_api, name='upload_text'),
    path('api/upload-file/', views.upload_file_api, name='upload_file'),
]
```

## 🗄️ 3단계: 데이터 모델 정의

### 3.1 Document 모델 생성
**chatbot/models.py**
```python
from django.db import models

class Document(models.Model):
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='documents/', null=True, blank=True)
    text_content = models.TextField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    chunk_count = models.IntegerField(default=0)
    
    def __str__(self):
        return self.title
```

### 3.2 데이터베이스 마이그레이션
```bash
python manage.py makemigrations
python manage.py migrate
```

## 🧠 4단계: RAG 엔진 구현

### 4.1 라이브러리 설치
```bash
pip install langchain langchain-community langchain-text-splitters
pip install pypdf python-docx scikit-learn
```

### 4.2 RAG 엔진 구현
**chatbot/rag_engine.py**
```python
import os
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import docx

class SimpleRAGEngine:
    def __init__(self):
        self.documents = []  # 메모리에 문서 저장
        print("간단한 키워드 기반 RAG 엔진을 사용합니다.")
    
    def add_text_document(self, text, title="문서"):
        """텍스트를 청크로 나누어 저장"""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " "]
        )
        
        doc = Document(page_content=text, metadata={"source": title})
        chunks = text_splitter.split_documents([doc])
        self.documents.extend(chunks)
        
        return len(chunks)
    
    def add_file_document(self, file_path):
        """파일을 로드하여 문서로 추가"""
        try:
            if file_path.endswith('.pdf'):
                loader = PyPDFLoader(file_path)
                documents = loader.load()
            elif file_path.endswith('.txt'):
                loader = TextLoader(file_path, encoding='utf-8')
                documents = loader.load()
            elif file_path.endswith('.docx'):
                doc = docx.Document(file_path)
                text = '\n'.join([paragraph.text for paragraph in doc.paragraphs])
                documents = [Document(page_content=text, metadata={"source": file_path})]
            else:
                return False, "지원하지 않는 파일 형식입니다."
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )
            chunks = text_splitter.split_documents(documents)
            self.documents.extend(chunks)
            
            return True, f"{len(chunks)}개 청크가 추가되었습니다."
            
        except Exception as e:
            return False, f"파일 처리 중 오류: {str(e)}"
    
    def search_documents(self, query, k=3):
        """키워드 기반 문서 검색"""
        if not self.documents:
            return []
        
        query_words = query.lower().split()
        scored_docs = []
        
        for doc in self.documents:
            content = doc.page_content.lower()
            score = 0
            
            # 키워드 매칭으로 점수 계산
            for word in query_words:
                if len(word) > 2:  # 2글자 이상만 검색
                    word_count = content.count(word)
                    score += word_count * len(word)
            
            if score > 0:
                scored_docs.append((doc, score))
        
        # 점수순 정렬 후 상위 k개 반환
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, score in scored_docs[:k]]
    
    def get_rag_response(self, query):
        """RAG 기반 응답 생성"""
        relevant_docs = self.search_documents(query, k=3)
        
        if not relevant_docs:
            return "죄송합니다. 관련된 문서를 찾을 수 없습니다."
        
        # 검색 결과를 포맷팅
        response_parts = ["📄 검색된 관련 내용:"]
        
        for i, doc in enumerate(relevant_docs, 1):
            source = doc.metadata.get('source', '알 수 없음')
            content = doc.page_content[:300]
            response_parts.append(f"\n[{i}] 출처: {source}")
            response_parts.append(f"내용: {content}...")
        
        return "\n".join(response_parts)
    
    def get_document_count(self):
        return len(self.documents)

# 전역 RAG 엔진 인스턴스
rag_engine = SimpleRAGEngine()
```

## 🌐 5단계: 백엔드 API 구현

### 5.1 뷰 함수 구현
**chatbot/views.py**
```python
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
import json
import os
from .rag_engine import rag_engine
from .models import Document

def chatbot_view(request):
    """메인 채팅 페이지"""
    doc_count = rag_engine.get_document_count()
    context = {'document_count': doc_count}
    return render(request, 'chatbot/chatbot.html', context)

@csrf_exempt
def chat_api(request):
    """채팅 메시지 처리 API"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            
            # RAG 응답 또는 기본 응답
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

@csrf_exempt
def upload_text_api(request):
    """텍스트 직접 업로드 API"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            text = data.get('text', '')
            title = data.get('title', '직접 입력 문서')
            
            if not text.strip():
                return JsonResponse({'status': 'error', 'message': '텍스트를 입력해주세요.'})
            
            # DB에 저장
            doc = Document.objects.create(
                title=title,
                text_content=text,
                processed=False
            )
            
            # RAG 엔진에 추가
            chunk_count = rag_engine.add_text_document(text, title)
            doc.processed = True
            doc.chunk_count = chunk_count
            doc.save()
            
            return JsonResponse({
                'status': 'success', 
                'message': f'텍스트가 업로드되었습니다. ({chunk_count}개 청크)',
                'document_count': rag_engine.get_document_count()
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

@csrf_exempt
def upload_file_api(request):
    """파일 업로드 API"""
    if request.method == 'POST' and request.FILES.get('file'):
        try:
            file = request.FILES['file']
            file_path = default_storage.save(f'documents/{file.name}', file)
            full_path = default_storage.path(file_path)
            
            # DB에 저장
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
                doc.delete()
                return JsonResponse({'status': 'error', 'message': message})
                
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

def get_simple_response(message):
    """문서가 없을 때의 기본 응답"""
    message = message.lower()
    
    if '안녕' in message:
        return "안녕하세요! 문서를 업로드하면 더 정확한 답변을 드릴 수 있어요."
    elif '문서' in message or '업로드' in message:
        return "아래 업로드 섹션에서 텍스트나 파일을 업로드해주세요!"
    else:
        return "아직 업로드된 문서가 없습니다. 먼저 문서를 업로드한 후 질문해주세요."
```

## 🎨 6단계: 프론트엔드 UI 구현

### 6.1 메인 템플릿 구현
**templates/chatbot/chatbot.html**
```html
<!DOCTYPE html>
<html>
<head>
    <title>RAG 챗봇</title>
    <meta charset="utf-8">
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 0; 
            background: #f5f5f5; 
        }
        .container { 
            max-width: 1200px; 
            margin: 0 auto; 
            padding: 20px; 
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .main-content {
            display: flex;
            gap: 20px;
        }
        .upload-section {
            flex: 1;
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .chat-section {
            flex: 2;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        /* 업로드 관련 스타일 */
        .upload-tabs {
            display: flex;
            margin-bottom: 20px;
        }
        .tab-btn {
            flex: 1;
            padding: 10px;
            background: #f0f0f0;
            border: none;
            cursor: pointer;
        }
        .tab-btn.active {
            background: #667eea;
            color: white;
        }
        .form-group {
            margin-bottom: 15px;
        }
        .form-group input, .form-group textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            box-sizing: border-box;
        }
        
        /* 채팅 관련 스타일 */
        .chat-box {
            height: 400px;
            overflow-y: auto;
            padding: 20px;
            background: #f9f9f9;
        }
        .message {
            margin-bottom: 15px;
            padding: 12px;
            border-radius: 10px;
            max-width: 80%;
        }
        .user-message {
            background: #667eea;
            color: white;
            margin-left: auto;
        }
        .bot-message {
            background: white;
            border: 1px solid #ddd;
            white-space: pre-line;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 RAG 챗봇</h1>
            <p>문서를 업로드하고 질문해보세요!</p>
        </div>

        <div class="main-content">
            <!-- 업로드 섹션 -->
            <div class="upload-section">
                <div class="upload-header">📁 문서 업로드</div>
                
                <div class="upload-tabs">
                    <button class="tab-btn active" onclick="showTab('text-tab')">텍스트 입력</button>
                    <button class="tab-btn" onclick="showTab('file-tab')">파일 업로드</button>
                </div>

                <!-- 텍스트 입력 탭 -->
                <div id="text-tab" class="tab-content active">
                    <div class="form-group">
                        <label>문서 제목:</label>
                        <input type="text" id="textTitle" placeholder="문서 제목을 입력하세요">
                    </div>
                    <div class="form-group">
                        <label>내용:</label>
                        <textarea id="textContent" placeholder="문서 내용을 입력하세요..."></textarea>
                    </div>
                    <button class="upload-btn" onclick="uploadText()">텍스트 업로드</button>
                </div>

                <!-- 파일 업로드 탭 -->
                <div id="file-tab" class="tab-content">
                    <div class="form-group">
                        <label>파일 선택:</label>
                        <input type="file" id="fileInput" accept=".txt,.pdf,.docx">
                    </div>
                    <button class="upload-btn" onclick="uploadFile()">파일 업로드</button>
                </div>

                <!-- 상태 정보 -->
                <div class="status-info">
                    <strong>📊 현재 상태:</strong><br>
                    저장된 문서: <span id="docCount">{{ document_count }}</span>개<br>
                    <div id="uploadMessage"></div>
                </div>
            </div>

            <!-- 채팅 섹션 -->
            <div class="chat-section">
                <div class="chat-header">
                    <h3>💬 채팅</h3>
                </div>
                
                <div id="chatBox" class="chat-box">
                    <div class="message bot-message">
                        안녕하세요! 문서를 업로드한 후 질문해주세요. 📚
                    </div>
                </div>
                
                <div class="input-container">
                    <input type="text" id="messageInput" placeholder="질문을 입력하세요..." onkeypress="handleKeyPress(event)">
                    <button id="sendBtn" onclick="sendMessage()">전송</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        // 탭 전환 기능
        function showTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            
            document.getElementById(tabId).classList.add('active');
            event.target.classList.add('active');
        }

        // 채팅 메시지 전송
        async function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            if (!message) return;

            addMessage(message, true);
            input.value = '';

            try {
                const response = await fetch('/api/chat/', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: message})
                });
                
                const data = await response.json();
                addMessage(data.response, false);
                
            } catch (error) {
                addMessage('죄송합니다. 오류가 발생했습니다.', false);
            }
        }

        // 텍스트 업로드
        async function uploadText() {
            const title = document.getElementById('textTitle').value.trim();
            const content = document.getElementById('textContent').value.trim();
            
            if (!content) {
                showMessage('내용을 입력해주세요.', 'error');
                return;
            }

            try {
                const response = await fetch('/api/upload-text/', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        title: title || '직접 입력 문서',
                        text: content
                    })
                });
                
                const data = await response.json();
                
                if (data.status === 'success') {
                    showMessage(data.message, 'success');
                    document.getElementById('textTitle').value = '';
                    document.getElementById('textContent').value = '';
                    document.getElementById('docCount').textContent = data.document_count;
                } else {
                    showMessage(data.message, 'error');
                }
                
            } catch (error) {
                showMessage('업로드 중 오류가 발생했습니다.', 'error');
            }
        }

        // 파일 업로드
        async function uploadFile() {
            const fileInput = document.getElementById('fileInput');
            const file = fileInput.files[0];
            
            if (!file) {
                showMessage('파일을 선택해주세요.', 'error');
                return;
            }

            const formData = new FormData();
            formData.append('file', file);

            try {
                const response = await fetch('/api/upload-file/', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.status === 'success') {
                    showMessage(data.message, 'success');
                    fileInput.value = '';
                    document.getElementById('docCount').textContent = data.document_count;
                } else {
                    showMessage(data.message, 'error');
                }
                
            } catch (error) {
                showMessage('업로드 중 오류가 발생했습니다.', 'error');
            }
        }

        // 유틸리티 함수들
        function addMessage(message, isUser) {
            const chatBox = document.getElementById('chatBox');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message ' + (isUser ? 'user-message' : 'bot-message');
            messageDiv.textContent = message;
            chatBox.appendChild(messageDiv);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        function showMessage(message, type) {
            const messageDiv = document.getElementById('uploadMessage');
            messageDiv.className = type === 'success' ? 'success-message' : 'error-message';
            messageDiv.textContent = message;
            
            setTimeout(() => {
                messageDiv.textContent = '';
                messageDiv.className = '';
            }, 5000);
        }

        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                sendMessage();
            }
        }
    </script>
</body>
</html>
```

## 🚀 7단계: 실행 및 테스트

### 7.1 서버 실행
```bash
python manage.py runserver
```

### 7.2 기능 테스트
1. **텍스트 업로드 테스트**:
   - 제목: "테스트 문서"
   - 내용: "Django는 파이썬 웹 프레임워크입니다. RAG는 검색 증강 생성입니다."

2. **파일 업로드 테스트**:
   - PDF, TXT, DOCX 파일 업로드

3. **채팅 테스트**:
   - "Django란 무엇인가요?"
   - "RAG에 대해 설명해주세요"

## 📦 8단계: 패키지 의존성 정리

### 8.1 requirements.txt 생성
```bash
pip freeze > requirements.txt
```

### 8.2 주요 패키지 목록
```txt
Django==4.2.0
langchain-community==0.3.74
langchain-text-splitters==0.3.9
langchain-core==0.3.74
pypdf==4.0.0
python-docx==1.2.0
scikit-learn==1.7.1
```

## 🔧 9단계: 개발 중 해결한 주요 이슈

### 9.1 LangChain Import 오류
**문제**: `ModuleNotFoundError: Module langchain_community.vectorstores not found`

**해결책**:
```bash
pip install langchain-community langchain-chroma
```

### 9.2 PyTorch 의존성 문제
**문제**: HuggingFace 임베딩 로딩 시 PyTorch 충돌

**해결책**: 키워드 기반 검색으로 대체
```python
class SimpleRAGEngine:
    def search_documents(self, query, k=3):
        # 키워드 매칭 기반 검색 구현
        pass
```

### 9.3 PDF 파일 처리 오류
**문제**: `pypdf package not found`

**해결책**:
```bash
pip install pypdf  # PyPDF2 대신 pypdf 사용
```

## 🎯 10단계: 향후 개선 방향

### 10.1 단기 개선사항
- [ ] 벡터 데이터베이스 연동 (ChromaDB)
- [ ] 실제 임베딩 모델 사용
- [ ] LLM API 연동 (OpenAI/Claude)
- [ ] 사용자 인증 시스템

### 10.2 장기 개선사항
- [ ] MCP (Model Context Protocol) 지원
- [ ] Claude Desktop 연동
- [ ] 멀티모달 지원
- [ ] 실시간 협업 기능

## 📝 개발 과정에서 배운 점

1. **점진적 개발의 중요성**: 기본 기능부터 구현 후 고급 기능 추가
2. **의존성 관리**: LangChain 버전별 import 경로 차이 주의
3. **에러 처리**: 사용자 친화적인 오류 메시지 제공
4. **UI/UX**: 직관적인 탭 기반 인터페이스 설계
5. **확장성**: 나중에 고급 기능을 추가하기 쉬운 구조 설계

## 🏆 완성된 기능 목록

✅ Django 프로젝트 기본 구조  
✅ 텍스트 직접 입력 업로드  
✅ 파일 업로드 (PDF, TXT, DOCX)  
✅ 키워드 기반 문서 검색  
✅ 실시간 AJAX 채팅  
✅ 반응형 웹 인터페이스  
✅ 문서 청크 단위 처리  
✅ 오류 처리 및 사용자 피드백  

이 가이드를 따라하면 Django 기반의 기본적인 RAG 챗봇 시스템을 구축할 수 있습니다!