# Financial Evidence Vectorization Strategy

Last reviewed: 2026-08-15

## Decision summary

The retrieval system must not treat every source as plain text and must not
bind evidence chunks to one embedding provider. The target design is:

1. preserve a canonical, source-linked document and its structural elements;
2. create source-aware child chunks that retain document, section, period,
   table-header, unit, page, and ticker context;
3. store embeddings separately from chunks, keyed by a versioned embedding
   profile;
4. retrieve with metadata filters plus lexical and dense search, then rerank;
5. answer numerical questions from structured facts or tables, not from vector
   similarity alone; and
6. evaluate every model/dimension choice on a fixed finance question set before
   making it the default.

The recommended first production baseline is a 1,024-dimensional multilingual
profile, such as `BAAI/bge-m3` locally or Alibaba `text-embedding-v4` through an
API. Gemini should be tested at 768 and 1,536 dimensions. This is a starting
point for evaluation, not a claim that 1,024 dimensions is universally best.

## What the project has today

`evidence_chunks.embedding` is currently `vector(1536)`. The value is produced
by the SQL function `local_text_embedding`, which lowercases text, hashes words
into 1,536 buckets, and stores bucket counts. It is deterministic and useful for
offline integration tests, but it is not a learned semantic embedding model.

Consequences:

- the current retrieval proves the storage/RPC/fallback path;
- it should be named and reported as `local-hash-v1`, not as an OpenAI-style
  embedding merely because both happen to use 1,536 dimensions;
- its similarity scores are not comparable with Gemini, Qwen, BGE, OpenAI, or
  any other model; and
- changing the number of hash buckets would not turn it into a stronger
  semantic model.

## Source-aware ingestion

### News

News is mostly prose, but fixed-size splitting alone still loses event context.
Use this hierarchy:

- parent: one article, with ticker, company, source, URL, author, publication
  time, ingestion time, language, and content hash;
- children: headline/standfirst and paragraph groups, normally 250–450 tokens;
- overlap: one paragraph or roughly 10–15%, only when a boundary would split a
  continuing idea;
- embedding text: a short deterministic context header followed by the child,
  for example `NVDA | news | 2026-08-15 | Earnings guidance | ...`;
- deduplication: canonical URL plus normalized-content hash, not feed position;
- updates: keep a document version when an article materially changes.

Most short RSS descriptions remain a single child. Full articles should be
split on paragraph/heading boundaries before applying a token limit.

### Filing narrative

SEC filings should follow the filing hierarchy rather than arbitrary word
windows:

- parent: filing accession and form;
- section parent: `Item 1A Risk Factors`, `Item 7 MD&A`, note, or accounting
  policy;
- child: heading-aware paragraph group, normally 350–650 tokens;
- repeated context: ticker, form, accession, reporting period, filing date,
  section path, and page/location;
- citations: retain accession URL and the exact source location for every
  returned chunk.

Small-to-big retrieval searches children but returns the child together with
its section parent. This keeps recall from small chunks while giving the judge
enough surrounding language to interpret references such as “the quarter” or
“these risks.” Contextual Retrieval research supports prepending concise
document context to otherwise ambiguous chunks, while parent-child retrieval
keeps that generated context auditable.

### Financial tables

A table must never be flattened into a stream of numbers without its headers.
The canonical representation should preserve:

- table title and statement/note name;
- row and column headers, including multi-level and merged headers;
- period, currency, scale (`USD`, `USD millions`, shares), sign, and units;
- cell values as both original text and parsed numeric values;
- footnotes and accounting-policy references;
- filing accession, page, bounding box, and parser/version provenance.

Create three complementary representations:

1. **Structured facts:** normalized rows/cells in PostgreSQL for filtering,
   aggregation, comparison, and arithmetic. SEC XBRL `companyfacts` is preferred
   for standard US-GAAP/IFRS facts because the SEC supplies taxonomy, units, and
   reporting contexts.
2. **Retrieval text:** a table summary and row groups rendered with the full
   header path repeated in every chunk. Example: `Consolidated statements of
   operations; USD millions; FY2025; Revenue = 12,345`.
3. **Original structure:** Markdown/HTML/JSON plus page/bounding-box references
   so the model and user can inspect the complete table and its footnotes.

Retrieve the table or row group by vectors/keywords, but perform arithmetic on
the structured values. The TAT-QA and FinQA benchmarks both show that financial
questions commonly require selecting relevant table cells and then executing
symbolic operations; semantic similarity is only the retrieval step.

For native PDFs or images, use a layout-aware parser with table-structure and
OCR support. Docling is the first open-source candidate because its document
model retains hierarchy, tables, pictures, and source locations. Parser output
must be quality-scored; low-confidence or malformed tables are quarantined for
review rather than silently embedded.

### Charts and images

Text embeddings cannot directly represent a chart image. Store the original
image/page, OCR text, a vision-generated description, detected chart type,
legend/axis labels, units, and any extracted series as separate artifacts.
Embed the description for discovery, retain structured series for calculations,
and use a separate multimodal embedding profile only when image-to-text or
image-to-image retrieval is an explicit requirement.

## Embedding profiles and dimensions

| Candidate | Native/flexible dimensions | Role in this project |
| --- | --- | --- |
| `local-hash-v1` | 1,536 fixed | Deterministic offline plumbing test only. |
| Gemini Embedding | 128–3,072; Google recommends 768, 1,536, or 3,072 | Cloud A/B candidate; test 768 and 1,536. Gemini Embedding 2 can also represent images, video, audio, and PDFs. |
| Alibaba `text-embedding-v4` | 64–2,048; default 1,024 | Chinese/English API baseline at 1,024. |
| Qwen3-Embedding | 1,024 / 2,560 / 4,096 by model size; MRL supports custom output dimensions | Local or hosted experiment; start with the 0.6B 1,024-dimensional model. |
| `BAAI/bge-m3` | 1,024 fixed dense vector, plus sparse and multi-vector modes | Free multilingual local baseline and future hybrid-retrieval candidate. |

Dimension is a model output contract, not a database-wide quality setting.
Larger vectors cost more storage and search time, but are not automatically
better on this corpus. Matryoshka Representation Learning permits supported
models to use useful prefixes of a vector; truncation must be requested from or
documented by the model provider, followed by normalization when required.

pgvector can store mixed dimensions in an unconstrained `vector` column, but an
approximate index can cover only rows of one dimension. The database should
therefore store a profile ID alongside every vector and create a partial
expression HNSW index for each production profile. Supabase currently documents
HNSW/IVFFlat index limits of 2,000 dimensions for `vector` and 4,000 for
`halfvec`. Consequently:

- 768, 1,024, and 1,536 profiles fit ordinary `vector` indexes;
- a native 3,072-dimensional Gemini or 4,096-dimensional Qwen vector requires
  `halfvec`, a supported reduced dimension, subvector/binary indexing, or a
  different vector service;
- use HNSW for the first production profile; the current six-row corpus does
  not need approximate indexing yet;
- never compare a query vector with stored rows from a different profile, even
  if their dimensions match; and
- re-embed from canonical chunks when the model, dimension, instruction,
  normalization, or preprocessing version changes.

## Target data model

`evidence_documents`

- canonical source, stable external ID, version/content hash, ticker, dates,
  language, parser status, and raw/structured artifact references.

`evidence_chunks`

- immutable retrieval unit;
- `parent_chunk_id`, `chunk_kind`, `section_path`, `token_count`, `content_hash`;
- page/bounding-box/table/row metadata and the exact text shown to the model;
- no provider-specific vector as the source of truth.

`embedding_profiles`

- stable slug, provider, model, dimensions, distance metric, normalization,
  query/document instructions, modality, and preprocessing version;
- lifecycle state: test, active, retired.

`chunk_embeddings`

- unique `(chunk_id, profile_id)` row;
- unconstrained `vector` plus a dimension-validation trigger;
- generation timestamp and input hash for stale-vector detection;
- partial HNSW index for each active profile.

This allows the same chunk to carry Gemini 768, Qwen 1,024, and another test
profile simultaneously without overwriting data or mixing vector spaces.

## Retrieval pipeline

1. classify the question as narrative, exact fact, comparison/arithmetic, or
   multimodal;
2. filter by ticker, reporting period, source type, language, and active profile;
3. run dense retrieval and lexical search in parallel;
4. fuse rankings with Reciprocal Rank Fusion;
5. rerank a bounded candidate set with a multilingual reranker;
6. expand selected children to their parent section/table and attach footnotes;
7. for numerical questions, query structured facts and execute calculations;
8. return answer claims with document, page/section/table, URL, and retrieval
   profile provenance.

Dense-only retrieval is not sufficient for tickers, accounting tags, dates,
exact figures, or unusual product names. pgvector itself documents hybrid
search using full-text search plus rank fusion or a cross-encoder.

## Evaluation before choosing a default

Create a versioned benchmark of at least 60 questions:

- 20 news/event questions, including paraphrases and exact names;
- 20 filing narrative questions across Risk Factors and MD&A;
- 15 table/fact questions requiring periods, units, and arithmetic;
- 5 negative or unanswerable questions.

Every question needs gold document/chunk IDs and, for numeric questions, gold
cells and calculation steps. Report:

- Recall@5 and Recall@10;
- MRR or nDCG@10;
- citation precision and answer faithfulness;
- numeric exact match with unit/period correctness;
- p50/p95 latency, embedding cost, index size, and ingestion throughput.

Run the same corpus and queries for each `(model, dimension, instruction,
chunker)` profile. Public leaderboards such as MTEB help shortlist models, but
the project decision must come from this finance-specific evaluation. The first
experiment matrix should be BGE-M3 1,024, Qwen/DashScope 1,024, Gemini 768, and
Gemini 1,536, followed by hybrid retrieval and reranking ablations.

## Implementation sequence

1. Add profile-separated storage while retaining `local-hash-v1` compatibility.
2. Add typed, contextual chunks and parent references for news and filing text.
3. Add lexical retrieval and a small gold evaluation set.
4. Add one real semantic profile and compare it with the local hash baseline.
5. Add SEC XBRL structured facts and table-aware retrieval.
6. Pilot Docling on filings that cannot be represented adequately by XBRL/HTML.
7. Add multimodal chart retrieval only after text/table evaluation shows a need.

## Presentation-ready points

- “We separated documents, retrieval chunks, and model-specific vectors, so an
  API-key or embedding-model change does not corrupt the evidence layer.”
- “The existing 1,536-dimensional vector is a deterministic hash baseline,
  explicitly retained for offline tests rather than misrepresented as AI.”
- “Narrative text, tables, and charts follow different ingestion paths; tables
  keep row/column/period/unit relationships and calculations run on structured
  values.”
- “We use child chunks for recall and parent sections for interpretation, then
  combine dense, lexical, metadata, and reranking signals.”
- “Dimension is selected by measured retrieval quality, cost, and pgvector index
  constraints—not by assuming more dimensions means more intelligence.”

## Sources

Primary and official references:

- [pgvector README: mixed dimensions, partial indexes, hybrid search, and index limits](https://github.com/pgvector/pgvector/blob/master/README.md)
- [Supabase vector columns](https://supabase.com/docs/guides/ai/vector-columns)
- [Supabase vector indexes](https://supabase.com/docs/guides/ai/vector-indexes)
- [Google Gemini Embeddings](https://ai.google.dev/gemini-api/docs/embeddings)
- [Alibaba Cloud Model Studio embedding and reranking models](https://help.aliyun.com/zh/model-studio/embedding-rerank-model/)
- [Qwen3-Embedding repository](https://github.com/QwenLM/Qwen3-Embedding)
- [FlagEmbedding / BGE-M3](https://github.com/FlagOpen/FlagEmbedding)
- [SEC EDGAR data APIs and XBRL company facts](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [Docling structured document parsing](https://github.com/docling-project/docling)
- [Anthropic Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)
- [Matryoshka Representation Learning](https://arxiv.org/abs/2205.13147)
- [Late Chunking](https://arxiv.org/abs/2409.04701)
- [TAT-QA](https://arxiv.org/abs/2105.07624)
- [FinQA](https://arxiv.org/abs/2109.00122)
- [MTEB evaluation repository](https://github.com/embeddings-benchmark/mteb)

Community evidence was used as a warning signal rather than a specification:
practitioners repeatedly report that naive word chunking and flattened PDF
tables lose header/cell relationships. See the discussions on
[hierarchical PDF chunking](https://www.reddit.com/r/LocalLLaMA/comments/1dpb9ow/),
[financial-report chunking](https://www.reddit.com/r/Rag/comments/1mjwde9/), and
[production table handling](https://www.reddit.com/r/Rag/comments/1pv9yup/).
