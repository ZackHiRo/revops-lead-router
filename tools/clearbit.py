import httpx
import os
from typing import Dict, Any, Optional
from loguru import logger

class ClearbitEnricher:
    """Data enrichment provider using Clearbit API (with fallback to mock data)."""
    
    def __init__(self):
        self.api_key = os.getenv("CLEARBIT_API_KEY")
        self.base_url = "https://person.clearbit.com/v2"
        
    async def enrich_person(self, email: str) -> Dict[str, Any]:
        """Enrich person data using Clearbit Person API."""
        if not self.api_key:
            logger.warning("No Clearbit API key, using mock data")
            return self._mock_person_data(email)
        
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    f"{self.base_url}/combined/find",
                    params={"email": email},
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Clearbit person enrichment failed: {e}")
            return self._mock_person_data(email)
    
    async def enrich_company(self, domain: str) -> Dict[str, Any]:
        """Enrich company data using Clearbit Company API."""
        if not self.api_key:
            logger.warning("No Clearbit API key, using mock data")
            return self._mock_company_data(domain)
        
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    f"https://company.clearbit.com/v2/companies/find",
                    params={"domain": domain},
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Clearbit company enrichment failed: {e}")
            return self._mock_company_data(domain)
    
    def _mock_person_data(self, email: str) -> Dict[str, Any]:
        """Generate mock person data for testing/fallback."""
        return {
            "person": {
                "email": email,
                "name": {"fullName": "Mock Person"},
                "employment": {
                    "title": "Director of Engineering",
                    "seniority": "director"
                },
                "location": {"country": "US"}
            }
        }
    
    def _mock_company_data(self, domain: str) -> Dict[str, Any]:
        """Generate mock company data for testing/fallback."""
        return {
            "company": {
                "domain": domain,
                "name": f"Mock Company ({domain})",
                "employees": 120,
                "industry": "SaaS",
                "category": {"industry": "Technology"},
                "tech": ["AWS", "Snowflake", "Python"],
                "location": {"country": "US"}
            }
        }

# Global enricher instance
enricher = ClearbitEnricher()

def enrich_domain_person(domain: Optional[str] = None, email: Optional[str] = None) -> Dict[str, Any]:
    """
    Enrich lead data with company and person information.
    
    Args:
        domain: Company domain for company enrichment
        email: Person email for person enrichment
        
    Returns:
        Combined enrichment data
    """
    import asyncio
    
    try:
        # Run async enrichment functions
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        company_data = {}
        person_data = {}
        
        if domain:
            company_data = loop.run_until_complete(enricher.enrich_company(domain))
        
        if email:
            person_data = loop.run_until_complete(enricher.enrich_person(email))
        
        loop.close()
        
        # Combine and normalize data
        enrichment = {
            "company": company_data.get("company", {}),
            "person": person_data.get("person", {}),
            "enrichment_source": "clearbit" if enricher.api_key else "mock"
        }
        
        return enrichment
        
    except Exception as e:
        logger.error(f"Enrichment failed: {e}")
        # Return basic mock data as fallback
        return {
            "company": {
                "domain": domain,
                "employees": 100,
                "industry": "Technology"
            },
            "person": {
                "email": email,
                "seniority": "manager"
            },
            "enrichment_source": "fallback"
        }
