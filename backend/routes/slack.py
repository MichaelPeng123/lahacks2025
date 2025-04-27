from fastapi import APIRouter, Depends, HTTPException, Request, Header
from typing import List, Dict, Optional
from backend.services.slack_service import SlackService
from pydantic import BaseModel
import json
import hmac
import hashlib

router = APIRouter()
slack_service = SlackService()

class ChannelTrackRequest(BaseModel):
    channel_id: str

async def verify_slack_signature(request: Request, x_slack_signature: Optional[str] = Header(None), x_slack_request_timestamp: Optional[str] = Header(None)):
    """Verify that the webhook request came from Slack using the signing secret."""
    if not x_slack_signature or not x_slack_request_timestamp:
        raise HTTPException(status_code=401, detail="Missing Slack signature headers")
    
    # Get raw request body
    payload_body = await request.body()
    
    # Get Slack signing secret from config
    from backend.config import settings
    signing_secret = settings.SLACK_SIGNING_SECRET.encode()
    
    # Create the signature base string
    sig_basestring = f"v0:{x_slack_request_timestamp}:".encode() + payload_body
    
    # Create our own signature
    signature = 'v0=' + hmac.new(signing_secret, sig_basestring, hashlib.sha256).hexdigest()
    
    # Compare signatures
    if not hmac.compare_digest(signature, x_slack_signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")
    
    return payload_body

@router.post("/webhook")
async def slack_webhook(request: Request):
    """Endpoint to receive Slack events."""
    
    print("\n============ SLACK EVENT RECEIVED ============")
    
    # First, let's get the raw body
    payload_body = await request.body()
    
    # Parse JSON payload
    try:
        payload = json.loads(payload_body)
        print("Received payload:", payload)
        
        # Handle Slack URL verification directly - before signature verification
        if payload.get('type') == 'url_verification':
            challenge = payload.get('challenge')
            print(f"URL Verification challenge received: {challenge}")
            return {"challenge": challenge}
        
        # For non-verification requests, verify signature
        await verify_slack_signature(request)
        
    except json.JSONDecodeError:
        # Handle URL-encoded form data
        body_str = payload_body.decode('utf-8')
        try:
            payload = {item.split('=')[0]: item.split('=')[1] for item in body_str.split('&')}
            if 'payload' in payload:
                import urllib.parse
                payload = json.loads(urllib.parse.unquote(payload['payload']))
        except Exception as e:
            print(f"Error parsing form data: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid payload format")
    
    # Get the event type
    event_type = payload.get('event', {}).get('type')
    if not event_type:
        print("No event type found in payload")
        return {"status": "ignored", "message": "No event type found"}
    
    print(f"Event Type: {event_type}")
    
    # Handle message events
    if event_type == 'message':
        event = payload.get('event', {})
        channel = event.get('channel')
        user = event.get('user')
        text = event.get('text')
        ts = event.get('ts')
        
        print(f"Channel: {channel}")
        print(f"User: {user}")
        print(f"Message: {text}")
        print(f"Timestamp: {ts}")
        
        # Process the message
        await slack_service.process_message_event(event)
        
        print("✅ Message event successfully processed")
        return {"status": "success", "message": "Message event processed"}
    
    # Return a 200 response for any other events we're not handling yet
    print(f"⚠️ Ignoring event type: {event_type}")
    return {"status": "ignored", "message": f"Event {event_type} ignored"}

@router.post("/track")
async def track_channel(request: ChannelTrackRequest):
    """
    Start tracking a Slack channel's messages.
    
    Args:
        request (ChannelTrackRequest): Request containing the channel ID to track
        
    Returns:
        Dict: Channel information and initial message history
    """
    try:
        result = await slack_service.track_channel(request.channel_id)
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{channel_id}")
async def get_channel_history(channel_id: str, limit: int = 100):
    """
    Get the message history for a specific channel.
    
    Args:
        channel_id (str): The ID of the channel to fetch history from
        limit (int): Maximum number of messages to fetch (default: 100)
        
    Returns:
        List[Dict]: List of messages from the channel
    """
    try:
        messages = await slack_service.get_channel_history(channel_id, limit)
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 