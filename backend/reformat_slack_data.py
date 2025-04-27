#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script to reformat Slack message data into the new entity-based format.
Transforms the existing JSON structure into Channel and Message entities format.
"""

import os
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any

# JSON storage location
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
SLACK_MESSAGES_FILE = os.path.join(DATA_DIR, "slack_messages.json")
REFORMATTED_FILE = os.path.join(DATA_DIR, "slack_entities.json")

def load_current_data():
    """Load the current JSON data file"""
    try:
        with open(SLACK_MESSAGES_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading messages from file: {str(e)}")
        return None

def save_reformatted_data(data):
    """Save the reformatted data to a new JSON file"""
    try:
        with open(REFORMATTED_FILE, 'w') as f:
            json.dump(data, indent=2, fp=f)
        print(f"Saved reformatted data to {REFORMATTED_FILE}")
        return True
    except Exception as e:
        print(f"Error saving reformatted data: {str(e)}")
        return False

def convert_slack_ts_to_iso(slack_ts):
    """
    Convert Slack timestamp format to ISO 8601 format.
    
    Args:
        slack_ts: Slack timestamp (e.g., "1745704536.966429")
        
    Returns:
        ISO 8601 formatted timestamp (e.g., "2025-04-26T15:22:16.966Z")
    """
    if not slack_ts:
        return None
        
    try:
        # Slack timestamps are Unix timestamps with milliseconds
        unix_ts = float(slack_ts)
        dt = datetime.fromtimestamp(unix_ts)
        # Format as ISO 8601 with Z for UTC
        return dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    except (ValueError, TypeError):
        return None

def reformat_data(current_data):
    """
    Reformat the current data structure into the new entity format
    
    New format:
    {
        "channels": [
            {
                "id": "uuid",
                "slackId": "C123456789",
                "name": "channel-name",
                "isPrivate": false
            },
            ...
        ],
        "messages": [
            {
                "id": "uuid",
                "slackId": "username", 
                "channelId": "C123456789",
                "text": "message text",
                "threadTs": "2025-04-26T15:22:16.966Z" or null,
                "createdAt": "2025-04-26T15:22:16.966Z"
            },
            ...
        ]
    }
    """
    # Initialize new data structure
    new_data = {
        "channels": [],
        "messages": []
    }
    
    # Track thread messages for additional processing
    threads_to_process = {}  # {channel_id: {thread_ts: parent_message}}
    
    # Process each channel
    for channel_id, channel_data in current_data["channels"].items():
        # Create channel entity
        channel_entity = {
            "id": str(uuid.uuid4()),
            "slackId": channel_id,
            "name": channel_data["name"],
            "isPrivate": False  # Default value, could be updated if needed
        }
        
        # Add to channels list
        new_data["channels"].append(channel_entity)
        
        # First pass: identify threads and create parent messages
        for message in channel_data["messages"]:
            # Track thread parent messages
            if message.get("thread_ts") == message.get("ts") and message.get("reply_count", 0) > 0:
                # This is a parent message of a thread
                if channel_id not in threads_to_process:
                    threads_to_process[channel_id] = {}
                threads_to_process[channel_id][message.get("ts")] = message
        
        # Process each message in this channel
        for message in channel_data["messages"]:
            # Skip system messages if desired (uncomment if needed)
            # if message.get("subtype") in ["channel_join", "channel_leave"]:
            #     continue
            
            # Get the username from user_info if available, else default to user_id
            username = message.get("user", "unknown")
            if isinstance(message.get("user_info"), dict):
                username = message["user_info"].get("name", username)
            elif message.get("user_id"):
                username = message.get("user_id")
            
            # Determine if this is a thread reply
            thread_ts = message.get("thread_ts")
            
            # Convert thread_ts and ts to ISO format
            iso_thread_ts = convert_slack_ts_to_iso(thread_ts) if thread_ts else None
            iso_created_at = convert_slack_ts_to_iso(message.get("ts", ""))
            
            # Create message entity
            message_entity = {
                "id": str(uuid.uuid4()),
                "slackId": username,
                "channelId": channel_id,
                "text": message.get("text", ""),
                "threadTs": iso_thread_ts,  # Will be None if not part of a thread
                "createdAt": iso_created_at
            }
            
            # Add to messages list
            new_data["messages"].append(message_entity)
    
    return new_data

def main():
    # Load current data
    current_data = load_current_data()
    if not current_data:
        print("Failed to load current data, exiting.")
        return
    
    # Reformat the data
    print(f"Reformatting data from {len(current_data['channels'])} channels...")
    new_data = reformat_data(current_data)
    
    # Print stats
    thread_messages = [m for m in new_data["messages"] if m["threadTs"] is not None]
    print(f"Converted to new format:")
    print(f"  - {len(new_data['channels'])} channels")
    print(f"  - {len(new_data['messages'])} messages")
    print(f"  - {len(thread_messages)} thread messages")
    
    # Save reformatted data
    if save_reformatted_data(new_data):
        print("✅ Successfully reformatted Slack data to new entity structure")
    else:
        print("❌ Failed to save reformatted data")

if __name__ == "__main__":
    main() 