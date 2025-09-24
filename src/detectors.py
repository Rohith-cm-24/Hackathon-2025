"""
Explicit content detection module for sensitive information.
Includes regex patterns, keyword matching, and PII detection using Presidio.
"""

import re
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
import spacy

logger = logging.getLogger(__name__)

@dataclass
class DetectionMatch:
    """Represents a detected sensitive match."""
    match_type: str
    rule_name: str
    matched_text: str
    confidence: float
    start_position: int
    end_position: int
    explanation: str

class ExplicitContentDetector:
    """
    Handles explicit content detection using regex patterns, keywords, and PII detection.
    """
    
    def __init__(self):
        self.keyword_patterns = self._load_keyword_patterns()
        self.regex_patterns = self._load_regex_patterns()
        self.presidio_analyzer = self._initialize_presidio()
        self.nlp = self._initialize_spacy()
        
    def _load_keyword_patterns(self) -> Dict[str, List[str]]:
        """Load keyword patterns for different categories."""
        return {
            "financial": [
                "credit card", "debit card", "bank account", "routing number",
                "account number", "ssn", "social security", "tax id",
                "salary", "income", "wage", "bonus", "compensation",
                "financial statement", "bank statement"
            ],
            "personal": [
                "password", "passcode", "pin", "secret", "confidential",
                "personal information", "private", "classified"
            ],
            "medical": [
                "medical record", "patient", "diagnosis", "treatment",
                "health information", "medical history", "prescription"
            ],
            "business": [
                "proprietary", "trade secret", "internal use only",
                "company confidential", "restricted", "nda", "non-disclosure"
            ],
            "legal": [
                "attorney-client", "privileged", "legal advice",
                "settlement", "litigation", "lawsuit"
            ]
        }
    
    def _load_regex_patterns(self) -> Dict[str, Tuple[re.Pattern, str]]:
        """Load compiled regex patterns for various PII types."""
        patterns = {
            "credit_card": (
                re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
                "Credit card number pattern"
            ),
            "ssn": (
                re.compile(r'\b\d{3}-?\d{2}-?\d{4}\b'),
                "Social Security Number pattern"
            ),
            "phone": (
                re.compile(r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b'),
                "Phone number pattern"
            ),
            "email": (
                re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
                "Email address pattern"
            ),
            "ip_address": (
                re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'),
                "IP address pattern"
            ),
            "mac_address": (
                re.compile(r'\b([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})\b'),
                "MAC address pattern"
            ),
            "url": (
                re.compile(r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?'),
                "URL pattern"
            ),
            "api_key": (
                re.compile(r'\b[A-Za-z0-9]{32,}\b'),
                "Potential API key pattern"
            ),
            "guid": (
                re.compile(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b'),
                "GUID pattern"
            )
        }
        return patterns
    
    def _initialize_presidio(self) -> AnalyzerEngine:
        """Initialize Presidio analyzer for PII detection."""
        try:
            # Create NLP engine configuration
            configuration = {
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]
            }
            
            # Create NLP engine provider
            nlp_engine_provider = NlpEngineProvider(nlp_configuration=configuration)
            nlp_engine = nlp_engine_provider.create_engine()
            
            # Create analyzer
            analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
            return analyzer
        except Exception as e:
            logger.warning(f"Failed to initialize Presidio: {e}. PII detection will be limited.")
            return None
    
    def _initialize_spacy(self):
        """Initialize spaCy NLP model."""
        try:
            nlp = spacy.load("en_core_web_sm")
            return nlp
        except OSError:
            logger.warning("spaCy model 'en_core_web_sm' not found. Named entity recognition will be limited.")
            return None
    
    def detect_keywords(self, text: str) -> List[DetectionMatch]:
        """Detect sensitive keywords in text."""
        matches = []
        text_lower = text.lower()
        
        for category, keywords in self.keyword_patterns.items():
            for keyword in keywords:
                keyword_lower = keyword.lower()
                start = 0
                while True:
                    pos = text_lower.find(keyword_lower, start)
                    if pos == -1:
                        break
                    
                    matches.append(DetectionMatch(
                        match_type="KEYWORD",
                        rule_name=f"{category}_keyword",
                        matched_text=text[pos:pos+len(keyword)],
                        confidence=0.9,
                        start_position=pos,
                        end_position=pos + len(keyword),
                        explanation=f"Found {category} related keyword: {keyword}"
                    ))
                    start = pos + 1
        
        return matches
    
    def detect_regex_patterns(self, text: str) -> List[DetectionMatch]:
        """Detect sensitive patterns using regex."""
        matches = []
        
        for pattern_name, (pattern, description) in self.regex_patterns.items():
            for match in pattern.finditer(text):
                matches.append(DetectionMatch(
                    match_type="REGEX",
                    rule_name=pattern_name,
                    matched_text=match.group(),
                    confidence=0.85,
                    start_position=match.start(),
                    end_position=match.end(),
                    explanation=f"Detected {description}: {match.group()}"
                ))
        
        return matches
    
    def detect_pii_presidio(self, text: str) -> List[DetectionMatch]:
        """Detect PII using Presidio analyzer."""
        matches = []
        
        if not self.presidio_analyzer:
            return matches
        
        try:
            results = self.presidio_analyzer.analyze(
                text=text,
                language="en",
                score_threshold=0.6
            )
            
            for result in results:
                matches.append(DetectionMatch(
                    match_type="PII",
                    rule_name=f"presidio_{result.entity_type.lower()}",
                    matched_text=text[result.start:result.end],
                    confidence=result.score,
                    start_position=result.start,
                    end_position=result.end,
                    explanation=f"Presidio detected {result.entity_type}: {text[result.start:result.end]}"
                ))
        except Exception as e:
            logger.error(f"Error in Presidio PII detection: {e}")
        
        return matches
    
    def detect_named_entities(self, text: str) -> List[DetectionMatch]:
        """Detect named entities using spaCy."""
        matches = []
        
        if not self.nlp:
            return matches
        
        try:
            doc = self.nlp(text)
            
            sensitive_entities = {"PERSON", "ORG", "GPE", "MONEY", "DATE"}
            
            for ent in doc.ents:
                if ent.label_ in sensitive_entities:
                    matches.append(DetectionMatch(
                        match_type="NER",
                        rule_name=f"spacy_{ent.label_.lower()}",
                        matched_text=ent.text,
                        confidence=0.7,
                        start_position=ent.start_char,
                        end_position=ent.end_char,
                        explanation=f"Named entity detected ({ent.label_}): {ent.text}"
                    ))
        except Exception as e:
            logger.error(f"Error in spaCy NER: {e}")
        
        return matches
    
    def detect_all(self, text: str) -> List[DetectionMatch]:
        """Run all explicit detection methods on the text."""
        all_matches = []
        
        # Run all detection methods
        all_matches.extend(self.detect_keywords(text))
        all_matches.extend(self.detect_regex_patterns(text))
        all_matches.extend(self.detect_pii_presidio(text))
        all_matches.extend(self.detect_named_entities(text))
        
        # Remove duplicates based on position and content
        unique_matches = self._deduplicate_matches(all_matches)
        
        # Sort by position
        unique_matches.sort(key=lambda x: x.start_position)
        
        return unique_matches
    
    def _deduplicate_matches(self, matches: List[DetectionMatch]) -> List[DetectionMatch]:
        """Remove duplicate matches based on overlapping positions."""
        if not matches:
            return matches
        
        # Sort by start position
        sorted_matches = sorted(matches, key=lambda x: x.start_position)
        unique_matches = [sorted_matches[0]]
        
        for current_match in sorted_matches[1:]:
            last_match = unique_matches[-1]
            
            # Check for overlap
            if (current_match.start_position < last_match.end_position and 
                current_match.end_position > last_match.start_position):
                # Keep the match with higher confidence
                if current_match.confidence > last_match.confidence:
                    unique_matches[-1] = current_match
            else:
                unique_matches.append(current_match)
        
        return unique_matches 