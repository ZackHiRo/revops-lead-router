import pytest
import json
import os
import sys
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph.state import LeadState
from graph.nodes.capture import capture
from graph.nodes.enrich import enrich
from graph.nodes.score import score
from graph.nodes.route import route
from graph.nodes.summarize import summarize
from graph.nodes.nurture import nurture
from tools.idempotency import Idem

class TestLeadProcessingFlow:
    """Test the complete lead processing workflow."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sample_lead = {
            "email": "john.doe@acme.com",
            "company": "Acme Corp",
            "full_name": "John Doe",
            "title": "Director of Engineering",
            "source": "website",
            "country": "US"
        }
        
        self.initial_state = {
            "raw": self.sample_lead,
            "errors": [],
            "notifications": [],
            "score_reasons": []
        }
    
    def test_capture_node(self):
        """Test the capture node normalizes lead data correctly."""
        state = self.initial_state.copy()
        result = capture(state)
        
        assert "normalized" in result
        assert result["normalized"]["email"] == "john.doe@acme.com"
        assert result["normalized"]["company"] == "Acme Corp"
        assert result["normalized"]["full_name"] == "John Doe"
        assert result["normalized"]["title"] == "Director of Engineering"
        assert result["lead_id"] == "john.doe@acme.com"
        assert len(result["errors"]) == 0
    
    def test_capture_node_missing_fields(self):
        """Test capture node handles missing required fields."""
        incomplete_lead = {
            "email": "test@example.com",
            # Missing company and full_name
        }
        
        state = {"raw": incomplete_lead, "errors": [], "notifications": [], "score_reasons": []}
        result = capture(state)
        
        assert len(result["errors"]) > 0
        assert "Missing required fields" in result["errors"][0]
    
    def test_enrich_node(self):
        """Test the enrich node adds enrichment data."""
        state = self.initial_state.copy()
        state = capture(state)  # First capture
        
        with patch('tools.clearbit.enrich_domain_person') as mock_enrich:
            mock_enrich.return_value = {
                "company": {
                    "domain": "acme.com",
                    "employees": 150,
                    "industry": "SaaS",
                    "tech": ["AWS", "Python"]
                },
                "person": {
                    "email": "john.doe@acme.com",
                    "seniority": "director"
                }
            }
            
            result = enrich(state)
            
            assert "enrichment" in result
            assert result["enrichment"]["company"]["industry"] == "SaaS"
            assert result["enrichment"]["company"]["employees"] == 150
            assert result["enrichment"]["person"]["seniority"] == "director"
    
    def test_enrich_node_failure(self):
        """Test enrich node handles API failures gracefully."""
        state = self.initial_state.copy()
        state = capture(state)
        
        with patch('tools.clearbit.enrich_domain_person') as mock_enrich:
            mock_enrich.side_effect = Exception("API timeout")
            
            result = enrich(state)
            
            assert "enrichment" in result
            assert result["enrichment"] == {}
            assert len(result["errors"]) > 0
            assert "enrich_failed" in result["errors"][0]
    
    def test_score_node(self):
        """Test the score node calculates lead scores correctly."""
        state = self.initial_state.copy()
        state = capture(state)
        state = enrich(state)
        
        with patch('tools.llm.score_lead_with_rubric') as mock_score:
            mock_score.return_value = (0.85, ["ICP match: SaaS", "Seniority: Director"])
            
            result = score(state)
            
            assert "score" in result
            assert result["score"] > 0
            assert "score_reasons" in result
            assert len(result["score_reasons"]) > 0
    
    def test_score_node_rule_based_fallback(self):
        """Test score node falls back to rule-based scoring when LLM fails."""
        state = self.initial_state.copy()
        state = capture(state)
        state = enrich(state)
        
        with patch('tools.llm.score_lead_with_rubric') as mock_score:
            mock_score.side_effect = Exception("LLM API error")
            
            result = score(state)
            
            assert "score" in result
            assert "score_reasons" in result
            assert "Rule-based scoring only" in result["score_reasons"][0]
    
    def test_route_node(self):
        """Test the route node assigns owners correctly."""
        state = self.initial_state.copy()
        state = capture(state)
        state = enrich(state)
        state = score(state)
        
        with patch('tools.hubspot.find_owner_by_rules') as mock_find_owner:
            mock_find_owner.return_value = "us-team@company.com"
            
            with patch('tools.hubspot.create_or_update_contact') as mock_crm:
                mock_crm.return_value = {"id": "12345", "action": "created"}
                
                result = route(state)
                
                assert "owner" in result
                assert result["owner"] == "us-team@company.com"
                assert "crm_record_id" in result
                assert result["crm_record_id"] == "12345"
                assert "route_reason" in result
    
    def test_route_node_fallback(self):
        """Test route node falls back to default owner on failure."""
        state = self.initial_state.copy()
        state = capture(state)
        state = enrich(state)
        state = score(state)
        
        with patch('tools.hubspot.find_owner_by_rules') as mock_find_owner:
            mock_find_owner.side_effect = Exception("Routing error")
            
            result = route(state)
            
            assert "owner" in result
            assert "route_reason" in result
            assert "Fallback to default owner" in result["route_reason"]
    
    def test_summarize_node(self):
        """Test the summarize node generates summaries and finds similar accounts."""
        state = self.initial_state.copy()
        state = capture(state)
        state = enrich(state)
        state = score(state)
        state = route(state)
        
        with patch('tools.pinecone_store.similar_accounts') as mock_similar:
            mock_similar.return_value = [
                {"account": "Acme Inc", "outcome": "Won", "reason": "Same industry"}
            ]
            
            with patch('tools.llm.summarize_for_ae') as mock_summary:
                mock_summary.return_value = "Mock summary for AE"
                
                result = summarize(state)
                
                assert "similar_accounts" in result
                assert len(result["similar_accounts"]) > 0
                assert "summary" in result
    
    def test_nurture_node(self):
        """Test the nurture node handles low-scoring leads correctly."""
        state = self.initial_state.copy()
        state = capture(state)
        state = enrich(state)
        state["score"] = 0.3  # Low score
        state = score(state)
        
        result = nurture(state)
        
        assert "decided_path" in result
        assert result["decided_path"] == "nurture"
        assert "nurture_data" in result
        assert "nurture_task" in result
        assert "email_sequence" in result
    
    def test_complete_workflow_high_score(self):
        """Test complete workflow for high-scoring lead."""
        state = self.initial_state.copy()
        
        # Mock all external dependencies
        with patch('tools.clearbit.enrich_domain_person') as mock_enrich, \
             patch('tools.llm.score_lead_with_rubric') as mock_score, \
             patch('tools.hubspot.find_owner_by_rules') as mock_owner, \
             patch('tools.hubspot.create_or_update_contact') as mock_crm, \
             patch('tools.pinecone_store.similar_accounts') as mock_similar, \
             patch('tools.llm.summarize_for_ae') as mock_summary:
            
            # Setup mocks
            mock_enrich.return_value = {
                "company": {"employees": 200, "industry": "SaaS", "tech": ["AWS"]},
                "person": {"seniority": "director"}
            }
            mock_score.return_value = (0.85, ["ICP match", "Seniority"])
            mock_owner.return_value = "us-team@company.com"
            mock_crm.return_value = {"id": "12345"}
            mock_similar.return_value = [{"account": "Test", "outcome": "Won"}]
            mock_summary.return_value = "Summary"
            
            # Execute workflow
            state = capture(state)
            state = enrich(state)
            state = score(state)
            state = route(state)
            state = summarize(state)
            
            # Verify final state
            assert state["score"] > 0.7
            assert state["owner"] == "us-team@company.com"
            assert state["crm_record_id"] == "12345"
            assert "summary" in state
            assert len(state["similar_accounts"]) > 0
    
    def test_complete_workflow_low_score(self):
        """Test complete workflow for low-scoring lead."""
        state = self.initial_state.copy()
        
        # Mock all external dependencies
        with patch('tools.clearbit.enrich_domain_person') as mock_enrich, \
             patch('tools.llm.score_lead_with_rubric') as mock_score:
            
            # Setup mocks for low score
            mock_enrich.return_value = {
                "company": {"employees": 5, "industry": "Retail"},
                "person": {"seniority": "junior"}
            }
            mock_score.return_value = (0.2, ["Small company", "Non-ICP"])
            
            # Execute workflow
            state = capture(state)
            state = enrich(state)
            state = score(state)
            state = nurture(state)
            
            # Verify final state
            assert state["score"] < 0.4
            assert state["decided_path"] == "nurture"
            assert "nurture_data" in state

class TestIdempotency:
    """Test the idempotency functionality."""
    
    def test_idempotency_check_and_set(self):
        """Test that duplicate keys are properly detected."""
        idem = Idem()
        
        # First call should succeed
        result1 = idem.check_and_set("test_key_1")
        assert result1 is True
        
        # Second call with same key should fail
        result2 = idem.check_and_set("test_key_1")
        assert result2 is False
    
    def test_idempotency_different_keys(self):
        """Test that different keys are processed independently."""
        idem = Idem()
        
        # Different keys should both succeed
        result1 = idem.check_and_set("key_1")
        result2 = idem.check_and_set("key_2")
        
        assert result1 is True
        assert result2 is True
    
    def test_idempotency_empty_key(self):
        """Test handling of empty keys."""
        idem = Idem()
        
        result = idem.check_and_set("")
        assert result is False

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
