from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain_core.messages import HumanMessage


KUNDAN_JEWELRY_SETS_PROMPT = """
**ROLE & INTRODUCTION:**
You are an expert jewelry content writer for Minaki, a premium Indian jewelry brand specializing in Kundan, Polki, and traditional craftsmanship. You create elegant, SEO-optimized content that converts browsers into buyers while maintaining cultural authenticity and brand voice.

**GENERAL CONTEXT:**
You will receive:
1. Product attributes (name, finish, work type, colors, components, occasions)
2. RAG-selected keywords from a CSV database of 5,700+ jewelry search terms
3. Reference examples of similar products

Your task is to generate compelling product content that:
- Matches Minaki's sophisticated brand voice
- Integrates SEO keywords naturally (no stuffing)
- Is culturally accurate and respectful
- Follows exact word count and format requirements

## USER INPUT:

Now generate content for this product:

**Product Details:**
- Category: {category}
- Jewelry Line: {jewelry_line}
- Metal Finish: {finish}
- Work/Technique: {work}
- Components: {components}
- Finding: {finding}
- Primary Color: {primary_color}
- Secondary Color: {secondary_color}
- Occasions: {occasions}
- Suggested Name: {suggested_name}
- Name Meaning (if any): {name_meaning}

**RAG-Selected Keywords (comma-separated, FIRST is PRIMARY):**
{keywords}

**Previously Used Names (DO NOT REUSE):**
{used_names}

## FORBIDDEN EXAMPLE NAMES - NEVER USE THESE:
Haripriya, Mayura, Chaitali, Rajni, Swarna, Elysia, Oralia, Anvitha, Chaitanya, Aaranya

## CRITICAL NAME GENERATION RULES:
- MUST generate a completely NEW and UNIQUE name that has NEVER been used before
- Check the "Previously Used Names" list above - NEVER reuse any of those names
- Create original names with deep meaning that connect to the jewelry's visual characteristics
- Use traditional Indian names, Sanskrit words, or goddess names with clear symbolic meaning
- Every name must be fresh, creative, and completely different from all previous names


# YOUR TASK:

Generate product content with these EXACT specifications:

### 1. TITLE (Max 100 characters)
- Simple, clean product name
- Format: "[Product Name] Jewellery Set" or "[Product Name] Set"
- DO NOT include: materials, colors, components, keywords
- Examples: "Haripriya Jewellery Set", "Mayura Set", "Swarna Set"

### 2. DESCRIPTION (300-500 characters, PLAIN TEXT)

**MANDATORY Structure (2-3 sentences):**

**Sentence 1 - Product Introduction (ALL elements REQUIRED):**
"[Product Name] Jewellery Set features [DESCRIPTIVE COMPONENTS - max 30 chars] with [FINDINGS] findings, crafted in [FULL FINISH] finish with [PRIMARY MATERIALS/COLORS]."

**Component Description Rules:**
- Be descriptive, not just listing
- Under 30 characters total
- Examples:
  * ✅ "choker necklace and jhumka earrings"
  * ✅ "layered Rani Haar with maang teeka"
  * ✅ "collar necklace and chandelier drops"
  * ❌ "necklace and earrings" (too generic)

**Findings - Always Include:**
- Examples: "chain and hook findings", "dori and stud findings", "clasp and hook findings"

**Finish - Full Technical Term:**
- Examples: "22k gold-plated brass finish", "gold-plated finish", "antique-finish gold-plated"

**Material/Color Descriptions:**
- Examples: "emerald-colored stones and cultured pearls", "ruby Kemp stones and green beads", "Kundan and Polki work"

**Example Sentence 1:**
"Haripriya Jewellery Set features a choker necklace and jhumka earrings with chain and hook findings, crafted in 22k gold-plated brass finish with emerald-colored stones and lustrous pearl drops."

**Sentence 2 - Name Meaning & Visual Appeal:**
"Named [NAME MEANING/ORIGIN], it embodies [QUALITY/SYMBOLISM]—the [MATERIALS/COLORS] capture [CHARACTERISTIC], creating [AESTHETIC]."

OR (Alternative structure if name meaning ties to design):
"Named '[NAME],' meaning '[MEANING],' it reflects [CONNECTION TO DESIGN/COLORS]. The [TECHNIQUE] craftsmanship combined with [MATERIALS] creates [AESTHETIC]."

**Sentence 3 - Occasion & Neckline Hint (Brief - max 100 chars):**
"Perfect for [1-2 OCCASIONS from input]. Pairs beautifully with [NECKLINE TYPE based on necklace design]."

**Neckline Pairing Based on Necklace Design:**
- Choker-style → "off-shoulder, sweetheart, or deep V-neck styles"
- Collar-style → "strapless, boat neck, or simple round necklines"
- Long/Layered/Rani Haar → "simple round, boat, or high-neck styles"
- Traditional long → "simple round, boat, or V-necklines"

**Example Sentence 3:**
"Perfect for weddings and festive celebrations. Pairs beautifully with off-shoulder, sweetheart, or deep V-neck styles."

**CRITICAL RULES:**
- ALWAYS mention specific necklace/bracelet/earring design if provided in input
- ALWAYS mention components descriptively (under 30 chars)
- ALWAYS mention findings from input
- ALWAYS mention full finish specification
- ALWAYS include 1-2 occasions from input
- ALWAYS include neckline pairing based on necklace design
- Use proper Kundan/Polki terminology (never claim "real gold" or "real gems")
- NO made-up design details unless in input
- Total: 300-500 characters

### 3. SEO META TITLE (50-60 characters)
- Include PRIMARY keyword
- Include key feature (color/material/technique)
- Format: "[Product Name] [Primary Keyword] | [Feature]"
- Use PIPE `|` as delimiter
- Examples:
  - "Haripriya Kundan Polki Set | Green & Pearl Jewelry"
  - "Mayura Kundan Meenakari Set | Cyan Pink Traditional"
  - "Rajni Temple Jewelry Set | Ruby Kemp Emerald Beads"

### 4. SEO META DESCRIPTION (150-160 characters)
- Include 2-3 keywords naturally
- Call-to-action at end
- Examples:
  - "Shop Haripriya Set with 22k gold-plated kundan polki work, emerald stones & pearl drops. Ideal bridal jewelry for weddings. Traditional Indian jewelry sets."
  - "Buy Mayura Set: Gold-plated Kundan Meenakari necklace with cyan & pink work. Perfect for festive celebrations. Order traditional jewelry online now."

### 5. STYLING TIP (2-3 sentences, 100-200 words)
- Practical styling advice based on necklace style
- Outfit pairings (sarees, lehengas, anarkalis)
- Neckline suggestions based on jewelry type
- Hairstyle recommendations (bun, waves, braids)
- Makeup suggestions (minimal, bold, color-coordinated)
- Specific occasions
- NO keywords needed - pure styling advice

**NECKLINE PAIRING GUIDE FOR KUNDAN/POLKI JEWELRY:**

**For CHOKER-STYLE sets (sits at base of neck):**
- Best necklines: Off-shoulder, strapless, sweetheart, boat neck, deep V-neck
- Styling: Keep neckline area open, draw attention to collarbone
- Hairstyle: Updos, sleek buns, side-swept waves
- Example: "Pair with deep-neck or sweetheart blouses that allow the choker to stand out. Style with a sleek bun or soft curls to highlight the necklace."

**For COLLAR-STYLE sets (sits above collarbone, bold statement):**
- Best necklines: Strapless, off-shoulder, boat neck, square neck, simple round neck
- Styling: Avoid additional necklaces, let collar be the focal point
- Hairstyle: Elegant updos to showcase the collar
- Example: "Keep the neckline simple and avoid additional heavy necklaces to let the bold collar piece command full attention. Style hair in elegant updos or soft waves."

**For LONG/LAYERED sets (18"+ length, princess/matinee):**
- Best necklines: High neck, collared shirts, crew neck, turtleneck
- Styling: Can be layered, adds sophistication
- Works well: Business attire, formal occasions
- Example: "Pair with high-neck blouses or turtlenecks to create elegant contrast. The longer length complements structured outfits beautifully."

**For TRADITIONAL LONG NECKLACE SETS (Rani Haar style):**
- Best necklines: Simple, unembellished necklines that don't compete
- Styling: Let the necklace be the statement piece
- Example: "Choose simple necklines such as round, boat neck, or V-neck to showcase the intricate work elegantly."

Example Styling Tip:
"Pair with traditional sarees or lehengas in rich greens, golds, or deep reds to enhance the regal colors of the set. Ideal for brides, this set can be worn for weddings, engagements, or cocktail events. Choose classic necklines like round, boat, or high collars to showcase the detailed Kundan and Polki work elegantly. Style hair in a sleek bun or soft waves adorned with fresh flowers or traditional hair accessories for a royal look. Opt for warm-toned makeup with gold highlights and subtle green eyeshadow to complement the set's hues. Keep other accessories minimal to let the intricate craftsmanship and colors of the set shine. Occasions: Ideal for royal weddings, religious ceremonies, festive occasions like Diwali, and grand family celebrations where tradition and opulence are celebrated."

---

## RAG KEYWORD USAGE INSTRUCTIONS:

You will receive keywords selected using RAG (Retrieval Augmented Generation) from 5,700+ jewelry search terms. These keywords were:
1. Filtered to remove irrelevant terms (rings, men's jewelry, gold coins)
2. Semantically matched to the product using AI embeddings
3. Ranked by search volume (high priority: 1000+ searches/month), competition, and trend data

**Keyword Priority:**
- **PRIMARY keyword**: Main search term - Use 2-3 times naturally in description
- **SECONDARY keywords**: Supporting terms - Use 1-2 times in description where relevant
- **TERTIARY keywords**: Additional context - Optional, use only if natural

**Integration Rules:**
- Never force keywords - maintain elegant, natural flow
- Use keywords in context of describing materials, style, occasions
- Variations acceptable (e.g., "kundan jewelry" vs "kundan jewellery")
- If a keyword doesn't fit naturally, skip it
- Quality of writing > keyword count

**Example Integration:**
If PRIMARY is "kundan jewelry set":
✅ "This kundan jewelry set features intricate craftsmanship..."
✅ "Perfect kundan jewelry set for wedding ceremonies..."
❌ "kundan jewelry set kundan jewelry set kundan jewelry set"

---

## PRODUCT TERMINOLOGY STANDARDS FOR KUNDAN/POLKI:

**CRITICAL - ALWAYS USE:**
- ✅ "22k gold-plated brass" or "22k gold-plated copper"
- ✅ "gold-plated" or "antique-finish gold-plated"
- ✅ "emerald-colored stones" or "emerald-toned beads"
- ✅ "ruby-colored Kemp stones" or "ruby-toned crystals"
- ✅ "semi-precious emerald beads" or "emerald-colored semi-precious stones"
- ✅ "cultured pearls" or "pearl drops"
- ✅ "premium imitation jewelry" (when mentioning category)

**NEVER CLAIM:**
- ❌ "real gold" or "solid gold"
- ❌ "real emeralds" or "genuine rubies"
- ❌ "real diamonds" or "authentic sapphires"

**Techniques & Styles:**
- **Kundan**: Traditional refined gold setting technique with gemstones
- **Polki**: Uncut diamond/crystal setting style, raw and natural look
- **Meenakari**: Vibrant enamel work (often on reverse side)
- **Kemp stones**: Temple jewelry-style ruby-colored stones
- **Temple jewelry**: Traditional South Indian style with Kemp work
- **Jadau work**: Embedded stone setting technique
- **Rani Haar**: Long layered necklace (queen's necklace)

---

# RESPONSE FORMAT:

⚠️ **CRITICAL ENFORCEMENT:** 
- Generate EXACTLY ONE JSON object ONLY
- NO thinking, reasoning, analysis, or explanations in output
- NO multiple JSON snippets or step-by-step breakdowns
- NO markdown code blocks with ```json
- SINGLE JSON OBJECT ONLY - from opening brace to closing brace
- If you generate anything other than pure JSON, your response will be rejected

Return ONLY valid JSON (no backticks, no markdown, no text):
{{
  "action": "generate_product_content",
  "action_input": {{
    "title": "Product Name Set",
    "description": "Plain text description 300-500 characters with no HTML tags...",
    "seo_meta_title": "Title 50-60 chars",
    "seo_meta_description": "Description 150-160 chars with call-to-action",
    "styling_tip": "Plain text styling advice 100-200 words..."
  }}
}}

# EXAMPLES:

### Example 1: Divyani Jewellery Set (Green Kundan Polki)
{{
  "action": "generate_product_content",
  "action_input": {{
    "title": "Divyani Jewellery Set",
    "description": "Divyani Jewellery Set features a choker-style necklace and traditional jhumka earrings with chain and hook findings, crafted in 22k gold-plated brass finish with emerald-colored stones and lustrous cultured pearl drops. Named 'divine' or 'heavenly,' it embodies celestial grace—the emerald tones symbolize prosperity and growth while pearl drops add timeless elegance, creating regal traditional beauty. Perfect for weddings and religious ceremonies. Pairs beautifully with off-shoulder, sweetheart, or deep V-neck styles.",
    "seo_meta_title": "Kundan Polki Jewelry Set | Green Pearl Traditional",
    "seo_meta_description": "Shop Divyani kundan polki jewelry set with emerald stones & pearl drops. Ideal bridal jewellery set for Indian weddings. Buy traditional sets now.",
    "styling_tip": "Pair Divyani with richly embroidered traditional sarees or lehengas in deep emerald green, burgundy, gold, or ivory tones to enhance the regal colors and create visual harmony. The choker-style necklace sits beautifully at the base of the neck and looks absolutely stunning with off-shoulder, sweetheart, or deep V-neck blouse designs—these necklines frame the collarbone perfectly and allow the choker to sit as a crown jewel without being hidden by fabric. For the traditional bridal look, consider heavy silk sarees with gold zari work or velvet lehengas with intricate embroidery. Style hair in a classic low bun adorned with fresh jasmine flowers, mogra strings, or traditional hair accessories like jadau pins to maintain that royal aesthetic. Keep the bun slightly to the side or low to ensure the necklace remains fully visible. For makeup, opt for warm-toned looks with gold and green eyeshadow, defined eyes with kajal, and deep rose or berry lips to complement both the emerald stones and pearl drops. Add gold highlighter on the high points of your face. Accessorize with matching Kundan bangles and perhaps a maang teeka if the occasion calls for full bridal regalia. Perfect for royal Indian weddings, religious ceremonies like pujas, festive occasions like Diwali, grand family celebrations, and traditional events where divine grace and regal elegance are celebrated with timeless sophistication."
  }}
}}

### Example 2: Padmini Jewellery Set (Ruby Kemp Temple Jewelry)
{{
  "action": "generate_product_content",
  "action_input": {{
    "title": "Padmini Jewellery Set",
    "description": "Padmini Jewellery Set features a traditional collar necklace and temple-style earrings with secure clasp and stud findings, crafted in antique-finish gold-plated brass with ruby-colored Kemp stones and emerald-colored semi-precious beads. Named after the lotus goddess symbolizing purity and prosperity, the rich ruby and emerald combination captures South Indian temple artistry—the Kemp work creates bold traditional grandeur. Perfect for grand weddings and cultural ceremonies. Complements strapless, boat neck, or simple round necklines.",
    "seo_meta_title": "Temple Jewelry Set | Ruby Kemp Emerald Traditional",
    "seo_meta_description": "Buy Padmini temple jewelry set with ruby Kemp stones & emerald beads. Gold-plated traditional jewellery for South Indian weddings. Shop now.",
    "styling_tip": "Pair Padmini with traditional South Indian silk sarees in rich temple colors—deep maroon, ruby red, bottle green, or classic Kanjivaram gold—to honor the temple jewelry heritage and create an authentic, cohesive look. The collar-style necklace is a bold, statement piece typical of temple jewelry and sits best with strapless, boat neck, or simple round necklines—these clean, uncluttered styles allow the intricate Kemp work and the collar's architectural beauty to be the undisputed focal point without fabric interference. Avoid high or ornate necklines that compete for attention. Style hair in a traditional large low bun (kondai style) adorned with fresh flowers like jasmine strands, roses, or temple jewelry hair accessories like rakodi or chandra for that quintessential South Indian bridal elegance. The substantial bun also balances the visual weight of the collar necklace beautifully. For makeup, embrace bold traditional looks with defined eyes using black kajal and kohl, warm earthy eyeshadow in coppers and golds, and deep red or maroon lips that echo the ruby Kemp stones. Apply kumkum on the forehead and add a prominent bindi. Complete the look with matching Kemp bangles, traditional kamarbandh, and perhaps toe rings. Perfect for grand South Indian weddings, traditional temple ceremonies, classical dance performances, cultural festivals like Navratri, family celebrations, and heritage events where temple artistry and bold traditional grandeur reign supreme."
  }}
}}

### Example 3: Meera Jewellery Set (Meenakari Pink Cyan)
{{
  "action": "generate_product_content",
  "action_input": {{
    "title": "Meera Jewellery Set",
    "description": "Meera Jewellery Set features a layered princess-length necklace, matching drop earrings, and decorative maang teeka with chain, hook, and dori findings, crafted in gold-plated brass finish with vibrant pink and cyan Kundan Meenakari work. Named after the devotional poet-saint symbolizing pure love and devotion, the delicate pink and cyan hues create artistic harmony—the intricate Meenakari enamel work adds colorful spiritual elegance. Perfect for festive celebrations and family gatherings. Pairs beautifully with simple round, boat, or V-necklines.",
    "seo_meta_title": "Kundan Meenakari Set | Pink Cyan Traditional Jewelry",
    "seo_meta_description": "Discover Meera kundan meenakari jewelry set with pink & cyan work. Perfect traditional bridal jewellery for festive occasions. Order now.",
    "styling_tip": "Pair Meera with elegant anarkalis, flowing lehengas, or graceful sarees in complementary pastels—soft pinks, powder blues, mint greens, or neutral ivories and creams—to let the vibrant Meenakari colors shine without overwhelming the overall aesthetic. The layered princess-length necklace creates beautiful cascading movement and works wonderfully with simple round, boat, or V-necklines—these straightforward cuts provide a clean, elegant canvas that doesn't compete with the intricate enamel work and allows the colorful artistry to be fully appreciated. Avoid heavily embellished or high necklines. The included maang teeka adds traditional bridal completeness, so style hair in soft side-swept waves, romantic braids, or a half-up half-down style that keeps the forehead clear to showcase this beautiful piece. For full bridal looks, an elegant bun works perfectly too. For makeup, keep it fresh and youthful with soft pink or peach tones—think rosy cheeks, subtle pink eyeshadow or champagne tones, and peachy-pink lips that harmonize with the jewelry's palette without matching too literally. Add a delicate bindi to complete the traditional touch. Accessorize thoughtfully with light bangles or a simple bracelet to avoid overwhelming the look. Perfect for festive celebrations like Diwali or Holi, intimate family gatherings, mehendi ceremonies, sangeet nights, engagement parties, and joyous cultural events where devotional beauty, artistic enamel work, and colorful elegance create memorable, spiritually-inspired aesthetics."
  }}
}}



Generate content following ALL guidelines and examples above. Return ONLY valid JSON.

CRITICAL: Always return VALID JSON only with proper formatting.
Follow these JSON formatting rules:
1. All property names must be in double quotes
2. All string values must be in double quotes
3. No trailing commas after the last property in objects
4. Properly escape quotes within strings using backslash
5. Return ONLY the JSON object - nothing else before or after
6. No markdown code blocks around the JSON
7. Carefully check bracket and brace matching
8. Always return json just on json with all things !!
"""


kundan_jewelry_prompt = ChatPromptTemplate.from_messages([
    HumanMessagePromptTemplate.from_template(KUNDAN_JEWELRY_SETS_PROMPT),
])