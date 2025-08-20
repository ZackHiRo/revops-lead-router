import os
import json
from typing import Tuple, List, Dict, Any
from loguru import logger

class LLMClient:
    """LLM client for scoring and summarization tasks."""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4")
        
        if not self.api_key:
            logger.warning("No OpenAI API key provided, using mock mode")
    
    def score_lead_with_rubric(self, state: Dict[str, Any], base_hint: float = 0.0) -> Tuple[float, List[str]]:
        """
        Score lead using LLM with scoring rubric.
        
        Args:
            state: Lead processing state
            base_hint: Base score from rule-based scoring
            
        Returns:
            Tuple of (score, reasons)
        """
        if not self.api_key:
            logger.info("Using mock LLM scoring")
            return self._mock_scoring(state, base_hint)
        
        try:
            # Prepare prompt
            prompt = self._build_scoring_prompt(state, base_hint)
            
            # Call OpenAI API
            import openai
            openai.api_key = self.api_key
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_scoring_rubric()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            # Parse response
            content = response.choices[0].message.content
            result = self._parse_scoring_response(content)
            
            logger.info(f"LLM scoring completed: {result['score']}")
            return result['score'], result['reasons']
            
        except Exception as e:
            logger.error(f"LLM scoring failed: {e}")
            return self._mock_scoring(state, base_hint)
    
    def summarize_for_ae(self, state: Dict[str, Any], similar_accounts: List[Dict[str, Any]]) -> str:
        """
        Generate lead summary for Account Executives.
        
        Args:
            state: Lead processing state
            similar_accounts: List of similar accounts
            
        Returns:
            Formatted summary string
        """
        if not self.api_key:
            logger.info("Using mock LLM summarization")
            return self._mock_summary(state, similar_accounts)
        
        try:
            # Prepare prompt
            prompt = self._build_summary_prompt(state, similar_accounts)
            
            # Call OpenAI API
            import openai
            openai.api_key = self.api_key
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_summary_rubric()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            summary = response.choices[0].message.content
            logger.info("LLM summary generated successfully")
            return summary
            
        except Exception as e:
            logger.error(f"LLM summarization failed: {e}")
            return self._mock_summary(state, similar_accounts)
    
    def _get_scoring_rubric(self) -> str:
        """Get the scoring rubric for LLM."""
        return """You are a Senior RevOps Analyst tasked with scoring B2B leads.

SCORING CRITERIA:
- Score range: 0.0 to 1.0
- ICP industries: SaaS, FinTech, Ecommerce, HealthTech, EdTech
- Minimum headcount: 20+ employees
- Preferred titles: Director+, VP, C-level, Head of, Lead
- Geographic focus: US, CA, UK, DE, FR, MA
- Penalty for free email domains (gmail, yahoo, etc.)

Return ONLY valid JSON in this format:
{"score": 0.85, "reasons": ["ICP match: SaaS", "Seniority: Director", "Good headcount: 150"]}"""
    
    def _get_summary_rubric(self) -> str:
        """Get the summary rubric for LLM."""
        return """You are a Sales Operations Specialist creating lead summaries for Account Executives.

Create a concise, actionable summary with 6-8 bullet points covering:
- Who they are (company, role, industry)
- Why now (timing signals, pain points)
- Similar accounts (success stories, patterns)
- Next best action (immediate next step)

Keep it professional, data-driven, and sales-ready."""
    
    def _build_scoring_prompt(self, state: Dict[str, Any], base_hint: float) -> str:
        """Build the scoring prompt for LLM."""
        normalized = state.get("normalized", {})
        enrichment = state.get("enrichment", {})
        
        prompt = f"""Score this lead based on the rubric:

LEAD DATA:
- Email: {normalized.get('email', 'N/A')}
- Company: {normalized.get('company', 'N/A')}
- Title: {normalized.get('title', 'N/A')}
- Country: {normalized.get('country', 'N/A')}
- Source: {normalized.get('source', 'N/A')}

ENRICHMENT:
- Industry: {enrichment.get('company', {}).get('industry', 'N/A')}
- Headcount: {enrichment.get('company', {}).get('employees', 'N/A')}
- Tech Stack: {enrichment.get('company', {}).get('tech', [])}
- Seniority: {enrichment.get('person', {}).get('seniority', 'N/A')}

Rule-based score hint: {base_hint:.3f}

Score this lead and provide specific reasons:"""
        
        return prompt
    
    def _build_summary_prompt(self, state: Dict[str, Any], similar_accounts: List[Dict[str, Any]]) -> str:
        """Build the summary prompt for LLM."""
        normalized = state.get("normalized", {})
        enrichment = state.get("enrichment", {})
        score = state.get("score", 0)
        
        # Format similar accounts
        similar_text = ""
        for i, account in enumerate(similar_accounts[:3], 1):
            similar_text += f"{i}. {account['account']} - {account['outcome']}: {account['reason']}\n"
        
        prompt = f"""Create a sales-ready summary for this lead:

LEAD: {normalized.get('full_name', 'N/A')} from {normalized.get('company', 'N/A')}
ROLE: {normalized.get('title', 'N/A')}
SCORE: {score:.2f}/1.0
INDUSTRY: {enrichment.get('company', {}).get('industry', 'N/A')}
SIZE: {enrichment.get('company', {}).get('employees', 'N/A')} employees

SIMILAR ACCOUNTS:
{similar_text}

Generate a 6-8 bullet summary for the AE:"""
        
        return prompt
    
    def _parse_scoring_response(self, content: str) -> Dict[str, Any]:
        """Parse the LLM scoring response."""
        try:
            # Try to extract JSON from response
            if "{" in content and "}" in content:
                start = content.find("{")
                end = content.rfind("}") + 1
                json_str = content[start:end]
                result = json.loads(json_str)
                
                # Validate response format
                if "score" in result and "reasons" in result:
                    score = float(result["score"])
                    reasons = result["reasons"] if isinstance(result["reasons"], list) else [str(result["reasons"])]
                    return {"score": score, "reasons": reasons}
            
            # Fallback parsing
            logger.warning("Could not parse LLM response as JSON, using fallback")
            return {"score": 0.5, "reasons": ["LLM response parsing failed"]}
            
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return {"score": 0.5, "reasons": ["Response parsing error"]}
    
    def _mock_scoring(self, state: Dict[str, Any], base_hint: float) -> Tuple[float, List[str]]:
        """Mock scoring for testing/fallback."""
        normalized = state.get("normalized", {})
        enrichment = state.get("enrichment", {})
        
        reasons = []
        score = base_hint
        
        # Add mock reasons based on data
        if enrichment.get("company", {}).get("industry"):
            reasons.append(f"ICP match: {enrichment['company']['industry']}")
            score += 0.1
        
        if enrichment.get("company", {}).get("employees", 0) >= 100:
            reasons.append("Enterprise size company")
            score += 0.1
        
        if any(title in (normalized.get("title") or "").lower() for title in ["director", "vp", "cxo"]):
            reasons.append("Senior decision maker")
            score += 0.1
        
        # Ensure score is within bounds
        score = max(0.0, min(1.0, score))
        
        if not reasons:
            reasons = ["Basic qualification met"]
        
        return score, reasons
    
    def _mock_summary(self, state: Dict[str, Any], similar_accounts: List[Dict[str, Any]]) -> str:
        """Mock summary for testing/fallback."""
        normalized = state.get("normalized", {})
        company = state.get("enrichment", {}).get("company", {})
        score = state.get("score", 0)
        
        summary = f"""Lead Summary for {normalized.get('full_name', 'Unknown')}

• Company: {normalized.get('company', 'Unknown')} ({company.get('industry', 'Unknown industry')})
• Role: {normalized.get('title', 'Unknown title')}
• Lead Score: {score:.2f}/1.0
• Company Size: {company.get('employees', 'Unknown')} employees
• Source: {normalized.get('source', 'Unknown')}
• Next Action: Schedule discovery call within 24 hours
• Similar Accounts: {len(similar_accounts)} accounts found for context
• Priority: {'High' if score > 0.7 else 'Medium' if score > 0.4 else 'Low'}"""
        
        return summary

# Global LLM client instance
llm_client = LLMClient()

def score_lead_with_rubric(state: Dict[str, Any], base_hint: float = 0.0) -> Tuple[float, List[str]]:
    """Score lead using the global LLM client."""
    return llm_client.score_lead_with_rubric(state, base_hint)

def summarize_for_ae(state: Dict[str, Any], similar_accounts: List[Dict[str, Any]]) -> str:
    """Generate summary using the global LLM client."""
    return llm_client.summarize_for_ae(state, similar_accounts)
