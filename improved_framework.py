"""Enhanced Self-Evolution Framework utilities
-------------------------------------------------
Improved version with better error handling, logging, and validation.
Maintains backward compatibility while adding robustness features.
"""
from __future__ import annotations

import json
import re
import logging
from typing import Dict, Tuple, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum

__all__ = [
    "ImprovedFramework",
    "ValidationResult",
    "ParseResult",
]

class ValidationStatus(Enum):
    """Status codes for validation results"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    UNKNOWN_STAGE = "unknown_stage"

@dataclass
class ValidationResult:
    """Structured validation result with detailed feedback"""
    status: ValidationStatus
    message: str
    score: float  # 0.0 to 1.0
    details: Dict[str, Any]

@dataclass
class ParseResult:
    """Structured parsing result with metadata"""
    data: Dict[str, Any]
    success: bool
    method_used: str
    confidence: float  # 0.0 to 1.0
    warnings: List[str]

class ImprovedFramework:
    """Enhanced collection of parsing, validation and heuristic-scoring helpers.
    
    Improvements over original:
    - Better error handling with structured results
    - More sophisticated JSON parsing strategies
    - Enhanced stage validation with partial success detection
    - Configurable logging and debugging
    - Better heuristic scoring with confidence metrics
    """

    def __init__(self, debug: bool = False, logger: Optional[logging.Logger] = None):
        self.debug = debug
        self.logger = logger or self._setup_logger()
        
        # Enhanced stage validators with partial success detection
        self.stage_validators: Dict[str, callable] = {
            "0": self._validate_stage0_enhanced,
            "1": self._validate_stage1_enhanced,
            "2": self._validate_stage2_enhanced,
            "3": self._validate_stage3_enhanced,
            "4": self._validate_stage4_enhanced,
            "meta": self._validate_meta_enhanced,
        }
        
        # Scoring weights for heuristic evaluation
        self.heuristic_weights = {
            "word_count": 0.2,
            "structure": 0.3,
            "stage_alignment": 0.4,
            "completeness": 0.1
        }

    def _setup_logger(self) -> logging.Logger:
        """Setup basic logger if none provided"""
        logger = logging.getLogger("improved_framework")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG if self.debug else logging.WARNING)
        return logger

    # ------------------------------------------------------------------
    # Enhanced JSON parsing with detailed results
    # ------------------------------------------------------------------

    def robust_json_parser(self, raw_response: str) -> ParseResult:
        """Enhanced JSON parser that returns structured results with metadata"""
        warnings = []
        
        if not raw_response or not raw_response.strip():
            return ParseResult(
                data={"scores": {}, "patch_note": "Empty response", "parsing_error": True},
                success=False,
                method_used="empty_fallback",
                confidence=0.0,
                warnings=["Empty or whitespace-only input"]
            )

        # Strategy 1: Direct JSON parsing
        try:
            data = json.loads(raw_response)
            return ParseResult(
                data=data,
                success=True,
                method_used="direct_json",
                confidence=1.0,
                warnings=[]
            )
        except json.JSONDecodeError as e:
            self.logger.debug(f"Direct JSON parse failed: {e}")

        # Strategy 2: Remove markdown code fences
        try:
            cleaned = re.sub(r"```(?:json)?\s*\n(.*?)\n```", r"\1", raw_response, flags=re.DOTALL)
            if cleaned != raw_response:
                data = json.loads(cleaned)
                warnings.append("Removed markdown code fences")
                return ParseResult(
                    data=data,
                    success=True,
                    method_used="markdown_cleanup",
                    confidence=0.9,
                    warnings=warnings
                )
        except json.JSONDecodeError as e:
            self.logger.debug(f"Markdown cleanup parse failed: {e}")

        # Strategy 3: Extract first JSON object
        try:
            # More sophisticated regex to handle nested braces
            brace_count = 0
            start_idx = -1
            
            for i, char in enumerate(raw_response):
                if char == '{' and start_idx == -1:
                    start_idx = i
                    brace_count = 1
                elif start_idx != -1:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_str = raw_response[start_idx:i+1]
                            data = json.loads(json_str)
                            warnings.append("Extracted first JSON object from text")
                            return ParseResult(
                                data=data,
                                success=True,
                                method_used="json_extraction",
                                confidence=0.8,
                                warnings=warnings
                            )
        except json.JSONDecodeError as e:
            self.logger.debug(f"JSON extraction failed: {e}")

        # Strategy 4: Heuristic construction
        try:
            data = self._construct_json_from_text_enhanced(raw_response)
            warnings.append("Used heuristic text parsing")
            return ParseResult(
                data=data,
                success=True,
                method_used="heuristic_construction",
                confidence=0.6,
                warnings=warnings
            )
        except Exception as e:
            self.logger.debug(f"Heuristic construction failed: {e}")

        # Final fallback
        preview = raw_response[:100] + "..." if len(raw_response) > 100 else raw_response
        return ParseResult(
            data={
                "scores": {},
                "patch_note": f"All parsing strategies failed. Preview: {preview}",
                "parsing_error": True,
            },
            success=False,
            method_used="final_fallback",
            confidence=0.0,
            warnings=warnings + ["All parsing strategies failed"]
        )

    def _construct_json_from_text_enhanced(self, text: str) -> Dict[str, Any]:
        """Enhanced heuristic JSON construction with better pattern matching"""
        result: Dict[str, Any] = {"scores": {}, "patch_note": ""}
        
        # More comprehensive patterns
        score_patterns = [
            r"(\w+):\s*(\d+)(?:/10)?(?:\s*(?:out of|\/)\s*10)?",  # numeric scores
            r"(\w+):\s*(High|Medium|Low|Excellent|Good|Fair|Poor)",  # categorical
            r"(\w+)\s*=\s*(\d+)",  # assignment style
            r"(\w+)\s*-\s*(\d+)",  # dash style
        ]
        
        for pattern in score_patterns:
            matches = re.findall(pattern, text, flags=re.IGNORECASE)
            for key, val in matches:
                key = key.lower().strip()
                if val.isdigit():
                    result["scores"][key] = min(10, max(0, int(val)))  # clamp to 0-10
                else:
                    # Convert categorical to numeric
                    cat_map = {
                        "excellent": 9, "high": 8, "good": 7, "medium": 5,
                        "fair": 4, "low": 3, "poor": 2
                    }
                    result["scores"][key] = cat_map.get(val.lower(), 5)

        # Enhanced patch note extraction
        note_patterns = [
            r"(?:patch[_\s]?note|note|comment):\s*(.+?)(?:\n|$)",
            r"(?:summary|conclusion):\s*(.+?)(?:\n|$)",
            r"(?:improvement|suggestion):\s*(.+?)(?:\n|$)",
        ]
        
        for pattern in note_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                result["patch_note"] = match.group(1).strip()
                break
        
        if not result["patch_note"]:
            result["patch_note"] = "Heuristic parsing - limited text analysis"

        return result

    # ------------------------------------------------------------------
    # Enhanced stage validation with partial success detection
    # ------------------------------------------------------------------

    def enhanced_stage_validator(self, stage: str, response: str) -> ValidationResult:
        """Enhanced validator that returns structured results"""
        validator = self.stage_validators.get(stage)
        if not validator:
            return ValidationResult(
                status=ValidationStatus.UNKNOWN_STAGE,
                message=f"Unknown stage: {stage}",
                score=0.0,
                details={"stage": stage}
            )
        
        return validator(response)

    def _validate_stage0_enhanced(self, response: str) -> ValidationResult:
        """Enhanced Stage 0 validation with partial success detection"""
        details = {}
        
        # Check for success indicators
        success_patterns = [r"success.*today", r"accomplished.*today", r"achieved.*today"]
        success_found = any(re.search(p, response, re.I) for p in success_patterns)
        details["success_statement"] = success_found
        
        # Check for constraint identification
        constraint_patterns = [r"(?:primary\s+)?constraint", r"limitation", r"blocking", r"obstacle"]
        constraint_found = any(re.search(p, response, re.I) for p in constraint_patterns)
        details["constraint_identification"] = constraint_found
        
        # Calculate score and status
        components_found = sum([success_found, constraint_found])
        score = components_found / 2.0
        
        if score == 1.0:
            status = ValidationStatus.SUCCESS
            message = "✅ Stage 0 complete - has success statement and constraint identification"
        elif score > 0:
            status = ValidationStatus.PARTIAL
            missing = []
            if not success_found:
                missing.append("success statement")
            if not constraint_found:
                missing.append("constraint identification")
            message = f"⚠️ Stage 0 partial - missing: {', '.join(missing)}"
        else:
            status = ValidationStatus.FAILED
            message = "❌ Stage 0 incomplete - missing success statement and constraint identification"
        
        return ValidationResult(status=status, message=message, score=score, details=details)

    def _validate_stage1_enhanced(self, response: str) -> ValidationResult:
        """Enhanced Stage 1 validation"""
        details = {}
        
        # Count structured items (bullets, numbers, etc.)
        bullet_patterns = [
            r"(?:^|\n)\s*(?:[-*•]|\d+[.)])\s+.+",
            r"(?:^|\n)\s*[•▪▫]\s+.+",
        ]
        bullet_items = []
        for pattern in bullet_patterns:
            bullet_items.extend(re.findall(pattern, response))
        
        # Count theme indicators
        theme_patterns = [r"theme\s*\d*[:\-]", r"category\s*\d*[:\-]", r"area\s*\d*[:\-]"]
        theme_count = sum(len(re.findall(p, response, re.I)) for p in theme_patterns)
        
        item_count = max(len(bullet_items), theme_count)
        details["item_count"] = item_count
        details["theme_count"] = theme_count
        details["bullet_items"] = len(bullet_items)
        
        # Scoring
        if item_count >= 3:
            status = ValidationStatus.SUCCESS
            message = f"✅ Stage 1 complete - found {item_count} themes/items"
            score = min(1.0, item_count / 3.0)
        elif item_count > 0:
            status = ValidationStatus.PARTIAL
            message = f"⚠️ Stage 1 partial - found {item_count} themes/items (need ≥3)"
            score = item_count / 3.0
        else:
            status = ValidationStatus.FAILED
            message = "❌ Stage 1 incomplete - no themes or structured items found"
            score = 0.0
        
        return ValidationResult(status=status, message=message, score=score, details=details)

    def _validate_stage3_enhanced(self, response: str) -> ValidationResult:
        """Enhanced Stage 3 validation - the stage from your example"""
        details = {}
        
        # Check for winning signal
        signal_patterns = [r"winning\s+signal", r"key\s+signal", r"primary\s+signal"]
        signal_found = any(re.search(p, response, re.I) for p in signal_patterns)
        details["winning_signal"] = signal_found
        
        # Count action steps
        step_patterns = [
            r"(?:^|\n)\s*(?:[-*•]|\d+[.)])\s*(?:step\s*\d*:?)?(.+)",
            r"(?:^|\n)\s*(?:step\s*\d+|action\s*\d*)[:\-]\s*(.+)",
        ]
        steps = []
        for pattern in step_patterns:
            steps.extend(re.findall(pattern, response, re.I))
        
        # Also check for micro-sprint/micro-step indicators
        micro_patterns = [r"micro[-\s]?(?:sprint|step|action)", r"quick\s+action", r"immediate\s+step"]
        micro_found = any(re.search(p, response, re.I) for p in micro_patterns)
        details["micro_actions"] = micro_found
        
        step_count = len(steps)
        details["step_count"] = step_count
        details["steps_found"] = steps[:5]  # Store first 5 for debugging
        
        # Enhanced scoring
        components = []
        if signal_found:
            components.append("winning signal")
        if step_count >= 3:
            components.append(f"{step_count} action steps")
        if micro_found:
            components.append("micro-actions")
        
        score = 0.0
        if signal_found:
            score += 0.4
        if step_count >= 3:
            score += 0.6
        elif step_count > 0:
            score += 0.3 * (step_count / 3.0)
        
        details["components_found"] = components
        
        if score >= 0.8:
            status = ValidationStatus.SUCCESS
            message = f"✅ Stage 3 complete - has {', '.join(components)}"
        elif score > 0.3:
            status = ValidationStatus.PARTIAL
            message = f"⚠️ Stage 3 partial - has {', '.join(components)}"
        else:
            status = ValidationStatus.FAILED
            message = "❌ Stage 3 incomplete - missing key components"
        
        return ValidationResult(status=status, message=message, score=score, details=details)

    # Placeholder implementations for other stages
    def _validate_stage2_enhanced(self, response: str) -> ValidationResult:
        # Similar pattern to stage 3, checking for patterns, motivation, emotional shifts
        # Implementation would follow same pattern as above
        return ValidationResult(ValidationStatus.SUCCESS, "Stage 2 validation placeholder", 0.8, {})
    
    def _validate_stage4_enhanced(self, response: str) -> ValidationResult:
        # Check for prototype goal, won't build list, checkpoints, completion declaration
        return ValidationResult(ValidationStatus.SUCCESS, "Stage 4 validation placeholder", 0.8, {})
    
    def _validate_meta_enhanced(self, response: str) -> ValidationResult:
        # Check for framework analysis, logic reflection, refinement, micro-actions
        return ValidationResult(ValidationStatus.SUCCESS, "Meta validation placeholder", 0.8, {})

    # ------------------------------------------------------------------
    # Enhanced heuristic evaluation with confidence metrics
    # ------------------------------------------------------------------

    def heuristic_evaluation(self, stage: str, response: str, is_meta: bool = False) -> Tuple[Dict[str, Any], str]:
        """Enhanced heuristic evaluation with confidence scoring"""
        if not response or not response.strip():
            return {"clarity": 1, "utility": 1, "stage_alignment": 1, "completeness": 1}, "Empty response - minimal scores"
        
        scores: Dict[str, Any] = {}
        word_count = len(response.split())
        
        # Enhanced structure detection
        structure_indicators = [
            r"(?:^|\n)\s*(?:[-*•]|\d+[.)])",  # bullets/numbers
            r"(?:^|\n)\s*\w+:",  # key-value pairs
            r"\*\*[^*]+\*\*",  # bold text (markdown)
            r"(?:step|action|phase)\s*\d+",  # numbered steps
        ]
        structure_score = sum(1 for pattern in structure_indicators 
                            if re.search(pattern, response, re.I))
        has_structure = structure_score > 0
        
        # Word count scoring (more sophisticated)
        if word_count < 50:
            clarity_base = 3
        elif word_count < 200:
            clarity_base = 6 + (word_count - 50) / 50 * 2  # 6-8 range
        elif word_count < 500:
            clarity_base = 8 + (word_count - 200) / 300 * 1  # 8-9 range
        else:
            clarity_base = 9  # Cap at 9, not 10 for very long responses
        
        scores["clarity"] = int(min(10, max(1, clarity_base)))
        scores["utility"] = 8 if has_structure else 5
        
        # Stage-specific alignment
        validation_result = self.enhanced_stage_validator(stage, response)
        scores["stage_alignment"] = int(validation_result.score * 10)
        scores["completeness"] = int(validation_result.score * 10)
        
        # Add confidence metrics
        confidence = min(1.0, (structure_score * 0.3 + min(word_count/200, 1) * 0.4 + validation_result.score * 0.3))
        
        note = f"Heuristic evaluation (confidence: {confidence:.2f}) - {validation_result.message}"
        scores["_confidence"] = round(confidence, 2)
        scores["_method"] = "heuristic"
        
        return scores, note

    # ------------------------------------------------------------------
    # Backward compatibility methods
    # ------------------------------------------------------------------

    def robust_json_parser_legacy(self, raw_response: str) -> Dict:
        """Legacy method that returns just the dict for backward compatibility"""
        result = self.robust_json_parser(raw_response)
        return result.data

    def simplified_stage_validator(self, stage: str, response: str) -> Tuple[bool, str]:
        """Legacy method for backward compatibility"""
        result = self.enhanced_stage_validator(stage, response)
        success = result.status in [ValidationStatus.SUCCESS, ValidationStatus.PARTIAL]
        return success, result.message
