"""Validation framework for field values"""

from typing import Any, Optional, List, Dict, Callable
from pydantic import BaseModel, ValidationError, field_validator
from datetime import datetime
import json


class ValidationResult:
    """Result of a validation check"""
    
    def __init__(self, valid: bool, error_message: Optional[str] = None):
        self.valid = valid
        self.error_message = error_message
    
    @classmethod
    def success(cls):
        return cls(True)
    
    @classmethod
    def failure(cls, message: str):
        return cls(False, message)


class FieldValidator:
    """Validates field values based on field type and rules"""
    
    @staticmethod
    def validate(field: Dict, value: Any) -> ValidationResult:
        """Validate a value for a given field"""
        field_type = field.get("type", "text")
        required = field.get("required", False)
        
        # Check required
        if required and (value is None or value == ""):
            return ValidationResult.failure(f"{field.get('label', 'Field')} is required")
        
        # If value is empty and not required, it's valid
        if value is None or value == "":
            return ValidationResult.success()
        
        # Type-specific validation
        if field_type == "integer":
            return FieldValidator.validate_integer(value)
        elif field_type == "decimal":
            return FieldValidator.validate_decimal(value)
        elif field_type == "checkbox":
            return FieldValidator.validate_checkbox(value)
        elif field_type == "date":
            return FieldValidator.validate_date(value)
        elif field_type == "datetime":
            return FieldValidator.validate_datetime(value)
        elif field_type in ("select", "single-select"):
            return FieldValidator.validate_select(field, value)
        elif field_type == "text":
            return FieldValidator.validate_text(field, value)
        elif field_type == "notes":
            return FieldValidator.validate_text(field, value)
        
        return ValidationResult.success()
    
    @staticmethod
    def validate_integer(value: Any) -> ValidationResult:
        try:
            int(value)
            return ValidationResult.success()
        except (ValueError, TypeError):
            return ValidationResult.failure("Must be a valid integer")
    
    @staticmethod
    def validate_decimal(value: Any) -> ValidationResult:
        try:
            float(value)
            return ValidationResult.success()
        except (ValueError, TypeError):
            return ValidationResult.failure("Must be a valid number")
    
    @staticmethod
    def validate_checkbox(value: Any) -> ValidationResult:
        # Accept various boolean representations
        if isinstance(value, bool):
            return ValidationResult.success()
        if isinstance(value, str):
            if value.lower() in ("true", "1", "yes", "on"):
                return ValidationResult.success()
            if value.lower() in ("false", "0", "no", "off", ""):
                return ValidationResult.success()
        return ValidationResult.failure("Must be true or false")
    
    @staticmethod
    def validate_date(value: Any) -> ValidationResult:
        if isinstance(value, str):
            # Try ISO format
            try:
                datetime.fromisoformat(value)
                return ValidationResult.success()
            except ValueError:
                pass
            
            # Try common formats
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]:
                try:
                    datetime.strptime(value, fmt)
                    return ValidationResult.success()
                except ValueError:
                    continue
        
        return ValidationResult.failure("Must be a valid date (YYYY-MM-DD)")
    
    @staticmethod
    def validate_datetime(value: Any) -> ValidationResult:
        if isinstance(value, str):
            try:
                datetime.fromisoformat(value)
                return ValidationResult.success()
            except ValueError:
                pass
        
        return ValidationResult.failure("Must be a valid date and time")
    
    @staticmethod
    def validate_select(field: Dict, value: Any) -> ValidationResult:
        options = field.get("options", [])
        if not options:
            return ValidationResult.success()  # No options defined, any value OK
        
        if isinstance(options, str):
            try:
                options = json.loads(options)
            except:
                options = []
        
        if str(value) in [str(opt) for opt in options]:
            return ValidationResult.success()
        
        return ValidationResult.failure(f"Must be one of: {', '.join(map(str, options))}")
    
    @staticmethod
    def validate_text(field: Dict, value: Any) -> ValidationResult:
        validation_rules = field.get("validation_rules")
        if not validation_rules:
            return ValidationResult.success()
        
        if isinstance(validation_rules, str):
            try:
                validation_rules = json.loads(validation_rules)
            except:
                return ValidationResult.success()
        
        value_str = str(value)
        
        # Check min length
        if "min_length" in validation_rules:
            min_len = validation_rules["min_length"]
            if len(value_str) < min_len:
                return ValidationResult.failure(f"Must be at least {min_len} characters")
        
        # Check max length
        if "max_length" in validation_rules:
            max_len = validation_rules["max_length"]
            if len(value_str) > max_len:
                return ValidationResult.failure(f"Must be no more than {max_len} characters")
        
        # Check pattern (regex)
        if "pattern" in validation_rules:
            import re
            pattern = validation_rules["pattern"]
            if not re.match(pattern, value_str):
                return ValidationResult.failure("Does not match required pattern")
        
        return ValidationResult.success()


class RecordValidator:
    """Validates entire records"""
    
    @staticmethod
    def validate_record(record: Dict, fields: List[Dict]) -> Dict[str, ValidationResult]:
        """Validate all fields in a record"""
        results = {}
        for field in fields:
            field_key = field["key"]
            value = record.get(field_key)
            results[field_key] = FieldValidator.validate(field, value)
        return results
    
    @staticmethod
    def is_record_valid(validation_results: Dict[str, ValidationResult]) -> bool:
        """Check if record is valid (all fields valid)"""
        return all(result.valid for result in validation_results.values())
    
    @staticmethod
    def get_errors(validation_results: Dict[str, ValidationResult]) -> Dict[str, str]:
        """Get error messages for invalid fields"""
        return {
            field_key: result.error_message
            for field_key, result in validation_results.items()
            if not result.valid
        }
