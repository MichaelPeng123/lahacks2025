"""
Script to import data with embeddings into a Neo4j graph database.
"""

import json
import os
import logging
import argparse
from typing import Dict, List, Any, Optional
from neo4j_service import Neo4jService

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Node type mapping
NODE_TYPE_LABELS = {
    "users": "User",
    "repositories": "Repository", 
    "pullRequests": "PullRequest",
    "issues": "Issue",
    "slackChannels": "Channel",
    "slackMessages": "Message",
    "textChunks": "TextChunk"
}

# Configure argument parser
parser = argparse.ArgumentParser(description='Import data into Neo4j graph database')
parser.add_argument('--input', type=str, default='mock_with_embeddings.json', 
                    help='Input JSON file with embeddings')
parser.add_argument('--neo4j-uri', type=str, default='neo4j://localhost:7687', 
                    help='Neo4j connection URI')
parser.add_argument('--neo4j-user', type=str, default='neo4j', 
                    help='Neo4j username')
parser.add_argument('--neo4j-password', type=str, default='password', 
                    help='Neo4j password')
parser.add_argument('--clear-db', action='store_true', 
                    help='Clear the database before importing')
parser.add_argument('--create-indexes', action='store_true', 
                    help='Create vector indexes for nodes with embeddings')
args = parser.parse_args()

def load_data(file_path: str) -> Dict[str, Any]:
    """Load JSON data from file"""
    logger.info(f"Loading data from {file_path}")
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data

def clear_database(neo4j: Neo4jService) -> bool:
    """Clear all data from the Neo4j database"""
    logger.info("Clearing database")
    
    try:
        with neo4j.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        return True
    except Exception as e:
        logger.error(f"Error clearing database: {e}")
        return False

def import_nodes(neo4j: Neo4jService, data: Dict[str, Any]) -> Dict[str, int]:
    """Import nodes from data into Neo4j"""
    results = {}
    
    for collection_name, nodes in data.items():
        if collection_name not in NODE_TYPE_LABELS:
            logger.info(f"Skipping collection {collection_name} - no mapping defined")
            continue
        
        label = NODE_TYPE_LABELS[collection_name]
        logger.info(f"Importing {len(nodes)} {label} nodes")
        
        success_count = 0
        for node in nodes:
            if neo4j.create_node(label, node):
                success_count += 1
        
        results[label] = success_count
        logger.info(f"Imported {success_count}/{len(nodes)} {label} nodes")
    
    return results

def create_relationships(neo4j: Neo4jService, data: Dict[str, Any]) -> Dict[str, int]:
    """Create relationships between nodes based on references in data"""
    results = {}
    
    # Import Pull Request author relationships
    if "pullRequests" in data and "users" in data:
        rel_type = "AUTHORED"
        logger.info(f"Creating {rel_type} relationships for Pull Requests")
        
        success_count = 0
        for pr in data["pullRequests"]:
            author_id = pr.get("authorId")
            if author_id:
                if neo4j.create_relationship("User", author_id, "PullRequest", pr["id"], rel_type):
                    success_count += 1
        
        results[f"User-{rel_type}->PullRequest"] = success_count
        logger.info(f"Created {success_count} {rel_type} relationships")
    
    # Import Issue author relationships
    if "issues" in data and "users" in data:
        rel_type = "AUTHORED"
        logger.info(f"Creating {rel_type} relationships for Issues")
        
        success_count = 0
        for issue in data["issues"]:
            author_id = issue.get("authorId")
            if author_id:
                if neo4j.create_relationship("User", author_id, "Issue", issue["id"], rel_type):
                    success_count += 1
        
        results[f"User-{rel_type}->Issue"] = success_count
        logger.info(f"Created {success_count} {rel_type} relationships")
    
    # Import Repository relationships for PRs and Issues
    if "repositories" in data:
        rel_type = "BELONGS_TO"
        logger.info(f"Creating {rel_type} relationships for PRs and Issues")
        
        pr_count = 0
        if "pullRequests" in data:
            for pr in data["pullRequests"]:
                repo_id = pr.get("repositoryId")
                if repo_id:
                    if neo4j.create_relationship("PullRequest", pr["id"], "Repository", repo_id, rel_type):
                        pr_count += 1
        
        issue_count = 0
        if "issues" in data:
            for issue in data["issues"]:
                repo_id = issue.get("repositoryId")
                if repo_id:
                    if neo4j.create_relationship("Issue", issue["id"], "Repository", repo_id, rel_type):
                        issue_count += 1
        
        results[f"PullRequest-{rel_type}->Repository"] = pr_count
        results[f"Issue-{rel_type}->Repository"] = issue_count
        logger.info(f"Created {pr_count} PR and {issue_count} Issue {rel_type} relationships")
    
    # Import PR reference relationships to Issues
    if "pullRequests" in data and "issues" in data:
        rel_type = "REFERENCES"
        logger.info(f"Creating {rel_type} relationships between PRs and Issues")
        
        success_count = 0
        # This is a simplified approach - in a real system you'd parse the PR body
        # to extract issue references like "fixes #123" or "closes #456"
        for pr in data["pullRequests"]:
            body = pr.get("body", "").lower()
            
            # Find issues referenced in the PR body
            for issue in data["issues"]:
                issue_number = issue.get("number")
                if not issue_number:
                    continue
                
                # Check for common reference patterns
                reference_patterns = [
                    f"fixes #{issue_number}",
                    f"closes #{issue_number}",
                    f"resolves #{issue_number}",
                    f"related to #{issue_number}",
                    f"##{issue_number}"
                ]
                
                referenced = any(pattern in body for pattern in reference_patterns)
                if referenced:
                    properties = {"referenceType": "fixes" if "fixes" in body else "related"}
                    if neo4j.create_relationship("PullRequest", pr["id"], "Issue", issue["id"], rel_type, properties):
                        success_count += 1
        
        results[f"PullRequest-{rel_type}->Issue"] = success_count
        logger.info(f"Created {success_count} {rel_type} relationships")
    
    # Import Slack Message author relationships
    if "slackMessages" in data and "users" in data:
        rel_type = "AUTHORED"
        logger.info(f"Creating {rel_type} relationships for Slack Messages")
        
        success_count = 0
        for msg in data["slackMessages"]:
            author_id = msg.get("authorId")
            if author_id:
                if neo4j.create_relationship("User", author_id, "Message", msg["id"], rel_type):
                    success_count += 1
        
        results[f"User-{rel_type}->Message"] = success_count
        logger.info(f"Created {success_count} {rel_type} relationships")
    
    # Import Slack Message channel relationships
    if "slackMessages" in data and "slackChannels" in data:
        rel_type = "POSTED_IN"
        logger.info(f"Creating {rel_type} relationships for Slack Messages")
        
        success_count = 0
        for msg in data["slackMessages"]:
            channel_id = msg.get("channelId")
            if channel_id:
                if neo4j.create_relationship("Message", msg["id"], "Channel", channel_id, rel_type):
                    success_count += 1
        
        results[f"Message-{rel_type}->Channel"] = success_count
        logger.info(f"Created {success_count} {rel_type} relationships")
    
    # Import Slack Message reply relationships
    if "slackMessages" in data:
        rel_type = "REPLIES_TO"
        logger.info(f"Creating {rel_type} relationships for Slack Messages")
        
        # Create a mapping of threadTs to message IDs
        thread_ts_to_id = {}
        for msg in data["slackMessages"]:
            slack_id = msg.get("slackId")
            if slack_id:
                thread_ts_to_id[slack_id] = msg["id"]
        
        success_count = 0
        for msg in data["slackMessages"]:
            thread_ts = msg.get("threadTs")
            if thread_ts and thread_ts in thread_ts_to_id:
                parent_id = thread_ts_to_id[thread_ts]
                if neo4j.create_relationship("Message", msg["id"], "Message", parent_id, rel_type):
                    success_count += 1
        
        results[f"Message-{rel_type}->Message"] = success_count
        logger.info(f"Created {success_count} {rel_type} relationships")
    
    # Import Slack Message references to GitHub PRs and Issues
    if "slackMessages" in data:
        rel_type = "REFERENCES_GITHUB"
        logger.info(f"Creating {rel_type} relationships for Slack Messages")
        
        pr_refs = 0
        issue_refs = 0
        
        # Simplistic approach - in a real system you'd use regex and URL parsing
        for msg in data["slackMessages"]:
            text = msg.get("text", "").lower()
            
            # Check for PR references
            if "pullRequests" in data:
                for pr in data["pullRequests"]:
                    pr_number = pr.get("number")
                    if not pr_number:
                        continue
                    
                    # Check for PR references in text
                    pr_patterns = [
                        f"pr #{pr_number}",
                        f"pr#{pr_number}",
                        f"pull request #{pr_number}",
                        f"pull request {pr_number}"
                    ]
                    
                    if any(pattern in text for pattern in pr_patterns) or f"pull/{pr_number}" in text:
                        properties = {"referenceType": "mention"}
                        if neo4j.create_relationship("Message", msg["id"], "PullRequest", pr["id"], rel_type, properties):
                            pr_refs += 1
            
            # Check for Issue references
            if "issues" in data:
                for issue in data["issues"]:
                    issue_number = issue.get("number")
                    if not issue_number:
                        continue
                    
                    # Check for Issue references in text
                    issue_patterns = [
                        f"issue #{issue_number}",
                        f"issue#{issue_number}",
                        f"#{issue_number}"
                    ]
                    
                    if any(pattern in text for pattern in issue_patterns) or f"issues/{issue_number}" in text:
                        properties = {"referenceType": "mention"}
                        if neo4j.create_relationship("Message", msg["id"], "Issue", issue["id"], rel_type, properties):
                            issue_refs += 1
        
        results[f"Message-{rel_type}->PullRequest"] = pr_refs
        results[f"Message-{rel_type}->Issue"] = issue_refs
        logger.info(f"Created {pr_refs} PR and {issue_refs} Issue reference relationships")
    
    # Import TextChunk relationships
    if "textChunks" in data:
        rel_type = "CHUNKED_FROM"
        logger.info(f"Creating {rel_type} relationships for TextChunks")
        
        success_count = 0
        for chunk in data["textChunks"]:
            source_id = chunk.get("sourceId")
            source_type = chunk.get("sourceType")
            
            if source_id and source_type:
                # Map source type to label
                if source_type == "PullRequest":
                    if neo4j.create_relationship("TextChunk", chunk["id"], "PullRequest", source_id, rel_type):
                        success_count += 1
                elif source_type == "Issue":
                    if neo4j.create_relationship("TextChunk", chunk["id"], "Issue", source_id, rel_type):
                        success_count += 1
                elif source_type == "SlackMessage":
                    if neo4j.create_relationship("TextChunk", chunk["id"], "Message", source_id, rel_type):
                        success_count += 1
        
        results[f"TextChunk-{rel_type}->Source"] = success_count
        logger.info(f"Created {success_count} {rel_type} relationships")
    
    return results

def create_vector_indexes(neo4j: Neo4jService) -> Dict[str, bool]:
    """Create vector indexes for nodes with embeddings"""
    results = {}
    
    # Node types with embeddings
    node_types = ["PullRequest", "Issue", "Message", "TextChunk"]
    
    for node_type in node_types:
        logger.info(f"Creating vector index for {node_type}")
        success = neo4j.create_vector_index(node_type)
        results[node_type] = success
    
    return results

def main():
    # Check if the input file exists
    if not os.path.exists(args.input):
        logger.error(f"Input file {args.input} not found")
        return
    
    # Load the data
    data = load_data(args.input)
    
    # Initialize Neo4j service
    neo4j = Neo4jService(args.neo4j_uri, args.neo4j_user, args.neo4j_password)
    
    # Test connection
    node_count = neo4j.test_connection()
    if node_count < 0:
        logger.error("Failed to connect to Neo4j")
        return
    
    logger.info(f"Connected to Neo4j database with {node_count} nodes")
    
    # Clear database if requested
    if args.clear_db:
        if not clear_database(neo4j):
            logger.error("Failed to clear database")
            neo4j.close()
            return
    
    # Create constraints
    if not neo4j.create_constraints():
        logger.error("Failed to create constraints")
        neo4j.close()
        return
    
    # Import nodes
    node_results = import_nodes(neo4j, data)
    logger.info(f"Node import results: {node_results}")
    
    # Create relationships
    rel_results = create_relationships(neo4j, data)
    logger.info(f"Relationship creation results: {rel_results}")
    
    # Create vector indexes if requested
    if args.create_indexes:
        index_results = create_vector_indexes(neo4j)
        logger.info(f"Vector index creation results: {index_results}")
    
    # Close Neo4j connection
    neo4j.close()
    
    logger.info("Import completed successfully")

if __name__ == "__main__":
    main()