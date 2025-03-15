from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from openagents.models.messages import BaseMessage, DirectMessage, BroadcastMessage, ProtocolMessage
from openagents.models.tool import AgentAdapterTool
from openagents.core.connector import NetworkConnector

class BaseProtocolAdapter(ABC):
    """Base class for agent adapter level protocols in OpenAgents.
    
    Agent adapter protocols define behaviors and capabilities for individual agents
    within the network.
    """

    def __init__(self, protocol_name: str):
        """Initialize the protocol adapter.
        
        Args:
            name: The name of the protocol adapter
        """
        self._protocol_name = protocol_name
        self._agent_id = None
        self._connector = None

    def bind_agent(self, agent_id: str) -> None:
        """Bind this protocol adapter to an agent.
        
        Args:
            agent_id: Unique identifier for the agent to bind to
        """
        self._agent_id = agent_id
    
    def bind_connector(self, connector: NetworkConnector) -> None:
        """Bind this protocol adapter to a connector.
        
        Args:
            connector: The connector to bind to
        """
        self._connector = connector

    @property
    def connector(self) -> NetworkConnector:
        """Get the connector for the protocol adapter.
        
        Returns:
            NetworkConnector: The connector for the protocol adapter
        """
        return self._connector
    
    @property
    def protocol_name(self) -> str:
        """Get the name of the protocol adapter.
        
        Returns:
            str: The name of the protocol adapter
        """
        return self._protocol_name
    
    @property
    def agent_id(self) -> Optional[str]:
        """Get the agent ID of the protocol adapter.
        
        Returns:
            Optional[str]: The agent ID of the protocol adapter
        """
        return self._agent_id
    
    def on_connect(self) -> None:
        """Called when the protocol adapter is connected to the network.
        """
    
    def on_disconnect(self) -> None:
        """Called when the protocol adapter is disconnected from the network.
        """
    
    def initialize(self) -> bool:
        """Initialize the protocol.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        return True
    
    def shutdown(self) -> bool:
        """Shutdown the protocol gracefully.
        
        Returns:
            bool: True if shutdown was successful, False otherwise
        """
        return True
    
    async def process_incoming_direct_message(self, message: DirectMessage) -> Optional[DirectMessage]:
        """Process an incoming message sent to this agent.
        
        Args:
            message: The message to handle
        
        Returns:
            Optional[DirectMessage]: The processed message, or None for stopping the message from being processed further by other adapters
        """
        return message
    
    async def process_incoming_broadcast_message(self, message: BroadcastMessage) -> Optional[BroadcastMessage]:
        """Process an incoming broadcast message.
        
        Args:
            message: The message to handle
        
        Returns:
            Optional[BroadcastMessage]: The processed message, or None for stopping the message from being processed further by other adapters
        """
        return message
    
    async def process_incoming_protocol_message(self, message: ProtocolMessage) -> Optional[ProtocolMessage]:
        """Process an incoming protocol message.
        
        Args:
            message: The message to handle
        
        Returns:
            Optional[ProtocolMessage]: The processed message, or None for stopping the message from being processed further by other adapters
        """
        return message
    
    async def process_outgoing_direct_message(self, message: DirectMessage) -> Optional[DirectMessage]:
        """Process an outgoing message sent to another agent.
        
        Args:
            message: The message to handle
        
        Returns:
            Optional[DirectMessage]: The processed message, or None for stopping the message from being processed further by other adapters
        """
        return message
        
    async def process_outgoing_broadcast_message(self, message: BroadcastMessage) -> Optional[BroadcastMessage]:
        """Process an outgoing broadcast message.
        
        Args:
            message: The message to handle
        
        Returns:
            Optional[BroadcastMessage]: The processed message, or None for stopping the message from being processed further by other adapters
        """
        return message

    async def process_outgoing_protocol_message(self, message: ProtocolMessage) -> Optional[ProtocolMessage]:
        """Process an outgoing protocol message.
        
        Args:
            message: The message to handle
        
        Returns:
            Optional[ProtocolMessage]: The processed message, or None for stopping the message from being processed further by other adapters
        """
        return message
    
    async def get_tools(self) -> List[AgentAdapterTool]:
        """Get the tools for the protocol adapter.
        
        Returns:
            List[AgentAdapterTool]: The tools for the protocol adapter
        """
        return []