import os
from typing import List, Dict, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader, UnstructuredWordDocumentLoader
from loguru import logger

class DocumentProcessor:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )

    def process_file(self, file_path: str) -> List[Dict[str, Any]]:
        logger.info(f"Processing file: {file_path}")
        
        try:
            if file_path.endswith('.pdf'):
                loader = PyPDFLoader(file_path)
                documents = loader.load()
            elif file_path.endswith('.txt'):
                loader = TextLoader(file_path)
                documents = loader.load()
            elif file_path.endswith('.docx') or file_path.endswith('.doc'):
                from markitdown import MarkItDown
                md = MarkItDown()
                res = md.convert(file_path)
                import re
                clean_text = re.sub(r'!\[\]\(data:image\/[a-zA-Z0-9+/]+;base64,[^)]+\)', '', res.text_content)
                from langchain_core.documents import Document
                documents = [Document(page_content=clean_text, metadata={"source": file_path})]
            else:
                logger.warning(f"Unsupported file type: {file_path}")
                return []

            # Split into chunks
            chunks = self.text_splitter.split_documents(documents)
            
            processed_chunks = []
            for i, chunk in enumerate(chunks):
                processed_chunks.append({
                    "content": chunk.page_content,
                    "metadata": {
                        "source_file": os.path.basename(file_path),
                        "file_path": file_path,
                        "chunk_index": i,
                        **chunk.metadata
                    }
                })
                
            return processed_chunks
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            return []

    def process_directory(self, directory_path: str) -> List[Dict[str, Any]]:
        all_chunks = []
        for root, _, files in os.walk(directory_path):
            for file in files:
                file_path = os.path.join(root, file)
                chunks = self.process_file(file_path)
                all_chunks.extend(chunks)
                
        return all_chunks
