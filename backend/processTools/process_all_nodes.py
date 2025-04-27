"""
Script to process all nodes in the mock data and add embeddings to them.
"""

import json
import os
from typing import Dict, Any, List
from embedding_service import EmbeddingService

INPUT_FILE = "mock.json"
OUTPUT_FILE = "mock_with_embeddings.json"

NODE_TYPE_MAPPING = {
    "users": "User",
    "repositories": "Repository",
    "pullRequests": "PullRequest",
    "issues": "Issue",
    "slackChannels": "Channel",
    "slackMessages": "Message",
    "textChunks": "TextChunk"
}

def load_data(file_path: str) -> Dict[str, Any]:
    """Load JSON data from file"""
    print(f"Loading data from {file_path}")
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data

def save_data(data: Dict[str, Any], file_path: str):
    """Save JSON data to file"""
    print(f"Saving data to {file_path}")
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

def process_all_nodes(data: Dict[str, Any], embedding_service: EmbeddingService) -> Dict[str, Any]:
    """Process all nodes in the data and add embeddings"""
    result = {}
    
    for collection_name, nodes in data.items():
        if collection_name in NODE_TYPE_MAPPING:
            node_type = NODE_TYPE_MAPPING[collection_name]
            print(f"Processing {len(nodes)} {node_type} nodes")
            
            processed_nodes = []
            for node in nodes:
                try:
                    node_with_embedding = embedding_service.add_embedding_to_node(node, node_type)
                    processed_nodes.append(node_with_embedding)
                except Exception as e:
                    print(f"Error processing node {node.get('id')}: {e}")
                    processed_nodes.append(node)
            
            result[collection_name] = processed_nodes
        else:
            result[collection_name] = nodes
    
    return result

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Input file {INPUT_FILE} not found")
        return
    
    data = load_data(INPUT_FILE)
    
    embedding_service = EmbeddingService()
    
    processed_data = process_all_nodes(data, embedding_service)
    
    save_data(processed_data, OUTPUT_FILE)
    
    print(f"Successfully processed data and saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()