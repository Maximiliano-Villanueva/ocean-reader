/**
 * Starter JSON bodies for schema authoring (agent + manual edit).
 */

/** Empty DSL v3 body — default when creating a new schema key via the assistant. */
export const EMPTY_SCHEMA_TEMPLATE = `{
  "version": "3",
  "fields": {},
  "rules": ["required", "range_validation", "type_check"]
}`;

export const WINE_QUALITY_TEMPLATE = `{
  "version": "3",
  "fields": {
    "ph": {
      "type": "number",
      "required": true,
      "min": 2.5,
      "max": 4.5,
      "aliases": ["pH", "Measured pH"]
    },
    "alcohol": {
      "type": "number",
      "required": true,
      "min": 8.0,
      "max": 15.0,
      "aliases": ["Alcohol", "Alcohol %"]
    },
    "quality": {
      "type": "number",
      "required": true,
      "min": 0,
      "max": 10,
      "aliases": ["Quality", "Quality score"]
    }
  },
  "rules": ["required", "range_validation", "type_check"]
}`;
