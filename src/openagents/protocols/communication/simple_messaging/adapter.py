"""
Agent-level simple messaging protocol for OpenAgents.

This protocol enables direct and broadcast messaging between agents with support for text and file attachments.
"""

import logging
import base64
import os
import uuid
import tempfile
from typing import Dict, Any, List, Optional, Callable, Union
from pathlib import Path

from openagents.core.base_protocol_adapter import BaseProtocolAdapter
from openagents.models.messages import (
    DirectMessage,
    BroadcastMessage,
    ProtocolMessage
)
from openagents.models.tool import AgentAdapterTool
from openagents.utils.message_util import (
    get_direct_message_thread_id,
    get_broadcast_message_thread_id,
    get_protocol_message_thread_id
)

logger = logging.getLogger(__name__)

# Type definitions for message handlers
MessageHandler = Callable[[Dict[str, Any], str], None]
FileHandler = Callable[[str, bytes, Dict[str, Any], str], None]

class SimpleMessagingAgentAdapter(BaseProtocolAdapter):
    """Agent-level simple messaging protocol implementation.
    
    This protocol enables:
    - Direct messaging between agents with text and file attachments
    - Broadcast messaging to all agents with text and file attachments
    - File transfer between agents
    """
    
    def __init__(self):
        """Initialize the simple messaging protocol for an agent.
        
        Args:
            agent_id: Unique identifier for the agent
        """
        super().__init__(
            protocol_name="simple_messaging"
        )
        
        # Initialize protocol state
        self.message_handlers: Dict[str, MessageHandler] = {}
        self.file_handlers: Dict[str, FileHandler] = {}
        self.pending_file_downloads: Dict[str, Dict[str, Any]] = {}  # request_id -> file metadata
        self.temp_dir = None
        self.file_storage_path = None

    
    def initialize(self) -> bool:
        """Initialize the protocol.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
                
        # Create a temporary directory for file storage
        self.temp_dir = tempfile.TemporaryDirectory(prefix=f"openagents_agent_{self.agent_id}_")
        self.file_storage_path = Path(self.temp_dir.name)
        
        logger.info(f"Initializing Simple Messaging protocol for agent {self.agent_id} with file storage at {self.file_storage_path}")
        return True
    
    def shutdown(self) -> bool:
        """Shutdown the protocol.
        
        Returns:
            bool: True if shutdown was successful, False otherwise
        """
        # Clean up the temporary directory
        try:
            self.temp_dir.cleanup()
            logger.info(f"Cleaned up temporary file storage directory for agent {self.agent_id}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory for agent {self.agent_id}: {e}")
        
        return True
    
    async def process_incoming_direct_message(self, message: DirectMessage) -> None:
        """Process an incoming direct message.
        
        Args:
            message: The direct message to process
        """
        logger.debug(f"Received direct message from {message.sender_id}")
        
        # Add message to the appropriate conversation thread
        thread_id = get_direct_message_thread_id(message.sender_id)
        self.add_message_to_thread(thread_id, message, text_representation=message.content.get("text", ""))
        
        # Check if the message contains file references
        if "files" in message.content and message.content["files"]:
            # Process file references
            await self._process_file_references(message)
        
        # Call registered message handlers
        for handler in self.message_handlers.values():
            try:
                handler(message.content, message.sender_id)
            except Exception as e:
                logger.error(f"Error in message handler: {e}")
    
    async def process_incoming_broadcast_message(self, message: BroadcastMessage) -> None:
        """Process an incoming broadcast message.
        
        Args:
            message: The broadcast message to process
        """
        logger.debug(f"Received broadcast message from {message.sender_id}")
        
        # Add message to the broadcast conversation thread
        thread_id = get_broadcast_message_thread_id()
        self.add_message_to_thread(thread_id, message, text_representation=message.content.get("text", ""))
        
        # Check if the message contains file references
        if "files" in message.content and message.content["files"]:
            # Process file references
            await self._process_file_references(message)
        
        # Call registered message handlers
        for handler in self.message_handlers.values():
            try:
                handler(message.content, message.sender_id)
            except Exception as e:
                logger.error(f"Error in message handler: {e}")
    
    async def process_incoming_protocol_message(self, message: ProtocolMessage) -> None:
        """Process an incoming protocol message.
        
        Args:
            message: The protocol message to process
        """
        logger.debug(f"Received protocol message from {message.sender_id}")
        
        # Handle protocol-specific messages
        action = message.content.get("action", "")
        
        if action == "file_download_response":
            # Handle file download response
            request_id = message.content.get("request_id")
            if request_id in self.pending_file_downloads:
                await self._handle_file_download_response(message)
        elif action == "file_deletion_response":
            # Handle file deletion response
            logger.debug(f"File deletion response: {message.content.get('success', False)}")
    
    def shutdown(self) -> bool:
        """Shutdown the protocol gracefully.
        
        Returns:
            bool: True if shutdown was successful, False otherwise
        """
        # Clean up the temporary directory
        try:
            self.temp_dir.cleanup()
            logger.info(f"Cleaned up temporary file storage directory for agent {self.agent_id}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory for agent {self.agent_id}: {e}")
        
        return True
    
    async def send_direct_message(self, target_agent_id: str, content: Dict[str, Any]) -> None:
        """Send a direct message to a specific agent.
        
        Args:
            target_agent_id: ID of the target agent
            content: Message content
        """
        if self.connector is None:
            logger.error(f"Cannot send message: connector is None for agent {self.agent_id}")
            return f"Error: Agent {self.agent_id} is not connected to a network"
            
        # Create and send the message
        message = DirectMessage(
            sender_id=self.agent_id,
            target_agent_id=target_agent_id,
            content=content,
            direction="outbound"
        )
        
        # Add message to the conversation thread
        thread_id = get_direct_message_thread_id(target_agent_id)
        self.add_message_to_thread(thread_id, message, requires_response=False, text_representation=message.content.get("text", ""))
        
        await self.connector.send_direct_message(message)
        logger.debug(f"Sent direct message to {target_agent_id}")
    
    async def send_broadcast_message(self, content: Dict[str, Any]) -> None:
        """Send a broadcast message to all agents.
        
        Args:
            content: Message content
        """
        if self.connector is None:
            logger.error(f"Cannot send broadcast message: connector is None for agent {self.agent_id}")
            return f"Error: Agent {self.agent_id} is not connected to a network"
            
        # Create and send the message
        message = BroadcastMessage(
            sender_id=self.agent_id,
            content=content,
            direction="outbound"
        )
        
        # Add message to the broadcast conversation thread
        thread_id = get_broadcast_message_thread_id()
        self.add_message_to_thread(thread_id, message, requires_response=False, text_representation=message.content.get("text", ""))
        
        await self.connector.send_broadcast_message(message)
        logger.debug("Sent broadcast message")
    
    async def send_text_message(self, target_agent_id: str, text: str) -> None:
        """Send a text message to a specific agent.
        
        Args:
            target_agent_id: ID of the target agent
            text: Text content of the message
        """
        if self.connector is None:
            logger.error(f"Cannot send message: connector is None for agent {self.agent_id}")
            return f"Error: Agent {self.agent_id} is not connected to a network"
            
        content = {"text": text}
        await self.send_direct_message(target_agent_id, content)
    
    async def broadcast_text_message(self, text: str) -> None:
        """Broadcast a text message to all agents.
        
        Args:
            text: Text content of the message
        """
        if self.connector is None:
            logger.error(f"Cannot broadcast message: connector is None for agent {self.agent_id}")
            return f"Error: Agent {self.agent_id} is not connected to a network"
            
        content = {"text": text}
        await self.send_broadcast_message(content)
    
    async def send_file(self, target_agent_id: str, file_path: Union[str, Path], message_text: Optional[str] = None) -> None:
        """Send a file to a specific agent.
        
        Args:
            target_agent_id: ID of the target agent
            file_path: Path to the file to send
            message_text: Optional text message to include
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return
        
        try:
            # Read the file
            with open(file_path, "rb") as f:
                file_content = f.read()
            
            # Encode as base64
            encoded_content = base64.b64encode(file_content).decode("utf-8")
            
            # Create message content
            content = {
                "files": [
                    {
                        "filename": file_path.name,
                        "content": encoded_content,
                        "mime_type": self._get_mime_type(file_path),
                        "size": len(file_content)
                    }
                ]
            }
            
            # Add text if provided
            if message_text:
                content["text"] = message_text
            
            # Send the message
            await self.send_direct_message(target_agent_id, content)
            logger.debug(f"Sent file {file_path.name} to {target_agent_id}")
        except Exception as e:
            logger.error(f"Error sending file: {e}")
    
    async def broadcast_file(self, file_path: Union[str, Path], message_text: Optional[str] = None) -> None:
        """Broadcast a file to all agents.
        
        Args:
            file_path: Path to the file to send
            message_text: Optional text message to include
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return
        
        try:
            # Read the file
            with open(file_path, "rb") as f:
                file_content = f.read()
            
            # Encode as base64
            encoded_content = base64.b64encode(file_content).decode("utf-8")
            
            # Create message content
            content = {
                "files": [
                    {
                        "filename": file_path.name,
                        "content": encoded_content,
                        "mime_type": self._get_mime_type(file_path),
                        "size": len(file_content)
                    }
                ]
            }
            
            # Add text if provided
            if message_text:
                content["text"] = message_text
            
            # Send the message
            await self.send_broadcast_message(content)
            logger.debug(f"Broadcast file {file_path.name}")
        except Exception as e:
            logger.error(f"Error broadcasting file: {e}")
    
    async def download_file(self, file_id: str) -> None:
        """Download a file from the network.
        
        Args:
            file_id: ID of the file to download
        """
        # Generate a request ID
        request_id = str(uuid.uuid4())
        
        # Create and send the protocol message
        message = ProtocolMessage(
            sender_id=self.agent_id,
            protocol="simple_messaging",
            content={
                "action": "get_file",
                "file_id": file_id
            },
            direction="outbound",
            relevant_agent_id=self.agent_id
        )
        
        # Store the request ID for later reference
        self.pending_file_downloads[message.message_id] = {
            "file_id": file_id,
            "timestamp": message.timestamp
        }
        
        await self.connector.send_protocol_message(message)
        logger.debug(f"Requested file download for file ID {file_id}")
    
    async def delete_file(self, file_id: str) -> None:
        """Request deletion of a file from the network.
        
        Args:
            file_id: ID of the file to delete
        """
        # Create and send the protocol message
        message = ProtocolMessage(
            sender_id=self.agent_id,
            protocol="simple_messaging",
            content={
                "action": "delete_file",
                "file_id": file_id
            },
            direction="outbound",
            relevant_agent_id=self.agent_id
        )
        
        await self.connector.send_protocol_message(message)
        logger.debug(f"Requested file deletion for file ID {file_id}")
    
    def register_message_handler(self, handler_id: str, handler: MessageHandler) -> None:
        """Register a handler for incoming messages.
        
        Args:
            handler_id: Unique identifier for the handler
            handler: Function to call when a message is received
        """
        self.message_handlers[handler_id] = handler
        logger.debug(f"Registered message handler {handler_id}")
    
    def unregister_message_handler(self, handler_id: str) -> None:
        """Unregister a message handler.
        
        Args:
            handler_id: Identifier of the handler to unregister
        """
        if handler_id in self.message_handlers:
            del self.message_handlers[handler_id]
            logger.debug(f"Unregistered message handler {handler_id}")
    
    def register_file_handler(self, handler_id: str, handler: FileHandler) -> None:
        """Register a handler for incoming files.
        
        Args:
            handler_id: Unique identifier for the handler
            handler: Function to call when a file is received
        """
        self.file_handlers[handler_id] = handler
        logger.debug(f"Registered file handler {handler_id}")
    
    def unregister_file_handler(self, handler_id: str) -> None:
        """Unregister a file handler.
        
        Args:
            handler_id: Identifier of the handler to unregister
        """
        if handler_id in self.file_handlers:
            del self.file_handlers[handler_id]
            logger.debug(f"Unregistered file handler {handler_id}")
    
    async def _process_file_references(self, message: Union[DirectMessage, BroadcastMessage]) -> None:
        """Process file references in a message.
        
        Args:
            message: The message containing file references
        """
        files = message.content.get("files", [])
        
        for file_data in files:
            if "file_id" in file_data and "filename" in file_data:
                # This is a file reference, download it
                file_id = file_data["file_id"]
                await self.download_file(file_id)
    
    async def _handle_file_download_response(self, message: ProtocolMessage) -> None:
        """Handle a file download response.
        
        Args:
            message: The protocol message containing the file download response
        """
        request_id = message.content.get("request_id")
        success = message.content.get("success", False)
        
        if not success:
            logger.error(f"File download failed: {message.content.get('error', 'Unknown error')}")
            # Clean up pending download
            if request_id in self.pending_file_downloads:
                del self.pending_file_downloads[request_id]
            return
        
        file_id = message.content.get("file_id")
        encoded_content = message.content.get("content")
        
        if not file_id or not encoded_content:
            logger.error("Missing file ID or content in download response")
            return
        
        try:
            # Decode the file content
            file_content = base64.b64decode(encoded_content)
            
            # Save the file
            file_path = self.file_storage_path / file_id
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            logger.debug(f"Downloaded file {file_id}")
            
            # Call registered file handlers
            for handler in self.file_handlers.values():
                try:
                    # Get original request metadata
                    metadata = self.pending_file_downloads.get(request_id, {})
                    handler(file_id, file_content, metadata, message.sender_id)
                except Exception as e:
                    logger.error(f"Error in file handler: {e}")
            
            # Clean up pending download
            if request_id in self.pending_file_downloads:
                del self.pending_file_downloads[request_id]
        except Exception as e:
            logger.error(f"Error handling file download: {e}")
    
    def _get_mime_type(self, file_path: Path) -> str:
        """Get the MIME type for a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            str: MIME type of the file
        """
        # Simple MIME type detection based on extension
        extension = file_path.suffix.lower()
        
        mime_types = {
            ".txt": "text/plain",
            ".html": "text/html",
            ".htm": "text/html",
            ".json": "application/json",
            ".xml": "application/xml",
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".ppt": "application/vnd.ms-powerpoint",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".mp3": "audio/mpeg",
            ".mp4": "video/mp4",
            ".wav": "audio/wav",
            ".zip": "application/zip",
            ".tar": "application/x-tar",
            ".gz": "application/gzip",
            ".csv": "text/csv",
            ".py": "text/x-python",
            ".js": "text/javascript",
            ".css": "text/css"
        }
        
        return mime_types.get(extension, "application/octet-stream") 
    
    def get_tools(self) -> List[AgentAdapterTool]:
        """Get the tools for the protocol adapter.
        
        Returns:
            List[AgentAdapterTool]: The tools for the protocol adapter
        """
        tools = []
        
        # Tool for sending a text message to a specific agent
        send_text_tool = AgentAdapterTool(
            name="send_text_message",
            description="Send a text message to a specific agent",
            input_schema={
                "type": "object",
                "properties": {
                    "target_agent_id": {
                        "type": "string",
                        "description": "ID of the agent to send the message to"
                    },
                    "text": {
                        "type": "string",
                        "description": "Text content of the message"
                    }
                },
                "required": ["target_agent_id", "text"]
            },
            func=self.send_text_message
        )
        tools.append(send_text_tool)
        
        # Tool for broadcasting a text message to all agents
        broadcast_text_tool = AgentAdapterTool(
            name="broadcast_text_message",
            description="Broadcast a text message to all agents",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text content of the message"
                    }
                },
                "required": ["text"]
            },
            func=self.broadcast_text_message
        )
        tools.append(broadcast_text_tool)
        
        # Tool for sending a file to a specific agent
        send_file_tool = AgentAdapterTool(
            name="send_file",
            description="Send a file to a specific agent",
            input_schema={
                "type": "object",
                "properties": {
                    "target_agent_id": {
                        "type": "string",
                        "description": "ID of the agent to send the file to"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to send"
                    },
                    "message_text": {
                        "type": "string",
                        "description": "Optional text message to include with the file"
                    }
                },
                "required": ["target_agent_id", "file_path"]
            },
            func=self.send_file
        )
        tools.append(send_file_tool)
        
        # Tool for broadcasting a file to all agents
        broadcast_file_tool = AgentAdapterTool(
            name="broadcast_file",
            description="Broadcast a file to all agents",
            input_schema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to broadcast"
                    },
                    "message_text": {
                        "type": "string",
                        "description": "Optional text message to include with the file"
                    }
                },
                "required": ["file_path"]
            },
            func=self.broadcast_file
        )
        tools.append(broadcast_file_tool)
        
        # Tool for downloading a file
        download_file_tool = AgentAdapterTool(
            name="download_file",
            description="Download a file from the network",
            input_schema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "ID of the file to download"
                    }
                },
                "required": ["file_id"]
            },
            func=self.download_file
        )
        tools.append(download_file_tool)
        
        # Tool for deleting a file
        delete_file_tool = AgentAdapterTool(
            name="delete_file",
            description="Request deletion of a file from the network",
            input_schema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "ID of the file to delete"
                    }
                },
                "required": ["file_id"]
            },
            func=self.delete_file
        )
        tools.append(delete_file_tool)
        
        return tools