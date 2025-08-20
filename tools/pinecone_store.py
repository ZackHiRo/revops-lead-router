import os
from typing import List, Dict, Any
from loguru import logger

class PineconeStore:
    """Pinecone vector store for finding similar accounts and outcomes."""
    
    def __init__(self):
        self.api_key = os.getenv("PINECONE_API_KEY")
        self.index_name = os.getenv("PINECONE_INDEX", "revops-similar-accounts")
        self.index = None
        
        if self.api_key:
            try:
                import pinecone
                pinecone.init(api_key=self.api_key, environment="us-west1-gcp")
                self.index = pinecone.Index(self.index_name)
                logger.info(f"Pinecone index '{self.index_name}' connected successfully")
            except Exception as e:
                logger.error(f"Pinecone connection failed: {e}")
                self.index = None
        else:
            logger.warning("No Pinecone API key provided, using mock mode")
    
    def similar_accounts(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find similar accounts based on company characteristics.
        
        Args:
            state: Lead processing state
            
        Returns:
            List of similar accounts with outcomes
        """
        if not self.index:
            logger.info("Using mock similar accounts")
            return self._mock_similar_accounts(state)
        
        try:
            # Extract company features for vector search
            company_features = self._extract_company_features(state)
            
            # Create embedding vector (simplified - in production, use proper embedding model)
            vector = self._create_embedding_vector(company_features)
            
            # Query Pinecone
            query_response = self.index.query(
                vector=vector,
                top_k=3,
                include_metadata=True
            )
            
            # Process results
            similar_accounts = []
            for match in query_response.matches:
                account_data = {
                    "account": match.metadata.get("company_name", "Unknown"),
                    "outcome": match.metadata.get("outcome", "Unknown"),
                    "reason": match.metadata.get("similarity_reason", "Vector similarity"),
                    "score": match.score,
                    "metadata": match.metadata
                }
                similar_accounts.append(account_data)
            
            logger.info(f"Found {len(similar_accounts)} similar accounts")
            return similar_accounts
            
        except Exception as e:
            logger.error(f"Pinecone search failed: {e}")
            return self._mock_similar_accounts(state)
    
    def _extract_company_features(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant company features for similarity matching."""
        enrichment = state.get("enrichment", {})
        company = enrichment.get("company", {})
        
        features = {
            "industry": company.get("industry", "").lower(),
            "headcount": company.get("employees", 0),
            "tech_stack": company.get("tech", []),
            "country": state.get("normalized", {}).get("country", "").upper()
        }
        
        return features
    
    def _create_embedding_vector(self, features: Dict[str, Any]) -> List[float]:
        """
        Create a simple embedding vector from company features.
        In production, this would use a proper embedding model.
        """
        # This is a simplified mock embedding
        # In reality, you'd use OpenAI embeddings or similar
        vector = [0.0] * 1536  # OpenAI embedding dimension
        
        # Simple feature encoding (very basic)
        if features["industry"]:
            vector[0] = 0.1
        if features["headcount"] > 100:
            vector[1] = 0.2
        if features["tech_stack"]:
            vector[2] = 0.1
        if features["country"] == "US":
            vector[3] = 0.1
            
        return vector
    
    def _mock_similar_accounts(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate mock similar accounts for testing/fallback."""
        industry = state.get("enrichment", {}).get("company", {}).get("industry", "Technology")
        headcount = state.get("enrichment", {}).get("company", {}).get("employees", 100)
        
        mock_accounts = [
            {
                "account": "Acme Inc",
                "outcome": "Won",
                "reason": f"Same industry ({industry}) & similar size ({headcount} employees)",
                "score": 0.85,
                "metadata": {
                    "company_name": "Acme Inc",
                    "industry": industry,
                    "employees": headcount,
                    "outcome": "Won",
                    "deal_size": "$50K"
                }
            },
            {
                "account": "BetaCo",
                "outcome": "Lost",
                "reason": "Budget timing issues, but good ICP fit",
                "score": 0.72,
                "metadata": {
                    "company_name": "BetaCo",
                    "industry": industry,
                    "employees": headcount * 2,
                    "outcome": "Lost",
                    "reason": "Budget constraints"
                }
            },
            {
                "account": "Gamma Solutions",
                "outcome": "Won",
                "reason": "Similar tech stack and use case",
                "score": 0.78,
                "metadata": {
                    "company_name": "Gamma Solutions",
                    "industry": "SaaS",
                    "employees": headcount,
                    "outcome": "Won",
                    "deal_size": "$75K"
                }
            }
        ]
        
        return mock_accounts
    
    def store_account_outcome(self, company_data: Dict[str, Any], outcome: str, metadata: Dict[str, Any] = None):
        """
        Store account outcome for future similarity matching.
        
        Args:
            company_data: Company information
            outcome: Deal outcome (Won/Lost/No Decision)
            metadata: Additional metadata
        """
        if not self.index:
            logger.info("Mock mode: would store account outcome")
            return
        
        try:
            # Create embedding vector
            features = {
                "industry": company_data.get("industry", "").lower(),
                "headcount": company_data.get("employees", 0),
                "tech_stack": company_data.get("tech", []),
                "country": company_data.get("country", "").upper()
            }
            
            vector = self._create_embedding_vector(features)
            
            # Prepare metadata
            vector_metadata = {
                "company_name": company_data.get("name", "Unknown"),
                "industry": company_data.get("industry", ""),
                "employees": company_data.get("employees", 0),
                "outcome": outcome,
                "timestamp": "now"
            }
            
            if metadata:
                vector_metadata.update(metadata)
            
            # Generate unique ID
            import uuid
            vector_id = str(uuid.uuid4())
            
            # Upsert to Pinecone
            self.index.upsert(
                vectors=[(vector_id, vector, vector_metadata)]
            )
            
            logger.info(f"Stored account outcome for {company_data.get('name', 'Unknown')}")
            
        except Exception as e:
            logger.error(f"Failed to store account outcome: {e}")

# Global Pinecone store instance
pinecone_store = PineconeStore()

def similar_accounts(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find similar accounts using the global Pinecone store."""
    return pinecone_store.similar_accounts(state)

def store_account_outcome(company_data: Dict[str, Any], outcome: str, metadata: Dict[str, Any] = None):
    """Store account outcome using the global Pinecone store."""
    pinecone_store.store_account_outcome(company_data, outcome, metadata)
