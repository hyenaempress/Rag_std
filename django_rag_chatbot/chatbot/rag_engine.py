import os
import re
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import docx

# ChromaDB 관련 임포트
try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMADB_AVAILABLE = True
    print("ChromaDB가 사용 가능합니다.")
except ImportError:
    CHROMADB_AVAILABLE = False
    print("ChromaDB 라이브러리가 설치되지 않음. 키워드 기반 검색만 사용합니다.")

try:
    from pykospacing import spacing
    PYKOSPACING_AVAILABLE = True
except ImportError:
    PYKOSPACING_AVAILABLE = False
    print("PyKoSpacing 라이브러리가 설치되지 않음. 기본 띄어쓰기 복원 방법을 사용합니다.")

try:
    from konlpy.tag import Okt
    KONLPY_AVAILABLE = True
except ImportError:
    KONLPY_AVAILABLE = False

class HybridRAGEngine:
    def __init__(self):
        self.documents = []  # 키워드 검색용 메모리 저장
        
        # ChromaDB 초기화
        if CHROMADB_AVAILABLE:
            try:
                # 한국어 임베딩 모델 설정
                self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="jhgan/ko-sroberta-multitask"
                )
                
                # ChromaDB 클라이언트 및 컬렉션 초기화
                chroma_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db")
                self.chroma_client = chromadb.PersistentClient(path=chroma_path)
                
                # 기존 컬렉션이 있으면 가져오고, 없으면 생성
                try:
                    self.collection = self.chroma_client.get_collection(
                        name="documents",
                        embedding_function=self.embedding_fn
                    )
                    print(f"기존 ChromaDB 컬렉션을 로드했습니다. 문서 수: {self.collection.count()}")
                except:
                    self.collection = self.chroma_client.create_collection(
                        name="documents",
                        embedding_function=self.embedding_fn
                    )
                    print("새로운 ChromaDB 컬렉션을 생성했습니다.")
                
                self.use_vector_search = True
                print("하이브리드 RAG 엔진 (키워드 + 벡터 검색)을 사용합니다.")
                
            except Exception as e:
                print(f"ChromaDB 초기화 실패: {e}")
                self.use_vector_search = False
                print("키워드 기반 검색으로 폴백합니다.")
        else:
            self.use_vector_search = False
            print("간단한 키워드 기반 RAG 엔진을 사용합니다.")
    
    def add_text_document(self, text, title="문서"):
        """텍스트를 청크로 나누어 키워드 검색과 벡터DB 모두에 저장"""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,  # 더 작은 청크로 세밀하게 분할
            chunk_overlap=200,  # 오버랩 증가로 내용 누락 방지
            separators=["\n\n", "\n", ". ", "! ", "? ", "。", "，", " "]
        )
        
        doc = Document(page_content=text, metadata={"source": title})
        chunks = text_splitter.split_documents([doc])
        
        # 키워드 검색용 메모리 저장
        self.documents.extend(chunks)
        
        # ChromaDB에 벡터로 저장
        if self.use_vector_search:
            try:
                documents_text = [chunk.page_content for chunk in chunks]
                metadatas = [chunk.metadata for chunk in chunks]
                ids = [f"{title}_{i}_{hash(chunk.page_content) % 10000}" for i, chunk in enumerate(chunks)]
                
                self.collection.add(
                    documents=documents_text,
                    metadatas=metadatas,
                    ids=ids
                )
                print(f"{len(chunks)}개 청크를 ChromaDB에 추가했습니다.")
            except Exception as e:
                print(f"ChromaDB 저장 오류: {e}")
        
        return len(chunks)
    
    def add_file_document(self, file_path):
        """파일을 로드하여 키워드 검색과 벡터DB 모두에 저장"""
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
                chunk_size=500,  # 더 작은 청크로 세밀하게 분할
                chunk_overlap=200,  # 오버랩 증가로 내용 누락 방지
                separators=["\n\n", "\n", ". ", "! ", "? ", "。", "，", " "]
            )
            chunks = text_splitter.split_documents(documents)
            
            # 키워드 검색용 메모리 저장
            self.documents.extend(chunks)
            
            # ChromaDB에 벡터로 저장
            if self.use_vector_search:
                try:
                    documents_text = [chunk.page_content for chunk in chunks]
                    metadatas = [chunk.metadata for chunk in chunks]
                    filename = os.path.basename(file_path)
                    ids = [f"{filename}_{i}_{hash(chunk.page_content) % 10000}" for i, chunk in enumerate(chunks)]
                    
                    self.collection.add(
                        documents=documents_text,
                        metadatas=metadatas,
                        ids=ids
                    )
                    print(f"파일 '{filename}'에서 {len(chunks)}개 청크를 ChromaDB에 추가했습니다.")
                except Exception as e:
                    print(f"ChromaDB 저장 오류: {e}")
            
            return True, f"{len(chunks)}개 청크가 추가되었습니다."
            
        except Exception as e:
            return False, f"파일 처리 중 오류: {str(e)}"
    
    def search_documents(self, query, k=5):
        """하이브리드 검색: 키워드 검색 + 벡터 검색 결합"""
        if self.use_vector_search:
            return self._hybrid_search(query, k)
        else:
            return self._keyword_search_only(query, k)
    
    def _hybrid_search(self, query, k=5):
        """키워드 검색과 벡터 검색을 결합한 하이브리드 검색"""
        print(f"하이브리드 검색 실행: '{query}'")
        
        # 1. 벡터 검색 (의미적 유사성)
        vector_results = []
        try:
            chroma_results = self.collection.query(
                query_texts=[query],
                n_results=k*2,  # 더 많은 후보 확보
                include=['documents', 'metadatas', 'distances']
            )
            
            if chroma_results['documents'] and chroma_results['documents'][0]:
                for i, (doc_text, metadata, distance) in enumerate(zip(
                    chroma_results['documents'][0],
                    chroma_results['metadatas'][0],
                    chroma_results['distances'][0]
                )):
                    # 거리를 유사도 점수로 변환 (거리가 작을수록 유사도 높음)
                    similarity_score = 1.0 / (1.0 + distance)
                    doc_obj = Document(page_content=doc_text, metadata=metadata)
                    vector_results.append((doc_obj, similarity_score, 'vector'))
                    
                print(f"벡터 검색 결과: {len(vector_results)}개")
            
        except Exception as e:
            print(f"벡터 검색 오류: {e}")
        
        # 2. 키워드 검색 (기존 방식)
        keyword_results = []
        if self.documents:
            query_words = self._extract_keywords(query.lower())
            print(f"검색 키워드: {query_words}")
            
            for doc in self.documents:
                content = doc.page_content.lower()
                score = self._calculate_relevance_score(content, query_words, query.lower())
                
                if score > 0:
                    # 키워드 점수를 0-1 범위로 정규화
                    normalized_score = min(score / 100.0, 1.0)
                    keyword_results.append((doc, normalized_score, 'keyword'))
            
            print(f"키워드 검색 결과: {len(keyword_results)}개")
        
        # 3. 결과 결합 및 중복 제거
        combined_results = self._combine_search_results(vector_results, keyword_results, k)
        
        # 디버그 출력
        if combined_results:
            print(f"최종 하이브리드 결과 ({len(combined_results)}개):")
            for i, (doc, final_score, sources) in enumerate(combined_results[:3]):
                preview = doc.page_content[:80].replace('\n', ' ')
                print(f"  {i+1}. 점수: {final_score:.3f} ({sources}) - {preview}...")
        
        return [doc for doc, score, sources in combined_results]
    
    def _keyword_search_only(self, query, k=5):
        """키워드 기반 검색만 사용 (기존 방식)"""
        if not self.documents:
            return []
        
        query_words = self._extract_keywords(query.lower())
        print(f"[DEBUG] 검색 키워드: {query_words}")
        scored_docs = []
        
        for doc in self.documents:
            content = doc.page_content.lower()
            score = self._calculate_relevance_score(content, query_words, query.lower())
            
            if score > 0:
                scored_docs.append((doc, score))
        
        # 점수순 정렬 후 상위 k개 반환
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        # 디버그: 상위 3개 결과 출력
        if scored_docs:
            print(f"[DEBUG] 상위 {min(3, len(scored_docs))}개 검색 결과:")
            for i, (doc, score) in enumerate(scored_docs[:3]):
                preview = doc.page_content[:100].replace('\n', ' ')
                print(f"  {i+1}. 점수: {score}, 내용: {preview}...")
        
        return [doc for doc, score in scored_docs[:k]]
    
    def _combine_search_results(self, vector_results, keyword_results, k):
        """벡터 검색과 키워드 검색 결과를 스마트하게 결합"""
        # 문서 내용으로 중복 제거를 위한 딕셔너리
        doc_scores = {}
        
        # 벡터 검색 결과 처리 (가중치: 0.6)
        for doc, score, source in vector_results:
            content_hash = hash(doc.page_content)
            if content_hash not in doc_scores:
                doc_scores[content_hash] = {
                    'doc': doc,
                    'vector_score': score * 0.6,
                    'keyword_score': 0.0,
                    'sources': set()
                }
            else:
                doc_scores[content_hash]['vector_score'] = max(
                    doc_scores[content_hash]['vector_score'], 
                    score * 0.6
                )
            doc_scores[content_hash]['sources'].add('벡터')
        
        # 키워드 검색 결과 처리 (가중치: 0.4)
        for doc, score, source in keyword_results:
            content_hash = hash(doc.page_content)
            if content_hash not in doc_scores:
                doc_scores[content_hash] = {
                    'doc': doc,
                    'vector_score': 0.0,
                    'keyword_score': score * 0.4,
                    'sources': set()
                }
            else:
                doc_scores[content_hash]['keyword_score'] = max(
                    doc_scores[content_hash]['keyword_score'], 
                    score * 0.4
                )
            doc_scores[content_hash]['sources'].add('키워드')
        
        # 최종 점수 계산 및 정렬
        final_results = []
        for content_hash, data in doc_scores.items():
            # 하이브리드 점수: 벡터 점수 + 키워드 점수 + 결합 보너스
            final_score = data['vector_score'] + data['keyword_score']
            
            # 두 방법 모두에서 찾은 경우 보너스 (높은 신뢰도)
            if len(data['sources']) > 1:
                final_score *= 1.2
            
            sources_str = '+'.join(sorted(data['sources']))
            final_results.append((data['doc'], final_score, sources_str))
        
        # 점수순으로 정렬하여 상위 k개 반환
        final_results.sort(key=lambda x: x[1], reverse=True)
        return final_results[:k]
    
    def _extract_keywords(self, query):
        """쿼리에서 의미있는 키워드 추출 (개선된 버전)"""
        # 불용어 제거 (질문 단어는 제외)
        stop_words = {
            '이', '그', '저', '의', '가', '을', '를', '에', '와', '과', '으로', '로',
            '은', '는', '이다', '다', '하다', '되다', '있다', '없다', '같다',
            '지', '까', '니', '냐', '야', '어', '아', '요', '에요',
            'what', 'is', 'are', 'the', 'a', 'an', 'and', 'or', 'but'
        }
        
        # 질문 단어들 (의미가 있는 경우가 많음)
        question_words = {'뭐', '뭔', '뭐야', '무엇', '어떤', '어디', '언제', '왜', '어떻게'}
        
        words = query.split()
        meaningful_words = []
        
        for word in words:
            # 정리된 단어 생성
            clean_word = word.rstrip('지?!.,').lower()
            
            # 3글자 이상이면 항상 포함 (핵심 키워드일 가능성 높음)
            if len(clean_word) >= 3:
                meaningful_words.append(clean_word)
            # 2글자이고 불용어가 아닌 경우
            elif len(clean_word) == 2 and clean_word not in stop_words:
                meaningful_words.append(clean_word)
            # 질문 단어인 경우 (컨텍스트에 따라 의미가 있을 수 있음)
            elif clean_word in question_words and len(meaningful_words) == 0:
                meaningful_words.append(clean_word)
        
        # 최소 하나의 키워드는 있어야 함
        if not meaningful_words and words:
            # 가장 긴 단어를 선택
            longest_word = max(words, key=len).rstrip('지?!.,').lower()
            if len(longest_word) > 0:
                meaningful_words.append(longest_word)
        
        return meaningful_words
    
    def _calculate_relevance_score(self, content, keywords, full_query):
        """관련성 점수 계산 (개선된 알고리즘)"""
        score = 0
        
        # 1. 완전한 구문 일치 (가장 높은 점수)
        if full_query in content:
            score += len(full_query) * 5
        
        # 2. 개별 키워드 점수 (키워드 중요도 가중치 적용)
        for keyword in keywords:
            if keyword in content:
                # 키워드 빈도
                frequency = content.count(keyword)
                
                # 키워드 길이에 따른 가중치 (긴 키워드가 더 중요)
                length_weight = len(keyword)
                
                # 핵심 키워드 보너스 (5글자 이상은 매우 중요한 키워드로 간주)
                if len(keyword) >= 5:
                    keyword_score = frequency * length_weight * 10  # 높은 가중치
                elif len(keyword) >= 3:
                    keyword_score = frequency * length_weight * 3
                else:
                    keyword_score = frequency * length_weight * 1
                    
                score += keyword_score
                
                # 키워드가 문장 시작 부분에 있으면 추가 점수
                if content[:50].count(keyword) > 0:
                    score += length_weight * 5
        
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
        """RAG 기반 응답 생성 (안전한 버전)"""
        try:
            relevant_docs = self.search_documents(query, k=5)  # 더 많은 문서 검색
            
            if not relevant_docs:
                return "죄송합니다. 관련된 문서를 찾을 수 없습니다."
            
            # 특정 키워드에 대해 구조화된 응답 생성
            if self._should_generate_structured_response(query):
                return self._generate_structured_response(query, relevant_docs)
            else:
                # 일반적인 응답 생성
                return self._generate_safe_response(query, relevant_docs)
            
        except Exception as e:
            print(f"RAG 응답 생성 오류: {e}")
            return f"검색은 완료했지만 응답 처리 중 문제가 발생했습니다. 오류: {str(e)}"
    
    def _should_generate_structured_response(self, query):
        """구조화된 응답이 필요한지 판단"""
        query_lower = query.lower()
        
        # 정의, 개념, 설명을 요구하는 질문들
        definition_keywords = ['뭐야', '뭔가', '무엇', '뭐지', '뭐임', '이란', '란', 
                             'what is', 'what are', '개념', '정의', '설명']
        
        return any(keyword in query_lower for keyword in definition_keywords)
    
    def _generate_structured_response(self, query, docs):
        """구조화된 요약 응답 생성"""
        try:
            # 키워드 추출
            keywords = self._extract_keywords(query.lower())
            main_keyword = keywords[0] if keywords else query.split()[0]
            
            # 문서에서 관련 정보 추출
            content_sections = self._extract_structured_info(docs, main_keyword)
            
            # 구조화된 응답 생성
            response_parts = [f'**{main_keyword.upper()}**\n']
            
            if content_sections['definition']:
                response_parts.append("**정의:**")
                response_parts.append(content_sections['definition'])
                response_parts.append("")
            
            if content_sections['features']:
                response_parts.append("**주요 특징:**")
                for feature in content_sections['features'][:5]:  # 최대 5개
                    response_parts.append(f"• {feature}")
                response_parts.append("")
            
            if content_sections['advantages']:
                response_parts.append("**장점:**")
                for advantage in content_sections['advantages'][:4]:  # 최대 4개
                    response_parts.append(f"• {advantage}")
                response_parts.append("")
            
            if content_sections['process']:
                response_parts.append("**과정/방법:**")
                for i, step in enumerate(content_sections['process'][:5], 1):  # 최대 5단계
                    response_parts.append(f"{i}. {step}")
                response_parts.append("")
            
            # 출처 표시
            sources = list(set([doc.metadata.get('source', '문서') for doc in docs[:2]]))
            source_names = [s.split('\\')[-1] if '\\' in s else s for s in sources]
            response_parts.append(f"**출처:** {', '.join(source_names)}")
            
            return "\n".join(response_parts)
            
        except Exception as e:
            print(f"구조화된 응답 생성 오류: {e}")
            # 오류 시 일반 응답으로 폴백
            return self._generate_safe_response(query, docs)
    
    def _extract_structured_info(self, docs, keyword):
        """문서에서 구조화된 정보 추출"""
        sections = {
            'definition': '',
            'features': [],
            'advantages': [],
            'process': []
        }
        
        # 모든 문서 내용 결합
        combined_text = '\n'.join([doc.page_content for doc in docs])
        
        # 띄어쓰기 복원
        combined_text = self.restore_korean_spacing(combined_text)
        
        # 문장 단위로 분리
        sentences = self._split_into_sentences(combined_text)
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            
            # 정의 추출
            if keyword in sentence_lower and any(word in sentence_lower for word in ['는', '란', '이란', '정의', '개념']):
                if not sections['definition'] and len(sentence) > 20:
                    sections['definition'] = sentence.strip()
            
            # 특징 추출
            if any(word in sentence_lower for word in ['특징', '기능', '역할', '수행', '가능', '제공']):
                feature = self._clean_bullet_point(sentence)
                if feature and len(feature) > 10:
                    sections['features'].append(feature)
            
            # 장점 추출
            if any(word in sentence_lower for word in ['장점', '이점', '강점', '우수', '효과', '개선', '향상', '감소']):
                advantage = self._clean_bullet_point(sentence)
                if advantage and len(advantage) > 10:
                    sections['advantages'].append(advantage)
            
            # 과정/단계 추출
            if any(word in sentence_lower for word in ['단계', '과정', '먼저', '다음', '이후', '최종', '순서']):
                process = self._clean_bullet_point(sentence)
                if process and len(process) > 10:
                    sections['process'].append(process)
        
        # 중복 제거
        sections['features'] = list(dict.fromkeys(sections['features']))
        sections['advantages'] = list(dict.fromkeys(sections['advantages']))
        sections['process'] = list(dict.fromkeys(sections['process']))
        
        return sections
    
    def _clean_bullet_point(self, text):
        """텍스트를 깔끔한 불릿 포인트로 정리"""
        # 불필요한 기호 제거
        text = re.sub(r'^[•·\-▪▫◦※]+\s*', '', text.strip())
        text = re.sub(r'^\d+[\.\)]\s*', '', text)  # 번호 제거
        
        # 너무 긴 텍스트는 잘라내기
        if len(text) > 100:
            text = text[:100] + '...'
        
        return text.strip()
    
    def _generate_safe_response(self, query, docs):
        """안전한 응답 생성 (개선된 버전)"""
        try:
            response_parts = [f'**"{query}"**에 대한 답변:\n']
            
            # 최대 2개의 관련 문서 사용
            num_docs_to_use = min(2, len(docs))
            combined_content = []
            sources = []
            
            for i in range(num_docs_to_use):
                doc = docs[i]
                content = doc.page_content
                source = doc.metadata.get('source', '문서')
                
                # 텍스트 정리
                clean_content = self._simple_clean_text(content)
                
                # 각 문서에서 500자씩 가져오기
                if len(clean_content) > 500:
                    clean_content = clean_content[:500]
                
                combined_content.append(clean_content)
                if source not in sources:
                    sources.append(source)
            
            # 출처 표시
            if sources:
                source_names = [s.split('\\')[-1] if '\\' in s else s for s in sources]
                response_parts.append(f"**출처:** {', '.join(source_names[:2])}")
            
            # 내용 결합 (최대 800자)
            full_content = '\n\n'.join(combined_content)
            if len(full_content) > 800:
                full_content = full_content[:800] + "..."
            
            response_parts.append(f"**내용:**\n{full_content}")
            
            # 추가 안내
            if len(docs) > 2:
                response_parts.append(f"\n추가로 {len(docs)-2}개의 관련 문서가 더 있습니다.")
            
            response_parts.append("\n더 구체적인 질문을 해주시면 더 정확한 답변을 드릴게요!")
            
            return "\n".join(response_parts)
            
        except Exception as e:
            print(f"안전한 응답 생성 오류: {e}")
            # 최후의 수단 - 아주 간단한 응답
            try:
                content = docs[0].page_content[:200] + "..."
                return f'**"{query}"**에 대한 답변:\n\n{content}\n\n더 자세한 내용이 필요하시면 다시 질문해주세요!'
            except:
                return "문서를 찾았지만 응답을 생성하는 중 오류가 발생했습니다."
    
    def _simple_clean_text(self, text):
        """간단한 텍스트 정리 (띄어쓰기 복원 포함)"""
        try:
            # 기본 정리
            text = re.sub(r'\s+', ' ', text)  # 연속 공백 제거
            text = text.strip()
            
            # 고급 띄어쓰기 복원 함수 사용
            text = self.restore_korean_spacing(text)
            
            return text
        except Exception as e:
            print(f"텍스트 정리 중 오류: {e}")
            # 오류 발생시 기본 띄어쓰기만 적용
            text = re.sub(r'([.!?])([가-힣A-Za-z])', r'\1 \2', text)
            text = re.sub(r'([A-Za-z])([가-힣])', r'\1 \2', text)
            text = re.sub(r'([가-힣])([A-Za-z])', r'\1 \2', text)
            return text
    
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
        """내용 정리 및 포맷팅 (띄어쓰기 복원 포함)"""
        # 1. 기본 정리
        content = re.sub(r'\s+', ' ', content)
        content = re.sub(r'[^\w\s가-힣,.!?():\-]', '', content)
        content = content.strip()
        
        # 2. 띄어쓰기 복원 (개선된 함수 사용)
        content = self.restore_korean_spacing(content)
        
        return content
    
    def restore_korean_spacing(self, text):
        """한국어 띄어쓰기 복원 함수 - 3단계 접근법"""
        if not text or len(text.strip()) == 0:
            return text
            
        try:
            # 1단계: PyKoSpacing 사용 (가장 좋은 품질)
            if PYKOSPACING_AVAILABLE:
                return spacing(text)
            
            # 2단계: KoNLPy 사용 (형태소 분석 기반)
            elif KONLPY_AVAILABLE:
                return self._restore_spacing_with_konlpy(text)
            
            # 3단계: 패턴 매칭 기반 (라이브러리 없이)
            else:
                return self._restore_spacing_with_patterns(text)
                
        except Exception as e:
            print(f"띄어쓰기 복원 오류: {e}")
            return self._restore_spacing_with_patterns(text)
    
    def _restore_spacing_with_konlpy(self, text):
        """KoNLPy를 사용한 띄어쓰기 복원"""
        try:
            okt = Okt()
            
            # 형태소 분석 후 띄어쓰기 적용 (normalize, stem 파라미터 제거)
            morphs = okt.morphs(text)
            pos_tags = okt.pos(text)
            
            spaced_text = ""
            for i, (morph, pos) in enumerate(pos_tags):
                if i == 0:
                    spaced_text += morph
                else:
                    # 조사, 어미, 접미사는 붙여쓰고 나머지는 띄어쓰기
                    if pos in ['Josa', 'Eomi', 'Suffix']:
                        spaced_text += morph
                    else:
                        spaced_text += " " + morph
            
            return spaced_text
            
        except Exception as e:
            print(f"KoNLPy 처리 중 오류: {e}")
            return self._restore_spacing_with_patterns(text)
    
    def _restore_spacing_with_patterns(self, text):
        """패턴 매칭을 사용한 띄어쓰기 복원 (라이브러리 없이)"""
        if not text:
            return text
        
        # 기본 정리
        text = re.sub(r'\s+', ' ', text).strip()
        
        patterns = [
            # 문장부호 뒤에 띄어쓰기
            (r'([.!?])([가-힣A-Za-z0-9])', r'\1 \2'),
            (r'([,;:])([가-힣A-Za-z0-9])', r'\1 \2'),
            
            # 숫자와 문자 사이
            (r'([0-9])([가-힣])', r'\1 \2'),
            (r'([가-힣])([0-9])', r'\1 \2'),
            
            # 영어와 한글 사이
            (r'([A-Za-z])([가-힣])', r'\1 \2'),
            (r'([가-힣])([A-Za-z])', r'\1 \2'),
            
            # 자주 사용되는 단어들 뒤
            (r'(이다|하다|되다|있다|없다|같다|이며|라고|이라고|한다|된다)([가-힣])', r'\1 \2'),
            (r'(그리고|하지만|그러나|또한|따라서|즉|예를들어|때문에)([가-힣])', r'\1 \2'),
            (r'(경우에|관련하여|대하여|통하여|위하여|의하여)([가-힣])', r'\1 \2'),
            
            # 기술용어와 한글 사이
            (r'(AI|ML|LLM|RAG|API|GPU|CPU|NLP|CNN|RNN|IoT|VR|AR)([가-힣])', r'\1 \2'),
            (r'([가-힣])(AI|ML|LLM|RAG|API|GPU|CPU|NLP|CNN|RNN|IoT|VR|AR)', r'\1 \2'),
            
            # 조사 앞뒤 처리 (조심스럽게)
            (r'([가-힣])(은는이가을를에서의로와과도만큼부터까지마다에게께서)([가-힣A-Z])', r'\1\2 \3'),
            
        ]
        
        result = text
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result)
        
        # 긴 한글 단어 분할 (별도 처리)
        result = self._split_long_korean_words(result)
        
        # 최종 정리
        result = re.sub(r'\s+', ' ', result)
        result = re.sub(r' +([,.!?;:])', r'\1', result)
        
        return result.strip()
    
    def _split_long_korean_words(self, text):
        """긴 한글 단어들을 분할"""
        def split_word(match):
            word = match.group(0)
            if len(word) <= 8:
                return word
                
            # 15자 이상이면 3등분
            if len(word) > 15:
                third = len(word) // 3
                return word[:third] + ' ' + word[third:2*third] + ' ' + word[2*third:]
            # 8자 이상이면 반으로
            else:
                half = len(word) // 2
                return word[:half] + ' ' + word[half:]
        
        # 8자 이상 연속된 한글 단어 찾아서 분할
        return re.sub(r'[가-힣]{8,}', split_word, text)
    
    def _smart_split_word(self, word):
        """긴 단어를 스마트하게 분할 (호환성을 위해 유지)"""
        if len(word) <= 8:
            return word
            
        # 15자 이상이면 3등분
        if len(word) > 15:
            third = len(word) // 3
            return word[:third] + ' ' + word[third:2*third] + ' ' + word[2*third:]
        # 8자 이상이면 반으로
        else:
            half = len(word) // 2
            return word[:half] + ' ' + word[half:]

    def _restore_spacing_advanced(self, text):
        """고급 띄어쓰기 복원 (기존 함수 유지 - 호환성을 위해)"""
        return self.restore_korean_spacing(text)
    
    def _restore_spacing_enhanced(self, text):
        """강화된 띄어쓰기 복원 (라이브러리 없이) - 한국어 특화"""
        if not text or len(text) < 2:
            return text
        
        # 1. 기본 정리
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 2. 한국어 띄어쓰기 패턴들 (실전 특화)
        patterns = [
            # 마침표, 느낌표, 물음표 뒤
            (r'([.!?])([가-힣A-Za-z가-힣])', r'\1 \2'),
            (r'([,;:])([가-힣A-Za-z])', r'\1 \2'),
            
            # 숫자와 한글 사이
            (r'([0-9])([가-힣])', r'\1 \2'),
            (r'([가-힣])([0-9])', r'\1 \2'),
            
            # 영어와 한글 사이  
            (r'([A-Za-z])([가-힣])', r'\1 \2'),
            (r'([가-힣])([A-Za-z])', r'\1 \2'),
            
            # 중요: 자주 등장하는 단어들 뒤에 띄어쓰기
            (r'(이다|하다|되다|있다|없다|같다|이며|라고|이라고)([가-힣])', r'\1 \2'),
            (r'(그리고|하지만|그러나|또한|따라서|즉|예를들어)([가-힣])', r'\1 \2'),
            (r'(때문에|경우에|관련하여|대하여|통하여)([가-힣])', r'\1 \2'),
            
            # 기술용어 분리
            (r'(LLM|RAG|AI|ML|API|GPU|CPU|NLP|CNN|RNN)([가-힣])', r'\1 \2'),
            (r'([가-힣])(LLM|RAG|AI|ML|API|GPU|CPU|NLP|CNN|RNN)', r'\1 \2'),
            
            # 특정 패턴 - 실제 문서에서 자주 보이는 것들
            (r'([가-힣])([CDEFGHIJKLMNOPQRSTUVWXYZ가-힣]{2,})', r'\1 \2'),
            (r'(을수|를수|에대해|에관해|로부터)([가-힣])', r'\1 \2'),
            
            # 조사 앞뒤 (조심스럽게)
            (r'([가-힣])(은는이가을를에서의로와과도만큼부터까지마다)([가-힣A-Z])', r'\1\2 \3'),
        ]
        
        result = text
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result)
        
        # 3. 특별히 긴 단어들 처리 (문서에서 자주 보이는 패턴)
        result = self._break_long_words(result)
        
        # 4. 정리
        result = re.sub(r'\s+', ' ', result)
        result = re.sub(r' +([,.!?;:])', r'\1', result)
        
        return result.strip()
    
    def _break_long_words(self, text):
        """과도하게 긴 연속 단어들을 적절히 분할"""
        # 10자 이상 연속된 한글을 찾아서 중간에 띄어쓰기 추가
        def split_long_korean(match):
            word = match.group(0)
            if len(word) > 15:  # 15자 이상이면 3등분
                third = len(word) // 3
                return word[:third] + ' ' + word[third:2*third] + ' ' + word[2*third:]
            elif len(word) > 8:  # 8자 이상이면 반으로
                half = len(word) // 2
                return word[:half] + ' ' + word[half:]
            return word
        
        # 연속된 한글 패턴 찾기
        text = re.sub(r'[가-힣]{8,}', split_long_korean, text)
        
        return text
    
    def _restore_spacing(self, text):
        """띄어쓰기 복원 함수"""
        if not text:
            return text
        
        # 한국어 띄어쓰기 패턴 적용
        patterns = [
            # 조사 앞에 띄어쓰기
            (r'([가-힣])([은는이가을를에서와과로으로의])([가-힣])', r'\1\2 \3'),
            
            # 마침표, 물음표, 느낌표 뒤에 띄어쓰기  
            (r'([.!?])([가-힣A-Za-z])', r'\1 \2'),
            
            # 쉼표 뒤에 띄어쓰기
            (r'([,])([가-힣A-Za-z])', r'\1 \2'),
            
            # 숫자와 한글 사이
            (r'([0-9])([가-힣])', r'\1 \2'),
            (r'([가-힣])([0-9])', r'\1 \2'),
            
            # 영어와 한글 사이
            (r'([A-Za-z])([가-힣])', r'\1 \2'),
            (r'([가-힣])([A-Za-z])', r'\1 \2'),
            
            # 특정 단어들 뒤에 띄어쓰기
            (r'(이다|있다|없다|하다|되다|같다)([가-힣])', r'\1 \2'),
            (r'(그리고|하지만|그러나|따라서|또한)([가-힣])', r'\1 \2'),
            
            # 자주 사용되는 접속어들
            (r'(LLM|RAG|AI|ML)([가-힣])', r'\1 \2'),
            (r'([가-힣])(LLM|RAG|AI|ML)', r'\1 \2'),
        ]
        
        result = text
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result)
        
        # 과도한 띄어쓰기 정리
        result = re.sub(r'\s+', ' ', result)
        
    def _restore_spacing_advanced(self, text):
        """고급 띄어쓰기 복원 (라이브러리 사용)"""
        try:
            # python-spacing 라이브러리 사용 (설치된 경우)
            from spacing import spacing
            return spacing(text)
        except ImportError:
            try:
                # khaiii 사용 (설치된 경우)
                from khaiii import KhaiiiApi
                api = KhaiiiApi()
                spaced_text = ""
                
                for word in api.analyze(text):
                    spaced_text += word.lex + " "
                
                return spaced_text.strip()
            except ImportError:
                # 라이브러리가 없으면 기본 방법 사용
                return self._restore_spacing(text)
        except Exception:
            # 오류 발생시 기본 방법 사용
            return self._restore_spacing(text)
    
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

    def migrate_existing_documents_to_chroma(self):
        """기존 메모리 문서들을 ChromaDB로 마이그레이션"""
        if not self.use_vector_search:
            print("ChromaDB가 비활성화되어 있어 마이그레이션을 건너뜁니다.")
            return False, "ChromaDB 비활성화"
        
        if not self.documents:
            print("마이그레이션할 문서가 없습니다.")
            return True, "마이그레이션할 문서 없음"
        
        try:
            # 기존 ChromaDB 컬렉션 내용 확인
            existing_count = self.collection.count()
            print(f"기존 ChromaDB 문서 수: {existing_count}")
            
            # 중복 방지를 위해 기존 문서 해시 수집
            existing_hashes = set()
            if existing_count > 0:
                existing_docs = self.collection.get()
                for doc_text in existing_docs['documents']:
                    existing_hashes.add(hash(doc_text))
            
            # 새로 추가할 문서들 필터링
            new_documents = []
            new_metadatas = []
            new_ids = []
            
            for i, doc in enumerate(self.documents):
                doc_hash = hash(doc.page_content)
                if doc_hash not in existing_hashes:
                    new_documents.append(doc.page_content)
                    new_metadatas.append(doc.metadata)
                    source_name = doc.metadata.get('source', 'unknown')
                    new_ids.append(f"migrated_{source_name}_{i}_{doc_hash % 10000}")
            
            if new_documents:
                self.collection.add(
                    documents=new_documents,
                    metadatas=new_metadatas,
                    ids=new_ids
                )
                print(f"{len(new_documents)}개 문서를 ChromaDB로 마이그레이션 완료!")
                return True, f"{len(new_documents)}개 문서 마이그레이션 완료"
            else:
                print("모든 문서가 이미 ChromaDB에 존재합니다.")
                return True, "중복 없음 - 마이그레이션 생략"
                
        except Exception as e:
            error_msg = f"마이그레이션 중 오류 발생: {str(e)}"
            print(error_msg)
            return False, error_msg
    
    def get_chroma_stats(self):
        """ChromaDB 통계 정보 반환"""
        if not self.use_vector_search:
            return {"status": "ChromaDB 비활성화"}
        
        try:
            count = self.collection.count()
            return {
                "status": "활성화",
                "총 벡터 문서 수": count,
                "컬렉션 이름": "documents",
                "임베딩 모델": "jhgan/ko-sroberta-multitask"
            }
        except Exception as e:
            return {"status": f"오류: {str(e)}"}

# 전역 RAG 엔진 인스턴스 (하이브리드 엔진으로 업그레이드)
rag_engine = HybridRAGEngine()