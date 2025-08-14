# Regional Measurement System Proposal

**✅ IMPLEMENTATION COMPLETE - 2025-08-13**

This proposal has been fully implemented and is in production use. The regional measurement system is complete with:
- Regional defaults for US/GB/CA English variants
- Smart fallback system for language variants  
- Full test coverage and production deployment
- Implementation located in: `src/stt/text_formatting/constants.py`

---

## Overview

Implement regional measurement preferences for the text formatting system to handle different measurement units (temperature, length, weight) based on user's locale and preferences.

## Current Problem

The system currently defaults to inconsistent measurement units:
- Generic temperature: "twenty degrees" → "20°" (ambiguous)
- No regional awareness: US users get Celsius, GB users might get Fahrenheit
- No user preference system for measurement units

## Proposed Solution

### Architecture: Regional Language Codes + Unit Preferences

```json
{
  "text_formatting": {
    "language": "en-US",
    "unit_temperature": "celsius",
    "unit_length": "metric", 
    "unit_weight": "metric"
  }
}
```

### Regional Defaults by Language Code

- **en-US**: Fahrenheit, Imperial (feet/inches, pounds)
- **en-GB**: Celsius, Metric (meters, kilograms) 
- **en-CA**: Celsius, Metric (with some Imperial exceptions)
- **en-AU**: Celsius, Metric

### Preference Override System

**Precedence**: `User unit_* overrides` → `Regional defaults` → `System fallbacks`

## Implementation Plan

### Phase 1: Resource Structure (2 files)

**1. Create Regional Resource Files**
```bash
src/stt/text_formatting/resources/
├── en-US.json          # US English with Fahrenheit/Imperial defaults
├── en-GB.json          # British English with Celsius/Metric defaults
├── en-CA.json          # Canadian English with Celsius/Metric defaults
└── en.json -> en-US.json   # Symlink for backward compatibility
```

**2. Add Regional Defaults to Resources**
```json
// en-US.json
{
  "regional_defaults": {
    "temperature": "fahrenheit",
    "length": "imperial", 
    "weight": "imperial"
  },
  // ... existing content
}
```

### Phase 2: Configuration System (2 files)

**3. Update config.json**
```json
{
  "text_formatting": {
    "language": "en-US",
    "unit_temperature": null,
    "unit_length": null,
    "unit_weight": null
  }
}
```

**4. Update config.py Migration**
```python
def migrate_legacy_language(config):
    """Migrate 'en' to 'en-US' for backward compatibility."""
    text_formatting = config.get("text_formatting", {})
    if text_formatting.get("language") == "en":
        text_formatting["language"] = "en-US"
    return config
```

### Phase 3: Core Integration (3 files)

**5. Update constants.py**
```python
def get_regional_defaults(language: str) -> dict:
    """Get regional measurement defaults for language code."""
    resources = get_resources(language)
    return resources.get("regional_defaults", {})

def get_measurement_preference(language: str, measurement_type: str, user_override: str = None) -> str:
    """Get measurement preference with fallback chain."""
    if user_override:
        return user_override
    regional_defaults = get_regional_defaults(language)
    return regional_defaults.get(measurement_type, "metric")  # System fallback
```

**6. Update formatter.py**
```python
class TextFormatter:
    def __init__(self, language: str = "en-US", regional_config: dict = None):
        self.language = language
        self.regional_config = regional_config or {}
        # Pass regional config to measurement converters
```

**7. Update measurement_converter.py**
```python
class MeasurementPatternConverter(BasePatternConverter):
    def __init__(self, number_parser, language: str = "en-US", regional_config: dict = None):
        super().__init__(number_parser, language)
        self.regional_config = regional_config or {}
        
    def convert_temperature(self, entity: Entity) -> str:
        """Convert temperature using regional preferences."""
        # Check for explicit scale first
        if "celsius" in entity.text.lower() or "fahrenheit" in entity.text.lower():
            return self._convert_explicit_temperature(entity)
            
        # Use regional preference for ambiguous temperatures
        temp_preference = self._get_temperature_preference()
        if temp_preference == "fahrenheit":
            return f"{parsed_number}°F"
        else:
            return f"{parsed_number}°C"
            
    def _get_temperature_preference(self) -> str:
        """Get temperature preference from config chain."""
        return get_measurement_preference(
            self.language, 
            "temperature", 
            self.regional_config.get("unit_temperature")
        )
```

### Phase 4: Entry Point Integration (1 file)

**8. Update conversation.py**
```python
# Load regional configuration
text_formatting_config = self.config.get("text_formatting", {})
language = text_formatting_config.get("language", "en-US")
regional_config = {
    "unit_temperature": text_formatting_config.get("unit_temperature"),
    "unit_length": text_formatting_config.get("unit_length"),
    "unit_weight": text_formatting_config.get("unit_weight")
}
self.text_formatter = TextFormatter(language=language, regional_config=regional_config)
```

### Phase 5: Testing Strategy (Test files)

**9. Regional Test Cases**
```python
def test_temperature_regional_behavior(self, preloaded_formatter):
    """Test temperature formatting with different regional configurations."""
    test_cases = [
        # input, language, unit_overrides, expected, description
        ("twenty degrees", "en-US", {}, "20°F", "US default Fahrenheit"),
        ("twenty degrees", "en-US", {"unit_temperature": "celsius"}, "20°C", "US override to Celsius"),
        ("twenty degrees", "en-GB", {}, "20°C", "GB default Celsius"),
        ("twenty degrees celsius", "en-US", {}, "20°C", "Explicit unit overrides regional default"),
    ]
    
    for input_text, language, overrides, expected, description in test_cases:
        with self.subTest(input=input_text, config=f"{language}+{overrides}", desc=description):
            formatter = TextFormatter(language=language, regional_config=overrides)
            assert formatter.format(input_text) == expected
```

## Files to Modify

### Core Configuration (2 files)
1. `/workspace/config.json` - Add regional config structure
2. `/workspace/src/stt/core/config.py` - Add migration logic

### Resource System (4 files)
3. `/workspace/src/stt/text_formatting/resources/en-US.json` - Create with regional defaults
4. `/workspace/src/stt/text_formatting/resources/en-GB.json` - Create with regional defaults
5. `/workspace/src/stt/text_formatting/resources/en-CA.json` - Create with regional defaults
6. `/workspace/src/stt/text_formatting/constants.py` - Add regional preference functions

### Text Formatting Integration (3 files)
7. `/workspace/src/stt/text_formatting/formatter.py` - Pass regional config to converters
8. `/workspace/src/stt/text_formatting/converters/measurement_converter.py` - Apply regional preferences
9. `/workspace/src/stt/modes/conversation.py` - Load and pass regional config

### Testing (Multiple files)
10. `/workspace/tests/unit/text_formatting/test_*.py` - Add regional test cases

**Total: 10+ files**

## API Design

### User Configuration Interface
```json
{
  "text_formatting": {
    "language": "en-US",           // Regional defaults applied automatically
    "unit_temperature": "celsius", // Override regional default  
    "unit_length": "metric",       // Override regional default
    "unit_weight": null            // Use regional default (imperial for en-US)
  }
}
```

### Internal API
```python
# Clean interface for converters
def get_measurement_preference(language: str, measurement_type: str, user_override: str = None) -> str:
    """Get measurement preference with clear fallback chain."""
    
# Enhanced converter initialization
converter = MeasurementPatternConverter(
    number_parser=parser,
    language="en-US", 
    regional_config={"unit_temperature": "celsius"}
)
```

## Success Criteria

### Functional Requirements
- ✅ Regional defaults work: `en-US` gets Fahrenheit, `en-GB` gets Celsius
- ✅ User overrides work: US user can override to Celsius
- ✅ Explicit units preserved: "twenty celsius" always gives "20°C"
- ✅ Backward compatibility: existing configs continue working

### Performance Requirements
- ✅ No significant performance impact (< 5ms overhead)
- ✅ Resource loading cached efficiently
- ✅ Regional preference lookup optimized

### Test Coverage
- ✅ Regional defaults for en-US, en-GB, en-CA tested
- ✅ User override scenarios tested
- ✅ Fallback behavior tested
- ✅ Migration from legacy "en" tested

## Migration Strategy

### Backward Compatibility
```python
# Auto-migration in config.py
def load_config():
    config = json.load(config_file)
    
    # Migrate legacy language setting
    text_formatting = config.get("text_formatting", {})
    if text_formatting.get("language") == "en":
        text_formatting["language"] = "en-US"
        logger.info("Migrated language setting from 'en' to 'en-US'")
    
    return config
```

### Resource Fallback
```bash
# Symlink ensures backward compatibility
ln -s en-US.json en.json
```

## Error Handling

### Invalid Language Codes
```python
def get_resources(language: str = "en-US") -> dict:
    """Load resources with fallback for invalid language codes."""
    try:
        return _load_language_resources(language)
    except FileNotFoundError:
        # Fall back to base language (en-US → en)
        base_language = language.split('-')[0]
        if base_language != language:
            return _load_language_resources(base_language)
        # Final fallback to en-US
        return _load_language_resources("en-US")
```

### Invalid Unit Preferences
```python
def get_measurement_preference(language: str, measurement_type: str, user_override: str = None) -> str:
    """Get measurement preference with validation."""
    valid_units = {
        "temperature": ["celsius", "fahrenheit"],
        "length": ["metric", "imperial"], 
        "weight": ["metric", "imperial"]
    }
    
    if user_override and user_override in valid_units.get(measurement_type, []):
        return user_override
        
    # Fall back to regional default
    regional_defaults = get_regional_defaults(language)
    return regional_defaults.get(measurement_type, "metric")
```

## Future Extensions

### Additional Regions
- `en-AU` (Australian English)
- `en-NZ` (New Zealand English) 
- `en-ZA` (South African English)

### Additional Measurement Types
- `unit_currency` (USD, EUR, GBP formatting)
- `unit_date` (MM/DD/YYYY vs DD/MM/YYYY)
- `unit_time` (12-hour vs 24-hour)

### Context-Aware Preferences
```json
{
  "unit_temperature": {
    "cooking": "fahrenheit",
    "weather": "celsius",
    "scientific": "celsius"
  }
}
```

## Implementation Timeline

- **Phase 1**: Resource structure (1 day)
- **Phase 2**: Configuration system (1 day)  
- **Phase 3**: Core integration (2 days)
- **Phase 4**: Entry point integration (0.5 days)
- **Phase 5**: Testing (1 day)

**Total Estimated Time: 5.5 days**

## Risk Mitigation

### Breaking Changes
- Symlink `en.json → en-US.json` maintains compatibility
- Auto-migration prevents user config breakage
- Graceful fallbacks prevent system failures

### Performance Impact
- Resource loading already cached in `constants.py`
- Regional preference lookup uses simple dictionary access
- No complex computation in conversion path

### Testing Complexity  
- Focus on core regional defaults (4 main variants)
- Use parameterized tests to reduce duplication
- Separate unit tests for preference logic from integration tests

This proposal provides a clean, extensible regional measurement system that maintains backward compatibility while enabling precise user control over measurement units.