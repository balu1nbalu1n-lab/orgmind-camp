"""
OrgMind @ SMART — CAMP Query Engine v4.1
"""

import os
from dotenv import load_dotenv
load_dotenv()

import os as _os

def _read_config(key):
    """Read value from config.txt (for passwords) or environment (for API keys)."""
    # Try config.txt first
    config_paths = [
        "/app/config.txt",
        "./config.txt",
        "/mount/src/orgmind-camp/config.txt"
    ]
    for path in config_paths:
        if _os.path.exists(path):
            try:
                with open(path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith(key + "="):
                            val = line.split("=", 1)[1].strip()
                            if val and not val.startswith("replace_with"):
                                return val
            except Exception:
                pass
    # Fall back to environment variable
    return _os.environ.get(key, "")

# Load API keys into environment if not already set
for _key in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"]:
    _val = _read_config(_key)
    if _val:
        _os.environ[_key] = _val


from langchain_anthropic import ChatAnthropic
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate

CHROMA_PATH = "./chroma_db"

# Collections available per access level
# legal_unlocked=True means user has entered the legal password
def get_collections(department, legal_unlocked=False):
    base = {
        "Legal & Contracts":      ["camp_legal",       "camp_general"],
        "Staff Related":          ["camp_staff",        "camp_general"],
        "Research Operations":    ["camp_research_ops", "camp_general"],
        "General CAMP":           ["camp_general"],
        "All (Search Everything)":["camp_staff", "camp_research_ops", "camp_general"],
    }
    # Add legal to All only if unlocked
    if legal_unlocked:
        base["All (Search Everything)"] = [
            "camp_legal", "camp_staff",
            "camp_research_ops", "camp_general"
        ]
    return base.get(department, base["All (Search Everything)"])

# Folder dropdown options per access level
def get_folder_options(legal_unlocked=False):
    base = ["Staff Related", "Research Operations",
            "General CAMP", "All (Search Everything)"]
    if legal_unlocked:
        return ["Legal & Contracts"] + base
    return base

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


def query(question, department="All (Search Everything)",
          doc_type_filter=None, legal_unlocked=False):

    is_synthesis = "RESEARCH SYNTHESIS" in question
    k_value = 20 if is_synthesis else 12

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    collections = get_collections(department, legal_unlocked)

    all_docs = []
    for coll in collections:
        try:
            vs = Chroma(
                collection_name=coll,
                persist_directory=CHROMA_PATH,
                embedding_function=embeddings
            )
            docs = vs.similarity_search(question, k=k_value)
            if doc_type_filter:
                keywords = AGREEMENT_TYPE_KEYWORDS.get(
                    doc_type_filter.upper(), [])
                if keywords:
                    filtered = [
                        d for d in docs if any(
                            kw.upper() in
                            d.metadata.get("source","").upper()
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
        f"[Source: {d.metadata.get('source','unknown')}]\n{d.page_content}"
        for d in all_docs
    )

    llm = ChatAnthropic(
        model="claude-sonnet-4-20250514",
        max_tokens=4000
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", QUERY_TEMPLATE)
    ])
    response = (prompt | llm).invoke({
        "question": question, "context": context
    })

    return {
        "answer": response.content,
        "sources": list(set(
            d.metadata.get("source","") for d in all_docs)),
        "chunks_used": len(all_docs)
    }
