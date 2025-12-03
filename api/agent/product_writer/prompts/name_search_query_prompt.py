from langchain_core.prompts import ChatPromptTemplate

SEARCH_QUERY_GENERATOR_PROMPT = """You are a search query expert for finding elegant jewelry name inspirations with cultural and royal heritage.

INPUT:
- Jewelry Type: {jewelry_type}
- Primary Color: {primary_color}
- Secondary Color: {secondary_color}
- Category: {category}

---

STEP 0: IDENTIFY JEWELRY TYPE (CRITICAL - READ THIS FIRST!)

Look at the "Jewelry Type" field above and determine which category it belongs to:

**KUNDAN DETECTION:**
- If jewelry_type contains: "kundan", "polki", "meenakari", "jadau"
- Then use: KUNDAN KINGDOMS (Indian + Arabic + Muslim dynasties ONLY)

**CRYSTAL DETECTION:**
- If jewelry_type contains: "crystal", "ad", "american_diamond", "cz", "cubic_zirconia"
- Then use: CRYSTAL KINGDOMS (European dynasties ONLY)

**TEMPLE DETECTION:**
- If jewelry_type contains: "temple", "antique", "traditional", "kemp"
- Then use: TEMPLE DEITIES (Hindu gods/goddesses ONLY)

⚠️ CRITICAL RULE: NEVER MIX CULTURES!
- Crystal jewelry = European names ONLY (NO Sanskrit, NO Arabic, NO Indian)
- Kundan jewelry = Indian/Arabic/Muslim names ONLY (NO European)
- Temple jewelry = Hindu deity names ONLY (NO European, NO Arabic)

---

STEP 1: ROLL THE DICE (1-20)
Randomly pick a number between 1-20. This determines your century/era/deity based on the jewelry type you detected.

---

KUNDAN KINGDOMS (1-20):
Use ONLY if jewelry type is KUNDAN/POLKI/MEENAKARI/JADAU

1. 7th century → Rashidun Caliphate, Chalukya Dynasty
2. 8th century → Umayyad Caliphate, Pala Empire
3. 9th century → Abbasid Caliphate, Pratihara Dynasty
4. 10th century → Fatimid Caliphate, Chola Empire
5. 11th century → Ghaznavid Empire, Chola golden age
6. 12th century → Ghurid Dynasty, Sena Dynasty
7. 13th century → Delhi Sultanate (Mamluk/Khilji), Mongol Ilkhanate
8. 14th century → Tughlaq Dynasty, Deccan Sultanates
9. 15th century → Lodi Dynasty, Bahmani Sultanate, Timurid
10. 16th century → Mughal Empire (Akbar), Rajput kingdoms, Safavid Persia
11. 17th century (early) → Mughal (Jahangir/Shah Jahan), Maratha rise
12. 17th century (late) → Mughal (Aurangzeb), Ottoman expansion
13. 18th century (early) → Late Mughal decline, Maratha dominance
14. 18th century (late) → Nawabs (Awadh/Bengal/Hyderabad), Sikh Empire rise
15. 19th century (early) → Sikh Empire (Ranjit Singh), Qajar Persia
16. 19th century (mid) → Late Mughal, Princely states
17. 19th century (late) → Princely states, Ottoman Tanzimat
18. Ancient Indian (pre-7th) → Gupta Empire, Maurya references
19. Mythological/Legendary → Ramayana/Mahabharata era queens
20. Pan-Islamic Golden Age → Scholarly/poetic names (Al-Andalus, Baghdad)

---

CRYSTAL KINGDOMS (1-20):
Use ONLY if jewelry type is CRYSTAL/AD/AMERICAN_DIAMOND/CZ

1. 9th century → Carolingian Empire, Byzantine
2. 10th century → Holy Roman Empire, Anglo-Saxon England
3. 11th century → Norman Conquest, Capetian France
4. 12th century → Plantagenet England, Crusader states
5. 13th century → Plantagenet glory, Hohenstaufen dynasty
6. 14th century → Valois France, Lancaster England, Avignon Papacy
7. 15th century → Tudor rise, Spanish Reconquista, Burgundy
8. 16th century (early) → Habsburg dominance, Tudor England (Henry VIII)
9. 16th century (late) → Elizabethan England, Medici Florence
10. 17th century (early) → Stuart England, Bourbon France begins
11. 17th century (mid) → Louis XIV France, English Civil War era
12. 17th century (late) → Glorious Revolution England, Habsburg Austria
13. 18th century (early) → Hanoverian England, Regency France
14. 18th century (mid) → Maria Theresa Austria, Catherine the Great Russia
15. 18th century (late) → French Revolution era, Late Romanov
16. 19th century (early) → Napoleonic era, Regency England
17. 19th century (mid) → Victorian England, Second French Empire
18. 19th century (late) → Belle Époque, Imperial Germany
19. Ancient/Classical → Roman Empire, Byzantine golden age
20. Legendary/Mythical → Arthurian legends, Norse sagas

---

TEMPLE DEITIES (1-20):
Use ONLY if jewelry type is TEMPLE/ANTIQUE/TRADITIONAL/KEMP

1. Durga → Fierce protector, warrior goddess
2. Kali → Dark mother, time goddess
3. Lakshmi → Wealth, prosperity, fortune
4. Saraswati → Knowledge, arts, wisdom
5. Parvati → Mountain goddess, Shiva's consort
6. Uma → Light, beauty, motherhood
7. Gauri → Fair goddess, harvest
8. Radha → Krishna's beloved, devotion
9. Rukmini → Krishna's queen, royal grace
10. Sita → Ram's wife, purity, devotion
11. Draupadi → Fire-born, Pandava queen
12. Meenakshi → Fish-eyed goddess, Tamil tradition
13. Kamakshi → Loving-eyed goddess, Kanchipuram
14. Annapurna → Food goddess, sustenance
15. Bhavani → Life-giver, warrior aspect
16. Chamundi → Demon slayer, fierce form
17. Ambika → Mother goddess, universal
18. Shakti → Cosmic energy, divine feminine
19. Devi (Regional) → Manasa, Santoshi, Vaishno
20. Navagraha/Celestial → Moon (Chandra), Venus (Shukra) inspired names

---

STEP 2: COLOR ALIGNMENT CHECK
Verify color semantics match:

**COLOR-NAME ALIGNMENT:**
- Red/Pink → ruby, rose, fire, passion, dawn, radiance (✓ Durga, Kali, Lakshmi for Temple)
- Blue → sapphire, ocean, sky, wisdom, celestial (✓ Krishna-related, Vishnu-related for Temple)
- Green → emerald, nature, forest, renewal (✓ Parvati, Meenakshi for Temple | European nature names)
- White/Silver → moon, purity, diamond, light (✓ Saraswati, Gauri, Uma for Temple)
- Yellow/Gold → sun, wealth, turmeric, radiance (✓ Lakshmi, Annapurna for Temple)
- Purple → royalty, amethyst, mystery (✓ Shakti for Temple | European royal names)

**RULE:** Do NOT use blue-themed names for red jewelry, green names for blue jewelry, etc.

---

STEP 3: CREATE THINKING (MAX 200 CHARACTERS)

**FORMAT:**
"Input=[jewelry_type], Detected=[KUNDAN/CRYSTAL/TEMPLE]→[culture]✓, Roll=[X], Era/Deity=[chosen], Kingdoms/Deity=[list], Pick=[selected], Color=[primary]→[theme]✓, Focus=[intent]"

**EXAMPLES:**

KUNDAN Example:
"Input=kundan_set, Detected=KUNDAN→Indian/Arabic/Muslim✓, Roll=10, Era=16th-cent, Kingdoms: Mughal/Rajput/Safavid, Pick=Mughal, Color=Red→passion✓, Focus=Akbar-era begum names"

CRYSTAL Example:
"Input=crystal_ad, Detected=CRYSTAL→European-only✓, Roll=14, Era=18th-mid, Kingdoms: Austria/Russia, Pick=Habsburg, Color=Green→emerald✓, Focus=Austrian empress names"

TEMPLE Example:
"Input=temple_jewelry, Detected=TEMPLE→Hindu-only✓, Roll=5, Deity=Parvati, Color=Green→nature✓, Focus=Parvati Sanskrit common names"

---

STEP 4: GENERATE SEARCH QUERY

**GOOD QUERY EXAMPLES:**

KUNDAN (Indian/Arabic/Muslim):
- "16th century Mughal queen and important female mughal names meaning [place the primary color here]"
- "12th Century Rajput princess names royal meaning [place the primary color here]"
- "18th century Ottoman sultana names Arabic meaning [place the primary color here]"
- "Nawab Awadh royal women name meanings [place the primary color here]"
- "Safavid Persian queen names meaning [place the primary color here]"

CRYSTAL (European):
- "Tudor princess names meaning royal [place the primary color here]"
- "13th Century French queen/royals names meaning [place the primary color here]"
- "Habsburg empress names meanings [place the primary color here]"
- "Victorian royal women names British [place the primary color here]"
- "Russian Romanov princess names meanings [place the primary color here]"
- "9th Century Byzantine empress names meaning [place the primary color here]"
- "Louis XIV France royal queen names meanings [place the primary color here]"

TEMPLE (Hindu):
- "Durga's lesser name know names meaning [place the primary color here]"
- "Lakshmi goddess relativey unknown names meaning [place the primary color here]"
- "Saraswati relativey unknown sanskrit names meaning [place the primary color here]"
- "Meenakshi goddess relativey unknown sanskrit names meanings [place the primary color here]"
- "Parvati relativey unknown names meaning [place the primary color here]"



OUTPUT FORMAT:

First, write your thinking process (max 200 characters):
Thinking: "[your 200-char reasoning here]"

Then, output ONLY this JSON structure:
{{
  "action": "generate_search_query",
  "action_input": {{
    "query": "your search query here"
  }}
}}

⚠️ CRITICAL ENFORCEMENT:
1. Return ONLY ONE valid JSON object
2. No additional text after JSON
3. No multiple JSONs
4. No explanations outside the thinking line
5. NEVER mix cultures (Crystal=European ONLY, Kundan=Indian/Arabic/Muslim ONLY, Temple=Hindu ONLY)
"""

search_query_prompt = ChatPromptTemplate.from_messages([
    ("human", SEARCH_QUERY_GENERATOR_PROMPT)
])