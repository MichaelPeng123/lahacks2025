# backend/routes/webhooks.py
from fastapi import APIRouter, Request, Response, Header, HTTPException, Depends
import hmac
import hashlib
import json
import os
from typing import Optional
from backend.services.github_service import process_push_event, process_pull_request_event
from backend.config import settings

router = APIRouter()

@router.post("/github-debug")
async def github_webhook_debug(request: Request):
    """Debug endpoint to log all webhook details without verification."""
    print("\n============ WEBHOOK DEBUG RECEIVED ============")
    
    # Log all headers
    print("=== HEADERS ===")
    for name, value in request.headers.items():
        print(f"{name}: {value}")
    
    # Log the raw body
    body = await request.body()
    print("\n=== RAW BODY ===")
    print(body)
    
    # Try to parse as JSON
    try:
        payload = json.loads(body)
        print("\n=== JSON PAYLOAD ===")
        print(json.dumps(payload, indent=2))
    except:
        print("Not a valid JSON payload")
    
    return {"status": "debug", "message": "Webhook details logged"}

async def verify_github_signature(request: Request, x_hub_signature_256: Optional[str] = Header(None)):
    """Verify that the webhook request came from GitHub using the webhook secret."""
    if not x_hub_signature_256:
        raise HTTPException(status_code=401, detail="Missing signature header")
    
    # Get raw request body
    payload_body = await request.body()
    
    # Create our own signature
    secret = settings.GITHUB_WEBHOOK_SECRET.encode()
    signature = 'sha256=' + hmac.new(secret, payload_body, hashlib.sha256).hexdigest()
    
    # Compare signatures
    if not hmac.compare_digest(signature, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    return payload_body

@router.post("/github")
async def github_webhook(request: Request, payload_body: bytes = Depends(verify_github_signature)):
    """Endpoint to receive GitHub webhook events."""
    
    print("\n============ WEBHOOK RECEIVED ============")
    print(f"Headers: {dict(request.headers)}")
    
    # Get the event type from headers
    github_event = request.headers.get("X-GitHub-Event")
    print(f"Event Type: {github_event}")
    
    # Parse JSON payload
    payload = json.loads(payload_body)
    
    # Debug: Log full payload for troubleshooting
    print("\n=== FULL PAYLOAD ===")
    print(json.dumps(payload, indent=2)[:1000] + "..." if len(json.dumps(payload)) > 1000 else json.dumps(payload, indent=2))
    
    # Handle different event types
    if github_event == "push":
        print(f"Repository: {payload.get('repository', {}).get('full_name', 'unknown')}")
        print(f"Commits: {len(payload.get('commits', []))}")
        
        # Process the push event
        await process_push_event(payload)
        
        print("✅ Push event successfully processed")
        return {"status": "success", "message": "Push event processed"}
        
    elif github_event == "pull_request":
        print(f"Repository: {payload.get('repository', {}).get('full_name', 'unknown')}")
        print(f"PR Number: {payload.get('number', 'unknown')}")
        print(f"Action: {payload.get('action', 'unknown')}")
        
        # Process the pull request event
        await process_pull_request_event(payload)
        
        print("✅ Pull request event successfully processed")
        return {"status": "success", "message": "Pull request event processed"}
    
    # Return a 200 response for any other events we're not handling yet
    print(f"⚠️ Ignoring event type: {github_event}")
    return {"status": "ignored", "message": f"Event {github_event} ignored"}