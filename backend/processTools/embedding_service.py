"""
Simple embedding service that can be called by an AI agent to create embeddings for nodes.
"""

import json
from typing import Dict, Any, List, Union, Optional
from sentence_transformers import SentenceTransformer

class EmbeddingService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the embedding service with a specific model.
        
        Args:
            model_name: Name of the sentence-transformers model to use
        """
        self.model_name = model_name
        self.model = None  # Lazy loading
    
    def _ensure_model_loaded(self):
        """Ensure the model is loaded before use"""
        if self.model is None:
            print(f"Loading model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            print(f"Model loaded with dimension: {self.model.get_sentence_embedding_dimension()}")
    
    def get_text_for_embedding(self, node: Dict[str, Any], node_type: str) -> str:
        """
        Extract text content from a node based on its type.
        
        Args:
            node: The node data
            node_type: Type of the node (e.g., 'PullRequest', 'Issue', 'Message')
            
        Returns:
            Extracted text for embedding
        """
        if node_type == "PullRequest":
            return f"{node.get('title', '')} {node.get('body', '')}"
        elif node_type == "Issue":
            return f"{node.get('title', '')} {node.get('body', '')}"
        elif node_type == "Message":
            return node.get('text', '')
        else:
            # Default case: try to find common text fields
            text_fields = ['content', 'text', 'body', 'description', 'title']
            texts = []
            for field in text_fields:
                if field in node and node[field]:
                    texts.append(node[field])
            
            return " ".join(texts)
    
    def create_embedding(self, node: Dict[str, Any], node_type: str) -> List[float]:
        """
        Create an embedding for a node.
        
        Args:
            node: The node data
            node_type: Type of the node
            
        Returns:
            Embedding vector as a list of floats
        """
        self._ensure_model_loaded()
        
        text = self.get_text_for_embedding(node, node_type)
        
        if not text or text.strip() == '':
            print(f"Warning: Empty text for node {node.get('id')}")
            return [0.0] * self.model.get_sentence_embedding_dimension()
        
        embedding = self.model.encode(text)
        
        return embedding.tolist()
    
    def add_embedding_to_node(self, node: Dict[str, Any], node_type: str) -> Dict[str, Any]:
        """
        Add an embedding to a node.
        
        Args:
            node: The node data
            node_type: Type of the node
            
        Returns:
            Node with embedding added
        """
        embedding = self.create_embedding(node, node_type)
        
        updated_node = node.copy()
        updated_node['embedding'] = embedding
        
        return updated_node

if __name__ == "__main__":
    service = EmbeddingService()
    
    example_node = {
        "id": "pr-1",
        "title": "Add OAuth2 integration",
        "body": "This PR adds OAuth2 integration with Google and GitHub providers."
    }
    
    node_with_embedding = service.add_embedding_to_node(example_node, "PullRequest")
    
    print(f"Node ID: {node_with_embedding['id']}")
    print(f"Embedding dimension: {len(node_with_embedding['embedding'])}")
    print(f"First 5 values: {node_with_embedding['embedding'][:5]}")