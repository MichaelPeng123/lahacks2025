"""
Neo4j service to handle interactions with the Neo4j graph database.
"""

from neo4j import GraphDatabase
from typing import Dict, List, Any, Optional, Tuple
import logging

class Neo4jService:
    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize the Neo4j service.
        
        Args:
            uri: Neo4j connection URI (e.g., "neo4j://localhost:7687")
            user: Neo4j username
            password: Neo4j password
        """
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None
        self.logger = logging.getLogger(__name__)
    
    def connect(self):
        """Establish connection to Neo4j database"""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self.logger.info(f"Connected to Neo4j at {self.uri}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to Neo4j: {e}")
            return False
    
    def close(self):
        """Close the Neo4j connection"""
        if self.driver:
            self.driver.close()
            self.driver = None
            self.logger.info("Disconnected from Neo4j")
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
    
    def test_connection(self) -> int:
        """Test the Neo4j connection and return node count"""
        if not self.driver:
            if not self.connect():
                return -1
        
        try:
            with self.driver.session() as session:
                result = session.run("MATCH (n) RETURN count(n) AS count")
                record = result.single()
                return record["count"] if record else 0
        except Exception as e:
            self.logger.error(f"Error testing connection: {e}")
            return -1
    
    def create_constraints(self):
        """Create necessary constraints for the knowledge graph"""
        if not self.driver:
            if not self.connect():
                return False
        
        constraints = [
            "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
            "CREATE CONSTRAINT repo_id IF NOT EXISTS FOR (r:Repository) REQUIRE r.id IS UNIQUE",
            "CREATE CONSTRAINT pr_id IF NOT EXISTS FOR (p:PullRequest) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT issue_id IF NOT EXISTS FOR (i:Issue) REQUIRE i.id IS UNIQUE",
            "CREATE CONSTRAINT channel_id IF NOT EXISTS FOR (c:Channel) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT message_id IF NOT EXISTS FOR (m:Message) REQUIRE m.id IS UNIQUE",
            "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:TextChunk) REQUIRE c.id IS UNIQUE"
        ]
        
        success = True
        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                    self.logger.info(f"Created constraint: {constraint}")
                except Exception as e:
                    self.logger.error(f"Error creating constraint: {e}")
                    success = False
        
        return success
    
    def create_vector_index(self, label: str, property_name: str = "embedding", dimension: int = 384):
        """
        Create a vector index for a node label and property.
        
        Args:
            label: Node label to index (e.g., "PullRequest")
            property_name: Name of the vector property (default: "embedding")
            dimension: Dimension of the vector (default: 384 for all-MiniLM-L6-v2)
        """
        if not self.driver:
            if not self.connect():
                return False
        
        # Check Neo4j version - vector indexes are available in Neo4j 5.11+
        try:
            with self.driver.session() as session:
                result = session.run("CALL dbms.components() YIELD versions RETURN versions[0] as version")
                record = result.single()
                version = record["version"] if record else "0.0.0"
                
                major, minor, _ = map(int, version.split('.', 2))
                if major < 5 or (major == 5 and minor < 11):
                    self.logger.error(f"Vector indexes require Neo4j 5.11+, but found {version}")
                    return False
                
                # Create vector index
                index_name = f"{label.lower()}_embedding_idx"
                query = f"""
                CREATE VECTOR INDEX {index_name} IF NOT EXISTS
                FOR (n:{label})
                ON n.{property_name}
                OPTIONS {{indexConfig: {{
                    `vector.dimensions`: {dimension},
                    `vector.similarity_function`: 'cosine'
                }}}}
                """
                
                session.run(query)
                self.logger.info(f"Created vector index: {index_name}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error creating vector index: {e}")
            return False
    
    def create_node(self, label: str, properties: Dict[str, Any]) -> bool:
        """
        Create a node in the Neo4j database.
        
        Args:
            label: Node label
            properties: Node properties
            
        Returns:
            True if successful, False otherwise
        """
        if not self.driver:
            if not self.connect():
                return False
        
        # Extract ID from properties
        node_id = properties.get("id")
        if not node_id:
            self.logger.error("Node properties must include an 'id'")
            return False
        
        try:
            with self.driver.session() as session:
                # Merge on ID to avoid duplicates
                query = f"""
                MERGE (n:{label} {{id: $id}})
                SET n += $properties
                RETURN n.id
                """
                
                result = session.run(query, id=node_id, properties=properties)
                return result.single() is not None
                
        except Exception as e:
            self.logger.error(f"Error creating node: {e}")
            return False
    
    def create_relationship(self, from_label: str, from_id: str, 
                           to_label: str, to_id: str, 
                           rel_type: str, properties: Optional[Dict[str, Any]] = None) -> bool:
        """
        Create a relationship between two nodes.
        
        Args:
            from_label: Label of the source node
            from_id: ID of the source node
            to_label: Label of the target node
            to_id: ID of the target node
            rel_type: Relationship type
            properties: Optional relationship properties
            
        Returns:
            True if successful, False otherwise
        """
        if not self.driver:
            if not self.connect():
                return False
        
        if properties is None:
            properties = {}
        
        try:
            with self.driver.session() as session:
                query = f"""
                MATCH (a:{from_label} {{id: $from_id}})
                MATCH (b:{to_label} {{id: $to_id}})
                MERGE (a)-[r:{rel_type}]->(b)
                SET r += $properties
                RETURN type(r)
                """
                
                result = session.run(query, from_id=from_id, to_id=to_id, properties=properties)
                return result.single() is not None
                
        except Exception as e:
            self.logger.error(f"Error creating relationship: {e}")
            return False
    
    def vector_search(self, label: str, vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Perform a vector similarity search.
        
        Args:
            label: Node label to search (e.g., "PullRequest")
            vector: Query vector
            limit: Maximum number of results
            
        Returns:
            List of nodes with similarity scores
        """
        if not self.driver:
            if not self.connect():
                return []
        
        try:
            with self.driver.session() as session:
                query = f"""
                MATCH (n:{label})
                WHERE n.embedding IS NOT NULL
                WITH n, vector.similarity(n.embedding, $vector) AS score
                ORDER BY score DESC
                LIMIT $limit
                RETURN n.id AS id, n.title AS title, score
                """
                
                result = session.run(query, vector=vector, limit=limit)
                return [dict(record) for record in result]
                
        except Exception as e:
            self.logger.error(f"Error performing vector search: {e}")
            return []
    
    def find_path(self, start_label: str, start_id: str, 
                 end_label: str, end_id: str, 
                 max_depth: int = 4) -> List[Dict[str, Any]]:
        """
        Find a path between two nodes in the graph.
        
        Args:
            start_label: Label of the start node
            start_id: ID of the start node
            end_label: Label of the end node
            end_id: ID of the end node
            max_depth: Maximum path length
            
        Returns:
            List of paths found
        """
        if not self.driver:
            if not self.connect():
                return []
        
        try:
            with self.driver.session() as session:
                query = f"""
                MATCH path = shortestPath(
                    (a:{start_label} {{id: $start_id}})-[*1..{max_depth}]-(b:{end_label} {{id: $end_id}})
                )
                RETURN path
                LIMIT 1
                """
                
                result = session.run(query, start_id=start_id, end_id=end_id)
                record = result.single()
                
                if not record:
                    return []
                
                path = record["path"]
                nodes = []
                relationships = []
                
                for node in path.nodes:
                    nodes.append(dict(node))
                
                for rel in path.relationships:
                    relationships.append({
                        "type": rel.type,
                        "start": rel.start_node.id,
                        "end": rel.end_node.id,
                        "properties": dict(rel)
                    })
                
                return [{
                    "nodes": nodes,
                    "relationships": relationships
                }]
                
        except Exception as e:
            self.logger.error(f"Error finding path: {e}")
            return []