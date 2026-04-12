"""
RAG (Retrieval-Augmented Generation) system for HerdWatch
Enables semantic search over historical analysis logs
"""

import os
import json
from datetime import datetime
from langchain_openai import AzureOpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstore import FAISS
from dotenv import load_dotenv

load_dotenv()

# ────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────

ANALYSIS_LOG_FILE = "analysis_log.txt"
INDEX_PATH = "herd_index"

class HerdRAG:
    """Retrieval-Augmented Generation for cow analysis history"""
    
    def __init__(self):
        """Initialize RAG system with Azure OpenAI embeddings"""
        self.vectorstore = None
        self.last_indexed = 0
        self.index_path = INDEX_PATH
        self._embeddings = None
        
    @property
    def embeddings(self):
        """Lazy load embeddings to avoid initialization errors"""
        if self._embeddings is None:
            try:
                self._embeddings = AzureOpenAIEmbeddings(
                    azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME"),
                    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                    api_key=os.getenv("AZURE_OPENAI_API_KEY")
                )
            except Exception as e:
                print(f"Warning: Could not initialize embeddings: {e}")
                return None
        return self._embeddings
    
    def build_index(self, log_file=ANALYSIS_LOG_FILE):
        """
        Parse log file and build/update FAISS index
        
        Args:
            log_file: Path to analysis log file
        """
        if not os.path.exists(log_file):
            return False
        
        # Check if file has been modified since last index
        mtime = os.path.getmtime(log_file)
        if mtime <= self.last_indexed:
            return False  # No changes
        
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                entries = f.readlines()
            
            # Filter out error entries and empty lines
            clean_entries = [
                e.strip() for e in entries 
                if e.strip() and "Analysis error" not in e
            ]
            
            if not clean_entries:
                return False
            
            # Split into chunks for embedding
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=200,
                chunk_overlap=20
            )
            docs = splitter.create_documents(clean_entries)
            
            if self.embeddings is None:
                print("Warning: Embeddings not available, RAG disabled")
                return False
            
            # Build FAISS index
            self.vectorstore = FAISS.from_documents(docs, self.embeddings)
            self.vectorstore.save_local(self.index_path)
            self.last_indexed = mtime
            
            print(f"✓ Updated analysis index: {len(docs)} chunks")
            return True
            
        except Exception as e:
            print(f"Error building index: {e}")
            return False
    
    def retrieve(self, query, k=5):
        """
        Retrieve k most relevant log entries for query
        
        Args:
            query: Search query
            k: Number of results to return
            
        Returns:
            list: Document objects with page_content
        """
        if self.vectorstore is None:
            if not self.build_index():
                return []
        
        if self.vectorstore is None:
            return []
        
        try:
            return self.vectorstore.similarity_search(query, k=k)
        except Exception as e:
            print(f"Error retrieving documents: {e}")
            return []
    
    def get_context(self, query):
        """
        Return formatted context string for prompt
        
        Args:
            query: User question or search query
            
        Returns:
            str: Formatted historical context
        """
        docs = self.retrieve(query)
        
        if not docs:
            return "No historical analysis available."
        
        # Format documents for inclusion in prompt
        context_parts = []
        for i, doc in enumerate(docs, 1):
            context_parts.append(f"• {doc.page_content}")
        
        return "\n".join(context_parts)


# Global RAG instance
herd_rag = HerdRAG()

# ────────────────────────────────────────────────────────────
# Utility Functions
# ────────────────────────────────────────────────────────────

def get_historical_context(question, k=5):
    """
    Get historical analysis context for a question
    
    Args:
        question: User's question
        k: Number of historical entries to retrieve
        
    Returns:
        str: Formatted context string
    """
    try:
        herd_rag.build_index()
        return herd_rag.get_context(question)
    except Exception as e:
        print(f"Error getting context: {e}")
        return "Historical data unavailable."

def rebuild_index():
    """Force rebuild of FAISS index"""
    try:
        herd_rag.last_indexed = 0
        return herd_rag.build_index()
    except Exception as e:
        print(f"Error rebuilding index: {e}")
        return False
