from neo4j import GraphDatabase
from neo4j_graphrag.retrievers import VectorRetriever
from neo4j_graphrag.llm import LLMInterface, LLMResponse
from neo4j_graphrag.generation import GraphRAG
from neo4j_graphrag.embeddings.sentence_transformers import SentenceTransformerEmbeddings
from neo4j_graphrag.indexes import create_vector_index
import requests
import json
import os
import sys
import re
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get Gemini API key from environment variables
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set")

# Custom Gemini LLM implementation using direct HTTP requests (no SDK)
class GeminiHttpLLM(LLMInterface):
    def __init__(self, model_name="gemini-2.0-flash", model_params=None, **kwargs):
        self.model_name = model_name
        self.model_params = model_params or {"temperature": 0.1, "maxOutputTokens": 1024}
        self.api_key = GEMINI_API_KEY
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
        
    def invoke(self, input, message_history=None, system_instruction=None):
        """
        Invoke the Gemini API using direct HTTP requests
        """
        url = f"{self.api_url}?key={self.api_key}"
        
        # Prepare messages for the API
        contents = []
        
        # Add system message if provided
        if system_instruction is None:
            system_instruction = """
            You are an AI assistant with access to a knowledge graph about developers and their contributions.
            
            Format your responses according to these guidelines:
            1. Begin with a direct and concise answer to the question.
            2. Follow with 2-3 sentences of supporting details or context.
            3. If providing technical information, highlight key technical terms.
            4. If uncertain about any part of the answer, clearly indicate what's uncertain.
            5. Keep your answer focused and avoid tangential information.
            6. When referring to a user, ALWAYS use their Github login name (not numeric IDs).
            7. If you see a numeric user ID in the context, check if there's an associated login or id field and use that instead.
            8. Format GitHub usernames with @ symbol (e.g., @username) to make them stand out.
            9. Only name 1 user at a time NEVER have more than one user in your response
            """
        
        if system_instruction:
            contents.append({
                "role": "user",
                "parts": [{"text": f"System: {system_instruction}"}]
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "I'll follow these instructions."}]
            })
        
        # Add message history if provided
        if message_history:
            for msg in message_history:
                role = "user" if msg.role == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg.content}]
                })
        
        # Add the user's query
        contents.append({
            "role": "user",
            "parts": [{"text": input}]
        })
        
        # Handle the case where we have no history (just the current query)
        if not message_history and not system_instruction:
            # For a single message, use the simpler format
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": input
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": self.model_params.get("temperature", 0.1),
                    "maxOutputTokens": self.model_params.get("maxOutputTokens", 1024),
                    "topP": self.model_params.get("topP", 0.95),
                    "topK": self.model_params.get("topK", 40)
                }
            }
        else:
            # For conversation with history, use the multi-turn format
            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": self.model_params.get("temperature", 0.1),
                    "maxOutputTokens": self.model_params.get("maxOutputTokens", 1024),
                    "topP": self.model_params.get("topP", 0.95),
                    "topK": self.model_params.get("topK", 40)
                }
            }
        
        # Make the API request
        headers = {
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            response.raise_for_status()  # Raise exception for 4XX/5XX responses
            
            response_data = response.json()
            
            # Extract the content from the response
            if "candidates" in response_data and len(response_data["candidates"]) > 0:
                candidate = response_data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    text = ""
                    for part in candidate["content"]["parts"]:
                        if "text" in part:
                            text += part["text"]
                    return LLMResponse(content=text)
            
            # If we couldn't extract a proper response
            return LLMResponse(content="Error: Unable to parse response from Gemini API")
            
        except Exception as e:
            print(f"Error calling Gemini API: {e}")
            if response and hasattr(response, 'text'):
                print(f"Response: {response.text}")
            return LLMResponse(content=f"Error: {str(e)}")

    async def ainvoke(self, input, message_history=None, system_instruction=None):
        return self.invoke(input, message_history, system_instruction)  # Synchronous fallback for async calls


def determine_best_node_type(query_text, available_node_types):
    """
    Analyzes the query text to determine which node type would be most relevant
    
    Args:
        query_text: The user's query
        available_node_types: Dict of node types with counts of available embeddings
        
    Returns:
        Tuple of (node_label, index_name, reason)
    """
    query = query_text.lower()
    
    # Define search term mappings
    node_type_keywords = {
        "PullRequest": ["pr", "pull request", "code change", "merge", "branch", "commit", "git", "repository", "repo", "developer", "contribution", "feature", "oauth", "implementation"],
        "Issue": ["issue", "bug", "ticket", "problem", "task", "feature request", "enhancement", "error", "defect", "tracker"],
        "Message": ["chat", "slack", "message", "conversation", "discussion", "said", "mentioned", "talk", "channel", "communication", "discuss"],
        "TextChunk": [] # Fallback, no specific keywords
    }
    
    # Check for highest priority node types first if they have embeddings
    if "Issue" in available_node_types and available_node_types["Issue"] > 0:
        if any(term in query for term in ["who reported", "issue reporter", "bug report", "filed an issue"]):
            return "Issue", f"issue_vector_idx", "Query specifically asks about issues"
    
    if "PullRequest" in available_node_types and available_node_types["PullRequest"] > 0:
        if any(term in query for term in ["who wrote", "who implemented", "who coded", "who developed", "oauth", "integration", "author"]):
            return "PullRequest", f"pullrequest_vector_idx", "Query asks about code authorship or implementation"
    
    if "Message" in available_node_types and available_node_types["Message"] > 0:
        if any(term in query for term in ["who said", "who mentioned", "who discussed", "who talked", "conversation", "chat", "slack"]):
            return "Message", f"message_vector_idx", "Query asks about discussions or conversations"
            
    # Count keyword matches for each node type
    scores = {node_type: 0 for node_type in available_node_types}
    
    for node_type, keywords in node_type_keywords.items():
        if node_type in available_node_types and available_node_types[node_type] > 0:
            for keyword in keywords:
                if keyword in query:
                    scores[node_type] += 1
    
    # Find the node type with the highest score
    max_score = -1
    best_node_type = None
    
    for node_type, score in scores.items():
        if score > max_score and available_node_types[node_type] > 0:
            max_score = score
            best_node_type = node_type
    
    # If we have a clear winner with matches
    if best_node_type and max_score > 0:
        return best_node_type, f"{best_node_type.lower()}_vector_idx", f"Query contains {max_score} keywords related to {best_node_type}"
    
    # If no clear winner by keywords, prioritize by data availability and generality
    for node_type in ["TextChunk", "PullRequest", "Issue", "Message"]:
        if node_type in available_node_types and available_node_types[node_type] > 0:
            return node_type, f"{node_type.lower()}_vector_idx", f"Fallback to {node_type} based on available data"
    
    # If nothing else, use TextChunk as absolute fallback
    return "TextChunk", "textchunk_vector_idx", "Default fallback"


# 1. Neo4j driver
URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "password")

EMBEDDING_PROPERTY = "embedding"  # Property where embeddings are stored
EMBEDDING_DIMENSION = 384  # Dimension for all-MiniLM-L6-v2

# Connect to Neo4j database
driver = GraphDatabase.driver(URI, auth=AUTH)

# Check Neo4j version and get available node types with embeddings
available_node_types = {}
try:
    with driver.session() as session:
        # Check Neo4j version
        result = session.run("CALL dbms.components() YIELD versions RETURN versions[0] as version")
        record = result.single()
        version = record["version"] if record else "unknown"
        print(f"Neo4j version: {version}")
        
        # List all existing indexes
        print("Checking for existing indexes...")
        result = session.run("SHOW INDEXES")
        indexes = [dict(record) for record in result]
        if indexes:
            print("Existing indexes:")
            for idx in indexes:
                print(f"  - {idx.get('name', 'unknown')} (type: {idx.get('type', 'unknown')}, labels: {idx.get('labelsOrTypes', [])})")
        else:
            print("No indexes found in the database.")
        
        # Check for nodes with embeddings for each important node type
        for node_label in ["TextChunk", "PullRequest", "Issue", "Message"]:
            result = session.run(f"MATCH (n:{node_label}) WHERE n.{EMBEDDING_PROPERTY} IS NOT NULL RETURN count(n) as count")
            record = result.single()
            count = record["count"] if record and record["count"] > 0 else 0
            available_node_types[node_label] = count
            if count > 0:
                print(f"Found {count} {node_label} nodes with embeddings.")
            else:
                print(f"No {node_label} nodes with embeddings found.")
                
except Exception as e:
    print(f"Error checking database state: {e}")

# Function to ensure a vector index exists for a given node type
def ensure_vector_index(node_label, index_name):
    print(f"\nEnsuring vector index '{index_name}' exists for {node_label} nodes...")
    try:
        # Check if index already exists
        with driver.session() as session:
            result = session.run(f"SHOW INDEXES WHERE name = '{index_name}'")
            if result.single():
                print(f"Vector index '{index_name}' already exists.")
                return True
                
        # Create the index if it doesn't exist
        create_vector_index(
            driver,
            index_name,
            label=node_label,
            embedding_property=EMBEDDING_PROPERTY,
            dimensions=EMBEDDING_DIMENSION,
            similarity_fn="cosine",
            fail_if_exists=False
        )
        print(f"Vector index '{index_name}' created successfully.")
        return True
    except Exception as e:
        print(f"Error creating vector index using neo4j_graphrag: {e}")
        print("\nTrying direct Cypher approach instead...")
        
        try:
            with driver.session() as session:
                # Try creating the index with direct Cypher for compatibility
                cypher = f"""
                CREATE VECTOR INDEX {index_name} IF NOT EXISTS
                FOR (n:{node_label})
                ON (n.{EMBEDDING_PROPERTY})
                OPTIONS {{indexConfig: {{`vector.dimensions`: {EMBEDDING_DIMENSION}, `vector.similarity_function`: 'cosine'}}}}
                """
                session.run(cypher)
                print(f"Vector index '{index_name}' created with direct Cypher.")
                return True
        except Exception as e2:
            print(f"Error creating index with direct Cypher: {e2}")
            return False

# Create embedder using SentenceTransformerEmbeddings from the library
print("\nInitializing sentence transformer embedder...")
embedder = SentenceTransformerEmbeddings(model="all-MiniLM-L6-v2")

# Query the graph function
def query_rag(query_text, top_k=500, capture_debug=None):
    """
    Query the graph using RAG and return the answer with metadata.
    
    Args:
        query_text (str): The user's query
        top_k (int): Maximum number of relevant documents to retrieve (increased from 5 to 15 for better coverage on large datasets)
        capture_debug (dict, optional): Dictionary to capture debug information
        
    Returns:
        tuple: (answer, node_type, reason) - The answer text, node type used, and reason for selection
    """
    # Determine the best node type for this query
    node_label, index_name, reason = determine_best_node_type(query_text, available_node_types)
    print(f"\nAnalyzing query: '{query_text}'")
    print(f"Selected {node_label} nodes with '{index_name}' index")
    print(f"Reason: {reason}")
    
    # Capture debug information if requested
    if capture_debug is not None:
        capture_debug["query"] = query_text
        capture_debug["selected_node_type"] = node_label
        capture_debug["index_name"] = index_name
        capture_debug["selection_reason"] = reason
        capture_debug["available_node_types"] = available_node_types
    
    # Ensure the vector index exists
    if not ensure_vector_index(node_label, index_name):
        print(f"Failed to create vector index for {node_label}. Falling back to TextChunk.")
        node_label = "TextChunk"
        index_name = "textchunk_vector_idx"
        if not ensure_vector_index(node_label, index_name):
            print("Failed to create fallback index. Cannot continue.")
            return f"Error: Unable to create necessary vector indexes.", node_label, "Failed to create index"
    
    try:
        # Initialize the retriever with the selected index name
        print(f"Initializing vector retriever with index '{index_name}'...")
        retriever = VectorRetriever(driver, index_name, embedder)
        
        # Initialize Gemini LLM with direct HTTP implementation
        print("Initializing Gemini HTTP LLM...")
        llm = GeminiHttpLLM(
            model_name="gemini-2.0-flash", 
            model_params={
                "temperature": 0.1, 
                "maxOutputTokens": 1024,
                "topP": 0.95,
                "topK": 40
            }
        )
        
        # Initialize the RAG pipeline
        print("Creating RAG pipeline...")
        rag = GraphRAG(retriever=retriever, llm=llm)
        
        # Set up a system instruction to help Gemini provide better responses
        system_instruction = """
        You are an AI assistant with access to a knowledge graph about developers and their contributions.
            
        Format your responses according to these guidelines:
        1. Begin with a direct and concise answer to the question.
        2. Follow with 2-3 sentences of supporting details or context.
        3. If providing technical information, highlight key technical terms.
        4. If uncertain about any part of the answer, clearly indicate what's uncertain.
        5. Keep your answer focused and avoid tangential information.
        6. When referring to a user, ALWAYS use their Github login name (not numeric IDs).
        7. If you see a numeric user ID in the context, check if there's an associated login or id field and use that instead.
        8. Format GitHub usernames with @ symbol (e.g., @username) to make them stand out.
        9. Only name 1 user at a time NEVER have more than one user in your response
        """
        
        # Execute the query
        print(f"Executing query...")
        # Check if the LLM accepts system instructions separately
        if hasattr(llm, 'set_system_instruction'):
            llm.set_system_instruction(system_instruction)
            
        # Instead of passing search_kwargs, we'll set the system instruction directly in the LLM
        # before calling search
        response = rag.search(
            query_text=query_text, 
            retriever_config={"top_k": top_k}
        )
        
        # Capture retrieved context if debug is enabled
        if capture_debug is not None:
            capture_debug["retrieved_docs_count"] = top_k
            # Try to extract the contexts used
            try:
                if hasattr(response, "context") and response.context:
                    capture_debug["contexts"] = response.context
                elif hasattr(response, "_context") and response._context:
                    capture_debug["contexts"] = response._context
            except Exception as e:
                capture_debug["context_extraction_error"] = str(e)
        
        return response.answer, node_label, reason
    except Exception as e:
        error_message = f"Error in RAG pipeline: {e}"
        print(error_message)
        
        if capture_debug is not None:
            capture_debug["error"] = str(e)
            
        return f"Error querying the knowledge graph: {str(e)}", node_label, "Error during query"


# Process the query if running as a script directly
if __name__ == "__main__":
    # Parse command-line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--interactive":
            print("\n--- Interactive RAG Query Mode (Gemini HTTP) ---")
            print("Type 'exit' or 'quit' to end the session")
            
            while True:
                print("\nEnter your question:")
                user_query = input("> ").strip()
                
                if user_query.lower() in ["exit", "quit", "q"]:
                    print("Exiting interactive mode.")
                    break
                    
                if not user_query:
                    continue
                    
                answer, node_type, reason = query_rag(user_query)
                print(f"\nNode type used: {node_type}")
                print(f"Reason: {reason}")
                print(f"\nAnswer: {answer}")
        else:
            # Use the first argument as a query
            query_text = " ".join(sys.argv[1:])
            answer, node_type, reason = query_rag(query_text)
            print(f"\nNode type used: {node_type}")
            print(f"Reason: {reason}")
            print(f"\nAnswer: {answer}")
    else:
        # Default query if no arguments provided
        query_text = "Who wrote the OAUTH Integration?"
        answer, node_type, reason = query_rag(query_text)
        print(f"\nNode type used: {node_type}")
        print(f"Reason: {reason}")
        print(f"\nAnswer: {answer}") 