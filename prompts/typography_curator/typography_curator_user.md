# REQUEST
{{editor_user_request}}

# BUSINESS CONTEXT
- Type: {{editor_business_type}}
- Description: {{editor_site_description}}


---

# INSTRUCTIONS

**If user requests a specific font:**
1. Search Presets → return matches if found
2. Else search Full Catalogue → design custom type scale

**If no specific font requested:**
1. Thoroughly analyze user request  and business attributes.
2. Analyze image reference typography style for inspiration
3.  Design 1-2 custom scales from Full Catalogue and select 1 Preset that matches best based on selection priority.

5. Ensure diversity (no duplicates, mix approaches)

CRITICAL:
- Only output fonts that exist in the catalogues
- Weight must be a number (400, 700), not "px"
- noMatch field: empty string unless substitution was made


Each typeScale must have all 9 roles (h1-h6, p1-p3) with:
- `font-family`: slug from catalogue
- `wt`: weight as string number ("400", "700")
- `size`: with px unit ("88px")
- `lh`: line-height with em unit ("1.1em")  
- `ls`: letter-spacing with em unit ("0em", "-0.02em")   

# Output Format
- Array format: [font-slug, wt, size, lh,  ls]
- Use font slug (e.g. inter, roboto-mono) not full name (e.g. Inter, Roboto Mono).    
- Output type-scales  in order of best match for the selection criteria, not based on the catalogues order.   