"""
TradeGumi Messaging Module

Discord integration for signal flow and decision notifications.
"""

import json
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class DiscordConfig:
    """Discord configuration."""
    incoming_channel: str
    outgoing_channel: str
    bot_token: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> 'DiscordConfig':
        """Load configuration from environment variables."""
        channels_str = os.getenv('TRADEGUMI_DISCORD_CHANNELS', '')
        channels = [c.strip() for c in channels_str.split(',') if c.strip()]
        
        if len(channels) >= 2:
            return cls(
                incoming_channel=channels[0],
                outgoing_channel=channels[1],
                bot_token=os.getenv('DISCORD_BOT_TOKEN')
            )
        else:
            return cls(
                incoming_channel='incoming-signals',
                outgoing_channel='outgoing-decisions',
                bot_token=os.getenv('DISCORD_BOT_TOKEN')
            )


class MessageHandler:
    """
    Handles Discord messaging for TradeGumi.
    
    Message Flow:
    1. Receive signal via webhook/Discord
    2. Process through decision engine
    3. Return decision JSON to channel
    """

    def __init__(self, config: Optional[DiscordConfig] = None):
        """
        Initialize message handler.
        
        Args:
            config: Discord configuration (uses env vars if not provided)
        """
        self.config = config or DiscordConfig.from_env()
        self.messages_sent = 0
        self.messages_received = 0

    def parse_inbound_signal(self, message_content: str) -> Optional[Dict[str, Any]]:
        """
        Parse inbound signal from Discord message.
        
        Args:
            message_content: Raw message content
            
        Returns:
            Parsed signal dictionary or None if invalid
        """
        self.messages_received += 1
        
        # Try to extract JSON from message
        try:
            # Handle code blocks
            if '```json' in message_content:
                # Extract JSON from code block
                start = message_content.find('```json') + 7
                end = message_content.find('```', start)
                json_str = message_content[start:end].strip()
            elif '```' in message_content:
                start = message_content.find('```') + 3
                end = message_content.find('```', start)
                json_str = message_content[start:end].strip()
            else:
                json_str = message_content.strip()
            
            signal_data = json.loads(json_str)
            return signal_data
            
        except (json.JSONDecodeError, ValueError) as e:
            # Not valid JSON
            return None

    def format_outbound_decision(self, decision_data: Dict[str, Any]) -> str:
        """
        Format decision output for Discord message.
        
        Args:
            decision_data: Decision output dictionary
            
        Returns:
            Formatted message string
        """
        # Create formatted message
        decision_emoji = {
            'approve': '✅',
            'reject': '❌',
            'modify': '⚠️'
        }
        
        emoji = decision_emoji.get(decision_data.get('decision', ''), '❓')
        
        # Build message
        lines = [
            f"{emoji} **TradeGumi Decision**",
            f"",
            f"**Signal ID:** `{decision_data.get('signal_id', 'unknown')}`",
            f"**Decision:** {decision_data.get('decision', 'unknown').upper()}",
            f"**Confidence:** {decision_data.get('confidence', 0):.1%}",
            f"**Size Adjustment:** {decision_data.get('size_adjustment', 1.0):.2f}x",
            f""
        ]
        
        # Add historical context
        hist_ctx = decision_data.get('historical_context', {})
        if hist_ctx:
            lines.extend([
                "**Historical Context:**",
                f"• Win Rate: {hist_ctx.get('win_rate', 0):.1%}",
                f"• Expectancy: {hist_ctx.get('expectancy', 0):.2f}R",
                f"• Sample Size: {hist_ctx.get('trade_count', 0)} trades",
                f""
            ])
        
        # Add notes
        if decision_data.get('notes'):
            lines.append(f"**Notes:** {decision_data.get('notes')}")
        
        return "\n".join(lines)

    def format_decision_json(self, decision_data: Dict[str, Any]) -> str:
        """
        Format decision as JSON for programmatic consumption.
        
        Args:
            decision_data: Decision output dictionary
            
        Returns:
            JSON string
        """
        return json.dumps(decision_data, indent=2)

    def send_decision(self, message: str, channel: Optional[str] = None,
                     as_json: bool = False) -> Dict[str, Any]:
        """
        Send decision message to Discord channel.
        
        Note: Actual Discord API integration would be implemented here.
        For now, returns message metadata for logging.
        
        Args:
            message: Message content
            channel: Target channel (uses outgoing_channel if not specified)
            as_json: Whether to send as JSON code block
            
        Returns:
            Message metadata
        """
        target_channel = channel or self.config.outgoing_channel
        
        # Format message
        if as_json:
            formatted_message = f"```json\n{message}\n```"
        else:
            formatted_message = message
        
        self.messages_sent += 1
        
        # Return metadata (actual sending would use Discord API)
        return {
            'channel': target_channel,
            'content': formatted_message,
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'sent'
        }

    def receive_signal(self, message_content: str) -> Optional[Dict[str, Any]]:
        """
        Receive and parse inbound signal.
        
        Args:
            message_content: Raw message content
            
        Returns:
            Parsed signal dictionary or None
        """
        return self.parse_inbound_signal(message_content)

    def get_stats(self) -> Dict[str, int]:
        """Get messaging statistics."""
        return {
            'messages_sent': self.messages_sent,
            'messages_received': self.messages_received
        }


class WebhookReceiver:
    """
    Receives signals via HTTP webhook.
    
    Alternative to Discord-based signal intake.
    """

    def __init__(self, message_handler: MessageHandler):
        """
        Initialize webhook receiver.
        
        Args:
            message_handler: MessageHandler instance
        """
        self.message_handler = message_handler
        self.webhooks_received = 0

    def handle_webhook(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Handle incoming webhook payload.
        
        Args:
            payload: Webhook JSON payload
            
        Returns:
            Parsed signal or None
        """
        self.webhooks_received += 1
        
        # Validate payload has required fields
        required_fields = ['symbol', 'side', 'indicators']
        if not all(field in payload for field in required_fields):
            return None
        
        return payload

    def get_stats(self) -> Dict[str, int]:
        """Get webhook statistics."""
        return {
            'webhooks_received': self.webhooks_received
        }
