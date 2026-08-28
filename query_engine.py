"""
OrgMind @ SMART — CAMP Query Engine v5.1
==========================================
New in v5.1:
  - Follow-up conversational queries. Callers may pass conversation_history
    (a list of {"question", "answer"} dicts for prior turns in the same
    session). Two things happen with it:
      1. Retrieval: the current question is combined with the most recent
         prior question when searching Chroma, so short follow-ups like
         "what about for MTA instead?" retrieve sensibly even though the
         question alone has little to search on.
      2. Generation: prior turns are sent to Claude as compact Human/AI
         message pairs (question text + final answer text only) -- NOT
         their retrieved chunk context. This keeps multi-turn conversations
         cheap and bounded; only the CURRENT turn's retrieval is sent as
         full document context.

Carried over from v5.0:
  - Retrieval depth (k) substantially increased (1M-token context window)
  - System prompt caching enabled
  - camp_general capped as a supplementary collection to avoid flooding
    out the department actually being queried

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
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

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

# ── Follow-up conversation settings ───────────────────────────────────────
# How many prior turns to keep, even if the caller passes more. Keeps
# per-request size bounded and predictable regardless of how long a
# session has been running.
MAX_HISTORY_TURNS = 6

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
6. If the person asks a follow-up question, use the prior conversation
   to understand what they mean (e.g. "what about for MTA instead"), but
   still answer ONLY from the document context provided for THIS turn.
7. CRITICAL — do not supplement missing information with your own general
   knowledge, even if it is factually true and seems helpful. This
   includes geographic reasoning, suggesting alternatives, filling gaps
   with common sense, or naming anything not explicitly present in the
   provided documents. If the documents do not contain the answer, stop
   after saying so. Do not add "you may wish to consider..." or similar
   suggestions based on outside knowledge — a plausible-sounding
   suggestion that isn't verified against CAMP's actual records is worse
   than no suggestion, because the person may act on it believing it
   came from the same verified source as the rest of the answer.
8. If genuinely not present say:
   "I could not find this in the CAMP knowledge base.
   Tip: Try rephrasing with different keywords, or ask your
   administrator to add the relevant document."
   Then STOP. Do not add anything after this beyond the tip already given.
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


def _build_retrieval_query(question, conversation_history):
    """
    For a fresh question, retrieval uses the question alone (unchanged
    behaviour). For a follow-up, short questions like "what about for MTA
    instead?" retrieve poorly on their own -- so the most recent prior
    question is prepended to give the embedding search something concrete
    to match against.
    """
    if not conversation_history:
        return question
    last_turn = conversation_history[-1]
    last_question = last_turn.get("question", "")
    if not last_question:
        return question
    return f"{last_question}\n{question}"


def query(question, department="All (Search Everything)",
          doc_type_filter=None, legal_unlocked=False,
          k=None, is_synthesis=None, conversation_history=None):

    # Allow explicit override; otherwise infer from question text as before,
    # falling back to the new, much larger defaults.
    if is_synthesis is None:
        is_synthesis = "RESEARCH SYNTHESIS" in question
    if k is None:
        k = SYNTHESIS_K if is_synthesis else DEFAULT_K

    conversation_history = (conversation_history or [])[-MAX_HISTORY_TURNS:]
    retrieval_query = _build_retrieval_query(question, conversation_history)

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    collections = get_collections(department, legal_unlocked)

    # camp_general is attached to almost every department as supplementary
    # context. At small k this was harmless; at large k it can flood out
    # the collection the query is actually about (e.g. a Research query
    # pulling in dozens of Risk Assessment SOPs). So: the collection(s)
    # that ARE the department get the full k; camp_general, when it's
    # riding along as a supplement rather than being the actual target,
    # is capped to a small fixed quota instead.
    #
    # NOTE: comparing raw similarity distance across different Chroma
    # collections is not reliable (different content profiles can skew
    # what counts as "close"), so collections are queried independently
    # and simply concatenated -- not globally re-ranked against each
    # other.
    GENERAL_SUPPLEMENT_K = 15
    is_general_the_actual_target = (department == "General CAMP")

    all_docs = []
    for coll in collections:
        try:
            vs = Chroma(
                collection_name=coll,
                persist_directory=CHROMA_PATH,
                embedding_function=embeddings
            )
            coll_k = k
            if coll == "camp_general" and not is_general_the_actual_target:
                coll_k = GENERAL_SUPPLEMENT_K

            docs = vs.similarity_search(retrieval_query, k=coll_k)
            if doc_type_filter:
                keywords = AGREEMENT_TYPE_KEYWORDS.get(
                    doc_type_filter.upper(), [])
                if keywords:
                    filtered = [
                        d for d in docs if any(
                            kw.upper() in
                            d.metadata.get("source", "").upper()
                            for kw in keywords)
                    ]
                    docs = filtered if filtered else docs
            all_docs.extend(docs)
        except Exception:
            pass

    if not all_docs:
        return {
            "answer": (
                f"I could not find relevant documents for this query "
                f"in the {department} knowledge base. "
                "Please ensure documents have been loaded."
            ),
            "sources": [], "chunks_used": 0
        }

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
    #
    # Prior turns are included as plain Human/AI message pairs -- question
    # and final answer text only. Their original retrieved chunk context
    # is deliberately NOT replayed here; only the CURRENT turn carries a
    # full document context block. This keeps a long conversation's token
    # cost roughly constant per turn rather than growing every turn.
    history_messages = []
    for turn in conversation_history:
        q = turn.get("question", "")
        a = turn.get("answer", "")
        if q:
            history_messages.append(HumanMessage(content=q))
        if a:
            history_messages.append(AIMessage(content=a))

    human_content = QUERY_TEMPLATE.format(question=question, context=context)
    messages = (
        [_cached_system_message()]
        + history_messages
        + [{"role": "user", "content": human_content}]
    )
    response = llm.invoke(messages)

    return {
        "answer": response.content,
        "sources": list(set(
            d.metadata.get("source", "") for d in all_docs)),
        "chunks_used": len(all_docs),
        "k_used": k,
    }

