#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Continuous Slack channel monitoring service
This module polls Slack channels for new messages and maintains history
"""

import os
import time
import logging
import asyncio
import json
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Set
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# JSON storage location
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
SLACK_MESSAGES_FILE = os.path.join(DATA_DIR, "slack_messages.json")
SLACK_ENTITIES_FILE = os.path.join(DATA_DIR, "slack_entities.json")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

class SlackMonitor:
    """Service for continuously monitoring Slack channels"""
    
    def __init__(self):
        """Initialize the Slack monitor with bot token"""
        self.token = os.getenv("SLACK_BOT_TOKEN")
        if not self.token:
            raise ValueError("SLACK_BOT_TOKEN environment variable not set")
            
        self.client = WebClient(token=self.token)
        self.monitored_channels = {}  # channel_id -> channel_info
        self.latest_timestamps = {}   # channel_id -> latest_ts
        self.message_cache = {}       # channel_id -> list of messages
        self.threads_seen = set()     # Set of parent_ts values we've processed
        self.running = False
        self.user_cache = {}          # user_id -> user_info
        
        # Initialize message storage files if they don't exist
        self._initialize_message_file()
        self._initialize_entities_file()
        
    def _initialize_message_file(self):
        """Initialize the JSON file for storing messages if it doesn't exist"""
        if not os.path.exists(SLACK_MESSAGES_FILE):
            with open(SLACK_MESSAGES_FILE, 'w') as f:
                json.dump({
                    "channels": {},
                    "last_updated": datetime.now().isoformat(),
                    "message_count": 0
                }, f, indent=2)
            logger.info(f"Created message storage file: {SLACK_MESSAGES_FILE}")
        else:
            logger.info(f"Using existing message storage file: {SLACK_MESSAGES_FILE}")

    def _initialize_entities_file(self):
        """Initialize the JSON file for storing entity-based data if it doesn't exist"""
        if not os.path.exists(SLACK_ENTITIES_FILE):
            with open(SLACK_ENTITIES_FILE, 'w') as f:
                json.dump({
                    "channels": [],
                    "messages": [],
                    "last_updated": datetime.now().isoformat()
                }, f, indent=2)
            logger.info(f"Created entity storage file: {SLACK_ENTITIES_FILE}")
        else:
            logger.info(f"Using existing entity storage file: {SLACK_ENTITIES_FILE}")
    
    def _load_messages_from_file(self):
        """Load messages from the JSON file"""
        try:
            with open(SLACK_MESSAGES_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error loading messages from file: {str(e)}")
            return {
                "channels": {},
                "last_updated": datetime.now().isoformat(),
                "message_count": 0
            }
    
    def _save_messages_to_file(self, data):
        """Save messages to the JSON file"""
        try:
            with open(SLACK_MESSAGES_FILE, 'w') as f:
                json.dump(data, indent=2, fp=f)
            logger.info(f"Updated message storage file with new messages")
        except Exception as e:
            logger.error(f"Error saving messages to file: {str(e)}")
    
    def _add_messages_to_storage(self, channel_id, new_messages):
        """Add new messages to the JSON storage file"""
        # Load current data
        data = self._load_messages_from_file()
        
        # Initialize channel if needed
        if channel_id not in data["channels"]:
            channel_name = self.monitored_channels[channel_id]['name']
            data["channels"][channel_id] = {
                "name": channel_name,
                "messages": []
            }
        
        # Process and add new messages
        for msg in new_messages:
            # Process user IDs in the message
            processed_msg = self._process_message_users(msg)
            data["channels"][channel_id]["messages"].insert(0, processed_msg)  # Insert at beginning to maintain reverse chronological order
        
        # Update metadata
        data["last_updated"] = datetime.now().isoformat()
        data["message_count"] = sum(len(channel_data["messages"]) for channel_data in data["channels"].values())
        
        # Save updated data
        self._save_messages_to_file(data)
        
        # Also save data in the entity format
        self._add_messages_to_entity_storage(channel_id, new_messages)
    
    def _load_entities_from_file(self):
        """Load entities from the JSON file"""
        try:
            with open(SLACK_ENTITIES_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error loading entities from file: {str(e)}")
            return {
                "channels": [],
                "messages": [],
                "last_updated": datetime.now().isoformat()
            }
    
    def _convert_slack_ts_to_iso(self, slack_ts):
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
    
    def _save_entities_to_file(self, data):
        """Save entities to the JSON file"""
        try:
            with open(SLACK_ENTITIES_FILE, 'w') as f:
                json.dump(data, indent=2, fp=f)
            logger.info(f"Updated entity storage file with new data")
        except Exception as e:
            logger.error(f"Error saving entities to file: {str(e)}")
    
    def _add_messages_to_entity_storage(self, channel_id, new_messages):
        """Add new messages to the entity-based JSON storage file"""
        # Load current entity data
        data = self._load_entities_from_file()
        
        # Check if channel exists, add if not
        channel_exists = False
        for channel in data["channels"]:
            if channel["slackId"] == channel_id:
                channel_exists = True
                break
                
        if not channel_exists:
            channel_name = self.monitored_channels[channel_id]['name']
            channel_entity = {
                "id": str(uuid.uuid4()),
                "slackId": channel_id,
                "name": channel_name,
                "isPrivate": False  # Default value, could be updated if needed
            }
            data["channels"].append(channel_entity)
        
        # Create a set of existing message content keys to check for duplicates
        # We don't use slackId in the key to avoid duplicates with different ID formats
        existing_content = set()
        for message in data["messages"]:
            content_key = (
                message.get("text", ""), 
                message.get("channelId", ""),
                message.get("createdAt", "")
            )
            existing_content.add(content_key)
            
        # Process and add new messages
        added_count = 0
        for msg in new_messages:
            # Process user IDs in the message
            processed_msg = self._process_message_users(msg)
            
            # Get username from user_info if available
            username = processed_msg.get("user", "unknown")
            if isinstance(processed_msg.get("user_info"), dict):
                username = processed_msg["user_info"].get("name", username)
            elif processed_msg.get("user_id"):
                username = processed_msg.get("user_id")
            
            # Convert timestamps to ISO format
            thread_ts = processed_msg.get("thread_ts")
            iso_thread_ts = self._convert_slack_ts_to_iso(thread_ts) if thread_ts else None
            iso_created_at = self._convert_slack_ts_to_iso(processed_msg.get("ts", ""))
            
            # Create message entity
            message_entity = {
                "id": str(uuid.uuid4()),
                "slackId": username,
                "channelId": channel_id,
                "text": processed_msg.get("text", ""),
                "threadTs": iso_thread_ts,
                "createdAt": iso_created_at
            }
            
            # Check if this message content already exists before adding
            # We only check the content, not the user ID
            content_key = (
                message_entity["text"], 
                message_entity["channelId"],
                message_entity["createdAt"]
            )
            
            if content_key not in existing_content:
                # Add to messages list only if not a duplicate
                data["messages"].append(message_entity)
                existing_content.add(content_key)
                added_count += 1
        
        if added_count > 0:
            # Update last_updated timestamp
            data["last_updated"] = datetime.now().isoformat()
            
            # Save updated data
            self._save_entities_to_file(data)
            logger.info(f"Added {added_count} new messages to entity storage")
        else:
            logger.info("No new messages added to entity storage (all were duplicates)")
        
        return added_count
    
    def get_entity_message_data(self):
        """Get all Slack messages in the entity format from the JSON storage file"""
        try:
            with open(SLACK_ENTITIES_FILE, 'r') as f:
                data = json.load(f)
                
                # Filter out duplicate messages
                if "messages" in data:
                    # Create a set to track unique message content
                    seen_messages = set()
                    unique_messages = []
                    
                    # Group messages by content, channel, and timestamp 
                    # (ignoring slackId differences)
                    message_groups = {}
                    
                    # First pass: group messages by their content/channel/timestamp
                    for message in data["messages"]:
                        # Create a content key based on text, channel, and timestamp
                        # (but NOT the user ID which may appear in multiple formats)
                        content_key = (
                            message.get("text", ""), 
                            message.get("channelId", ""),
                            message.get("createdAt", "")
                        )
                        
                        if content_key not in message_groups:
                            message_groups[content_key] = []
                        
                        message_groups[content_key].append(message)
                    
                    # Second pass: for each group, pick one message to keep
                    # Prefer messages with username (non-U prefixed IDs) over user IDs
                    for content_key, group in message_groups.items():
                        if not group:
                            continue
                            
                        # Sort the group to prefer usernames over user IDs
                        # (Slack IDs start with 'U' followed by alphanumeric chars)
                        sorted_group = sorted(group, key=lambda m: 1 if m.get("slackId", "").startswith("U") else 0)
                        
                        # Add the best one to our unique messages list
                        unique_messages.append(sorted_group[0])
                    
                    # Replace with deduplicated messages
                    original_count = len(data["messages"])
                    data["messages"] = unique_messages
                    
                    # Sort messages first by thread and then chronologically
                    
                    # 1. Group messages by thread
                    thread_groups = {}
                    for message in data["messages"]:
                        # For thread parents or standalone messages, use their createdAt as the thread key
                        thread_key = message.get("threadTs") or message.get("createdAt")
                        if thread_key not in thread_groups:
                            thread_groups[thread_key] = []
                        thread_groups[thread_key].append(message)
                    
                    # 2. Sort each thread group chronologically
                    for thread_key in thread_groups:
                        thread_groups[thread_key].sort(key=lambda m: m.get("createdAt", ""))
                    
                    # 3. Flatten the sorted thread groups into a single list
                    # First sort the threads themselves chronologically by their first message
                    sorted_thread_keys = sorted(thread_groups.keys())
                    
                    # Then flatten the groups
                    sorted_messages = []
                    for thread_key in sorted_thread_keys:
                        sorted_messages.extend(thread_groups[thread_key])
                    
                    # Update the messages list with sorted messages
                    data["messages"] = sorted_messages
                    
                    # Add original count to track deduplication stats
                    data["original_count"] = original_count
                    
                    # If duplicates were removed or messages were resorted, save the file
                    if len(unique_messages) < original_count or data["messages"] != unique_messages:
                        logger.info(f"Removed {original_count - len(unique_messages)} duplicate messages and sorted by thread and time")
                        self._save_entities_to_file(data)
                
                return data
        except Exception as e:
            logger.error(f"Error reading entity message data: {str(e)}")
            return None
            
    def convert_to_entity_format(self):
        """Convert existing message data to entity format"""
        # Load current data from traditional format
        old_data = self._load_messages_from_file()
        
        # Initialize new data structure
        new_data = {
            "channels": [],
            "messages": [],
            "last_updated": datetime.now().isoformat()
        }
        
        # Process each channel
        for channel_id, channel_data in old_data["channels"].items():
            # Create channel entity
            channel_entity = {
                "id": str(uuid.uuid4()),
                "slackId": channel_id,
                "name": channel_data["name"],
                "isPrivate": False  # Default value, could be updated if needed
            }
            
            # Add to channels list
            new_data["channels"].append(channel_entity)
            
            # Process each message in this channel
            for message in channel_data["messages"]:
                # Get username from user_info if available
                username = message.get("user", "unknown")
                if isinstance(message.get("user_info"), dict):
                    username = message["user_info"].get("name", username)
                elif message.get("user_id"):
                    username = message.get("user_id")
                
                # Convert timestamps to ISO format
                thread_ts = message.get("thread_ts")
                iso_thread_ts = self._convert_slack_ts_to_iso(thread_ts) if thread_ts else None
                iso_created_at = self._convert_slack_ts_to_iso(message.get("ts", ""))
                
                # Create message entity
                message_entity = {
                    "id": str(uuid.uuid4()),
                    "slackId": username,
                    "channelId": channel_id,
                    "text": message.get("text", ""),
                    "threadTs": iso_thread_ts,
                    "createdAt": iso_created_at
                }
                
                # Add to messages list
                new_data["messages"].append(message_entity)
        
        # Save the entity data
        self._save_entities_to_file(new_data)
        
        return {
            "status": "success",
            "channel_count": len(new_data["channels"]),
            "message_count": len(new_data["messages"])
        }
    
    async def add_channel(self, channel_name_or_id: str) -> Dict:
        """
        Start monitoring a channel by name or ID
        
        Args:
            channel_name_or_id: Channel name or ID to monitor
            
        Returns:
            Dict with channel information
        """
        try:
            # Get channel ID if name was provided
            channel_id = channel_name_or_id
            if not channel_name_or_id.startswith("C"):
                # Look up channel ID by name
                logger.info(f"Looking up channel ID for: {channel_name_or_id}")
                response = self.client.conversations_list()
                for channel in response["channels"]:
                    if channel["name"] == channel_name_or_id:
                        channel_id = channel["id"]
                        break
                else:
                    return {"status": "error", "error": f"Channel {channel_name_or_id} not found"}
            
            # Get initial info about the channel
            channel_info = self.client.conversations_info(channel=channel_id)["channel"]
            
            # Store channel in our monitored list
            self.monitored_channels[channel_id] = {
                "id": channel_id,
                "name": channel_info.get("name", "unknown"),
                "added_at": datetime.now().isoformat()
            }
            
            # Get initial history to establish latest timestamp
            history = self.client.conversations_history(channel=channel_id, limit=50)  # Increased limit to get more past messages
            messages = history.get("messages", [])
            
            if messages:
                # Store the latest timestamp we've seen
                self.latest_timestamps[channel_id] = messages[0].get("ts")
                # Cache these messages
                self.message_cache[channel_id] = messages
                
                # Add messages to JSON storage
                self._add_messages_to_storage(channel_id, messages)
                
                # Log info about channel
                channel_name = channel_info.get('name')
                logger.info(f"Added channel #{channel_name} ({channel_id}) with {len(messages)} initial messages")
                
                # Process any existing threads
                await self._process_threads(channel_id, messages)
            else:
                self.latest_timestamps[channel_id] = "0"
                self.message_cache[channel_id] = []
                logger.info(f"Added channel #{channel_info.get('name')} ({channel_id}) with no messages")
            
            return {
                "status": "success", 
                "channel": self.monitored_channels[channel_id],
                "message_count": len(messages)
            }
            
        except SlackApiError as e:
            logger.error(f"Error adding channel {channel_name_or_id}: {e.response['error']}")
            return {"status": "error", "error": e.response["error"]}
    
    async def _process_threads(self, channel_id: str, messages: List[Dict]) -> None:
        """
        Process thread replies for a list of messages
        
        Args:
            channel_id: The channel ID
            messages: List of message objects
        """
        for msg in messages:
            # Skip if no replies or already processed
            ts = msg.get("ts")
            reply_count = msg.get("reply_count", 0)
            thread_key = f"{channel_id}:{ts}"
            
            if reply_count > 0 and thread_key not in self.threads_seen:
                try:
                    logger.info(f"Reading {reply_count} thread replies in channel {channel_id}")
                    thread_replies = self.client.conversations_replies(
                        channel=channel_id,
                        ts=ts,
                        limit=100  # Get all replies
                    )
                    
                    # Process thread replies (store, analyze, etc)
                    thread_messages = thread_replies.get("messages", [])
                    
                    # Skip the first message as it's the parent
                    thread_replies = thread_messages[1:] if len(thread_messages) > 1 else []
                    
                    # Mark as processed
                    self.threads_seen.add(thread_key)
                    
                    # Add thread replies to storage
                    if thread_replies:
                        # Make sure all replies have the thread_ts set to the parent message
                        for reply in thread_replies:
                            if "thread_ts" not in reply:
                                reply["thread_ts"] = ts
                                
                        # Add replies to storage
                        self._add_thread_replies_to_storage(channel_id, thread_replies)
                    
                    logger.info(f"Processed thread with {len(thread_replies)} replies")
                    
                except SlackApiError as e:
                    logger.error(f"Error processing thread {ts}: {e.response['error']}")
    
    def _add_thread_replies_to_storage(self, channel_id, thread_replies):
        """Add thread replies to both JSON storage formats"""
        # Add to traditional storage format
        data = self._load_messages_from_file()
        
        if channel_id in data["channels"]:
            # Process each reply
            for reply in thread_replies:
                processed_reply = self._process_message_users(reply)
                
                # Check if this reply is already in the storage to avoid duplicates
                # Note: We need to check by ts (timestamp) which is the unique ID for messages
                existing_replies = [m for m in data["channels"][channel_id]["messages"] 
                                   if m.get("ts") == reply.get("ts")]
                
                if not existing_replies:
                    # Add to channel messages
                    data["channels"][channel_id]["messages"].insert(0, processed_reply)
            
            # Update metadata
            data["last_updated"] = datetime.now().isoformat()
            data["message_count"] = sum(len(channel_data["messages"]) for channel_data in data["channels"].values())
            
            # Save updated data
            self._save_messages_to_file(data)
        
        # Also add to entity storage format
        self._add_thread_replies_to_entity_storage(channel_id, thread_replies)
    
    def _add_thread_replies_to_entity_storage(self, channel_id, thread_replies):
        """Add thread replies to the entity-based JSON storage file"""
        # Load current entity data
        data = self._load_entities_from_file()
        
        # Create a set of existing message content keys to check for duplicates
        # We don't use slackId in the key to avoid duplicates with different ID formats
        existing_content = set()
        for message in data["messages"]:
            content_key = (
                message.get("text", ""), 
                message.get("channelId", ""),
                message.get("createdAt", "")
            )
            existing_content.add(content_key)
        
        # Process and add thread replies
        added_count = 0
        for reply in thread_replies:
            # Process user IDs in the message
            processed_reply = self._process_message_users(reply)
            
            # Get username from user_info if available
            username = processed_reply.get("user", "unknown")
            if isinstance(processed_reply.get("user_info"), dict):
                username = processed_reply["user_info"].get("name", username)
            elif processed_reply.get("user_id"):
                username = processed_reply.get("user_id")
            
            # Convert timestamps to ISO format
            thread_ts = processed_reply.get("thread_ts")
            iso_thread_ts = self._convert_slack_ts_to_iso(thread_ts) if thread_ts else None
            iso_created_at = self._convert_slack_ts_to_iso(processed_reply.get("ts", ""))
            
            # Create message entity for the reply
            message_entity = {
                "id": str(uuid.uuid4()),
                "slackId": username,
                "channelId": channel_id,
                "text": processed_reply.get("text", ""),
                "threadTs": iso_thread_ts,
                "createdAt": iso_created_at
            }
            
            # Check if this message content already exists before adding
            # We only check the content, not the user ID
            content_key = (
                message_entity["text"], 
                message_entity["channelId"],
                message_entity["createdAt"]
            )
            
            if content_key not in existing_content:
                # Add to messages list only if not a duplicate
                data["messages"].append(message_entity)
                existing_content.add(content_key)
                added_count += 1
        
        if added_count > 0:
            # Update metadata
            data["last_updated"] = datetime.now().isoformat()
            
            # Save updated data
            self._save_entities_to_file(data)
            logger.info(f"Added {added_count} new thread replies to entity storage")
        else:
            logger.info("No new thread replies added (all were duplicates)")
            
        return added_count
    
    async def check_for_updates(self) -> Dict:
        """
        Check all monitored channels for new messages
        
        Returns:
            Dict with update information
        """
        updates = {"new_messages": {}}
        
        for channel_id in self.monitored_channels:
            try:
                # Get messages newer than what we've seen
                latest_ts = self.latest_timestamps.get(channel_id, "0")
                
                history = self.client.conversations_history(
                    channel=channel_id,
                    limit=50,  # Reasonable limit for new messages
                    oldest=latest_ts  # Get messages newer than what we've seen
                )
                
                messages = history.get("messages", [])
                
                if messages and messages[0].get("ts") != latest_ts:
                    # Update the latest timestamp
                    self.latest_timestamps[channel_id] = messages[0].get("ts")
                    
                    # Filter out messages we've already seen
                    new_messages = [msg for msg in messages if msg.get("ts") != latest_ts]
                    
                    if new_messages:
                        channel_name = self.monitored_channels[channel_id]['name']
                        logger.info(f"Found {len(new_messages)} new messages in #{channel_name}")
                        
                        # Add to our message cache (prepend to keep chronological order)
                        self.message_cache[channel_id] = new_messages + self.message_cache[channel_id]
                        
                        # Add new messages to JSON storage
                        self._add_messages_to_storage(channel_id, new_messages)
                        
                        # Process any threads in the new messages
                        await self._process_threads(channel_id, new_messages)
                        
                        # Add to updates
                        updates["new_messages"][channel_id] = {
                            "count": len(new_messages),
                            "channel_name": self.monitored_channels[channel_id]["name"],
                            "messages": new_messages
                        }
                
                # Additionally, check for new replies in existing threads
                await self._check_thread_updates(channel_id)
            
            except SlackApiError as e:
                logger.error(f"Error checking channel {channel_id}: {e.response['error']}")
        
        return updates
    
    async def _check_thread_updates(self, channel_id: str):
        """Check for new replies in existing threads"""
        # Load existing messages
        data = self._load_messages_from_file()
        
        if channel_id not in data["channels"]:
            return
            
        # Find messages with threads
        threaded_messages = [
            msg for msg in data["channels"][channel_id]["messages"]
            if msg.get("reply_count", 0) > 0
        ]
        
        # Process up to 10 most recent threads to avoid rate limiting
        for message in threaded_messages[:10]:
            thread_ts = message.get("ts")
            thread_key = f"{channel_id}:{thread_ts}"
            
            # We'll check threads again periodically to get new replies
            # But we'll use reply_count to determine if we need to check
            previous_reply_count = message.get("reply_count", 0)
            
            try:
                # Get current thread state
                thread_info = self.client.conversations_replies(
                    channel=channel_id,
                    ts=thread_ts,
                    limit=100
                )
                
                thread_messages = thread_info.get("messages", [])
                current_reply_count = len(thread_messages) - 1  # Subtract 1 for the parent message
                
                # If there are new replies, process them
                if current_reply_count > previous_reply_count:
                    logger.info(f"Found {current_reply_count - previous_reply_count} new replies in thread {thread_ts}")
                    
                    # Skip the first message (parent) and only get new replies
                    new_replies = thread_messages[previous_reply_count+1:] if current_reply_count > 0 else []
                    
                    if new_replies:
                        # Make sure all replies have the thread_ts set
                        for reply in new_replies:
                            if "thread_ts" not in reply:
                                reply["thread_ts"] = thread_ts
                                
                        # Add replies to storage
                        self._add_thread_replies_to_storage(channel_id, new_replies)
                        
                        logger.info(f"Added {len(new_replies)} new replies to thread {thread_ts}")
                
            except SlackApiError as e:
                logger.error(f"Error checking thread {thread_ts}: {e.response['error']}")
                continue
    
    async def start_monitoring(self, channels: List[str] = None, interval: int = 60) -> None:
        """
        Start continuous monitoring of specified channels
        
        Args:
            channels: List of channel names or IDs to monitor
            interval: Polling interval in seconds
        """
        self.running = True
        
        # Add initial channels if specified
        if channels:
            for channel in channels:
                await self.add_channel(channel)
        
        logger.info(f"Starting continuous monitoring of {len(self.monitored_channels)} channels")
        
        # Main monitoring loop
        while self.running:
            try:
                # Check for new messages in all channels
                updates = await self.check_for_updates()
                
                # Process updates (this is where you'd add custom logic)
                new_message_count = sum(info["count"] for info in updates["new_messages"].values())
                
                if new_message_count > 0:
                    logger.info(f"Processed {new_message_count} new messages across all channels")
                
                # Wait for the next interval
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                await asyncio.sleep(interval)  # Still wait before retrying
    
    def stop_monitoring(self) -> None:
        """Stop the monitoring loop"""
        self.running = False
        logger.info("Stopping Slack channel monitoring")
    
    def get_channel_history(self, channel_id: str, limit: int = 100) -> List[Dict]:
        """
        Get cached message history for a channel
        
        Args:
            channel_id: The channel ID
            limit: Maximum number of messages to return
            
        Returns:
            List of message objects
        """
        if channel_id not in self.message_cache:
            return []
            
        return self.message_cache[channel_id][:limit]
    
    def get_monitored_channels(self) -> Dict:
        """
        Get information about all monitored channels
        
        Returns:
            Dict with channel information
        """
        return {
            cid: {
                "info": info,
                "message_count": len(self.message_cache.get(cid, [])),
                "latest_ts": self.latest_timestamps.get(cid)
            }
            for cid, info in self.monitored_channels.items()
        }
        
    def print_all_channel_messages(self, channel_id: str = None) -> None:
        """
        Print all cached messages for a channel or all channels to JSON file
        instead of console output.
        
        Args:
            channel_id: Optional specific channel ID to print, or None for all channels
        """
        # Instead of printing, ensure all messages are saved to the JSON file
        if channel_id:
            # Update JSON for specific channel
            if channel_id in self.message_cache:
                channel_name = self.monitored_channels[channel_id]['name']
                messages = self.message_cache[channel_id]
                
                logger.info(f"Saving {len(messages)} messages from channel #{channel_name} to JSON file")
                
                # Add to JSON storage
                self._add_messages_to_storage(channel_id, messages)
                
                # Log location of the data file
                logger.info(f"Messages saved to: {SLACK_MESSAGES_FILE}")
            else:
                logger.warning(f"No messages found for channel {channel_id}")
        else:
            # Update JSON for all channels
            for cid, info in self.monitored_channels.items():
                if cid in self.message_cache:
                    channel_name = info['name']
                    messages = self.message_cache[cid]
                    
                    logger.info(f"Saving {len(messages)} messages from channel #{channel_name} to JSON file")
                    
                    # Add to JSON storage
                    self._add_messages_to_storage(cid, messages)
            
            # Log location of the data file
            logger.info(f"All messages saved to: {SLACK_MESSAGES_FILE}")

    def get_json_message_data(self) -> Dict:
        """
        Get all messages from the JSON storage file
        
        Returns:
            Dict containing all messages and metadata
        """
        return self._load_messages_from_file()
        
    def update_existing_messages_with_user_info(self):
        """
        Update all existing messages in the JSON file with user information
        
        Returns:
            Dict with update status
        """
        try:
            logger.info("Starting update of existing messages with user info")
            data = self._load_messages_from_file()
            
            total_messages = data["message_count"]
            processed_count = 0
            
            # Process each channel
            for channel_id, channel_data in data["channels"].items():
                channel_name = channel_data.get("name", "unknown")
                logger.info(f"Processing {len(channel_data['messages'])} messages in channel {channel_name}")
                
                # Process each message in the channel
                for i, message in enumerate(channel_data["messages"]):
                    # Process user IDs in the message
                    processed_msg = self._process_message_users(message)
                    # Replace the original message with the processed one
                    channel_data["messages"][i] = processed_msg
                    processed_count += 1
                    
                    # Log progress periodically
                    if processed_count % 100 == 0:
                        logger.info(f"Processed {processed_count}/{total_messages} messages")
            
            # Update metadata
            data["last_updated"] = datetime.now().isoformat()
            
            # Save updated data
            self._save_messages_to_file(data)
            
            logger.info(f"Completed update of {processed_count} messages with user info")
            return {
                "status": "success",
                "processed_count": processed_count,
                "total_messages": total_messages
            }
            
        except Exception as e:
            logger.error(f"Error updating messages with user info: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

    def _get_user_info(self, user_id):
        """
        Get user information for a given user ID
        
        Args:
            user_id: The Slack user ID
            
        Returns:
            Dict containing user info
        """
        if not user_id:
            return {"id": "unknown", "name": "Unknown", "real_name": "Unknown User"}
            
        # Return cached user info if available
        if user_id in self.user_cache:
            return self.user_cache[user_id]
            
        try:
            # Fetch user info from Slack API
            result = self.client.users_info(user=user_id)
            user = result["user"]
            
            # Create user info dict
            user_info = {
                "id": user["id"],
                "name": user["name"],
                "real_name": user.get("real_name", user["name"]),
                "display_name": user["profile"].get("display_name", user["name"]),
                "image_url": user["profile"].get("image_72", "")
            }
            
            # Cache user info
            self.user_cache[user_id] = user_info
            return user_info
            
        except SlackApiError as e:
            logger.error(f"Error fetching user info for {user_id}: {e.response['error']}")
            return {"id": user_id, "name": "unknown", "real_name": "Unknown User"}
            
    def _process_message_users(self, message):
        """
        Process a message to replace user IDs with user info
        
        Args:
            message: The message to process
            
        Returns:
            Processed message with user info
        """
        # Make a copy of the message to avoid modifying the original
        processed_msg = message.copy()
        
        # Process the main message user
        if "user" in processed_msg and processed_msg["user"]:
            user_id = processed_msg["user"]
            user_info = self._get_user_info(user_id)
            # Store user ID and set user field to username for easier display
            processed_msg["user_id"] = user_id
            processed_msg["user"] = user_info["name"]
            processed_msg["user_info"] = user_info
        
        # Process reply users if present
        if "reply_users" in processed_msg and processed_msg["reply_users"]:
            # Store original IDs for reference
            processed_msg["reply_users_ids"] = processed_msg["reply_users"].copy()
            
            # Set reply_users to usernames
            reply_users_info = []
            reply_usernames = []
            for reply_user_id in processed_msg["reply_users"]:
                user_info = self._get_user_info(reply_user_id)
                reply_users_info.append(user_info)
                reply_usernames.append(user_info["name"])
            
            processed_msg["reply_users_info"] = reply_users_info
            processed_msg["reply_users"] = reply_usernames
            
        # Process message mentions in text
        if "text" in processed_msg and processed_msg["text"]:
            # Find user mentions in format <@USER_ID>
            mentions = re.findall(r'<@(U[A-Z0-9]+)>', processed_msg["text"])
            for mention_id in mentions:
                user_info = self._get_user_info(mention_id)
                # Replace mention with username
                processed_msg["text"] = processed_msg["text"].replace(
                    f"<@{mention_id}>", 
                    f"@{user_info['name']}"
                )
                
        return processed_msg

# Create a singleton instance
slack_monitor = SlackMonitor()

async def start_monitor(channels: List[str] = None, interval: int = 60) -> None:
    """
    Start the Slack monitor with specified channels
    
    Args:
        channels: List of channel names or IDs to monitor
        interval: Polling interval in seconds
    """
    await slack_monitor.start_monitoring(channels, interval)

# For testing the module directly
if __name__ == "__main__":
    print("=" * 50)
    print("SLACK CHANNEL MONITOR")
    print("=" * 50)
    
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python slack_monitor.py <channel_name> [<interval_seconds>]")
        print("Example: python slack_monitor.py general 30")
        sys.exit(1)
    
    channel = sys.argv[1]
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    
    print(f"Starting monitor for channel #{channel} with {interval}s interval")
    print("Press Ctrl+C to stop")
    
    try:
        # Setup the monitor and channels
        monitor = SlackMonitor()
        asyncio.run(monitor.add_channel(channel))
        
        # Then start monitoring
        asyncio.run(monitor.start_monitoring(interval=interval))
    except KeyboardInterrupt:
        print("\nMonitoring stopped") 