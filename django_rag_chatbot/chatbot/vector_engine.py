"""
벡터 DB 기반 RAG 엔진
ChromaDB를 사용한 의미적 검색 구현
"""

import chromadb
from chromadb.utils import embedding_functions
import hashlib
from typing import List, Dict, Any
import os

class VectorRAGEngine:
    def __init__(self, persist_directory="./chroma_db"):
        """
        벡터 DB 초기화
        Args:
            persist_directory: ChromaDB 저장 경로
        """
        # 한국어 임베딩 모델 설정
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="jhgan/ko-sroberta-multitask"
        )
        
        # ChromaDB 클라이언트 초기화
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # 컬렉션 생성 또는 로드
        try:
            self.collection = self.client.get_collection(
                name="documents",
                embedding_function=self.embedding_function
            )
            print(f"기존 벡터 DB 로드: {self.collection.count()}개 문서")
        except:
            self.collection = self.client.create_collection(
                name="documents",
                embedding_function=self.embedding_function,
                metadata={"hnsw:space": "cosine"}  # 코사인 유사도 사용
            )
            print("새로운 벡터 DB 생성")
    
    def add_document(self, text: str, metadata: Dict[str, Any] = None) -> str:
        """
        문서를 벡터 DB에 추가
        Args:
            text: 문서 내용
            metadata: 메타데이터 (source, title 등)
        Returns:
            문서 ID
        """
        # 문서 ID 생성 (중복 방지)
        doc_id = hashlib.md5(text.encode()).hexdigest()
        
        # 기본 메타데이터 설정
        if metadata is None:
            metadata = {}
        
        metadata['text_length'] = len(text)
        
        try:
            # 벡터 DB에 추가
            self.collection.add(
                documents=[text],
                metadatas=[metadata],
                ids=[doc_id]
            )
            print(f"문서 추가 완료: {doc_id[:8]}...")
            return doc_id
        except Exception as e:
            print(f"문서 추가 실패: {e}")
            return None
    
    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        의미적 유사성 검색
        Args:
            query: 검색 쿼리
            k: 반환할 문서 수
        Returns:
            검색 결과 리스트
        """
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=k,
                include=['documents', 'metadatas', 'distances']
            )
            
            # 결과 포맷팅
            formatted_results = []
            for i in range(len(results['documents'][0])):
                formatted_results.append({
                    'content': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'score': 1 - results['distances'][0][i]  # 코사인 유사도로 변환
                })
            
            return formatted_results
        except Exception as e:
            print(f"검색 오류: {e}")
            return []
    
    def delete_document(self, doc_id: str) -> bool:
        """
        문서 삭제
        Args:
            doc_id: 삭제할 문서 ID
        Returns:
            성공 여부
        """
        try:
            self.collection.delete(ids=[doc_id])
            return True
        except:
            return False
    
    def clear_all(self) -> bool:
        """
        모든 문서 삭제
        Returns:
            성공 여부
        """
        try:
            self.client.delete_collection("documents")
            self.collection = self.client.create_collection(
                name="documents",
                embedding_function=self.embedding_function
            )
            return True
        except:
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        벡터 DB 통계
        Returns:
            통계 정보
        """
        return {
            'total_documents': self.collection.count(),
            'embedding_model': 'jhgan/ko-sroberta-multitask',
            'vector_dimension': 768,
            'similarity_metric': 'cosine'
        }

# 하이브리드 검색을 위한 통합 엔진
class HybridRAGEngine:
    def __init__(self, keyword_engine=None, vector_engine=None):
        """
        키워드 + 벡터 하이브리드 검색
        Args:
            keyword_engine: 기존 키워드 기반 엔진
            vector_engine: 벡터 DB 엔진
        """
        self.keyword_engine = keyword_engine
        self.vector_engine = vector_engine or VectorRAGEngine()
    
    def search(self, query: str, k: int = 5, alpha: float = 0.7) -> List[Dict]:
        """
        하이브리드 검색 (키워드 + 벡터)
        Args:
            query: 검색 쿼리
            k: 반환할 문서 수
            alpha: 벡터 검색 가중치 (0~1)
        Returns:
            통합 검색 결과
        """
        results = []
        
        # 1. 벡터 검색
        if self.vector_engine:
            vector_results = self.vector_engine.search(query, k)
            for r in vector_results:
                r['search_type'] = 'vector'
                r['final_score'] = r['score'] * alpha
                results.append(r)
        
        # 2. 키워드 검색 (기존 엔진 있을 경우)
        if self.keyword_engine:
            keyword_results = self.keyword_engine.search_documents(query, k)
            for doc in keyword_results:
                results.append({
                    'content': doc.page_content,
                    'metadata': doc.metadata,
                    'search_type': 'keyword',
                    'final_score': (1 - alpha) * 0.5  # 정규화된 점수
                })
        
        # 3. 점수 기준 정렬
        results.sort(key=lambda x: x['final_score'], reverse=True)
        
        return results[:k]

# 전역 인스턴스
vector_engine = None

def initialize_vector_engine():
    """벡터 엔진 초기화"""
    global vector_engine
    vector_engine = VectorRAGEngine()
    return vector_engine