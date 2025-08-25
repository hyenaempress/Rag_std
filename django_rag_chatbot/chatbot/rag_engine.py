import os
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import docx

class SimpleEmbeddings:
    """간단한 TF-IDF 기반 임베딩 (PyTorch 없이)"""
    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.vectorizer = TfidfVectorizer(max_features=1000)
        self.fitted = False
    
    def embed_documents(self, texts):
        if not self.fitted:
            self.vectorizer.fit(texts)
            self.fitted = True
        return self.vectorizer.transform(texts).toarray().tolist()
    
    def embed_query(self, text):
        if not self.fitted:
            return [0] * 1000
        return self.vectorizer.transform([text]).toarray()[0].tolist()

class RAGEngine:
    def __init__(self):
        # 일단 간단한 임베딩 사용
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
            print("HuggingFace 임베딩을 사용합니다.")
        except Exception as e:
            print(f"HuggingFace 임베딩 로드 실패: {e}")
            print("간단한 TF-IDF 임베딩을 사용합니다.")
            self.embeddings = SimpleEmbeddings()
        
        self.vectorstore = None
        self.vectorstore_path = "./vectorstore"
        self.documents = []  # 문서 저장용
        # 일단 벡터스토어 로딩은 스킵
    
    def add_text_document(self, text, title="문서"):
        """텍스트를 저장 (일단 간단하게)"""
        # 텍스트를 청크로 나누기
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " "]
        )
        
        doc = Document(page_content=text, metadata={"source": title})
        chunks = text_splitter.split_documents([doc])
        
        # 일단 메모리에만 저장
        self.documents.extend(chunks)
        
        return len(chunks)
    
    def add_file_document(self, file_path):
        """파일을 문서로 추가"""
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
            
            # 메모리에 저장
            self.documents.extend(chunks)
            
            return True, f"{len(chunks)}개 청크가 추가되었습니다."
            
        except Exception as e:
            return False, f"파일 처리 중 오류: {str(e)}"
    
    def search_documents(self, query, k=3):
        """간단한 키워드 기반 검색"""
        if not self.documents:
            return []
        
        query = query.lower()
        scored_docs = []
        
        for doc in self.documents:
            content = doc.page_content.lower()
            score = 0
            
            # 간단한 키워드 매칭
            for word in query.split():
                if word in content:
                    score += content.count(word)
            
            if score > 0:
                scored_docs.append((doc, score))
        
        # 점수순 정렬
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        return [doc for doc, score in scored_docs[:k]]
    
    def get_rag_response(self, query):
        """RAG 기반 응답 생성"""
        relevant_docs = self.search_documents(query, k=3)
        
        if not relevant_docs:
            return "죄송합니다. 관련된 문서를 찾을 수 없습니다. 먼저 문서를 업로드해주세요."
        
        context = "\n\n".join([doc.page_content for doc in relevant_docs])
        response = f"검색된 관련 내용:\n\n{context[:800]}..."
        
        return response
    
    def get_document_count(self):
        """저장된 문서 청크 개수"""
        return len(self.documents)

# 전역 RAG 엔진 인스턴스
rag_engine = RAGEngine()