# Roadmap: Digital Twin Mode Implementation

## Goal

Enable strict `[USER IMAGE]` mode ("Digital Twin" behavior) where the system faithfully replicates the user's reference image style, even when it conflicts with business type conventions.

**Design Principle**: Minimal changes to the Architect. Push detection logic upstream to Copier.

---

## Entity 1: Copier (Brand Book Generator)

### Change Summary
The Copier **only runs when a user uploads an image**. All outputs are implicitly `[USER IMAGE]` mode. Add the `[USER IMAGE]` label to output title and add **specific sensors** that downstream entities need.

### Additions Required

#### A. Output Title Label
Add `[USER IMAGE]` to the Brand Book title so downstream entities know to apply Digital Twin behavior:

```markdown
# [USER IMAGE] Technical Design Specification (Brand Book)
```

#### B. Density Sensor
Classify layout density for downstream spacing decisions:
- **Hyper-Dense**: Minimal gaps, content-packed
- **Standard**: Typical web spacing
- **Airy**: Heavy negative space, generous margins

#### C. Treatment Sensor
Distinguish between subject matter and applied stylistic treatment:
- **Subject Color**: The subject happens to be that color
- **Applied Treatment**: A filter/effect applied to images (name it specifically)

#### D. Geometry Classification
Provide font geometry hints for matching:
- **Width**: Condensed, Normal, Extended
- **Weight Class**: Hairline, Light, Regular, Bold, Black
- **Style**: Geometric, Humanist, Slab, Display
- **Relative Scale**: Note if typography is dramatically sized

---

## Entity 2: Typography Curator

### Change Summary
**Flip selection priority** when `[USER IMAGE]` is detected.

### Priority Change

**Current (all modes)**:
```
1. User Request
2. Industry & Cultural Fit  ← Business fit wins
3. Image Reference
```

**Proposed for [USER IMAGE]**:
```
1. User Request
2. Visual Geometry Match    ← Image geometry wins
3. Industry & Cultural Fit  ← Demoted
```

### Implementation

Add mode-aware selection logic:

```markdown
# SELECTION PRIORITY

**When Brand Book title contains [USER IMAGE]:**
Priority: Visual Geometry Match > Industry/Cultural Fit

**Otherwise (no Brand Book or internal image):**
Priority: Industry/Cultural Fit > Image Vibe

## Geometric Matching (USER IMAGE)
When [USER IMAGE] is detected, match the geometry classification from the Brand Book:
- Match Width (Condensed/Normal/Extended)
- Match Weight Class
- Match Style category
- Respect relative scale indications
```

---

## Entity 3: Architect (Design Brief Creator)

### Change Summary
**Minimal changes required.** The Architect already has `[USER IMAGE]` mode logic in sections 6 (colors), 7 (typography), and 12 (photos). Only refinements needed.

### Modifications Required

#### A. Hierarchy Rule (Already Exists - Verify)

The Architect's user prompt already contains mode handling. Verify this logic is clear and unambiguous.

#### B. Section 7 (Typography) - Strengthen Existing Logic

Ensure the existing `[USER IMAGE]` logic references:
- The Curator's geometry-matched font selection
- The relative scale/proportions from the Brand Book
- Priority of physical characteristics over conventional sizing

#### C. Treatment Propagation (Existing Logic - Verify)

Ensure Local Briefs reference the treatment name from the Global Brief so section generators apply it consistently.

---

## Implementation Order

**Phase 1: Copier Sensors** ✅ COMPLETE
1. ✅ Add [USER IMAGE] label to output title
2. ✅ Add Density Sensor output
3. ✅ Add Treatment Sensor output  
4. ✅ Add Geometry Classification output
5. ✅ Add Relative Scale for headers

**Phase 2: Curator Priority Flip** ✅ COMPLETE
1. ✅ Add mode detection check (check for `[USER IMAGE]` in Brand Book title)
2. ✅ Implement priority switch: Visual Geometry Match > Industry Fit
3. ✅ Reference geometry classification from Brand Book

**Phase 3: Architect Refinements** ✅ COMPLETE (minimal changes)
1. ✅ Existing hierarchy rule verified - already clear
2. ✅ Typography section refined to clarify geometry priority for [USER IMAGE]
3. ✅ Treatment propagation already in existing §12 logic

---

## Testing Scenarios

| Scenario | Expected Behavior |
|----------|-------------------|
| Industrial image + Farm business | Typography matches reference geometry, not "friendly farm" convention |
| Dense layout reference | Spacing replicates Brand Book density description |
| Treated photo reference | Treatment name from Brand Book applied consistently |
| Dramatic header scale reference | Relative proportions preserved, not normalized |
| Unconventional aesthetic + Traditional business | Reference aesthetic wins, business content adapts |

---

## Success Criteria

1. **Visual Fidelity**: Generated site is recognizably "the same design" as reference
2. **Content Adaptation**: Business content correctly populated
3. **Treatment Consistency**: All images receive the treatment specified in Brand Book
4. **Typography Character**: Font geometry and scale match Brand Book analysis
5. **Principle-Based**: No hardcoded values in prompts—all specifics come from Brand Book analysis
