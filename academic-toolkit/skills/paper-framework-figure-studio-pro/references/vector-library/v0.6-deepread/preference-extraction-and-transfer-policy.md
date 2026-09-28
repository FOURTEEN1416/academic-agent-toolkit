# Preference Extraction and Transfer Policy

User-provided preferred figures, style references, architecture diagrams, or visual examples are style evidence, not paper evidence.

## Extractable Preference Dimensions

Create `user_preference_profile.json` with:

- palette: dominant colors, accent colors, saturation, contrast, background;
- layout rhythm: grid, freeform, panels, cards, lanes, radial, loop, hierarchy;
- shape language: rounded cards, sharp boxes, pills, nodes, tiles, callouts;
- icon style: outline, filled, duotone, soft-3D, cartoon, technical line;
- arrow grammar: thick/thin, orthogonal/curved, dashed/solid, feedback loops;
- typography: label weight, title presence, all-caps/normal, label density;
- dimensionality: flat 2D, line-art, isometric, soft 3D;
- abstraction level: symbolic, schematic, semi-illustrative, illustrative;
- density: sparse, medium, dense;
- evidence treatment: mini-chart, metric badge, result cards, before/after strip;
- tone: academic, technical, friendly, premium, playful, system-engineering;
- positive preferences;
- negative preferences;
- vector risk;
- transfer strength: weak / medium / strong / locked.

## Preference Transfer Contract

Create `preference_transfer_contract.json`:

```json
{
  "profile_id": "pref.v1",
  "transfer_strength": "medium",
  "round1_policy": "use as 1-2 preference-informed directions unless user locks style",
  "round2_policy": "apply only when it does not reduce paper clarity, vector buildability, or reviewer comprehension",
  "locked_properties": [],
  "soft_properties": ["palette", "rounded cards", "duotone icons"],
  "do_not_copy": ["source paper facts", "unique copyrighted layout", "unreadable micro-details"],
  "conflicts": []
}
```

## Conflict Resolution

Priority order:

1. paper facts;
2. reviewer-first comprehension;
3. vector/PPT buildability;
4. candidate fidelity lock;
5. user preference;
6. decorative style.

If a preference is visually attractive but makes the figure poster-like or too hard to vectorize, simplify it and record the simplification.
