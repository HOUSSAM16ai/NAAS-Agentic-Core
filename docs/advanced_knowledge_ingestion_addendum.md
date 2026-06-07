# RAG Ingestion Addendum

## Strict Entity Parsing
To ensure the RAG engine does not hallucinate (Bug B: RAG Semantic Blindness), all insertions into `bac_exercises` MUST contain a `parsed_entities` JSON payload matching the structural reality of the text.

**Example for Probability:**
```json
{"container": "كيس", "total_items": 11, "components": [{"entity": "كرة بيضاء", "count": 2}]}
```

**Example for Complex Numbers:**
```json
{"equation": "(z - 1 + 2√3)[z² - 2(1-√3)z + 5 - 2√3] = 0"}
```

Without these entities, the system relies purely on naive vector similarity, which causes cross-contamination between exercises in the same PDF or subject.
