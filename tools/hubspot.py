import httpx
import os
from typing import Dict, Any, Optional
from loguru import logger

class HubSpotClient:
    """HubSpot CRM integration client."""
    
    def __init__(self):
        self.api_key = os.getenv("HUBSPOT_API_KEY")
        self.base_url = "https://api.hubapi.com"
        
        if not self.api_key:
            logger.warning("No HubSpot API key provided, using mock mode")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for HubSpot API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        } if self.api_key else {}
    
    def find_owner_by_rules(self, normalized: Dict[str, Any], enrichment: Dict[str, Any], routes: Dict[str, str]) -> str:
        """
        Find appropriate owner based on routing rules.
        
        Args:
            normalized: Normalized lead data
            enrichment: Enriched company/person data
            routes: Territory routing configuration
            
        Returns:
            Owner email address
        """
        if not self.api_key:
            logger.info("Using mock owner assignment")
            return self._mock_owner_assignment(normalized, enrichment, routes)
        
        try:
            # Try to find existing contact first
            existing_contact = self._find_contact_by_email(normalized.get("email"))
            if existing_contact and existing_contact.get("properties", {}).get("hubspot_owner_id"):
                return existing_contact["properties"]["hubspot_owner_id"]
            
            # Apply routing rules
            country = (normalized.get("country") or "").upper()
            industry = (enrichment.get("company", {}).get("industry") or "").lower()
            
            # Check for specific territory matches
            if country in routes:
                return routes[country]
            
            # Check for industry-specific routing
            industry_routes = {
                "saas": "saas-team@company.com",
                "fintech": "fintech-team@company.com",
                "ecommerce": "ecommerce-team@company.com"
            }
            
            if industry in industry_routes:
                return industry_routes[industry]
            
            # Default fallback
            return routes.get("DEFAULT", "unassigned@company.com")
            
        except Exception as e:
            logger.error(f"Owner lookup failed: {e}")
            return routes.get("DEFAULT", "unassigned@company.com")
    
    def create_or_update_contact(self, state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create or update contact in HubSpot.
        
        Args:
            state: Lead processing state
            
        Returns:
            Contact record or None if failed
        """
        if not self.api_key:
            logger.info("Using mock contact creation")
            return self._mock_contact_creation(state)
        
        try:
            normalized = state.get("normalized", {})
            enrichment = state.get("enrichment", {})
            
            # Prepare contact properties
            properties = {
                "email": normalized.get("email"),
                "firstname": normalized.get("full_name", "").split()[0] if normalized.get("full_name") else "",
                "lastname": " ".join(normalized.get("full_name", "").split()[1:]) if normalized.get("full_name") else "",
                "company": normalized.get("company"),
                "jobtitle": normalized.get("title"),
                "country": normalized.get("country"),
                "lead_score": str(state.get("score", 0)),
                "lead_source": normalized.get("source", "webhook")
            }
            
            # Add enrichment data
            if enrichment.get("company"):
                properties.update({
                    "company_size": str(enrichment["company"].get("employees", "")),
                    "industry": enrichment["company"].get("industry", ""),
                    "website": enrichment["company"].get("domain", "")
                })
            
            # Check if contact exists
            existing_contact = self._find_contact_by_email(normalized.get("email"))
            
            if existing_contact:
                # Update existing contact
                contact_id = existing_contact["id"]
                response = self._update_contact(contact_id, properties)
                logger.info(f"Updated existing contact {contact_id}")
                return {"id": contact_id, "action": "updated"}
            else:
                # Create new contact
                response = self._create_contact(properties)
                contact_id = response.get("id")
                logger.info(f"Created new contact {contact_id}")
                return {"id": contact_id, "action": "created"}
                
        except Exception as e:
            logger.error(f"Contact creation/update failed: {e}")
            return None
    
    def _find_contact_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Find contact by email address."""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    f"{self.base_url}/crm/v3/objects/contacts/search",
                    headers=self._get_headers(),
                    json={
                        "filterGroups": [{
                            "filters": [{
                                "propertyName": "email",
                                "operator": "EQ",
                                "value": email
                            }]
                        }]
                    }
                )
                response.raise_for_status()
                data = response.json()
                return data.get("results", [{}])[0] if data.get("results") else None
        except Exception as e:
            logger.error(f"Contact search failed: {e}")
            return None
    
    def _create_contact(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Create new contact in HubSpot."""
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}/crm/v3/objects/contacts",
                headers=self._get_headers(),
                json={"properties": properties}
            )
            response.raise_for_status()
            return response.json()
    
    def _update_contact(self, contact_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing contact in HubSpot."""
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.patch(
                f"{self.base_url}/crm/v3/objects/contacts/{contact_id}",
                headers=self._get_headers(),
                json={"properties": properties}
            )
            response.raise_for_status()
            return response.json()
    
    def _mock_owner_assignment(self, normalized: Dict[str, Any], enrichment: Dict[str, Any], routes: Dict[str, str]) -> str:
        """Mock owner assignment for testing."""
        country = (normalized.get("country") or "").upper()
        return routes.get(country, routes.get("DEFAULT", "mock@company.com"))
    
    def _mock_contact_creation(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Mock contact creation for testing."""
        return {"id": "mock_12345", "action": "created"}

# Global HubSpot client instance
hubspot_client = HubSpotClient()

def find_owner_by_rules(normalized: Dict[str, Any], enrichment: Dict[str, Any], routes: Dict[str, str]) -> str:
    """Find owner using the global HubSpot client."""
    return hubspot_client.find_owner_by_rules(normalized, enrichment, routes)

def create_or_update_contact(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create or update contact using the global HubSpot client."""
    return hubspot_client.create_or_update_contact(state)
