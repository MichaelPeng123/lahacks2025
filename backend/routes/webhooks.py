# backend/routes/webhooks.py
from fastapi import APIRouter, Request, Response, Header, HTTPException, Depends
import hmac
import hashlib
import json
import os
from typing import Optional
from services.github_processor import GitHubProcessor
from config import settings
from uagents import Context

router = APIRouter()

import logging
logging.basicConfig(level=logging.INFO)

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
    
    # Get the event type from headers
    github_event = request.headers.get("X-GitHub-Event")
    
    # Parse JSON payload
    payload = json.loads(payload_body)
    
    # Process with the GitHub processor - using original for compatibility
    processed_entities = GitHubProcessor.process_webhook(github_event, payload)
    entities_count = len(processed_entities)
    
    
    # Return success with entity count
    return {
        "status": "success", 
        "message": f"{github_event} event processed",
        "entities_processed": entities_count
    }




