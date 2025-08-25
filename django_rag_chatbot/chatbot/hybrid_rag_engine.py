"""
하이브리드 RAG 엔진 - 키워드 + 벡터 검색 통합
점진적 전환을 위한 기존 엔진과 벡터 DB 병행 사용
"""

import os
import hashlib
from typing import List, Dict, Any, Optional
from .rag_engine import SimpleRAGEngine

try:
    import chromadb
    from sentence_transformers import SentenceTransformer
    VECTOR_DB_AVAILABLE = True
    print("Vector DB available: ChromaDB + SentenceTransformers")
except ImportError:
    VECTOR_DB_AVAILABLE = False
    print("Vector DB libraries not available. Using keyword search only.")

class HybridRAGEngine:
    """키워드 검색 + 벡터 검색 하이브리드 엔진"""
    
    def __init__(self, persist_directory="./chroma_db"):
        # 기존 키워드 엔진 초기화
        self.keyword_engine = SimpleRAGEngine()
        
        # 벡터 DB 초기화
        self.vector_engine = None
        self.use_vector_search = False
        
        if VECTOR_DB_AVAILABLE:
            try:
                self._initialize_vector_db(persist_directory)
                self.use_vector_search = True
                print("Hybrid mode: Keyword + Vector search")
            except Exception as e:
                print(f"Vector DB initialization failed: {e}")
                print("Using keyword search only.")
        else:
            print("Keyword search mode")
    
    def _initialize_vector_db(self, persist_directory):
        """벡터 DB 초기화"""
        # 한국어 임베딩 모델 로드
        self.embedding_model = SentenceTransformer('jhgan/ko-sroberta-multitask')
        
        # ChromaDB 클라이언트 초기화
        self.chroma_client = chromadb.PersistentClient(path=persist_directory)
        
        # 컬렉션 생성 또는 로드
        try:
            self.collection = self.chroma_client.get_collection("documents")
            print(f"Existing vector DB loaded: {self.collection.count()} documents")
        except:
            self.collection = self.chroma_client.create_collection(
                name="documents",
                metadata={"hnsw:space": "cosine"}
            )
            print("New vector DB created")
    
    def add_text_document(self, text: str, title: str = "문서"):
        """텍스트 문서 추가 (키워드 + 벡터 DB 모두에 저장)"""
        # 1. 기존 키워드 엔진에 추가
        keyword_chunks = self.keyword_engine.add_text_document(text, title)
        
        # 2. 벡터 DB에 추가 (사용 가능한 경우)
        vector_chunks = 0
        if self.use_vector_search:
            try:
                vector_chunks = self._add_to_vector_db(text, title)
            except Exception as e:
                print(f"벡터 DB 추가 오류: {e}")
        
        return {
            'keyword_chunks': keyword_chunks,
            'vector_chunks': vector_chunks,
            'total_chunks': max(keyword_chunks, vector_chunks)
        }
    
    def add_file_document(self, file_path: str):
        """파일 문서 추가"""
        # 1. 기존 키워드 엔진에 추가
        keyword_result = self.keyword_engine.add_file_document(file_path)
        
        # 2. 벡터 DB에 추가 (사용 가능한 경우)
        vector_chunks = 0
        if self.use_vector_search and keyword_result[0]:  # 키워드 엔진 성공시
            try:
                # 키워드 엔진에서 처리한 문서를 벡터 DB에도 추가
                # 키워드 엔진의 문서 내용 가져오기
                if hasattr(self.keyword_engine, 'documents') and self.keyword_engine.documents:
                    # 최근 추가된 문서들 (마지막에 추가된 것들)
                    recent_docs = []
                    for doc in reversed(self.keyword_engine.documents):
                        if doc.metadata.get('source') == file_path:
                            recent_docs.append(doc)
                        elif recent_docs:  # 다른 파일의 문서가 나오면 중단
                            break
                    
                    # 문서 내용을 결합하여 벡터 DB에 추가
                    if recent_docs:
                        full_content = "\n\n".join([doc.page_content for doc in recent_docs])
                        vector_chunks = self._add_to_vector_db(full_content, file_path)
                        print(f"벡터 DB에 {len(recent_docs)}개 청크를 {vector_chunks}개 벡터 청크로 변환하여 추가")
                        
            except Exception as e:
                print(f"벡터 DB 파일 추가 오류: {e}")
                import traceback
                traceback.print_exc()
        
        return keyword_result[0], f"{keyword_result[1]} (벡터: {vector_chunks}개)"
    
    def _add_to_vector_db(self, text: str, source: str) -> int:
        """벡터 DB에 텍스트 추가"""
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        
        # 텍스트 청킹
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100,
            separators=["\n\n", "\n", ". ", "! ", "? ", " "]
        )
        
        chunks = text_splitter.split_text(text)
        
        # 각 청크를 벡터 DB에 추가
        for i, chunk in enumerate(chunks):
            doc_id = hashlib.md5(f"{source}_{i}_{chunk}".encode()).hexdigest()
            
            # 임베딩 생성
            embedding = self.embedding_model.encode(chunk).tolist()
            
            # ChromaDB에 추가
            self.collection.add(
                documents=[chunk],
                metadatas=[{"source": source, "chunk_id": i}],
                ids=[doc_id],
                embeddings=[embedding]
            )
        
        return len(chunks)
    
    def search_documents(self, query: str, k: int = 5, hybrid_mode: bool = True):
        """하이브리드 검색 (키워드 + 벡터)"""
        results = []
        
        if hybrid_mode and self.use_vector_search:
            # 하이브리드 검색
            results = self._hybrid_search(query, k)
        else:
            # 키워드 검색만
            keyword_docs = self.keyword_engine.search_documents(query, k)
            # Document 객체를 dict로 변환
            for doc in keyword_docs:
                results.append({
                    'content': doc.page_content,
                    'metadata': doc.metadata,
                    'score': 1.0,
                    'search_type': 'keyword'
                })
        
        return results
    
    def _hybrid_search(self, query: str, k: int = 5) -> List[Dict]:
        """하이브리드 검색 실행"""
        all_results = []
        
        # 1. 벡터 검색 (의미적 유사성)
        try:
            query_embedding = self.embedding_model.encode(query).tolist()
            vector_results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=k,
                include=['documents', 'metadatas', 'distances']
            )
            
            # 벡터 검색 결과 처리
            for i in range(len(vector_results['documents'][0])):
                score = 1 - vector_results['distances'][0][i]  # 거리를 유사도로 변환
                all_results.append({
                    'content': vector_results['documents'][0][i],
                    'metadata': vector_results['metadatas'][0][i],
                    'score': score * 0.7,  # 벡터 검색 가중치 70%
                    'search_type': 'vector'
                })
        except Exception as e:
            print(f"벡터 검색 오류: {e}")
        
        # 2. 키워드 검색 (정확한 매칭)
        try:
            keyword_docs = self.keyword_engine.search_documents(query, k)
            for doc in keyword_docs:
                # 중복 제거를 위해 내용 기반으로 체크
                is_duplicate = any(
                    result['content'][:100] == doc.page_content[:100] 
                    for result in all_results
                )
                
                if not is_duplicate:
                    all_results.append({
                        'content': doc.page_content,
                        'metadata': doc.metadata,
                        'score': 0.3,  # 키워드 검색 가중치 30%
                        'search_type': 'keyword'
                    })
        except Exception as e:
            print(f"키워드 검색 오류: {e}")
        
        # 점수 기준으로 정렬
        all_results.sort(key=lambda x: x['score'], reverse=True)
        
        return all_results[:k]
    
    def get_rag_response(self, query: str):
        """RAG 응답 생성 (하이브리드 검색 사용)"""
        # 하이브리드 검색으로 문서 찾기
        relevant_results = self.search_documents(query, k=5, hybrid_mode=True)
        
        if not relevant_results:
            return "죄송합니다. 관련된 문서를 찾을 수 없습니다."
        
        # 검색 결과를 Document 형태로 변환하여 기존 응답 생성 로직 사용
        from langchain_core.documents import Document
        docs = []
        for result in relevant_results:
            doc = Document(
                page_content=result['content'],
                metadata=result['metadata']
            )
            docs.append(doc)
        
        # 기존 응답 생성 로직 사용
        return self.keyword_engine._generate_formatted_response(query, docs)
    
    def get_document_count(self):
        """저장된 문서 수"""
        keyword_count = self.keyword_engine.get_document_count()
        vector_count = 0
        
        if self.use_vector_search:
            try:
                vector_count = self.collection.count()
            except:
                vector_count = 0
        
        return {
            'keyword_chunks': keyword_count,
            'vector_chunks': vector_count,
            'total': max(keyword_count, vector_count)
        }
    
    def get_search_stats(self, query: str):
        """검색 통계 (디버깅용)"""
        if not self.use_vector_search:
            return {"mode": "keyword_only"}
        
        # 각 검색 방식별 결과 수 확인
        vector_results = self.collection.query(
            query_embeddings=[self.embedding_model.encode(query).tolist()],
            n_results=5,
            include=['documents']
        )
        
        keyword_results = self.keyword_engine.search_documents(query, 5)
        
        return {
            "mode": "hybrid",
            "vector_results": len(vector_results['documents'][0]) if vector_results['documents'] else 0,
            "keyword_results": len(keyword_results),
            "vector_db_total": self.collection.count(),
            "keyword_db_total": self.keyword_engine.get_document_count()
        }

# 전역 인스턴스
hybrid_rag_engine = None

def get_hybrid_engine():
    """하이브리드 엔진 싱글톤 인스턴스 반환"""
    global hybrid_rag_engine
    if hybrid_rag_engine is None:
        hybrid_rag_engine = HybridRAGEngine()
    return hybrid_rag_engine