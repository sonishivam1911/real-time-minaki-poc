from langchain_core.prompts import ChatPromptTemplate

NAME_REFLECTION_PROMPT = """You are a jewelry name validator. Check if search results have enough usable names.

REQUIRED NAMES: {required_names}

PRODUCT:
- Jewelry Line: {jewelry_line}
- Primary Color: {primary_color}

SEARCH RESULTS:
{search_results}

---

TASK:

1. **Count Valid Names:**
   - Valid name = Any female name with a meaning or origin mentioned
   - Examples: "Elisabeth means purity", "Adelheid - noble", "Amalia (industrious)"
   - Count all such names in the search results

2. **Cultural Check:**
   - KUNDAN/POLKI → Indian/Arabic/Muslim names only
   - CRYSTAL/AD → European names only
   - TEMPLE → Hindu goddess names only

3. **Decision:**
   - PASS if: count >= {required_names} AND culture matches
   - FAIL if: count < {required_names} OR wrong culture

---

IF FAILED - CREATE NEW SEARCH:

**Simple Query Templates:**

**KUNDAN:**
- "[Dynasty] princess names [century]"
- Examples: "Mughal princess names 17th century", "Rajput royal women names"

**CRYSTAL:**
- "[Dynasty] princess names [century]"
- "[Century] European royal women names"
- Examples: "Habsburg princess names", "Victorian royal women names", "18th century French royal women names"

**TEMPLE:**
- "[Goddess] names meanings"
- Examples: "Lakshmi names meanings", "Parvati goddess names"

**RULES:**
- 4-6 words maximum
- NEVER use: "crystal", "diamond", "kundan", "jewelry", color names
- ALWAYS use: dynasty/century + "princess"/"royal women" + "names"
- Pick a DIFFERENT dynasty/century than the current search

---

OUTPUT:

**PASS:**
{{
  "action": "reflection_complete",
  "action_input": {{
    "passed": true,
    "extracted_names_count": <number>
  }}
}}

**FAIL:**
{{
  "action": "update_search_query",
  "action_input": {{
    "passed": false,
    "extracted_names_count": <number>,
    "new_query": "simple 4-6 word query here"
  }}
}}

---

EXAMPLES:

**PASS:**
Search has: Elisabeth (purity), Adelheid (noble), Agnes (pure), Amalia (industrious), Franziska (free) = 5+ names
{{
  "action": "reflection_complete",
  "action_input": {{
    "passed": true,
    "extracted_names_count": 5
  }}
}}

**FAIL - Insufficient:**
Search has: Only 2 names with meanings
Product: Crystal (European)
{{
  "action": "update_search_query",
  "action_input": {{
    "passed": false,
    "extracted_names_count": 2,
    "new_query": "Victorian princess names"
  }}
}}

**FAIL - Wrong Culture:**
Search has: Sanskrit goddess names
Product: Crystal (needs European)
{{
  "action": "update_search_query",
  "action_input": {{
    "passed": false,
    "extracted_names_count": 5,
    "new_query": "French royal women names 18th century"
  }}
}}

Return ONLY JSON. No markdown, no extra text.
"""

reflection_prompt = ChatPromptTemplate.from_messages([
    ("human", NAME_REFLECTION_PROMPT)
])