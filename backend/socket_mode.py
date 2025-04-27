#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Socket Mode handler for Slack.
This module establishes and maintains a WebSocket connection with Slack using Socket Mode.
"""

import logging
import os
import json
import asyncio
from typing import Dict, Any

from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.errors import SlackApiError

from .config import settings
from .services.slack_service import SlackService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize services
slack_service = SlackService()

async def handle_event(event_data: Dict[str, Any]) -> None:
    """
    Process a Slack event.
    
    Args:
        event_data: The Slack event data
    """
    try:
        event_type = event_data.get("type")
        
        if event_type == "message":
            # Get message details
            channel = event_data.get("channel")
            user = event_data.get("user")
            text = event_data.get("text", "")
            ts = event_data.get("ts")
            
            logger.info(f"Received message: {text} from {user} in {channel}")
            
            # Process message through SlackService
            await slack_service.process_message(text, user, channel, ts)
        
        # Add handlers for other event types as needed
        # elif event_type == "reaction_added":
        #     ...
        
    except Exception as e:
        logger.error(f"Error handling event: {e}")

async def process_event(client: SocketModeClient, req: SocketModeRequest) -> None:
    """
    Process Socket Mode requests.
    
    Args:
        client: SocketModeClient instance
        req: SocketModeRequest object
    """
    # Acknowledge the request
    client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))
    
    # Handle the event based on type
    if req.type == "events_api":
        # Extract the event from the payload
        payload = req.payload
        event = payload.get("event", {})
        
        # Skip bot messages to prevent loops
        if event.get("bot_id"):
            return
            
        # Process the event
        await handle_event(event)

async def start_socket_mode() -> None:
    """
    Initialize the Socket Mode client and connect to Slack.
    """
    # Initialize the WebClient with the bot token
    web_client = AsyncWebClient(token=settings.SLACK_BOT_TOKEN)
    
    # Initialize the SocketModeClient with the app token
    socket_client = SocketModeClient(
        app_token=settings.SLACK_APP_TOKEN,  # xapp-... token
        web_client=web_client
    )
    
    # Add a process handler
    socket_client.socket_mode_request_listeners.append(process_event)
    
    try:
        # Connect to Slack
        await socket_client.connect()
        logger.info("Connected to Slack with Socket Mode!")
        
        # Keep the connection alive
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"Error with Socket Mode: {e}")
    finally:
        # Close the connection when done
        await socket_client.close()

if __name__ == "__main__":
    # Validate required tokens
    if not settings.SLACK_BOT_TOKEN or not settings.SLACK_APP_TOKEN:
        logger.error("Missing required Slack tokens. Check your environment variables.")
        exit(1)
        
    if not settings.SLACK_APP_TOKEN.startswith("xapp-"):
        logger.error("Invalid Slack App token. It should start with 'xapp-'")
        exit(1)
        
    if not settings.SLACK_BOT_TOKEN.startswith("xoxb-"):
        logger.error("Invalid Slack Bot token. It should start with 'xoxb-'")
        exit(1)
        
    # Run the Socket Mode client
    asyncio.run(start_socket_mode()) 