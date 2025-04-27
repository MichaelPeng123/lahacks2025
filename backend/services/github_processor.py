import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from config import settings

logger = logging.getLogger(__name__)

class GitHubProcessor:
    """
    Class to process GitHub webhook events and extract relevant entities.
    """
    
    @classmethod
    def process_webhook(cls, event_type: str, payload: Dict[Any, Any]) -> List[Dict]:
        """
        Process a GitHub webhook event and extract relevant entities.
        
        Args:
            event_type: The type of GitHub event (push, pull_request, etc.)
            payload: The webhook payload from GitHub
            
        Returns:
            List of entities extracted from the event
        """
        entities = []
        
        # Extract common data
        repository = cls._extract_repository_data(payload)
        if repository:
            entities.append(repository)
        
        # Extract contributor data
        contributor = cls._extract_contributor(event_type, payload)
        if contributor:
            entities.append(contributor)
        
        # Process specific event types
        if event_type == "push":
            push_data = cls._process_push_event(payload)
            if push_data:
                entities.append(push_data)
                
        elif event_type == "pull_request":
            pr_data = cls._process_pull_request_event(payload)
            if pr_data:
                entities.append(pr_data)
                
        elif event_type == "issues":
            issue_data = cls._process_issue_event(payload)
            if issue_data:
                entities.append(issue_data)
                
        elif event_type == "issue_comment":
            comment_data = cls._process_issue_comment_event(payload)
            if comment_data:
                entities.append(comment_data)
                
        elif event_type == "pull_request_review":
            review_data = cls._process_pr_review_event(payload)
            if review_data:
                entities.append(review_data)
                
        elif event_type == "pull_request_review_comment":
            review_comment_data = cls._process_pr_review_comment_event(payload)
            if review_comment_data:
                entities.append(review_comment_data)
        
        # Save extracted entities to the actions file
        if entities:
            cls._save_to_actions_file(entities)
        
        return entities
    
    @staticmethod
    def _extract_repository_data(payload: Dict) -> Optional[Dict]:
        """Extract repository information from the payload."""
        if "repository" not in payload:
            return None
            
        repo = payload["repository"]
        return {
            "type": "repository",
            "id": repo.get("id"),
            "name": repo.get("name"),
            "full_name": repo.get("full_name"),
            "url": repo.get("html_url"),
            "description": repo.get("description"),
            "owner": repo.get("owner", {}).get("login"),
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def _extract_contributor(event_type: str, payload: Dict) -> Optional[Dict]:
        """Extract contributor information based on event type."""
        user_data = None
        
        if event_type == "push":
            user_data = payload.get("sender")
        elif event_type == "pull_request":
            user_data = payload.get("pull_request", {}).get("user")
        elif event_type == "issues":
            user_data = payload.get("issue", {}).get("user")
        elif event_type == "issue_comment":
            user_data = payload.get("comment", {}).get("user")
        elif event_type in ["pull_request_review", "pull_request_review_comment"]:
            user_data = payload.get("review", {}).get("user") or payload.get("comment", {}).get("user")
        
        if not user_data:
            return None
            
        return {
            "type": "contributor",
            "id": user_data.get("id"),
            "login": user_data.get("login"),
            "name": user_data.get("name", user_data.get("login")),
            "avatar_url": user_data.get("avatar_url"),
            "url": user_data.get("html_url"),
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def _process_push_event(payload: Dict) -> Optional[Dict]:
        """Process push event data."""
        if "commits" not in payload:
            return None
            
        commits = payload.get("commits", [])
        commit_count = len(commits)
        
        return {
            "type": "push",
            "id": payload.get("after"),
            "ref": payload.get("ref"),
            "commit_count": commit_count,
            "commits": [
                {
                    "id": commit.get("id"),
                    "message": commit.get("message"),
                    "author": commit.get("author", {}).get("name"),
                    "url": commit.get("url")
                }
                for commit in commits[:5]  # Limit to first 5 commits
            ],
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def _process_pull_request_event(payload: Dict) -> Optional[Dict]:
        """Process pull request event data."""
        if "pull_request" not in payload:
            return None
            
        pr = payload.get("pull_request", {})
        
        return {
            "type": "pull_request",
            "id": pr.get("id"),
            "number": pr.get("number"),
            "title": pr.get("title"),
            "state": pr.get("state"),
            "action": payload.get("action"),
            "created_at": pr.get("created_at"),
            "updated_at": pr.get("updated_at"),
            "merged": pr.get("merged", False),
            "url": pr.get("html_url"),
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def _process_issue_event(payload: Dict) -> Optional[Dict]:
        """Process issue event data."""
        if "issue" not in payload:
            return None
            
        issue = payload.get("issue", {})
        
        return {
            "type": "issue",
            "id": issue.get("id"),
            "number": issue.get("number"),
            "title": issue.get("title"),
            "state": issue.get("state"),
            "action": payload.get("action"),
            "created_at": issue.get("created_at"),
            "updated_at": issue.get("updated_at"),
            "url": issue.get("html_url"),
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def _process_issue_comment_event(payload: Dict) -> Optional[Dict]:
        """Process issue comment event data."""
        if "comment" not in payload or "issue" not in payload:
            return None
            
        comment = payload.get("comment", {})
        issue = payload.get("issue", {})
        
        return {
            "type": "issue_comment",
            "id": comment.get("id"),
            "issue_id": issue.get("id"),
            "issue_number": issue.get("number"),
            "body": comment.get("body", "")[:100],  # Truncate long comments
            "action": payload.get("action"),
            "created_at": comment.get("created_at"),
            "updated_at": comment.get("updated_at"),
            "url": comment.get("html_url"),
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def _process_pr_review_event(payload: Dict) -> Optional[Dict]:
        """Process pull request review event data."""
        if "review" not in payload or "pull_request" not in payload:
            return None
            
        review = payload.get("review", {})
        pr = payload.get("pull_request", {})
        
        return {
            "type": "pr_review",
            "id": review.get("id"),
            "pr_id": pr.get("id"),
            "pr_number": pr.get("number"),
            "state": review.get("state"),
            "action": payload.get("action"),
            "body": review.get("body", "")[:100],  # Truncate long reviews
            "submitted_at": review.get("submitted_at"),
            "url": review.get("html_url"),
            "timestamp": datetime.now().isoformat()
        }
    
    @staticmethod
    def _process_pr_review_comment_event(payload: Dict) -> Optional[Dict]:
        """Process pull request review comment event data."""
        if "comment" not in payload or "pull_request" not in payload:
            return None
            
        comment = payload.get("comment", {})
        pr = payload.get("pull_request", {})
        
        return {
            "type": "pr_review_comment",
            "id": comment.get("id"),
            "pr_id": pr.get("id"),
            "pr_number": pr.get("number"),
            "body": comment.get("body", "")[:100],  # Truncate long comments
            "action": payload.get("action"),
            "created_at": comment.get("created_at"),
            "updated_at": comment.get("updated_at"),
            "url": comment.get("html_url"),
            "timestamp": datetime.now().isoformat()
        }
    
    @classmethod
    def _save_to_actions_file(cls, entities: List[Dict]) -> None:
        """Save entities to the actions file."""
        actions_file = settings.ACTIONS_FILE_PATH
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(actions_file)), exist_ok=True)
        
        # Load existing data
        existing_data = []
        if os.path.exists(actions_file):
            try:
                with open(actions_file, 'r') as f:
                    existing_data = json.load(f)
            except json.JSONDecodeError:
                # If file exists but is empty or invalid JSON
                existing_data = []
        
        # Add new entities
        updated_data = existing_data + entities
        
        # Save updated data
        with open(actions_file, 'w') as f:
            json.dump(updated_data, f, indent=2)
            
        logger.info(f"Saved {len(entities)} entities to {actions_file}") 