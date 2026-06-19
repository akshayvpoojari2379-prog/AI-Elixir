import os
import re
from typing import List, Dict, Any
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain_core.documents import Document
from loguru import logger

class DocumentLoader:
    def __init__(self):
        self.supported_extensions = {
            '.pdf': self._load_pdf,
            '.docx': self._load_docx,
            '.txt': self._load_txt
        }
        
    def load_directory(self, directory_path: str) -> List[Document]:
        documents = []
        for root, _, files in os.walk(directory_path):
            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file_path)[1].lower()
                
                if ext in self.supported_extensions:
                    try:
                        docs = self.supported_extensions[ext](file_path)
                        documents.extend(docs)
                        logger.info(f"Successfully loaded {file_path}")
                    except Exception as e:
                        logger.error(f"Error loading {file_path}: {str(e)}")
                        
        return documents

    def _clean_text(self, text: str) -> str:
        # Remove multiple newlines
        text = re.sub(r'\n+', '\n', text)
        # Remove multiple spaces
        text = re.sub(r' +', ' ', text)
        return text.strip()

    def _process_documents(self, docs: List[Document], doc_type: str) -> List[Document]:
        for doc in docs:
            doc.page_content = self._clean_text(doc.page_content)
            source_file = doc.metadata.get('source', '')
            category = os.path.basename(os.path.dirname(source_file))
            
            doc.metadata.update({
                'document_type': doc_type,
                'category': category,
                'source_file': source_file
            })
        return docs

    def _load_pdf(self, file_path: str) -> List[Document]:
        loader = PyPDFLoader(file_path)
        docs = loader.load()
        return self._process_documents(docs, 'PDF')

    def _load_docx(self, file_path: str) -> List[Document]:
        loader = Docx2txtLoader(file_path)
        docs = loader.load()
        return self._process_documents(docs, 'DOCX')

    def _load_txt(self, file_path: str) -> List[Document]:
        loader = TextLoader(file_path)
        docs = loader.load()
        return self._process_documents(docs, 'TXT')
