import os
from typing import Dict, Any, Optional
from loguru import logger

class SlackNotifier:
    """Slack integration for sending lead notifications to sales teams."""
    
    def __init__(self):
        self.token = os.getenv("SLACK_BOT_TOKEN")
        self.default_channel = os.getenv("SLACK_DEFAULT_CHANNEL", "#sales-leads")
        
        if not self.token:
            logger.warning("No Slack token provided, using mock mode")
    
    def send_lead_notification(self, state: Dict[str, Any], channel: Optional[str] = None) -> Optional[str]:
        """
        Send lead notification to Slack channel.
        
        Args:
            state: Lead processing state
            channel: Slack channel (optional, uses default if not specified)
            
        Returns:
            Slack message timestamp or None if failed
        """
        if not self.token:
            logger.info("Mock mode: would send Slack notification")
            return "mock_timestamp_123"
        
        try:
            import slack_sdk
            from slack_sdk.web import WebClient
            from slack_sdk.errors import SlackApiError
            
            client = WebClient(token=self.token)
            target_channel = channel or self.default_channel
            
            # Build message
            message = self._build_lead_message(state)
            
            # Send message
            response = client.chat_postMessage(
                channel=target_channel,
                text=message["text"],
                blocks=message["blocks"]
            )
            
            message_ts = response["ts"]
            logger.info(f"Slack notification sent to {target_channel}: {message_ts}")
            
            return message_ts
            
        except Exception as e:
            logger.error(f"Slack notification failed: {e}")
            return None
    
    def send_high_priority_alert(self, state: Dict[str, Any], channel: Optional[str] = None) -> Optional[str]:
        """
        Send high-priority lead alert to dedicated channel.
        
        Args:
            state: Lead processing state
            channel: Slack channel (optional)
            
        Returns:
            Slack message timestamp or None if failed
        """
        if not self.token:
            logger.info("Mock mode: would send high-priority alert")
            return "mock_alert_timestamp_456"
        
        try:
            import slack_sdk
            from slack_sdk.web import WebClient
            
            client = WebClient(token=self.token)
            target_channel = channel or "#high-priority-leads"
            
            # Build high-priority message
            message = self._build_high_priority_message(state)
            
            # Send with @here mention
            response = client.chat_postMessage(
                channel=target_channel,
                text=message["text"],
                blocks=message["blocks"]
            )
            
            message_ts = response["ts"]
            logger.info(f"High-priority alert sent to {target_channel}: {message_ts}")
            
            return message_ts
            
        except Exception as e:
            logger.error(f"High-priority alert failed: {e}")
            return None
    
    def _build_lead_message(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Build Slack message for lead notification."""
        normalized = state.get("normalized", {})
        enrichment = state.get("enrichment", {})
        score = state.get("score", 0)
        owner = state.get("owner", "Unassigned")
        
        # Determine emoji based on score
        if score >= 0.8:
            emoji = "🚀"
            priority = "HIGH"
        elif score >= 0.6:
            emoji = "✅"
            priority = "MEDIUM"
        else:
            emoji = "📧"
            priority = "LOW"
        
        # Build text summary
        text = f"{emoji} New Lead: {normalized.get('full_name', 'Unknown')} from {normalized.get('company', 'Unknown')}"
        
        # Build rich blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} New Lead Assigned"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Name:*\n{normalized.get('full_name', 'Unknown')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Company:*\n{normalized.get('company', 'Unknown')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Title:*\n{normalized.get('title', 'Unknown')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Score:*\n{score:.2f}/1.0 ({priority})"
                    }
                ]
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Industry:*\n{enrichment.get('company', {}).get('industry', 'Unknown')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Size:*\n{enrichment.get('company', {}).get('employees', 'Unknown')} employees"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Country:*\n{normalized.get('country', 'Unknown')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Source:*\n{normalized.get('source', 'Unknown')}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Assigned to:* {owner}"
                }
            }
        ]
        
        # Add similar accounts if available
        similar_accounts = state.get("similar_accounts", [])
        if similar_accounts:
            similar_text = "\n".join([
                f"• {acc['account']} - {acc['outcome']}: {acc['reason']}"
                for acc in similar_accounts[:2]
            ])
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Similar Accounts:*\n{similar_text}"
                }
            })
        
        # Add action buttons
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View in CRM"
                    },
                    "url": f"https://app.hubspot.com/contacts/{state.get('crm_record_id', '')}",
                    "style": "primary"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Mark Contacted"
                    },
                    "value": f"contacted_{state.get('lead_id', '')}",
                    "action_id": "mark_contacted"
                }
            ]
        })
        
        return {"text": text, "blocks": blocks}
    
    def _build_high_priority_message(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Build high-priority Slack message."""
        normalized = state.get("normalized", {})
        score = state.get("score", 0)
        
        text = f"🚨 HIGH PRIORITY LEAD: {normalized.get('full_name', 'Unknown')} from {normalized.get('company', 'Unknown')} (Score: {score:.2f})"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 HIGH PRIORITY LEAD ALERT"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<here>* New high-priority lead requires immediate attention!"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Name:*\n{normalized.get('full_name', 'Unknown')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Company:*\n{normalized.get('company', 'Unknown')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Score:*\n{score:.2f}/1.0"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Owner:*\n{state.get('owner', 'Unassigned')}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Next Action:* Schedule discovery call within 2 hours"
                }
            }
        ]
        
        return {"text": text, "blocks": blocks}
    
    def update_message(self, channel: str, timestamp: str, new_text: str) -> bool:
        """
        Update an existing Slack message.
        
        Args:
            channel: Slack channel
            timestamp: Message timestamp
            new_text: New message text
            
        Returns:
            True if successful, False otherwise
        """
        if not self.token:
            logger.info("Mock mode: would update Slack message")
            return True
        
        try:
            import slack_sdk
            from slack_sdk.web import WebClient
            
            client = WebClient(token=self.token)
            
            response = client.chat_update(
                channel=channel,
                ts=timestamp,
                text=new_text
            )
            
            logger.info(f"Slack message updated: {timestamp}")
            return True
            
        except Exception as e:
            logger.error(f"Slack message update failed: {e}")
            return False

# Global Slack notifier instance
slack_notifier = SlackNotifier()

def send_lead_notification(state: Dict[str, Any], channel: Optional[str] = None) -> Optional[str]:
    """Send lead notification using the global Slack notifier."""
    return slack_notifier.send_lead_notification(state, channel)

def send_high_priority_alert(state: Dict[str, Any], channel: Optional[str] = None) -> Optional[str]:
    """Send high-priority alert using the global Slack notifier."""
    return slack_notifier.send_high_priority_alert(state, channel)
