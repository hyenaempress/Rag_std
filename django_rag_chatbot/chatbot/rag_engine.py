import os
import re
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
            chunk_size=800,  # 더 작은 청크로 분할
            chunk_overlap=150,
            separators=["\n\n", "\n", ". ", "! ", "? ", " "]
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
                chunk_size=800,
                chunk_overlap=150,
                separators=["\n\n", "\n", ". ", "! ", "? ", " "]
            )
            chunks = text_splitter.split_documents(documents)
            self.documents.extend(chunks)
            
            return True, f"{len(chunks)}개 청크가 추가되었습니다."
            
        except Exception as e:
            return False, f"파일 처리 중 오류: {str(e)}"
    
    def search_documents(self, query, k=3):
        """키워드 기반 문서 검색 (개선된 버전)"""
        if not self.documents:
            return []
        
        query_words = self._extract_keywords(query.lower())
        scored_docs = []
        
        for doc in self.documents:
            content = doc.page_content.lower()
            score = self._calculate_relevance_score(content, query_words, query.lower())
            
            if score > 0:
                scored_docs.append((doc, score))
        
        # 점수순 정렬 후 상위 k개 반환
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, score in scored_docs[:k]]
    
    def _extract_keywords(self, query):
        """쿼리에서 의미있는 키워드 추출"""
        # 불용어 제거
        stop_words = {
            '이', '그', '저', '의', '가', '을', '를', '에', '와', '과', '으로', '로',
            '은', '는', '이다', '다', '하다', '되다', '있다', '없다', '같다',
            '뭐', '뭔', '뭐야', '무엇', '어떤', '어디', '언제', '왜', '어떻게',
            'what', 'is', 'are', 'the', 'a', 'an', 'and', 'or', 'but'
        }
        
        words = query.split()
        meaningful_words = []
        
        for word in words:
            # 2글자 이상이고 불용어가 아닌 경우
            if len(word) > 1 and word not in stop_words:
                meaningful_words.append(word)
        
        return meaningful_words
    
    def _calculate_relevance_score(self, content, keywords, full_query):
        """관련성 점수 계산 (개선된 알고리즘)"""
        score = 0
        
        # 1. 완전한 구문 일치 (가장 높은 점수)
        if full_query in content:
            score += len(full_query) * 3
        
        # 2. 개별 키워드 점수
        for keyword in keywords:
            if keyword in content:
                # 키워드 빈도 * 키워드 길이
                frequency = content.count(keyword)
                keyword_score = frequency * len(keyword) * 2
                score += keyword_score
        
        # 3. 키워드 근접성 보너스 (키워드들이 가까이 있으면 추가 점수)
        if len(keywords) > 1:
            proximity_bonus = self._calculate_proximity_bonus(content, keywords)
            score += proximity_bonus
        
        return score
    
    def _calculate_proximity_bonus(self, content, keywords):
        """키워드 간 근접성 계산"""
        try:
            positions = {}
            for keyword in keywords:
                positions[keyword] = [m.start() for m in re.finditer(keyword, content)]
            
            # 모든 키워드가 100자 이내에 있으면 보너스
            for pos_list in positions.values():
                for pos in pos_list:
                    nearby_keywords = 0
                    for other_keyword, other_positions in positions.items():
                        for other_pos in other_positions:
                            if abs(pos - other_pos) <= 100:  # 100자 이내
                                nearby_keywords += 1
                    
                    if nearby_keywords >= len(keywords):
                        return 50  # 근접성 보너스
            
            return 0
        except:
            return 0
    
    def get_rag_response(self, query):
        """RAG 기반 응답 생성 (대폭 개선)"""
        relevant_docs = self.search_documents(query, k=3)
        
        if not relevant_docs:
            return "죄송합니다. 관련된 문서를 찾을 수 없습니다."
        
        # 응답 생성
        return self._generate_formatted_response(query, relevant_docs)
    
    def _generate_formatted_response(self, query, docs):
        """포맷된 응답 생성"""
        try:
            response_parts = [f'💡 **"{query}"**에 대한 답변:\n']
            
            # 가장 관련성 높은 문서에서 핵심 정보 추출
            main_content = docs[0].page_content
            
            # 1. 핵심 요약 (첫 번째 문서에서)
            summary = self._extract_key_summary(main_content, query)
            if summary:
                response_parts.append(f"**📋 요약:**")
                response_parts.append(f"{summary}\n")
            
            # 2. 상세 정보들 (여러 문서에서)
            response_parts.append("**📚 상세 내용:**")
            
            for i, doc in enumerate(docs[:2], 1):  # 상위 2개 문서만
                source = doc.metadata.get('source', '문서')
                clean_content = self._clean_and_format_content(doc.page_content)
                
                # 300자로 제한하고 문장 단위로 자르기
                truncated = self._smart_truncate(clean_content, 300)
                
                response_parts.append(f"\n**[{i}] 출처: {source}**")
                response_parts.append(f"{truncated}")
            
            # 3. 추가 도움말
            response_parts.append("\n💡 **더 구체적인 질문**을 하시면 더 정확한 답변을 드릴 수 있어요!")
            
            return "\n".join(response_parts)
            
        except Exception as e:
            # 오류 발생시 기본 응답
            return f"관련 내용을 찾았지만 응답 생성 중 오류가 발생했습니다. 다시 질문해주세요."
    
    def _extract_key_summary(self, content, query):
        """핵심 요약 추출"""
        try:
            # 쿼리 키워드가 포함된 문장들 찾기
            sentences = self._split_into_sentences(content)
            query_words = self._extract_keywords(query.lower())
            
            relevant_sentences = []
            for sentence in sentences:
                sentence_lower = sentence.lower()
                if any(word in sentence_lower for word in query_words):
                    relevant_sentences.append(sentence.strip())
                    if len(relevant_sentences) >= 2:  # 최대 2문장
                        break
            
            if relevant_sentences:
                return " ".join(relevant_sentences)
            
            # 키워드가 포함된 문장이 없으면 첫 번째 문장 반환
            return sentences[0].strip() if sentences else None
            
        except:
            return None
    
    def _split_into_sentences(self, text):
        """텍스트를 문장으로 분할"""
        # 문장 구분자로 분할
        sentences = re.split(r'[.!?]\s+', text)
        
        # 너무 짧은 문장 제거
        valid_sentences = []
        for sentence in sentences:
            if len(sentence.strip()) > 10:  # 10자 이상인 문장만
                valid_sentences.append(sentence.strip())
        
        return valid_sentences
    
    def _clean_and_format_content(self, content):
        """내용 정리 및 포맷팅"""
        # 연속된 공백 제거
        content = re.sub(r'\s+', ' ', content)
        
        # 특수문자나 이상한 문자 정리
        content = re.sub(r'[^\w\s가-힣,.!?():\-]', '', content)
        
        # 앞뒤 공백 제거
        return content.strip()
    
    def _smart_truncate(self, text, max_length):
        """스마트한 텍스트 자르기 (문장 단위로)"""
        if len(text) <= max_length:
            return text
        
        # max_length 근처에서 문장 끝을 찾아 자르기
        truncated = text[:max_length]
        
        # 마지막 완전한 문장 찾기
        last_period = truncated.rfind('.')
        last_exclamation = truncated.rfind('!')
        last_question = truncated.rfind('?')
        
        last_sentence_end = max(last_period, last_exclamation, last_question)
        
        if last_sentence_end > max_length * 0.7:  # 70% 이상이면 문장 단위로 자르기
            return truncated[:last_sentence_end + 1]
        else:
            # 문장 끝이 너무 앞에 있으면 단어 단위로 자르기
            last_space = truncated.rfind(' ')
            if last_space > 0:
                return truncated[:last_space] + "..."
            else:
                return truncated + "..."
    
    def get_document_count(self):
        """저장된 문서 청크 개수"""
        return len(self.documents)
    
    def get_document_stats(self):
        """문서 통계 정보"""
        if not self.documents:
            return {"총 문서": 0, "평균 길이": 0}
        
        sources = {}
        total_length = 0
        
        for doc in self.documents:
            source = doc.metadata.get('source', '알 수 없음')
            sources[source] = sources.get(source, 0) + 1
            total_length += len(doc.page_content)
        
        return {
            "총 청크": len(self.documents),
            "문서 종류": len(sources),
            "평균 청크 길이": total_length // len(self.documents),
            "문서별 청크": sources
        }

# 전역 RAG 엔진 인스턴스
rag_engine = SimpleRAGEngine()