from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from typing import List, Dict, Optional
import logging
from datetime import datetime
from backend.config import settings

logger = logging.getLogger(__name__)

class SlackService:
    def __init__(self):
        self.client = WebClient(token=settings.SLACK_BOT_TOKEN)
        
    async def get_channel_history(self, channel_id: str, limit: int = 100) -> List[Dict]:
        """
        Fetch the chat history for a specific channel.
        
        Args:
            channel_id (str): The ID of the channel to fetch history from
            limit (int): Maximum number of messages to fetch (default: 100)
            
        Returns:
            List[Dict]: List of messages from the channel
        """
        try:
            result = self.client.conversations_history(
                channel=channel_id,
                limit=limit
            )
            
            messages = result["messages"]
            formatted_messages = []
            
            for msg in messages:
                # Get user info for each message
                user_info = await self._get_user_info(msg.get("user"))
                
                formatted_messages.append({
                    "timestamp": datetime.fromtimestamp(float(msg.get("ts", 0))).isoformat(),
                    "user": user_info,
                    "text": msg.get("text", ""),
                    "reactions": msg.get("reactions", []),
                    "thread_ts": msg.get("thread_ts"),
                    "is_thread": bool(msg.get("thread_ts")),
                    "attachments": msg.get("attachments", []),
                    "files": msg.get("files", [])
                })
            
            return formatted_messages
            
        except SlackApiError as e:
            logger.error(f"Error fetching channel history: {e.response['error']}")
            return []
            
    async def _get_user_info(self, user_id: Optional[str]) -> Dict:
        """
        Get user information for a given user ID.
        
        Args:
            user_id (Optional[str]): The Slack user ID
            
        Returns:
            Dict: User information
        """
        if not user_id:
            return {"name": "Unknown", "real_name": "Unknown User"}
            
        try:
            result = self.client.users_info(user=user_id)
            user = result["user"]
            return {
                "id": user["id"],
                "name": user["name"],
                "real_name": user.get("real_name", user["name"]),
                "profile": {
                    "image_72": user["profile"].get("image_72", ""),
                    "email": user["profile"].get("email", "")
                }
            }
        except SlackApiError as e:
            logger.error(f"Error fetching user info: {e.response['error']}")
            return {"name": "Unknown", "real_name": "Unknown User"}
            
    async def track_channel(self, channel_id: str) -> Dict:
        """
        Start tracking a channel's messages.
        
        Args:
            channel_id (str): The ID of the channel to track
            
        Returns:
            Dict: Status of the tracking operation
        """
        try:
            # Get channel info
            channel_info = self.client.conversations_info(channel=channel_id)
            channel = channel_info["channel"]
            
            # Get initial history
            messages = await self.get_channel_history(channel_id)
            
            return {
                "status": "success",
                "channel": {
                    "id": channel["id"],
                    "name": channel["name"],
                    "topic": channel.get("topic", {}).get("value", ""),
                    "purpose": channel.get("purpose", {}).get("value", ""),
                    "member_count": channel.get("num_members", 0)
                },
                "message_count": len(messages),
                "messages": messages
            }
            
        except SlackApiError as e:
            logger.error(f"Error tracking channel: {e.response['error']}")
            return {
                "status": "error",
                "error": e.response["error"]
            }
    
    async def process_message_event(self, event: Dict) -> Dict:
        """
        Process an incoming Slack message event.
        
        Args:
            event (Dict): The Slack event data
            
        Returns:
            Dict: The processed message
        """
        try:
            # Extract important information
            channel_id = event.get("channel")
            user_id = event.get("user")
            text = event.get("text", "")
            ts = event.get("ts")
            
            # Get user details
            user_info = await self._get_user_info(user_id)
            
            # Format the message
            message = {
                "timestamp": datetime.fromtimestamp(float(ts or 0)).isoformat(),
                "channel_id": channel_id,
                "user": user_info,
                "text": text,
                "thread_ts": event.get("thread_ts"),
                "is_thread": bool(event.get("thread_ts")),
                "attachments": event.get("attachments", []),
                "files": event.get("files", []),
                "is_bot": bool(event.get("bot_id")),
            }
            
            # Log the message
            logger.info(f"New message in channel {channel_id} from {user_info.get('name')}: {text[:50]}...")
            
            # Here you would add additional logic to store the message in a database
            # For example:
            # await database.store_message(message)
            
            return message
            
        except Exception as e:
            logger.error(f"Error processing message event: {str(e)}")
            raise
            
    async def process_message(self, text: str, user_id: str, channel_id: str, ts: str) -> Dict:
        """
        Process a message received through Socket Mode.
        
        Args:
            text (str): The message text
            user_id (str): The user who sent the message
            channel_id (str): The channel the message was sent in
            ts (str): The message timestamp
            
        Returns:
            Dict: The processed message
        """
        try:
            # Get user details
            user_info = await self._get_user_info(user_id)
            
            # Format the message
            message = {
                "timestamp": datetime.fromtimestamp(float(ts or 0)).isoformat(),
                "channel_id": channel_id,
                "user": user_info,
                "text": text,
            }
            
            # Log the message
            logger.info(f"Socket Mode: Message in channel {channel_id} from {user_info.get('name')}: {text[:50]}...")
            
            # Here you would add logic to process the message
            # For example, respond to commands, store in database, etc.
            
            # Example: Respond to a simple greeting
            if text.lower().startswith(("hi", "hello", "hey")):
                await self.send_message(
                    channel_id=channel_id,
                    text=f"Hello <@{user_id}>! How can I help you today?"
                )
            
            return message
            
        except Exception as e:
            logger.error(f"Error processing Socket Mode message: {str(e)}")
            raise
            
    async def send_message(self, channel_id: str, text: str, thread_ts: Optional[str] = None) -> Dict:
        """
        Send a message to a Slack channel.
        
        Args:
            channel_id (str): The channel to send the message to
            text (str): The message text
            thread_ts (Optional[str]): Thread timestamp if replying in a thread
            
        Returns:
            Dict: The Slack API response
        """
        try:
            params = {
                "channel": channel_id,
                "text": text
            }
            
            if thread_ts:
                params["thread_ts"] = thread_ts
                
            response = self.client.chat_postMessage(**params)
            return response
        except SlackApiError as e:
            logger.error(f"Error sending message: {e.response['error']}")
            raise
