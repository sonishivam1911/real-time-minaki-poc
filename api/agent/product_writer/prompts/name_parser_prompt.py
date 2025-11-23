from langchain_core.prompts import ChatPromptTemplate

NAME_PARSER_PROMPT = """Extract jewelry name inspirations from these search results.

SEARCH RESULTS:
{search_results}

TASK:
Find 10-15 names with cultural meanings suitable for jewelry products.

⚠️ **CRITICAL ENFORCEMENT:**
- Return EXACTLY ONE JSON object ONLY
- NO explanations, thinking, or reasoning
- NO multiple JSON snippets
- NO markdown code blocks
- SINGLE JSON OBJECT ONLY - from opening {{ to closing }}
- If you generate anything other than pure JSON, your response will be rejected

OUTPUT FORMAT (JSON):
{{
  "action": "parse_names",
  "action_input": {{
    "names": [
      {{"name": "ExampleName", "meaning": "cultural meaning and origin"}},
      {{"name": "AnotherName", "meaning": "cultural meaning and origin"}}
    ]
  }}
}}

RULES:
1. Extract names with clear meanings
2. Prefer names related to: gems, light, beauty, royalty, nature
3. Each name must have a meaningful origin story
4. Minimum 10 names, maximum 15 names
5. Return ONLY the complete JSON structure - no other text
6. All property names in double quotes
7. No trailing commas
8. Escape quotes within strings using backslash

Return the complete JSON structure with all extracted names. NOTHING ELSE.
"""

name_parser_prompt = ChatPromptTemplate.from_messages([
    ("human", NAME_PARSER_PROMPT)
])