# Django RAG 챗봇 🤖

Django 기반의 Retrieval-Augmented Generation (RAG) 챗봇으로, 문서를 업로드하고 내용에 기반한 질문응답을 제공합니다.

![RAG Chatbot Demo](./ss2025-08-25.png)

## ✨ 주요 기능

- 📄 **다양한 문서 형식 지원**: PDF, TXT, DOCX 파일 업로드 또는 텍스트 직접 입력
- 💬 **실시간 채팅**: AJAX 기반 즉시 응답
- 🔍 **지능형 검색**: 키워드 기반으로 관련 문서 내용 검색
- 📱 **반응형 UI**: 깔끔하고 직관적인 사용자 인터페이스

## 🚀 빠른 시작

### 필수 요구사항
- Python 3.8 이상
- Django 4.0 이상

### 설치 방법

```bash
# 1. 프로젝트 클론
git clone https://github.com/username/django-rag-chatbot.git
cd django-rag-chatbot

# 2. 가상환경 설정
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 패키지 설치
pip install -r requirements.txt

# 4. 데이터베이스 설정
python manage.py makemigrations
python manage.py migrate

# 5. 서버 실행
python manage.py runserver
```

브라우저에서 `http://127.0.0.1:8000/` 접속

## 📋 사용법

### 1. 문서 추가
- **텍스트 입력**: 제목과 내용을 직접 입력
- **파일 업로드**: PDF, TXT, DOCX 파일 선택

### 2. 질문하기
채팅창에 질문을 입력하면 업로드된 문서에서 관련 내용을 찾아 답변합니다.

**예시:**
```
📚 회사 매뉴얼 → "휴가 신청 절차는?"
🔧 기술 문서 → "API 인증 방법은?"
📖 학습 자료 → "머신러닝이란?"
```

## 🏗️ 기술 스택

- **Backend**: Django, Python
- **Frontend**: HTML, CSS, JavaScript
- **문서 처리**: LangChain, PyPDF, python-docx
- **검색**: scikit-learn TF-IDF 기반
- **Database**: SQLite (개발용)

## 📦 프로젝트 구조

```
django_rag_chatbot/
├── manage.py
├── mainapp/                 # Django 설정
├── chatbot/                 # 메인 앱
│   ├── models.py           # 문서 모델
│   ├── views.py            # API 뷰
│   ├── rag_engine.py       # RAG 엔진
│   └── urls.py             # URL 라우팅
├── templates/chatbot/       # UI 템플릿
├── media/documents/         # 업로드 파일
└── requirements.txt
```

## 🔧 개발 로드맵

### ✅ v1.0 (현재)
- 기본 문서 업로드 및 텍스트 입력
- **문서 처리**: LangChain, PyPDF, python-docx
- **검색**: scikit-learn TF-IDF 기반 키워드 검색 시스템
- Django 기반 웹 인터페이스 구현

### 🚧 필수 개선사항

**보안 & 품질**
- CSRF 보안 강화 (`@csrf_exempt` 제거)
- 파일 형식/용량 검증 및 보안 강화
- 예외 처리 및 로깅 시스템 구축

**데이터 영속성**
- 벡터 데이터베이스 연동 (ChromaDB, FAISS)
- 서버 재시작 후에도 데이터 유지

**검색 성능**
- BM25 + Dense 하이브리드 검색
- 다국어 임베딩 모델 적용 (한국어 최적화)
- 검색 결과 출처 및 하이라이트 표시

### 🎯 v2.0 계획
- LLM API 연동 (OpenAI, Claude)
- 실시간 스트리밍 응답
- 사용자 인증 시스템
- 비동기 파일 처리

### 🌟 v3.0 계획
- MCP (Model Context Protocol) 지원
- Claude Desktop 연동
- 멀티모달 지원 (이미지, 오디오)
- 실시간 협업 기능

## 🛠️ 개발 환경 설정

```bash
# 개발용 패키지 추가 설치
pip install django-debug-toolbar

# 테스트 실행
python manage.py test

# 정적 파일 수집 (배포시)
python manage.py collectstatic
```

## ⚠️ 알려진 이슈

- PDF 파일의 한글 처리 제한 (pypdf 라이브러리 한계)
- 대용량 파일 업로드시 메모리 사용량 증가
- 복잡한 문서 구조 처리 한계

## 🤝 기여하기

1. Fork 후 Feature Branch 생성
2. 변경사항 커밋
3. Pull Request 제출

## 📞 문의

- **Email**: catnaro16@gmail.com
- **Issues**: GitHub Issues 탭 이용

## 📄 라이선스

MIT License - [LICENSE](LICENSE) 파일 참조

## 🙏 오픈소스 라이브러리

- [LangChain](https://github.com/langchain-ai/langchain) - 문서 처리 프레임워크
- [Django](https://www.djangoproject.com/) - 웹 프레임워크  
- [scikit-learn](https://scikit-learn.org/) - 머신러닝 라이브러리

---

⭐ **이 프로젝트가 유용하다면 스타를 눌러주세요!**