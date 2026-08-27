"""
OrgMind @ SMART — CAMP Query Engine v5.0
==========================================
New in v5.0:
  - Retrieval depth (k) substantially increased, enabled by Claude's
    1M-token context window (Sonnet 4.6 / Sonnet 5). Default queries now
    pull far more of the knowledge base per question, reducing the chance
    that a relevant chunk is missed simply because it fell outside a
    narrow top-16 similarity search.
  - System prompt caching enabled (Anthropic prompt caching) — the
    (static, unchanging) system prompt is now cached server-side,
    cutting its per-query cost by ~10x on repeat calls.
  - k values are now configurable per call rather than hardcoded.

Carried over from v4.3:
  - Research Operations -> Research folder rename
"""

import os
from dotenv import load_dotenv
load_dotenv()

from langchain_anthropic import ChatAnthropic
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage

CHROMA_PATH = "./chroma_db"

# ── Retrieval depth ────────────────────────────────────────────────────────
# With a 1M-token context window, these values are conservative relative to
# what the model can actually hold (250 chunks * ~375 tokens/chunk =~
# 94,000 tokens -- well under the 1M ceiling), while still being a large
# jump up from the original k=16 / k=20. Tune upward if testing shows
# queries still miss relevant chunks; tune downward if cost per query
# becomes a concern before prompt-caching/batching optimisations land.
DEFAULT_K = 150
SYNTHESIS_K = 250

def get_folder_options(legal_unlocked=False):
    base = ["Staff Related", "Research",
            "General CAMP", "All (Search Everything)"]
    if legal_unlocked:
        return ["Legal & Contracts"] + base
    return base

def get_collections(department, legal_unlocked=False):
    base = {
        "Legal & Contracts":      ["camp_legal",       "camp_general"],
        "Staff Related":          ["camp_staff",        "camp_general"],
        "Research":               ["camp_research_ops", "camp_general"],
        "General CAMP":           ["camp_general"],
        "All (Search Everything)":["camp_staff", "camp_research_ops", "camp_general"],
    }
    if legal_unlocked:
        base["All (Search Everything)"] = [
            "camp_legal", "camp_staff",
            "camp_research_ops", "camp_general"
        ]
    return base.get(department, base["All (Search Everything)"])

CAMP_COLLECTIONS = {
    "Legal & Contracts":      ["camp_legal",       "camp_general"],
    "Staff Related":          ["camp_staff",        "camp_general"],
    "Research":               ["camp_research_ops", "camp_general"],
    "General CAMP":           ["camp_general"],
    "All (Search Everything)":["camp_staff", "camp_research_ops", "camp_general"],
}

AGREEMENT_TYPE_KEYWORDS = {
    "RCA": ["RCA", "Research Collaboration"],
    "NDA": ["NDA", "Non-Disclosure"],
    "MTA": ["MTA", "Material Transfer"],
    "LOA": ["LOA", "Letter of Award"],
}

SYSTEM_PROMPT = """You are OrgMind, the institutional memory AI for CAMP
(Critical Analytics for Manufacturing Personalised Medicine) at SMART
(Singapore-MIT Alliance for Research and Technology Centre).

Rules:
1. Search ALL provided context carefully before saying answer is unavailable.
2. ONLY answer from the documents provided. Never invent or guess.
3. CITE your source — exact filename for every factual claim.
4. Reason about SPIRIT and INTENT, not just literal wording.
5. Classify as STANDARD | WATCH | CRITICAL when comparing practice.
6. If genuinely not present say:
   "I could not find this in the CAMP knowledge base.
   Tip: Try rephrasing with different keywords, or ask your
   administrator to add the relevant document."
"""

QUERY_TEMPLATE = """A CAMP staff member asks:

{question}

Relevant content from CAMP's institutional documents:
{context}

Answer based only on the documents above.
End with: Sources consulted: [list filenames used]"""


def _cached_system_message():
    """
    Builds the system message as a content-block list with Anthropic
    prompt caching enabled (cache_control: ephemeral). The system prompt
    is identical on every call, so caching it means Claude only pays full
    price to process it once per cache window (~5 min rolling), and gets
    a ~10x cheaper cache-read on every call after that.
    """
    return SystemMessage(content=[
        {
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ])


def query(question, department="All (Search Everything)",
          doc_type_filter=None, legal_unlocked=False,
          k=None, is_synthesis=None):

    # Allow explicit override; otherwise infer from question text as before,
    # falling back to the new, much larger defaults.
    if is_synthesis is None:
        is_synthesis = "RESEARCH SYNTHESIS" in question
    if k is None:
        k = SYNTHESIS_K if is_synthesis else DEFAULT_K

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    collections = get_collections(department, legal_unlocked)

    # Pull a generous candidate pool from EACH collection (so we don't miss
    # anything genuinely relevant that happens to sit in a smaller
    # collection), but keep the (doc, distance) score so we can rank
    # everything together afterwards. Lower distance = more relevant.
    CANDIDATE_POOL_PER_COLLECTION = max(k, 100)

    scored_candidates = []
    for coll in collections:
        try:
            vs = Chroma(
                collection_name=coll,
                persist_directory=CHROMA_PATH,
                embedding_function=embeddings
            )
            scored = vs.similarity_search_with_score(
                question, k=CANDIDATE_POOL_PER_COLLECTION)
            if doc_type_filter:
                keywords = AGREEMENT_TYPE_KEYWORDS.get(
                    doc_type_filter.upper(), [])
                if keywords:
                    filtered = [
                        (d, dist) for d, dist in scored if any(
                            kw.upper() in
                            d.metadata.get("source", "").upper()
                            for kw in keywords)
                    ]
                    scored = filtered if filtered else scored
            scored_candidates.extend(scored)
        except Exception:
            pass

    if not scored_candidates:
        return {
            "answer": (
                f"I could not find relevant documents for this query "
                f"in the {department} knowledge base. "
                "Please ensure documents have been loaded."
            ),
            "sources": [], "chunks_used": 0
        }

    # Rank ALL candidates together across collections (lower distance =
    # more relevant) and keep only the true top-k overall. This is the
    # fix for "camp_general SOPs flooding in": a collection contributing
    # only weak matches will simply rank low and get trimmed out here,
    # rather than automatically supplying its full k-sized quota.
    scored_candidates.sort(key=lambda pair: pair[1])
    top = scored_candidates[:k]
    all_docs = [doc for doc, _dist in top]

    context = "\n\n---\n\n".join(
        f"[Source: {d.metadata.get('source', 'unknown')}]\n{d.page_content}"
        for d in all_docs
    )

    llm = ChatAnthropic(
        model="claude-sonnet-4-6",
        max_tokens=4000
    )

    # Built directly (rather than via ChatPromptTemplate) so the system
    # message can carry the cache_control block -- ChatPromptTemplate's
    # simple ("system", str) tuple form does not expose this.
    human_content = QUERY_TEMPLATE.format(question=question, context=context)
    messages = [
        _cached_system_message(),
        {"role": "user", "content": human_content},
    ]
    response = llm.invoke(messages)

    return {
        "answer": response.content,
        "sources": list(set(
            d.metadata.get("source", "") for d in all_docs)),
        "chunks_used": len(all_docs),
        "k_used": k,
        "weakest_relevance_distance": top[-1][1] if top else None,
    }
