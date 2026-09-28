# Style Token Governance

Style tokens must include vector constraints and lockable properties.

```json
{
  "style_id": "iclr_clean_flat_modular_v1",
  "palette": {},
  "stroke_width": 2,
  "corner_radius": 18,
  "shadow_policy": "none_or_soft_single_layer",
  "icon_style": "duotone",
  "lockable_properties": {
    "palette": true,
    "stroke_width": true,
    "corner_radius": true,
    "arrow_style": true,
    "font_policy": true,
    "shadow_policy": true
  },
  "vector_constraints": {
    "allow_raster": false,
    "allow_filter": false,
    "allow_mask": false,
    "max_gradients": 1,
    "prefer_live_text": true
  }
}
```
