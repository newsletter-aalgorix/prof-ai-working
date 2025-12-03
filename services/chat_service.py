"""
Chat Service - Handles RAG-based conversations and multilingual support
"""

import time
import logging
from typing import Dict, Any
import config
from services.document_service import DocumentProcessor
from services.rag_service import RAGService
from services.llm_service import LLMService
from services.sarvam_service import SarvamService

class ChatService:
    """Main chat service that coordinates RAG, translation, and LLM services."""
    
    def __init__(self):
        self.llm_service = LLMService()
        self.sarvam_service = SarvamService()
        self.document_processor = DocumentProcessor()
        self.vector_store = self._initialize_vector_store()
        
        if self.vector_store:
            self.rag_service = RAGService(self.vector_store)
            self.is_rag_active = True
            logging.info("✅ Vectorstore loaded and RAG chain initialized")
        else:
            self.rag_service = None
            self.is_rag_active = False
            logging.warning("❗ No vectorstore found. Operating in general knowledge mode")

    def _initialize_vector_store(self):
        """Initializes the vector store from ChromaDB Cloud or local FAISS."""
        try:
            if config.USE_CHROMA_CLOUD:
                from core.cloud_vectorizer import CloudVectorizer
                logging.info("Attempting to load vector store from ChromaDB Cloud...")
                cloud_vectorizer = CloudVectorizer()
                return cloud_vectorizer.get_vector_store()
            else:
                logging.info("Attempting to load vector store from local FAISS...")
                return self.document_processor.get_vectorstore()
        except Exception as e:
            logging.error(f"Failed to initialize vector store: {e}")
            return None

    def _fix_tts_pronunciation(self, text: str) -> str:
        """Fix common abbreviations for better TTS pronunciation."""
        import re
        
        replacements = {
            # AI/ML abbreviations
            r'\bA\.I\.?\b': 'Artificial Intelligence',
            r'\bAI\b': 'Artificial Intelligence',
            r'\bM\.L\.?\b': 'Machine Learning',
            r'\bML\b': 'Machine Learning',
            r'\bN\.L\.P\.?\b': 'Natural Language Processing',
            r'\bNLP\b': 'Natural Language Processing',
            r'\bA\.P\.I\.?\b': 'Application Programming Interface',
            r'\bAPI\b': 'Application Programming Interface',
            r'\bUI\b': 'User Interface',
            r'\bUX\b': 'User Experience',
            r'\bDB\b': 'Database',
            r'\bSQL\b': 'Structured Query Language',
            r'\bHTML\b': 'Hypertext Markup Language',
            r'\bCSS\b': 'Cascading Style Sheets',
            r'\bJS\b': 'JavaScript',
            r'\bRAM\b': 'Random Access Memory',
            r'\bCPU\b': 'Central Processing Unit',
            r'\bGPU\b': 'Graphics Processing Unit',
            
            # Common abbreviations
            r'\betc\.?\b': 'et cetera',
            r'\be\.g\.?\b': 'for example',
            r'\bi\.e\.?\b': 'that is',
            r'\bvs\.?\b': 'versus',
            
            # Symbols
            r'@': ' at ',
            r'&': ' and ',
            r'%': ' percent ',
        }
        
        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        return text

    async def ask_question(self, query: str, query_language_code: str = "en-IN") -> Dict[str, Any]:
        """Answer a question using RAG with multilingual support."""
        
        response_lang_name = next(
            (lang["name"] for lang in config.SUPPORTED_LANGUAGES if lang["code"] == query_language_code), 
            "English"
        )

        if self.is_rag_active:
            # Translate query to English if needed
            start_time = time.time()
            english_query = query
            if query_language_code != "en-IN":
                logging.info("[TASK] Translating query to English using Sarvam AI...")
                english_query = await self.sarvam_service.translate_text(
                    text=query,
                    source_language_code=query_language_code,
                    target_language_code="en-IN"
                )
                end_time = time.time()
                logging.info(f"  > Translation complete in {end_time - start_time:.2f}s. (Query: '{english_query}')")
            
            try:
                # Execute RAG chain
                logging.info("[TASK] Executing RAG chain...")
                start_time = time.time()
                answer = await self.rag_service.get_answer(english_query, response_lang_name)
                end_time = time.time()
                logging.info(f"  > RAG chain complete in {end_time - start_time:.2f}s.")
                
                # Fix TTS pronunciation issues
                answer = self._fix_tts_pronunciation(answer)
                
                # Check if RAG found an answer
                if "I cannot find the answer" in answer:
                    logging.info("  > RAG chain failed. Falling back to general LLM...")
                    start_time = time.time()
                    answer = await self.llm_service.get_general_response(query, response_lang_name)
                    answer = self._fix_tts_pronunciation(answer)
                    end_time = time.time()
                    logging.info(f"  > Fallback complete in {end_time - start_time:.2f}s.")
                    return {"answer": answer, "sources": ["General Knowledge Fallback"]}

                return {"answer": answer, "sources": ["Course Content"]}

            except Exception as e:
                logging.error(f"  > Error during RAG chain invocation: {e}. Falling back...")
        
        # Fallback to general knowledge
        logging.info("[TASK] Using general knowledge fallback...")
        start_time = time.time()
        answer = await self.llm_service.get_general_response(query, response_lang_name)
        answer = self._fix_tts_pronunciation(answer)
        end_time = time.time()
        logging.info(f"  > General knowledge fallback complete in {end_time - start_time:.2f}s.")
        return {"answer": answer, "sources": ["General Knowledge"]}
    
    def update_with_course_content(self, course_data: dict):
        """Update the RAG system with new course content."""
        try:
            # Extract course documents
            course_documents = self.document_processor.extract_course_documents(course_data)
            
            if course_documents:
                # Split documents
                split_course_docs = self.document_processor.split_documents(course_documents)
                
                # Add to vectorstore
                if self.vector_store:
                    self.vector_store.add_documents(split_course_docs)
                else:
                    # This case is unlikely if initialization is correct, but handled for safety
                    self.vector_store = self._initialize_vector_store()
                    if self.vector_store:
                        self.vector_store.add_documents(split_course_docs)
                        self.rag_service = RAGService(self.vector_store)
                        self.is_rag_active = True
                
                logging.info(f"✅ Added {len(split_course_docs)} course content chunks to RAG system")
                
        except Exception as e:
            logging.error(f"⚠️ Error updating RAG with course content: {e}")
            raise e