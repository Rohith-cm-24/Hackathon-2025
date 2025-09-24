"""
Semantic analysis module for detecting sensitive content based on business rules.
Uses sentence transformers to compare input text with predefined confidential policies.
"""

import logging
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import json
import os

from detectors import DetectionMatch

logger = logging.getLogger(__name__)

@dataclass
class BusinessRule:
    """Represents a business rule for confidential content."""
    name: str
    description: str
    examples: List[str]
    category: str
    severity: str  # LOW, MEDIUM, HIGH
    embedding: Optional[np.ndarray] = None

class SemanticAnalyzer:
    """
    Semantic analyzer for detecting sensitive content based on business rules.
    Uses sentence transformers for semantic similarity matching.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", similarity_threshold: float = 0.7):
        """
        Initialize the semantic analyzer.
        
        Args:
            model_name: Name of the sentence transformer model to use
            similarity_threshold: Minimum similarity score to consider a match
        """
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold
        self.model = None
        self.business_rules: List[BusinessRule] = []
        self.rule_embeddings: Optional[np.ndarray] = None
        
        self._initialize_model()
        self._load_default_business_rules()
        self._precompute_rule_embeddings()
    
    def _initialize_model(self):
        """Initialize the sentence transformer model."""
        try:
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Successfully loaded sentence transformer model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to load sentence transformer model: {e}")
            self.model = None
    
    def _load_default_business_rules(self):
        """Load default business rules for common sensitive content."""
        default_rules = [
            BusinessRule(
                name="salary_information",
                description="Information about employee salaries, wages, or compensation",
                examples=[
                    "My salary is $75,000 per year",
                    "I got a raise to $80k",
                    "The new hire's compensation package",
                    "Annual bonus of $10,000",
                    "Hourly wage increased to $35"
                ],
                category="financial",
                severity="HIGH"
            ),
            BusinessRule(
                name="company_financials",
                description="Company financial information and performance data",
                examples=[
                    "Our quarterly revenue was $2.5M",
                    "The company lost $500k last quarter",
                    "Budget allocation for next year",
                    "Profit margins are declining",
                    "Investment rounds and funding"
                ],
                category="financial",
                severity="HIGH"
            ),
            BusinessRule(
                name="employee_performance",
                description="Employee performance reviews and evaluations",
                examples=[
                    "John's performance review was poor",
                    "She received an excellent rating",
                    "Performance improvement plan",
                    "Annual review scores",
                    "Employee evaluation metrics"
                ],
                category="hr",
                severity="MEDIUM"
            ),
            BusinessRule(
                name="layoffs_restructuring",
                description="Information about layoffs, firings, or company restructuring",
                examples=[
                    "We're planning layoffs next month",
                    "The engineering team will be reduced",
                    "Restructuring the sales department",
                    "Budget cuts affecting headcount",
                    "Termination decisions"
                ],
                category="hr",
                severity="HIGH"
            ),
            BusinessRule(
                name="product_strategy",
                description="Confidential product development and business strategy",
                examples=[
                    "Our new product launch strategy",
                    "Competitive analysis and positioning",
                    "Product roadmap for next year",
                    "Market expansion plans",
                    "Proprietary technology details"
                ],
                category="business",
                severity="HIGH"
            ),
            BusinessRule(
                name="client_information",
                description="Confidential client or customer information",
                examples=[
                    "Client ABC Corp signed a $1M deal",
                    "Customer complaints about our service",
                    "Client meeting notes and discussions",
                    "Customer contract terms",
                    "Account management strategies"
                ],
                category="business",
                severity="MEDIUM"
            ),
            BusinessRule(
                name="legal_matters",
                description="Legal issues, disputes, or compliance matters",
                examples=[
                    "The lawsuit against our company",
                    "Compliance violation discovered",
                    "Legal counsel's advice on the matter",
                    "Settlement negotiations",
                    "Regulatory investigation"
                ],
                category="legal",
                severity="HIGH"
            ),
            BusinessRule(
                name="merger_acquisition",
                description="Information about mergers, acquisitions, or partnerships",
                examples=[
                    "We're acquiring Company XYZ",
                    "Merger discussions with competitor",
                    "Due diligence process ongoing",
                    "Strategic partnership negotiations",
                    "Acquisition target evaluation"
                ],
                category="business",
                severity="HIGH"
            ),
            BusinessRule(
                name="internal_processes",
                description="Internal company processes and procedures",
                examples=[
                    "Our hiring process needs improvement",
                    "Internal audit findings",
                    "Process optimization initiatives",
                    "Workflow automation plans",
                    "Operational efficiency metrics"
                ],
                category="internal",
                severity="LOW"
            ),
            BusinessRule(
                name="technology_infrastructure",
                description="IT infrastructure and security information",
                examples=[
                    "Server migration planned for weekend",
                    "Security vulnerability discovered",
                    "Database performance issues",
                    "Network architecture changes",
                    "Cloud infrastructure costs"
                ],
                category="technical",
                severity="MEDIUM"
            )
        ]
        
        self.business_rules = default_rules
        logger.info(f"Loaded {len(default_rules)} default business rules")
    
    def _precompute_rule_embeddings(self):
        """Precompute embeddings for all business rules."""
        if not self.model or not self.business_rules:
            return
        
        try:
            # Combine description and examples for each rule
            rule_texts = []
            for rule in self.business_rules:
                # Create a comprehensive text representation of the rule
                rule_text = f"{rule.description}. Examples: {' '.join(rule.examples)}"
                rule_texts.append(rule_text)
            
            # Compute embeddings for all rules at once
            embeddings = self.model.encode(rule_texts, convert_to_tensor=False)
            self.rule_embeddings = np.array(embeddings)
            
            # Store individual embeddings in rule objects
            for i, rule in enumerate(self.business_rules):
                rule.embedding = embeddings[i]
            
            logger.info(f"Precomputed embeddings for {len(self.business_rules)} business rules")
        
        except Exception as e:
            logger.error(f"Failed to precompute rule embeddings: {e}")
            self.rule_embeddings = None
    
    def add_custom_rule(self, rule: BusinessRule):
        """Add a custom business rule."""
        if self.model:
            try:
                # Compute embedding for the new rule
                rule_text = f"{rule.description}. Examples: {' '.join(rule.examples)}"
                embedding = self.model.encode([rule_text], convert_to_tensor=False)[0]
                rule.embedding = embedding
                
                self.business_rules.append(rule)
                
                # Update the rule embeddings matrix
                if self.rule_embeddings is not None:
                    self.rule_embeddings = np.vstack([self.rule_embeddings, embedding])
                else:
                    self.rule_embeddings = np.array([embedding])
                
                logger.info(f"Added custom business rule: {rule.name}")
            except Exception as e:
                logger.error(f"Failed to add custom rule: {e}")
        else:
            self.business_rules.append(rule)
    
    def analyze_text(self, text: str, custom_threshold: Optional[float] = None) -> List[DetectionMatch]:
        """
        Analyze text for semantic matches against business rules.
        
        Args:
            text: Input text to analyze
            custom_threshold: Optional custom similarity threshold
            
        Returns:
            List of detection matches
        """
        if not self.model or not self.business_rules or self.rule_embeddings is None:
            logger.warning("Semantic analyzer not properly initialized")
            return []
        
        threshold = custom_threshold if custom_threshold is not None else self.similarity_threshold
        matches = []
        
        try:
            # Encode the input text
            text_embedding = self.model.encode([text], convert_to_tensor=False)[0]
            text_embedding = text_embedding.reshape(1, -1)
            
            # Compute similarities with all rules
            similarities = cosine_similarity(text_embedding, self.rule_embeddings)[0]
            
            # Find matches above threshold
            for i, similarity in enumerate(similarities):
                if similarity >= threshold:
                    rule = self.business_rules[i]
                    matches.append(DetectionMatch(
                        match_type="SEMANTIC",
                        rule_name=rule.name,
                        matched_text=text,  # For semantic matches, the entire text is considered
                        confidence=float(similarity),
                        start_position=0,
                        end_position=len(text),
                        explanation=f"Semantic match with {rule.name}: {rule.description} (similarity: {similarity:.3f})"
                    ))
            
            # Sort by confidence (highest first)
            matches.sort(key=lambda x: x.confidence, reverse=True)
            
        except Exception as e:
            logger.error(f"Error in semantic analysis: {e}")
        
        return matches
    
    def analyze_sentences(self, text: str, custom_threshold: Optional[float] = None) -> List[DetectionMatch]:
        """
        Analyze text by splitting into sentences and checking each one.
        This can provide more granular matches for longer texts.
        
        Args:
            text: Input text to analyze
            custom_threshold: Optional custom similarity threshold
            
        Returns:
            List of detection matches
        """
        if not self.model:
            return []
        
        try:
            # Simple sentence splitting (could be improved with spaCy)
            sentences = [s.strip() for s in text.split('.') if s.strip()]
            if not sentences:
                return self.analyze_text(text, custom_threshold)
            
            all_matches = []
            current_position = 0
            
            for sentence in sentences:
                if len(sentence.strip()) < 10:  # Skip very short sentences
                    current_position += len(sentence) + 1  # +1 for the period
                    continue
                
                # Analyze this sentence
                sentence_matches = self.analyze_text(sentence, custom_threshold)
                
                # Adjust positions to be relative to the full text
                for match in sentence_matches:
                    match.start_position = current_position
                    match.end_position = current_position + len(sentence)
                    match.matched_text = sentence
                    all_matches.append(match)
                
                current_position += len(sentence) + 1  # +1 for the period
            
            # Remove duplicates and sort by confidence
            unique_matches = self._remove_duplicate_semantic_matches(all_matches)
            unique_matches.sort(key=lambda x: x.confidence, reverse=True)
            
            return unique_matches
        
        except Exception as e:
            logger.error(f"Error in sentence-level semantic analysis: {e}")
            return []
    
    def _remove_duplicate_semantic_matches(self, matches: List[DetectionMatch]) -> List[DetectionMatch]:
        """Remove duplicate semantic matches based on rule name and similarity."""
        seen_rules = set()
        unique_matches = []
        
        for match in sorted(matches, key=lambda x: x.confidence, reverse=True):
            if match.rule_name not in seen_rules:
                unique_matches.append(match)
                seen_rules.add(match.rule_name)
        
        return unique_matches
    
    def get_rule_by_name(self, rule_name: str) -> Optional[BusinessRule]:
        """Get a business rule by name."""
        for rule in self.business_rules:
            if rule.name == rule_name:
                return rule
        return None
    
    def list_rules(self) -> List[Dict]:
        """List all business rules with their details."""
        return [
            {
                "name": rule.name,
                "description": rule.description,
                "category": rule.category,
                "severity": rule.severity,
                "example_count": len(rule.examples)
            }
            for rule in self.business_rules
        ]
    
    def save_rules_to_file(self, filepath: str):
        """Save business rules to a JSON file."""
        try:
            rules_data = []
            for rule in self.business_rules:
                rule_dict = {
                    "name": rule.name,
                    "description": rule.description,
                    "examples": rule.examples,
                    "category": rule.category,
                    "severity": rule.severity
                }
                rules_data.append(rule_dict)
            
            with open(filepath, 'w') as f:
                json.dump(rules_data, f, indent=2)
            
            logger.info(f"Saved {len(rules_data)} business rules to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save rules to file: {e}")
    
    def load_rules_from_file(self, filepath: str):
        """Load business rules from a JSON file."""
        try:
            if not os.path.exists(filepath):
                logger.warning(f"Rules file not found: {filepath}")
                return
            
            with open(filepath, 'r') as f:
                rules_data = json.load(f)
            
            loaded_rules = []
            for rule_dict in rules_data:
                rule = BusinessRule(
                    name=rule_dict["name"],
                    description=rule_dict["description"],
                    examples=rule_dict["examples"],
                    category=rule_dict["category"],
                    severity=rule_dict["severity"]
                )
                loaded_rules.append(rule)
            
            self.business_rules = loaded_rules
            self._precompute_rule_embeddings()
            
            logger.info(f"Loaded {len(loaded_rules)} business rules from {filepath}")
        except Exception as e:
            logger.error(f"Failed to load rules from file: {e}") 