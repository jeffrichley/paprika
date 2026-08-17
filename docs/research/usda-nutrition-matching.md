# Research: USDA FoodData Central and ingredient matching

> Resolves [#7](https://github.com/jeffrichley/paprika/issues/7).
> Date: 2026-08-16. All API facts verified against live calls to `api.nal.usda.gov/fdc/v1` on that date.

## TL;DR

The API is easy, free, permissively licensed, and **not the hard part**. The hard part is the join:
turning `2 large yellow onions, diced` into a food record with a defensible gram weight.

Parsing that line into `qty=2 / size=large / name=yellow onion / prep=diced` is solved
(**95.6% sentence-level** with the best maintained open-source CRF). **Matching** it to the right
USDA record is not, and will not be solved by this plugin: the best published USDA-specific result
is **94.49% coverage but only 71.6% correct** — i.e. it returns a confident *wrong* record about a
quarter of the time. Worse, verified empirically here, **matcher confidence scores are not
calibrated**: both a leading open-source matcher and a commercial API returned ~1.0 confidence while
inventing specificity (`butter` → `Butter, stick, unsalted`; `milk` → `Milk, fluid, 1% fat`).

Honest end-to-end accuracy for whole-recipe macros from free text is roughly **±20-25% on a good
day, worse for anything cooked, mixed, or fatty** — and the error is not random, it is
systematically biased.

**Verdict on targets: meaningful only if scoped to "trend and relative comparison," never
"measurement."** See [Verdict](#verdict-are-targets-meaningful-or-theatre).

---

## Part A — The API

### Facts table

| Item | Value | Source |
|---|---|---|
| Base URL | `https://api.nal.usda.gov/fdc/v1` | API guide |
| Key required | Yes — a **data.gov** key on every request | "a data.gov API key must be incorporated into each API request" |
| Key cost | Free, instant, self-service signup | api-key-signup |
| Rate limit (real key) | **1,000 requests/hour per IP address** | API guide |
| Rate limit (`DEMO_KEY`) | **30/hour per IP, 50/day** documented — but the live response header returned `x-ratelimit-limit: 10` on 2026-08-16 | docs vs. observed header |
| Over-limit behaviour | HTTP **429**, temporary block for 1 hour | API guide |
| Usage introspection | `X-RateLimit-Limit`, `X-RateLimit-Remaining` response headers | verified live |
| Endpoints | `/food/{fdcId}`, `/foods` (batch), `/foods/list`, `/foods/search` | OpenAPI spec |
| `/foods` batch max | **20 fdcIds** per request | OpenAPI spec (`maxItems: 20`) |
| `/foods/search` page size | default **50**, **max 200** | OpenAPI spec (`maximum: 200`) |
| `nutrients` filter | up to **25** nutrient numbers per request | OpenAPI spec |
| `format` | `abridged` or `full` (default `full`) | OpenAPI spec |
| Data types | Foundation, SR Legacy, Survey (FNDDS), Branded, Experimental | data-documentation |
| Licence | **CC0 1.0 Universal** — public domain, not copyrighted | FDC licensing |
| Attribution | Not legally required; USDA *requests* you cite FoodData Central | FDC licensing |
| Bulk download | Full CSV/JSON dumps, **no API key needed** | download-datasets |

**Practical gotcha (verified):** `GET /foods/search?dataType=Survey (FNDDS)` fails with an nginx
`400 Bad Request` because of the spaces and parentheses, even URL-encoded. Use **POST** with a JSON
body (`{"dataType":["Survey (FNDDS)"]}`) for any data-type-filtered search.

### Rate limits in practice

1,000 req/hr per **IP**, not per key — this matters. The limit is shared by everyone behind a NAT
or a CI runner. For a local Claude Code plugin hitting it from one developer machine it is
effectively unlimited: a 20-ingredient recipe costs ~20-40 calls, so ~25 recipes/hour worst case,
and that is before any caching. With a local cache it is a non-issue.

### Licensing verdict

**Clean. Redistribution is explicitly fine.**

FDC data are US Government works, released as **CC0 1.0 Universal**. USDA's own wording: the data
"are in the public domain and they are not copyrighted... No permission is needed for their use,"
with a *request* (not a requirement) to cite FoodData Central as the source. Suggested citation:

> U.S. Department of Agriculture, Agricultural Research Service. FoodData Central, 2019.
> fdc.nal.usda.gov.

This covers Branded Foods too, despite it being a public-private partnership carrying manufacturer
trademarks — the *nutrient data* is CC0. Shipping brand names and product descriptions in a
redistributed dataset is a trademark question, not a copyright one, and is fine for nominative
descriptive use. **We should avoid shipping Branded data anyway** for reasons in Part B.

So: a public plugin may bundle, cache, transform, and redistribute USDA nutrient values with no
licence obligation beyond good manners.

### Can the plugin ship an API key? **No — and it does not need to.**

USDA is unambiguous, on both the API guide and the signup page:

> "It is the API Key holder's responsibility to ensure that their key is not made publicly
> available. **Any API keys discovered online, such as those in a code repository, will be
> deactivated** to prevent malicious use."

A key committed to a public repo is not merely against the rules — it is **automatically revoked**,
so shipping one is a guaranteed outage, not a calculated risk. The three real options:

1. **Each user supplies their own key** (env var / plugin config). Free and instant, but it is a
   signup wall in front of first use — real friction for a "just works" plugin.
2. **Ship a pre-built local dataset from the bulk downloads.** No key, no rate limit, no network,
   works offline, reproducible. Sizes make this genuinely practical:
   - Foundation Foods: **3.7 MB zipped** CSV (32 MB unzipped)
   - SR Legacy: **6.7 MB zipped** CSV (54 MB unzipped)
   - Survey/FNDDS: 3.7 MB zipped JSON (64 MB unzipped)
   - Branded: 428 MB zipped — excluded, and we do not want it
3. **Hybrid:** bundle the curated subset; let a user-supplied key unlock live Branded lookups for
   packaged goods.

**Recommendation: option 2, with option 3 as an escape hatch.** A curated Foundation + SR Legacy +
FNDDS subset covering common cooking ingredients compresses to a few MB — smaller than most plugin
dependencies. It removes the key problem entirely, removes the rate limit entirely, makes results
deterministic and reproducible (the same recipe always yields the same numbers, which matters a lot
for a provenance-labelled tool), and works offline.

### Which data type is right for home cooking?

The five types are not interchangeable, and the trade-off is sharp.

Counts below are **live, from the `aggregations.dataType` facet** (FDC v15.3, 2026-07-23), and
portion coverage was computed from the bulk CSVs — not estimated:

| Data type | Foods | Last updated | Portion coverage | Portions/food | Nutrient quality |
|---|---|---|---|---|---|
| **Foundation** | **394** | Apr 2026 (2×/yr) | **21.0%** (83 foods) | ~1.3 | **Best** — analytical, real `data_points` |
| **SR Legacy** | **7,793** | **Frozen Apr 2018** | **96.7%** | 1.92 | Good, ageing |
| **Survey (FNDDS)** | **5,432** | Oct 2024 (2021-2023) | **99.3%** | **4.09** | Derived, not independent |
| **Branded** | **433,082** | Monthly | serving-size only | 1 | Label-accuracy only |
| **Experimental** | 115 | Occasional | — | — | N/A for us |
| *Total* | *446,816* | | | | |

**Branded is 97% of the database.** That single fact explains the search behaviour below and is the
reason data-type filtering is non-negotiable.

Three qualifiers that matter more than the headline coverage numbers:

- **Foundation is tiny — 394 foods, and 79% of them have no portion record at all.** It is a
  precision overlay, not a base layer. It cannot carry a recipe tool.
- **SR Legacy's coverage is shallower than 96.7% suggests.** 2,760 foods have exactly one portion
  and 3,618 have exactly two, and the single most common modifier is `"oz"` (3,166 of 14,449 rows =
  22%) — a trivial 28.35 g identity conversion carrying no information.
- **FNDDS has the most portion data and the least evidence behind it: 0 of 22,046 portion rows have
  any `data_points`.** Not one. SR Legacy has them on 24.5% of rows; Foundation on 97%.

And a loss worth recording: the old SR28 `WEIGHT.txt` carried **`Std_Dev`** alongside each gram
weight. **FoodData Central's `food_portion.csv` dropped it.** Portion-weight uncertainty existed in
the source data and was discarded in the migration — so we cannot compute honest error bars from
FDC itself, and must assert our own.

I verified the portion problem directly on one ingredient — `yellow onion`:

**Foundation `790646` "Onions, yellow, raw"** — exactly **2** portions:
```
1 Onion (Edible)  -> 143 g
1 RACC            ->  85 g
```
No small/medium/large. It cannot answer "2 **large** onions."

**SR Legacy `170000` "Onions, raw"** — **10** portions:
```
1 large                    -> 150 g      1 cup, chopped -> 160 g
1 medium (2-1/2" dia)      -> 110 g      1 cup, sliced  -> 115 g
1 small                    ->  70 g      1 tbsp chopped ->  10 g
1 slice, medium (1/8")     ->  14 g      10 rings       ->  60 g
```

**Survey/FNDDS `2709795` "Onions, raw"** — good but no size gradation for onions:
```
1 cup -> 160 g    1 whole -> 148 g    1 slice -> 15 g    1 ring -> 5 g
Quantity not specified -> 15 g
```
(FNDDS *does* carry gradation for some foods — its `Apple, raw` has `1 small 165 g`,
`1 medium 200 g`, `1 extra large 295 g`.)

**This is the central structural finding of Part A.** The data type with the best modern nutrient
values (Foundation) has the *worst* portion data. The only type that can resolve the word "large"
for an onion is **SR Legacy, frozen since April 2018**. You cannot get both from one record — you
must join across data types, and that join is itself a guess.

Note also the three sources disagree on what one onion weighs: **143 g / 148 g / 150 g**. That
spread is small (~5%) and is the *good* case — a well-defined vegetable. It gets much worse.

#### Trap 1: `modifier` means three different things

The portion schema is shared across data types but **populated incompatibly**, and a generic parser
will silently produce garbage:

| Data type | `measure_unit_id` | `portion_description` | `modifier` |
|---|---|---|---|
| **Foundation** | **real** (`cup`, `tablespoon`, `each`, `slice`…) | empty | free-text qualifier, or empty for 61 of 83 foods |
| **SR Legacy** | **`9999 undetermined` for all 14,449 rows** | empty | **the whole measure as prose** — `cup, chopped`, `slice, medium (1/8" thick)`, `large` |
| **FNDDS** | **`9999 undetermined` for all 22,046 rows** | **the measure as text** — `1 cup`, `1 large` | **a numeric 5-digit FNDDS portion code** — `10205`, `62368`, `90000` |

So `parse_portion(modifier)` is a bug: in FNDDS `modifier` is a **foreign key**, not prose. And in
SR Legacy, consuming USDA's portion data means parsing *USDA's own free text* — a second parsing
problem nested inside the first.

Branded is different again: no `foodPortions` array at all, just `servingSize`, `servingSizeUnit`
(`GRM`/`MLT`), and an unnormalised `householdServingFullText` like
`"3/4 cup (20g) (age 1-3 years)"`.

#### Trap 2: "Quantity not specified" is often the *first* portion returned

FNDDS portion code **90000 = "Quantity not specified"** appears **5,326 times — 24% of all portion
rows** — and frequently sorts first. USDA warns users "should not assume that QNS values accurately
represent the average amount." For `Onions, raw`, QNS = **15 g** while a whole onion is **148 g**.

**Any matcher that takes `foodPortions[0]` will sometimes be wrong by 10×.**

#### Trap 3: FNDDS "as consumed" records double-count the recipe's own cooking

This is the one that would quietly wreck a recipe tool. FNDDS onion codes, per 100 g:

| FNDDS food | kcal | Fat g | **Sodium mg** |
|---|---|---|---|
| Onions, raw (2709795) | 38 | 0.08 | **1** |
| Onions, cooked, no added fat (2709950) | 47 | 0.12 | **141** |
| Onions, cooked, fat added (2709951) | **73** | **3.11** | **147** |
| Onions, cooked, as ingredient (2710796) | 47 | 0.12 | **5** |

- Matching `2 onions, diced` in a recipe that separately lists olive oil to **`fat added`**
  double-counts the oil: **+92% energy**.
- Even **`no added fat`** carries **141 mg sodium from nowhere** — because WWEIA *respondents*
  salted their onions. For 300 g of onion that is ~420 mg of sodium the cook never added. **147×
  the raw value.**
- The correct record is **`as ingredient`** (5 mg Na) — and there are only **37 "as ingredient"
  codes in the entire database.** They do not exist for most ingredients.
- Cooked energy is higher per 100 g simply because water boiled off. Applying a *raw* gram weight
  to a *cooked* record overstates energy ~24%, and FDC ships no yield factors to fix it.

**Recommendation (revised against the measured evidence):** **SR Legacy as the base layer for raw
and commodity ingredients; FNDDS for portion weights and genuinely prepared components; Foundation
as a nutrient override where it exists; Branded only for explicitly named products.**

This reverses the intuitive choice, and the reason is coverage of *raw* foods:

- SR Legacy: **1,433 of 7,793 foods (18.4%)** contain "raw"
- FNDDS: **146 of 5,432 (2.7%)**

FNDDS is nearly **ten times thinner on raw commodities** — by design, since it exists to code
24-hour dietary recalls, not ingredient lists. Accepting a database frozen in 2018 is uncomfortable,
but the composition of a raw onion has not changed since 2018; this matters far more for processed
foods than for the whole ingredients a recipe tool spends most of its time on.

(Two honest caveats on this recommendation: FNDDS values are largely *derived* — USDA states about
1,700 FDC items were used to compute all 5,432 FNDDS items, and only ~a quarter of FNDDS codes map
directly to a single FDC code. And the databases disagree with each other: SR Legacy raw onion is
40 kcal / 1.1 g protein vs FNDDS 38 kcal / 0.86 g — **22% apart on protein** for the same food.)

### The search endpoint is the first failure mode

Default relevance ranking is close to unusable for cooking. Live query `yellow onion`,
no filters — **118,789 total hits**, and the aggregation breakdown is damning:

| Data type | Hits | Share |
|---|---|---|
| Branded | 118,394 | **99.7%** |
| Survey (FNDDS) | 258 | 0.2% |
| SR Legacy | 124 | 0.1% |
| Foundation | 12 | 0.01% |
| Experimental | 1 | — |

The top two results were Branded records literally named `YELLOW ONION` (relevance score 1456.3),
scoring **2.3× higher** than the actually-correct `Onions, yellow, raw`
(Foundation `790646`, score 624.8) at rank 3.

So: an unfiltered search for the most ordinary ingredient imaginable returns a packaged product as
the best answer, and the canonical whole food third. **Data-type filtering is mandatory, not an
optimisation.** Any naive "take the top search hit" implementation is wrong roughly all of the time.

---

## Part B — The hard part: parsing, matching, and conversion

The pipeline has four stages, and they fail in very different ways and at very different rates:

```
"2 large yellow onions, diced"
  │
  ├─ 1. PARSE      qty=2, size=large, name=yellow onion, prep=diced   ← ~95%, solved enough
  ├─ 2. MATCH      -> which of 118,789 records?                       ← the real problem
  ├─ 3. QUANTIFY   "large onion" -> grams                             ← lossy, often impossible
  └─ 4. TRANSFORM  raw ingredient -> cooked dish                      ← large systematic bias
```

Stage 1 is a solved research problem. Stages 2-4 are where the accuracy budget is spent, and no
amount of engineering closes them, because **the information is not present in the input text.**

(Note: good parsers treat `large` as a **size modifier**, not a unit — `unit` is null here. That is
the correct modelling and it matters in stage 3, because a size modifier has no fixed gram value.)

### Stage 1 — parsing: genuinely solved, with a caveat

Best-in-class open source is **`ingredient-parser-nlp`** (strangetom, MIT, actively maintained —
last push the day of this research). A CRF over 81,346 labelled sentences (NYT 30k, AllRecipes 15k,
BBC 15k, Cookstr 15k, TasteCove 6.3k), reporting on a 20% held-out split:

- **95.62% sentence-level**, **98.26% word-level** (F1 98.25%)

The widely-cited ancestor, NYT's **`ingredient-phrase-tagger`**, is **archived read-only since March
2019** (Python 2, CRF++). Running its own `roundtrip.sh` gives:

- **74.39% sentence-level**, 90.75% word-level

That gap is the caveat worth stating: "parsing is solved" is true of *current, maintained* tools,
not of the archived NYT tagger that much of the ecosystem — including **Mealie** — still builds on.
It also shows how badly per-token accuracy flatters results: 90.75% per-token means **1 in 4 lines
has at least one wrong token.**

Academic ceiling (UCL attention-based parser, ESANN 2022, arXiv:2210.02535), entity-level F1:
Quantity 96.47, Unit 95.68, Size 94.17, Name 93.31, Temperature 80.90. Cross-domain generalisation
drops (train AllRecipes → test Food.com: 87.51 vs 91.45 in-domain) — parsers do not transfer cleanly
between recipe sources.

**`recipe-scrapers`** (hhursev, MIT, very active) is frequently miscited as a parser. It is not.
`ingredients()` returns **raw strings**; `ingredient_groups()` only splits by heading. A PR to add
structured parsing (#733) was **closed unmerged in Oct 2024**; the maintainer's position is that
parsing "won't be in the core package." Correct framing: **recipe-scrapers gets you the ingredient
strings; you still need a parser.**

### Stage 2 — matching: not solved, and it fails *silently*

Here is the structural tell. `ingredient-parser-nlp` publishes parsing accuracy to four significant
figures — and **publishes no accuracy figure at all for its USDA matching.** Its changelog
repeatedly says "improve accuracy of foundation foods matching" without ever quoting a number, and
its docs concede the match threshold is "based on manual testing and is unlikely to be perfect."

Published matching numbers, all far below parsing:

| Study | Recognition | Linking / matching |
|---|---|---|
| **USDA FDC matching** (arXiv:2004.12286) | 94.49% *coverage* | **71.6% correct** (3,580/5,000 manually verified) |
| FoodNER (JMIR 2021) | 94.31% macro F1 | FoodOn 78.13%, SNOMED 76.01% |
| FoodBase (Oxford *Database*) | FoodIE 0.961 F1 | NCBO+FoodOn **~0.639** (recall **0.535**) |
| FoodSEM (arXiv:2509.22125), SOTA fine-tuned LLM | — | 0.83-0.86 in-domain; **0.0 zero-shot** |
| FoodSEM **out-of-domain** (branded) | — | **36.9% / 29.2%** Acc@1 |
| FoodOntoRAG (arXiv:2603.09758) | — | **57-60% strict Acc@1** |

**The USDA row is the number to remember: 94.49% of ingredients got _a_ match; only 71.6% got the
_right_ one.** Matching does not fail loudly — it returns a confident wrong record about 28% of the
time. In that study the downstream effect was **36.42 kcal average per-serving error**, and the
authors note "the main problem lies in matching the units."

The FoodSEM authors state the general case bluntly: food named-entity linking "cannot be accurately
solved by state-of-the-art general-purpose (large) language models or custom domain-specific
models/systems."

Three documented structural reasons:

1. **Recall collapse** — the database simply lacks the surface form (NCBO+FoodOn recall 0.535 misses
   half of all mentions).
2. **Granularity ambiguity — there is often no single correct answer.** FoodOntoRAG adjudicated 381
   flagged errors and found only **9.2% genuinely wrong**; **76.9% were semantically equivalent at a
   different granularity.** This is unlike parsing, where ground truth is well defined.
3. **Out-of-distribution brittleness** — 0.83 F1 in-domain collapses to ~30-37% on branded lists.

### The empirical finding that should drive the design: match confidence is not calibrated

Both `ingredient-parser-nlp` v2.7.0 (local install) and the live Zestful API were run against the
ticket's edge cases. **Parsing was near-perfect. Matching quietly invented specificity.**

| Ingredient | Zestful → USDA | ingredient-parser-nlp → FDC |
|---|---|---|
| `yellow onions` | `Onions, raw` (170000), labelled **`matchMethod: "exact"`** despite dropping "yellow" | `Onions, yellow, raw` (790646), conf 1.0 ✅ |
| `milk` | **`Milk, fluid, 1% fat`** via `closestUnbranded` — **invented a fat percentage** | `Milk, NFS`, conf 1.0 ✅ |
| `cream` | (parse failed first) | **`Cream, whipped`**, conf 0.819 — wrong sense |
| `salt` | `Salt, table` ✅ | **`Salt, table, iodized`, conf 1.0** — unwarranted |
| `butter` | `Butter, without salt` | **`Butter, stick, unsalted`, conf 1.0** — unwarranted; salted vs unsalted is a real nutritional difference |

**Confidence 1.0 on `butter` → `unsalted stick` and on `salt` → `iodized`.** Zestful labelling a
lossy match `"exact"`. Zestful's own documented degradation ladder is
`exact → closestUnbranded → closestBranded`, and its docs openly show "apple cider vinegar"
resolving to **"BRAGG, ORGANIC APPLE CIDER VINEGAR"** — a branded substitution.

**Conclusion: parsing confidences are meaningful; matching confidences are not.** Any pipeline that
trusts a matcher's self-reported score will silently attach wrong nutrition data at full confidence.
This is the single most important design input from Part B — see the tiering rules below, which
deliberately derive confidence from *structural* evidence (did the unit match a real `foodPortion`?)
rather than from a matcher's score.

### Parser failure modes (empirically verified)

| Input | Zestful | ingredient-parser-nlp |
|---|---|---|
| `2-3 cloves garlic` | qty **2** — upper bound **silently dropped**, no field for it ❌ | qty 2, quantity_max 3, `RANGE=True` ✅ |
| `1 (14.5 oz) can diced tomatoes` | product `"can diced tomatoes"`, no USDA match, **conf 0.264** ❌ | `1 can` + `14.5 ounce` ✅ |
| `salt to taste` | "to taste" **silently dropped**, **conf 0.999** ⚠️ | `comment="to taste"` ✅ |
| `1 cup milk or cream` | product `milk`, prep `"or cream"` — alternative misfiled ❌ | two names: `milk`, `cream` ✅ |
| `2 tbsp butter, divided, plus more for greasing` | "plus more for greasing" **dropped**, **conf 0.903** ⚠️ | prep `divided` + comment preserved ✅ |
| `a handful of parsley` | qty 1, unit `handful` ✅ | ✅ |

Note the pattern: Zestful flagged the *structural* failure (conf 0.264) but reported **0.903 and
0.999 while silently discarding data.** Confidence scores catch malformed input, not information
loss. Zestful's own documented limitations confirm: mixed units ("2 8-oz cans"), non-numeric
quantities ("Three tablespoons"), and multi-ingredient lines all fail.

### A caution on citing accuracy numbers in this space

Two documented reproducibility failures are worth carrying forward:

- The UCL authors could not reproduce Diwan et al.'s claimed **0.95 F1**, obtaining **0.61**; the
  original code was unavailable and the authors did not respond.
- arXiv:2503.02650 (recipe → Cooklang via LLM) **contradicts itself**: the abstract claims
  ROUGE-L 0.9722 / WER 0.0730 while the body reports **0.8209 / 0.3509**. Its strict
  Ingredient Identification Score for GPT-4o is **0.33**.
- The circulating "RecipeNLG 0.92 F1" is **not** an NER score — it is the corpus deduplication
  threshold.

Rule adopted for this document: cite only numbers traceable to a run someone actually executed.

### Licensing of the tooling

| Asset | Licence | Usable here |
|---|---|---|
| `ingredient-parser-nlp` (code) | MIT | ✅ — but training-corpus provenance is undocumented |
| NYT `ingredient-phrase-tagger` | Apache 2.0 | ⚠️ archived 2019 |
| `recipe-scrapers` | MIT | ✅ (scraping only) |
| `ingreedypy`, `parse-ingredient`, `ingredient-slicer` | MIT | ✅ — none publish accuracy |
| Zestful | Commercial, **$0.02/ingredient** | ✅ permits retention/resale, but no published accuracy and a 2021-04-28 USDA snapshot |
| **RecipeNLG** | non-commercial research/education only | ❌ |
| **Recipe1M / 1M+** | research institutions only, gated | ❌ |
| FoodOn ontology | CC BY 4.0 | ✅ |

### Stage 3 — quantity is lossy even when parsing and matching are perfect

This deserves emphasis because it is the failure people underestimate. Assume we parsed perfectly
and matched to exactly the right record. `2 large yellow onions` is *still* ambiguous:

- SR Legacy says a large onion is 150 g. Actual supermarket "large" onions routinely run
  110-250 g. The word "large" is doing very little work.
- `diced` changes nothing nutritionally but changes every volume measure — "1 cup chopped" (160 g)
  and "1 cup sliced" (115 g) differ by **39%** for the same food, in USDA's own table.
- The classic case is flour: a cup ranges from ~120 g (spoon-and-level) to ~155 g+ (dip-and-sweep),
  a **~30% swing** on the single largest contributor to a baked good's calories.

No parser and no database fixes this. A volume or count measurement of a compressible or
size-variable food carries irreducible uncertainty of roughly **±15-30%**, contributed by the
*recipe author*, before our pipeline touches it.

### Stage 3 (cont.) — how volume→mass is actually solved, and why USDA disclaims it

Four mechanisms exist. Only one is broadly usable, and USDA explicitly tells you not to use it the
way we want to.

**(a) FNDDS portion tables** — the workhorse. 22,046 gram weights; 67.9% of foods have a cup
measure. It is the only broad, free, machine-readable volume→mass table keyed to specific foods.
**But**, verbatim from the FNDDS 2021-2023 documentation:

> "Weights are estimations to represent a group of foods and beverages and **may not account for all
> sizes available** for a specific product... portion gram weights reflect a generic food/beverage
> or a **composite of several similar products**."

> "**Portion weights in FNDDS... may not be applicable for calculating density or weight per volume**
> for any specific liquid."

**USDA is explicitly disclaiming its own portion data as a density source.** It is a survey-coding
instrument. It is nevertheless what everyone uses, because nothing better is free.

**(b) The old SR `WEIGHT.txt`** — survives as SR Legacy's `food_portion.csv`, minus `Std_Dev`,
frozen 2018, capped at ~2 measures per food.

**(c) FDA RACC (21 CFR 101.12)** — **not a density table, and must not be used as one.** RACC
assigns a reference amount *per product category* for label serving-size determination. It answers
"how much is a serving of breakfast cereal," never "what does a cup of *this* chopped onion weigh."
Its only real use here is sanity-checking Branded `servingSize` values.

**(d) FAO/INFOODS Density Database v2.0 (2012)** — **638 entries across 20 food groups**,
distinguishing mass density, bulk density and specific gravity. Small, but it is genuinely density
(g/mL), which FNDDS is not, and it handles liquids — exactly the case USDA disclaims. Unmaintained
since 2012.

For stage 4, **USDA Agriculture Handbook 102** / the **Cooking Yield Database** / the **Table of
Cooking Yields for Meat and Poultry** supply raw→cooked yield and moisture/fat factors. They are
PDFs and legacy formats, not APIs — usable, but only via manual curation.

**Gap:** there is **no actively maintained, openly licensed, machine-readable ingredient density
dataset** with meaningfully broader coverage than FNDDS + FAO/INFOODS. The good ones are proprietary
(Nutritics, ESHA, NDSR).

#### How big is the volume error? USDA's own data answers it

From SR Legacy `Onions, raw` — same food, same volume, different knife work:

> **1 cup, chopped = 160 g · 1 cup, sliced = 115 g — a 39% difference.**

And size words: **small 70 g · medium 110 g · large 150 g.** A "large" onion is **114% heavier than
a small one**, so an unqualified "1 onion" spans more than 2× in USDA's own table.

Flour, per King Arthur Baking (the standard industry reference): their recipes assume **1 cup =
120 g**, and *"if the flour is more condensed, a cup can hold **up to 160 grams**"* — a **33%**
swing from scooping technique alone, on the largest calorie contributor in most baked goods.

**Honesty note on the flour figure:** this is a commercial baking authority's own testing, **not
peer-reviewed** — no published study measuring cup-of-flour variance was found. Related claims
circulating online ("a 2023 Journal of Food Engineering study found...", "89% of consumer scales
drift >1.5 g") trace to AI-generated SEO domains with **fabricated citations** that do not check
out. Likewise the commonly-quoted "a large onion is 170-340 g" contradicts USDA by 13-127% and comes
from the same sources. **Not cited here, and should not be cited downstream.**

### Stage 4 — raw ingredients ≠ the cooked dish

If we sum raw ingredient records and present the total as the dish's nutrition, we are wrong in a
*directional, non-cancelling* way. USDA maintains the Table of Cooking Yields and the Table of
Nutrient Retention Factors precisely because cooking changes weight (moisture loss, water
absorption, fat gain/loss) and destroys some nutrients.

A 2025 study applying cooked-meat codes to a recipe-based ingredient database quantified the gap
between raw-code and cooked-code estimates:

| Nutrient | Difference when raw codes used instead of cooked codes |
|---|---|
| Energy | **−10% to −51%** (beef brisket point: −51.3% ± 1.5) |
| Fat | **−20% to −62%** (beef brisket point: −62.3% ± 1.2) |
| Protein | **−6.5% to +34.2%** (beef tenderloin: +34.2% ± 4.1) |

These are not rounding errors, and they do not average out across a recipe — they are systematic
and food-dependent. Water loss concentrates nutrients per gram; rendered fat leaves the pan (or
does not, if you make a sauce from it, which the text does not tell us). Deep-frying *adds* fat in
an amount determined by oil temperature and surface area, neither of which appears in the recipe.

**Implication:** per-serving numbers for any cooked dish carry an additional systematic error on
top of everything else, and the plugin has no way to observe cooking method reliably enough to
correct it.

### How existing tools actually solve this: almost all of them punt

| Tool | Automatic nutrition from free text? | Reality |
|---|---|---|
| **Tandoor Recipes** | Partial, user-mediated | FDC ID must be supplied **per food, by hand**. Open [issue #4415](https://github.com/TandoorRecipes/recipes/issues/4415) (Feb 2026): *"Users must manually define or estimate conversions between volume and weight units for each ingredient, even when authoritative data exists"* — and requests exactly the `foodPortions` pipeline described in this doc. |
| **Mealie** | **No** — manual, unscaled | Nutrition is entered per recipe and *"no scaling is being done when changing Servings/Yield."* Requests span [#109](https://github.com/hay-kot/mealie/issues/109) → #2748 → #3601 → #4357. Mealie **has** a good NYT-derived CRF parser — it can parse `1 large onion, diced` fine. **It just has nothing to match the parsed food to.** |
| **Grocy** | Partial, and a known bug source | Product-level unit conversions, all **user-entered**; no food database behind them. Repeated changelog fixes for wrong energy when conversions are involved. |
| **Open Food Facts** | Inverse problem | `recipe-estimator` goes the *other* way (panel + ingredient list → ingredient percentages), via CIQUAL. Documented limitation: *"not all ingredients can be matched... and not all ingredients in the taxonomy have an association to the CIQUAL database."* Taxonomy→composition mapping [open since 2020](https://github.com/openfoodfacts/openfoodfacts-server/issues/2997). **Same matching problem, opposite direction, also unsolved.** |
| **Cronometer** | **No** — manual selection | Widely regarded as the most accurate consumer tool; refuses crowdsourced values into its verified tier, and makes users pick records by hand. |
| **MyFitnessPal** | Yes-ish, crowdsourced | ~14M entries, no verification gate. Error data below. |
| **Nutritionix / Edamam / Spoonacular** | Yes, commercial | Return `serving_weight_grams` / `weight` directly. Edamam notably *"adjusts quantity for certain ingredients to account for the cooking process"* (oil absorption in frying) — the only surveyed tool addressing stage 4. **None publishes any accuracy figure.** |

**The pattern is the finding.** Every open-source recipe manager punts to manual selection, and
Mealie, Grocy and Tandoor independently give the **same** stated blocker — not food-name matching,
but **volume→gram conversion**. And the most accurate consumer tool (Cronometer) is the one that
punts hardest. That is not a coincidence; it is the honest response to this problem.

**On commercial accuracy claims:** neither Nutritionix, Edamam, nor Spoonacular publishes an
accuracy metric, error bound, or validation study, and **no credible independent benchmark of any of
them exists.** The "~85% accuracy" figure for Nutritionix that circulates online traces to an SEO
blog with no methodology, no test set, and no author. Similarly, two frequently-cited MyFitnessPal
studies ("37% of entries had energy errors >20%", "a 2019 Nutrition Journal analysis found errors in
27% of entries") could not be located and appear to be fabricated. **Treat all four as non-existent
until someone produces a DOI.**

### Published error ranges — the real studies

These measure *app vs. research database*, which bounds database-and-matching error. Note they
mostly use **weighed** records, deliberately removing the volume-measurement variable — so they are
*optimistic* relative to our case.

**MyFitnessPal validation (JMIR 2020;22(10):e18237, n=50, vs Nubel):**

| Nutrient | Difference | | Nutrient | Difference |
|---|---|---|---|---|
| Energy | **+1.3%** | | Fiber | **−21%** |
| Fat | −1.7% | | Sodium | **−51%** |
| Carbohydrate | −6.4% | | Cholesterol | **−77%** |
| Protein | −7.8% | | Sugar | −13% |

Conclusion: accurate for energy and macros; **complete statistical power loss for cholesterol and
sodium.**

**Fallaize et al. (JMIR Mhealth 2019;7(2):e9838, n=20, weighed records, 5 apps):** energy
differences +14.7 to −146 kcal; sodium significantly low in several apps (r only 0.44-0.51); and
micronutrients collapse — **iron correlation r = −0.12 (Samsung Health) and r = 0.13
(MyFitnessPal)**, i.e. essentially no relationship to truth.

**JAND 2022 comparative validity — the most relevant study, because it isolates the
minimally-processed whole foods a recipe tool actually matches:** CalorieKing ICC 0.90-1.00;
Lose It!/MyFitnessPal 0.89-1.00 except MFP fiber **0.67**; Fitbit 0.52-0.98 with vegetable-group
fiber at **ICC 0.16**. And the number to internalise:

> MyFitnessPal energy agreement: **mean 8.35 kcal (SD 133.31).**

**A trivial mean hiding an enormous spread is the signature of a matching problem.** Errors are
large and roughly symmetric, so they cancel in aggregate and are invisible in summary statistics
while being badly wrong item by item. Any evaluation of this plugin that reports only mean error
will therefore look excellent and mean nothing.

**Professional recipe-analysis software vs. itself (Nutrition & Food Science 2026;56(3):612)** —
12 recipes across FCW, Nutritics and MyFood24: energy differences up to **101 kcal on a single
recipe (~35% of a ~280 kcal portion)**; salt **36.4% lower** in one package; potassium, vitamin A
and folate differences sometimes **>20%**.

That last study is the sharpest available answer to "how good can this get?" — **three professional,
commercially maintained nutrition packages, fed the same 12 recipes, disagree with each other by up
to 35% on energy and 36% on salt.** There is no consensus ground truth to converge on.

### What could not be found (flagged, not papered over)

1. **No study isolating volume→mass conversion error.** Every validation study above uses weighed
   records, deliberately removing the single variable that dominates our use case. This appears
   genuinely unmeasured in the literature.
2. **No published accuracy from any commercial natural-language nutrition API.**
3. **No peer-reviewed measurement of cup-of-flour variance.**
4. **No quantification of compounded volume error across a full ingredient list.**

### What the ceiling looks like for LLM-based estimation

Since this plugin is LLM-driven, the relevant benchmark is **NutriBench** (2024), which evaluates
LLMs on estimating nutrition from natural-language meal descriptions — very close to our task.

Best result, **GPT-4o with chain-of-thought**:
- **Acc@7.5 = 66.8%** — i.e. within 7.5 g of true carbohydrate only **two-thirds of the time**
- **MAE = 8.61 g carbohydrate** per meal
- Base prompting without CoT: **43.2%**; CoT alone: 47.5%; RAG+CoT (Llama 3.1 405B): 59.9%

The sobering companion result: the authors also had **three professional nutritionists** estimate
the same 72 meals. **GPT-4o beat all three.** Humans took 43 minutes; the model took 2.

Read that honestly in both directions:

- **Against optimism:** a third of meals are off by more than 7.5 g of carbs, from the best model,
  on a benchmark designed for the task. That is nowhere near "measurement."
- **Against nihilism:** the *human expert* baseline is also bad. There is no accurate alternative
  being displaced. The ceiling is low for everyone because the input text genuinely underdetermines
  the answer.

That second point is the crux of the verdict below. The failure here is not a Claude failure or a
USDA failure — it is that "2 large yellow onions, diced" does not contain enough information to
compute a number, and no system, human or machine, can recover what was never written down.

---

## The error budget, stage by stage

Pulling every verified number together — the three stages are wildly unequal, and the effort should
be allocated accordingly:

| Stage | Error magnitude | Evidence |
|---|---|---|
| **1. Parse text → (qty, unit, food)** | **~2-4% sentence error** | 95.62% sentence / 98.26% word, n>81k. **Effectively solved, off the shelf, MIT.** |
| **2. Match string → record** | **0% to >100%** | 71.6% correct against USDA. FNDDS onion raw 38 vs cooked-fat-added 73 kcal (+92%); sodium 1 vs 147 mg (**147×**). Cross-database raw onion disagrees 22% on protein. |
| **3. Convert volume/count → grams** | **±30-40% routinely, 10× at worst** | cup chopped 160 g vs sliced 115 g (39%); onion small 70 vs large 150 g (114%); flour 120→160 g (33%); QNS 15 g vs whole 148 g (**10×**). |
| **4. Raw ingredients → cooked dish** | **−10% to −51% energy, −20% to −62% fat** | Cooked-vs-raw meat codes; systematic and non-cancelling. |

**Stage 1 is solved and cheap. Stages 2-4 hold all the error, and stage 3 is where every
open-source project has stalled** — Tandoor #4415, Mealie #109/#4357, Grocy #177/#1132/#1752 all
describe the identical wall.

The honest one-line framing: **the hard part of recipe nutrition is not natural language. It is that
"1 cup of onion" is not a well-defined quantity of matter — and USDA explicitly disclaims its own
portion data as a density source.**

---

## Recommended pipeline with explicit confidence tiers

The design principle follows directly from the user's constraint — *an estimate presented as a
measurement is worse than nothing.* So the pipeline's job is **not** to maximise accuracy. It is to
**know which tier each number is in and never let a number drift upward into a tier it did not
earn.**

### The pipeline

```
ingredient line
   │
   ├─ 1. PARSE          `ingredient-parser-nlp` (MIT, CRF, 95.6% sentence-level). LLM only as
   │                    fallback on parser failure — NOT as the primary path.
   │                    → qty, quantity_max, unit, size, name(s), prep, comment
   │                    → it already emits RANGE / multiple names / preserved comments, which is
   │                      exactly the metadata tiers C and D need
   │
   ├─ 2. NORMALISE      strip prep words that don't change identity (diced, chopped, minced)
   │                    keep the ones that DO (roasted, cooked, dried, canned, raw)
   │
   ├─ 3. MATCH          search a LOCAL bundled index, restricted to
   │                    SR Legacy (raw base) + FNDDS (prepared) + Foundation (override).
   │                    NEVER Branded by default — it is 97% of the DB and outranks real food.
   │                    → prefer "raw" / "as ingredient" records; actively DEPRIORITISE
   │                      FNDDS "cooked, fat added" and "cooked, no added fat" for ingredient
   │                      lines (they double-count fat and carry phantom survey sodium)
   │                    → keep the top-N, and record which descriptors were dropped
   │
   ├─ 4. QUANTIFY       resolve qty+unit to grams via foodPortions:
   │                    a) exact unit match on the matched record        → highest confidence
   │                    b) portion from a sibling record (SR Legacy)     → degraded
   │                    c) FAO/INFOODS density (liquids) or generic table→ degraded further
   │                    d) LLM estimate                                  → lowest
   │                    NEVER take foodPortions[0] — 24% of FNDDS rows are portion code
   │                    90000 "Quantity not specified" and it often sorts first (15 g vs 148 g).
   │                    Parse `modifier` PER DATA TYPE — it is prose in SR Legacy and a
   │                    numeric foreign key in FNDDS.
   │
   ├─ 5. AGGREGATE      sum, and propagate the WORST tier in the recipe to the total
   │
   └─ 6. LABEL          render every number with its tier. Always. No exceptions.
```

Three rules that matter more than the rest:

- **Never trust a matcher's confidence score.** This is the empirical finding from Part B: matchers
  report ~1.0 while inventing specificity. Confidence must be derived from **structural evidence we
  can check ourselves** — did the parsed unit match an actual `foodPortion` on the matched record?
  did the match preserve every descriptor in the parsed name (`yellow`, `unsalted`)? was the record
  in the allowed data types? A dropped descriptor is an automatic demotion, regardless of score.

- **Tier propagation is pessimistic.** A recipe total is only as trustworthy as its worst
  ingredient. One `salt to taste` is harmless; one `1 lb meat, your choice` poisons the total and
  the total must say so. Do not average confidence — take the minimum.
- **Never silently fall back.** Every degradation step (b, c, d above) must be recorded on the
  number, not swallowed. A silent fallback is exactly how an estimate becomes a "measurement."

### Confidence tiers

These are the visual/semantic contract. Four tiers, deliberately few enough to be legible at a
glance.

| Tier | Name | Criteria | Realistic error | Rendering |
|---|---|---|---|---|
| **A** | **Measured** | Explicit mass/volume in the line (`250 g flour`, `2 tbsp olive oil`) **and** an unambiguous match to a Foundation/SR Legacy/FNDDS record **and** an exact `foodPortion` unit match | **±5-10%** | Plain number. The only tier allowed to look like a fact. |
| **B** | **Derived** | Good record match, but grams came from a count/size portion (`1 large` → 150 g) or a volume→mass conversion | **±15-30%** | Number **plus explicit ± range**, marked as derived |
| **C** | **Estimated** | No confident record match, or an LLM-supplied gram weight, or a compound/prepared item decomposed by the model | **±30-50%+** | **Range only, never a point value.** Visually distinct (different colour/prefix). Must read as a guess. |
| **D** | **Unquantified** | `to taste`, `for serving`, `1 lb meat of your choice`, unparseable, or a range the author left open | Not computable | **No number at all.** Listed as excluded, with a reason. |

Tier D existing at all is the honest part. The temptation is to make everything a number; refusing
to is what separates this from the tools that quietly guess.

Additional labelling requirements:

- **Cooked dishes carry a standing caveat.** Per Stage 4, any total summed from raw ingredients and
  presented as a cooked dish should be capped at **Tier B at best**, and should say that cooking
  losses/gains are not modelled. Given the −10% to −51% energy swing measured for meats, a raw-sum
  total for a roast or a fry is arguably Tier C regardless of how clean the individual matches were.
- **Show the matched record.** Every Tier A/B number should be traceable to an `fdcId` and its
  description, so a user can see we matched `Onions, raw` when they wrote `yellow onion` and
  disagree if they want. Provenance means *inspectable*, not just *badged*.
- **LLM numbers never render identically to USDA numbers.** This is the hard requirement from the
  ticket, and it should be enforced at the type level — make it impossible to construct a rendered
  nutrition value without a provenance tag attached, rather than relying on call sites to remember.

### What this implies for "targets"

A daily/weekly target compared against Tier A/B data is defensible. The same target compared
against a plate of Tier C numbers is a number generator with a progress bar. So:

- Targets should be evaluated **against the tier-aware total**, and the UI should show target
  progress with the same uncertainty the underlying data has — a band, not a point.
- If a day's log is majority Tier C, the honest display is "we can't tell you whether you hit this"
  rather than a filled progress ring.
- **Relative comparisons are far more defensible than absolute ones.** "This version of the recipe
  has ~30% less fat than the last one" survives systematic error that "this recipe has 612 kcal"
  does not, because the biases largely cancel between two variants of the same dish.

---

## Verdict: are targets meaningful, or theatre?

**Both, depending entirely on what the target is asked to do. Stated plainly:**

**Targets as precise measurement instruments — "you consumed 1,847 kcal today, 153 to go" — are
theatre.** The evidence is not close:

- The best USDA-specific matcher: **94.49% coverage, 71.6% correct** — confidently wrong ~28% of
  the time, and **match confidences are not calibrated** (verified: 1.0 confidence on
  `butter` → `unsalted stick`).
- The best LLM on a purpose-built benchmark is within 7.5 g of carbohydrate **only 67%** of the time.
- **Three professional, commercially maintained nutrition packages, given the same 12 recipes,
  disagree with each other by up to 101 kcal (~35%) on energy and 36% on salt.** There is no
  consensus ground truth to converge on.
- USDA's own table: `1 cup chopped` = 160 g, `1 cup sliced` = 115 g — **39% apart for the same
  food**. A "large" onion is 114% heavier than a "small" one.
- **USDA explicitly disclaims its portion data as a density source.**
- Raw-vs-cooked codes misstate energy by 10-51% and fat by 20-62%.
- Sodium and micronutrients are simply not recoverable: −51% sodium, −77% cholesterol, iron
  correlation ≈ 0 in shipping consumer apps.

Presenting a four-significant-figure daily total on top of that stack is precisely the "estimate
presented as a measurement" the user warned against, and no engineering in this plugin changes it —
the uncertainty is contributed by the recipe text and by human cooking, upstream of anything we
control.

**Corollary for how we evaluate ourselves:** MyFitnessPal's energy agreement on whole foods was
**mean 8.35 kcal with SD 133.31**. A trivial mean concealing a huge spread is the *signature* of a
matching problem. If we ever benchmark this plugin, **report the distribution, never the mean** — a
mean-error metric here will look superb and tell us nothing.

**Targets as directional instruments — trend over weeks, relative comparison between recipe
variants, catching a 2× error rather than a 10% one — are genuinely meaningful.** Systematic bias
that ruins an absolute number largely cancels in a comparison, and a ±25% signal is still more than
enough to distinguish "this week was much heavier than last" or "swapping cream for yoghurt cut the
fat substantially." That is real, usable value.

**So the deliverable is not accuracy — it is calibrated honesty.** The tiering above is the actual
product. A Tier A number is worth showing as a number; a Tier C number is worth showing only as a
range that visibly refuses to be a measurement; a Tier D ingredient is worth showing as "we don't
know." A tool that does this is more useful than every mainstream calorie tracker, not because its
numbers are better — they are not — but because its numbers do not lie about what they are.

**One thing to resist:** the pressure to make Tier C look like Tier A because a UI full of ranges
and "unknown" feels unpolished. That pressure is exactly the failure mode the user identified. If
the plugin ships one rule, it should be that **provenance is not removable** — the number and its
tier are the same object, and there is no code path that renders one without the other.

Worth noting where that puts us: **Cronometer, the most accurate consumer nutrition tool, is the one
that punts hardest to manual selection.** Every open-source recipe manager surveyed reached the same
conclusion independently and stopped. We are not proposing to beat them on accuracy — we cannot.
We are proposing to be the one that *says so per number*, which none of them do.

---

## Sources

**USDA primary** — [FoodData Central](https://fdc.nal.usda.gov/) ·
[API guide](http://fdc.nal.usda.gov/api-guide/) ·
[API key signup](http://fdc.nal.usda.gov/api-key-signup/) ·
[Data documentation](http://fdc.nal.usda.gov/data-documentation/) ·
[Download datasets](http://fdc.nal.usda.gov/download-datasets/) ·
[Update log](http://fdc.nal.usda.gov/log/) ·
[OpenAPI spec](https://fdc.nal.usda.gov/api-spec/fdc_api.yaml) ·
[FNDDS 2021-2023 documentation (PDF)](https://www.ars.usda.gov/ARSUserFiles/80400530/pdf/fndds/2021_2023_FNDDS_Doc.pdf) ·
[SR28 documentation (PDF)](https://www.ars.usda.gov/arsuserfiles/80400525/data/sr/sr28/sr28_doc.pdf) ·
[Table of Cooking Yields for Meat & Poultry, Release 2 (PDF)](https://www.ars.usda.gov/ARSUserFiles/80400535/Data/retn/USDA_CookingYields_MeatPoultry02.pdf)

**Reference data** — [21 CFR 101.12 (RACC)](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-101/subpart-A/section-101.12) ·
[FAO/INFOODS Density Database v2.0 (PDF)](https://www.fao.org/fileadmin/templates/food_composition/documents/density_DB_v2_0_01.pdf) ·
[King Arthur Baking: how to measure flour](https://www.kingarthurbaking.com/blog/2023/10/13/how-to-measure-flour)

**Parsers & matchers** — [strangetom/ingredient-parser](https://github.com/strangetom/ingredient-parser) ·
[NYT ingredient-phrase-tagger](https://github.com/nytimes/ingredient-phrase-tagger) (archived) ·
[recipe-scrapers](https://github.com/hhursev/recipe-scrapers) ·
[Zestful](https://zestfuldata.com/) ·
[mtlynch: resurrecting the NYT tagger](https://mtlynch.io/resurrecting-1/)

**Papers** — NutriBench [arXiv:2407.12843](https://arxiv.org/html/2407.12843v2) ·
USDA FDC matching [arXiv:2004.12286](https://arxiv.org/abs/2004.12286) ·
UCL ingredient parser [arXiv:2210.02535](https://arxiv.org/abs/2210.02535) ·
FoodSEM [arXiv:2509.22125](https://arxiv.org/abs/2509.22125) ·
FoodOntoRAG [arXiv:2603.09758](https://arxiv.org/abs/2603.09758) ·
FoodNER [JMIR 2021 (10.2196/28229)](https://doi.org/10.2196/28229) ·
[Cooked meat codes in recipe databases, PMC12688007](https://pmc.ncbi.nlm.nih.gov/articles/PMC12688007/)

**Validation studies** — [MyFitnessPal validation, JMIR 2020;22(10):e18237](https://www.jmir.org/2020/10/e18237/) ·
[Fallaize et al., JMIR Mhealth 2019;7(2):e9838](https://pmc.ncbi.nlm.nih.gov/articles/PMC6401676/) ·
[Griffiths et al., Public Health Nutr 2018;21(8):1495](https://pubmed.ncbi.nlm.nih.gov/30785409/) ·
[JAND 2022 comparative validity](https://www.sciencedirect.com/science/article/abs/pii/S2212267221013824) ·
[Recipe software comparison, Nutrition & Food Science 2026;56(3):612](https://www.emerald.com/nfs/article/56/3/612/1344359/Comparing-recipe-nutrient-calculations-across)

**Ecosystem evidence** — [Tandoor #4415](https://github.com/TandoorRecipes/recipes/issues/4415) ·
[Mealie #109](https://github.com/hay-kot/mealie/issues/109) ·
[Mealie ingredient parser guide](https://docs.mealie.io/contributors/guides/ingredient-parser/) ·
[grocy-nutrients](https://github.com/yura1106/grocy-nutrients/blob/main/RECIPE_NUTRIENTS.md) ·
[OFF recipe-estimator](https://github.com/openfoodfacts/recipe-estimator/blob/main/docs/HOW_IT_WORKS.md) ·
[openfoodfacts-server #2997](https://github.com/openfoodfacts/openfoodfacts-server/issues/2997) ·
[Nutritionix v2/natural](https://github.com/nutritionix/api-documentation/blob/master/v2/natural.md) ·
[Edamam Nutrition Analysis](https://developer.edamam.com/edamam-docs-nutrition-api)

> **Excluded deliberately.** Several widely-circulated figures were traced to AI-generated SEO
> domains with fabricated citations and are **not** used in this document: a claimed "~85% accuracy"
> for Nutritionix; "37% of MyFitnessPal entries had energy errors >20% (2024 study)"; "a 2019
> *Nutrition Journal* analysis found errors in 27% of entries"; "a 2023 *Journal of Food
> Engineering* study" on scale drift; and consumer claims that a large onion weighs 170-340 g.
> Two genuine reproducibility failures also inform the standard applied here: a published 0.95 F1
> that reproduced at **0.61**, and a 2025 paper whose abstract claims ROUGE-L 0.9722 while its body
> reports 0.8209. **Rule adopted: cite only numbers traceable to a run someone actually executed.**

</content>
