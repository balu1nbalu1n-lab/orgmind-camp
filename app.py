"""
OrgMind @ SMART — CAMP URL Platform v4.2
Clean environment variable reading for Render deployment.
"""

import streamlit as st
import tempfile
import os
from query_engine import query, get_folder_options, get_collections, CAMP_COLLECTIONS

st.set_page_config(
    page_title="OrgMind — CAMP @ SMART",
    page_icon="🧠", layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-title  { font-size:2.0rem; font-weight:800; color:#1B3A5C; margin-bottom:0; }
    .camp-badge  { font-size:1.0rem; font-weight:700; color:#C9A84C; margin-bottom:0.2rem; }
    .sub-title   { font-size:0.95rem; color:#4A5568; font-style:italic; margin-bottom:0.5rem; }
    .answer-box  { background:#F0F4F8; border-left:4px solid #C9A84C;
                   padding:1.2rem 1.5rem; border-radius:4px; margin:1rem 0; }
    .source-tag  { background:#1B3A5C; color:white; padding:0.2rem 0.6rem;
                   border-radius:3px; font-size:0.8rem; font-family:monospace;
                   margin:0.2rem; display:inline-block; }
    .hint-box    { background:#F8F5EE; border-left:3px solid #C9A84C;
                   padding:0.8rem 1rem; border-radius:4px;
                   font-size:0.88rem; color:#4A5568; margin-bottom:1rem; }
    .legal-badge { background:#1B3A5C; color:#C9A84C; padding:0.2rem 0.8rem;
                   border-radius:20px; font-size:0.85rem; font-weight:600; }
</style>
""", unsafe_allow_html=True)

# ── PASSWORDS — read from environment variables ───────────────────────────────
USER_PASSWORD  = os.environ.get("USER_PASSWORD",  "camp2026")
LEGAL_PASSWORD = os.environ.get("LEGAL_PASSWORD", "camplegal2026")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "campadmin2026")

# ── SESSION STATE ─────────────────────────────────────────────────────────────
for key, val in [
    ("authenticated", False), ("is_admin", False),
    ("legal_unlocked", False), ("clear_count", 0),
    ("query_text", "")
]:
    if key not in st.session_state:
        st.session_state[key] = val

# ── LOGIN SCREEN ──────────────────────────────────────────────────────────────
if not st.session_state["authenticated"]:
    st.markdown('<p class="main-title">🧠 OrgMind @ SMART</p>',
                unsafe_allow_html=True)
    st.markdown('<p class="camp-badge">CAMP — Critical Analytics for Manufacturing Personalised Medicine</p>',
                unsafe_allow_html=True)
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Sign In")
        password = st.text_input("Password:", type="password",
                                  placeholder="Enter your access password")
        if st.button("Sign In", type="primary", use_container_width=True):
            if password == ADMIN_PASSWORD:
                st.session_state.update({
                    "authenticated": True, "is_admin": True,
                    "legal_unlocked": True
                })
                st.rerun()
            elif password == LEGAL_PASSWORD:
                st.session_state.update({
                    "authenticated": True, "is_admin": False,
                    "legal_unlocked": True
                })
                st.rerun()
            elif password == USER_PASSWORD:
                st.session_state.update({
                    "authenticated": True, "is_admin": False,
                    "legal_unlocked": False
                })
                st.rerun()
            else:
                st.error("Incorrect password. Please try again.")
        st.caption("Contact your CAMP OrgMind administrator for access.")
    st.stop()

# ── EXCEPTION PROMPT BUILDER ──────────────────────────────────────────────────
def build_exception_prompt(doc_type, combined_context):
    positions = {
        "RCA": """
- Liability cap: SGD 10,000 for ALL parties equally (not A*STAR only)
- Joint IP: "tenants in common in equal and undivided shares"
- Governing law: Singapore always
- Force majeure: 60 days multi-party, 30 days bilateral
- Confidentiality: 3-5 years post-termination
- Publication review: 14-30 days; 60-day patent delay""",
        "NDA": """
- Confidentiality: minimum 3 years, ideally 5 years
- Scope: written and oral disclosures covered
- Governing law: Singapore
- Permitted disclosures: affiliates/employees on need-to-know only""",
        "MTA": """
- Materials: strictly for stated research purpose only
- No transfer to third parties without prior written consent
- Biological samples must be de-identified
- Governing law: Singapore""",
        "LOA": """
- Budget: flag restrictions on reallocation
- Overhead: check if 15% applies
- IP ownership: grantor rights to research IP
- Reporting: note all deadlines and audit rights""",
    }.get(doc_type.upper(), "Apply CAMP/SMART standard positions.")

    return f"""
You are analysing a complete {doc_type} for CAMP @ SMART.
Document in three sections (A, B, C) — COMPLETE agreement.
Read ALL THREE. Do NOT say it is incomplete.
Produce ONE unified exception report using spirit-based analysis.

CAMP/SMART established positions:
{positions}

Classify each as: ✅ STANDARD | ⚠️ WATCH | 🚨 CRITICAL

Assess all 10 categories:
1. Parties and structure
2. IP Ownership — sole developed
3. Joint IP Ownership — exact language
4. Background IP usage rights
5. Confidentiality — duration and scope
6. Publication / disclosure rights
7. Liability cap — amount and parties covered
8. Termination triggers and cure periods
9. Force majeure trigger period
10. Dispute resolution and governing law

For every WATCH or CRITICAL item:
• What this document says (quote the clause)
• What CAMP's established practice says (cite source file)
• Specific risk for CAMP/SMART
• Proposed amendment language

End with a SUMMARY TABLE of all 10 categories and their status.

COMPLETE DOCUMENT:
{combined_context}
"""

# ── MAIN HEADER ───────────────────────────────────────────────────────────────
col_title, col_folder = st.columns([3, 1])
with col_title:
    st.markdown('<p class="main-title">🧠 OrgMind @ SMART</p>',
                unsafe_allow_html=True)
    st.markdown('<p class="camp-badge">CAMP — Critical Analytics for Manufacturing Personalised Medicine</p>',
                unsafe_allow_html=True)
    if st.session_state["is_admin"]:
        badge = "🔑 Administrator"
    elif st.session_state["legal_unlocked"]:
        badge = "⚖️ Legal Access"
    else:
        badge = "👤 Staff Access"
    st.markdown(
        f'<p class="sub-title">Institutional Memory &nbsp;|&nbsp; '
        f'<span class="legal-badge">{badge}</span></p>',
        unsafe_allow_html=True)

with col_folder:
    st.markdown("&nbsp;")
    folder_options = get_folder_options(st.session_state["legal_unlocked"])
    selected_folder = st.selectbox("Folder:", folder_options, index=0)

# ── LEGAL UNLOCK ──────────────────────────────────────────────────────────────
if (not st.session_state["is_admin"]
        and not st.session_state["legal_unlocked"]):
    with st.expander("🔒 Have Legal & Contracts access? Unlock here"):
        legal_pw = st.text_input("Legal access password:",
                                  type="password", key="legal_unlock_input")
        if st.button("Unlock Legal Access"):
            if legal_pw == LEGAL_PASSWORD:
                st.session_state["legal_unlocked"] = True
                st.success("Legal & Contracts access unlocked.")
                st.rerun()
            else:
                st.error("Incorrect legal password.")

st.markdown("---")

# ── TABS ──────────────────────────────────────────────────────────────────────
legal_unlocked = st.session_state["legal_unlocked"]
is_admin = st.session_state["is_admin"]
is_staff = selected_folder == "Staff Related"
is_legal = selected_folder == "Legal & Contracts"

if is_admin:
    if is_staff:
        tab1, tab_admin = st.tabs(["💬  Ask OrgMind", "⚙️  Admin"])
        tab2 = None
    else:
        tab1, tab2, tab_admin = st.tabs([
            "💬  Ask OrgMind", "📋  Exception Analyser", "⚙️  Admin"])
else:
    tab_admin = None
    if is_staff:
        tabs = st.tabs(["💬  Ask OrgMind"])
        tab1 = tabs[0]
        tab2 = None
    else:
        tab1, tab2 = st.tabs(["💬  Ask OrgMind", "📋  Exception Analyser"])

# ══ TAB 1: ASK ORGMIND ════════════════════════════════════════════════════════
with tab1:
    hints = {
        "Legal & Contracts":
            "Ask about any clause, term or precedent from CAMP's signed "
            "agreements — RCAs, NDAs, MTAs, LOAs, Sub-Contracts or "
            "pre-agreement discussions in Miscellaneous.",
        "Staff Related":
            "Ask about any SMART policy — leave, travel, claims, "
            "onboarding, training or HR procedures.",
        "Research Operations":
            "Ask about lab equipment, inventory, locations, reports "
            "or research project findings.",
        "General CAMP":
            "Ask about CAMP policies, EHS rules, finance procedures "
            "or general institutional decisions.",
        "All (Search Everything)":
            "Searches across all accessible CAMP folders simultaneously.",
    }
    st.markdown(
        f'<div class="hint-box">💡 {hints.get(selected_folder, "Ask OrgMind anything about CAMP.")}</div>',
        unsafe_allow_html=True)

    query_text = st.text_area(
        "Your question:",
        value=st.session_state.get("query_text", ""),
        height=100,
        key=f'qbox_{st.session_state["clear_count"]}',
        placeholder="Type your question here in your own words..."
    )

    s_col, c_col = st.columns([5, 1])
    with s_col:
        search_clicked = st.button("🔍  Search CAMP Knowledge Base",
                                    type="primary", use_container_width=True)
    with c_col:
        if st.button("Clear", use_container_width=True):
            st.session_state["query_text"] = ""
            st.session_state["clear_count"] += 1
            st.rerun()

    if search_clicked and query_text.strip():
        st.session_state["query_text"] = query_text.strip()
        with st.spinner("Searching CAMP's institutional memory..."):
            result = query(
                query_text.strip(), selected_folder,
                legal_unlocked=legal_unlocked
            )
        st.markdown("### Answer")
        st.markdown(
            f'<div class="answer-box">{result["answer"]}</div>',
            unsafe_allow_html=True)
        if result["sources"]:
            unique = sorted(set(s for s in result["sources"] if s))
            st.markdown("**Documents consulted:**")
            html = " ".join(
                f'<span class="source-tag">{s}</span>' for s in unique)
            st.markdown(html, unsafe_allow_html=True)
        fb1, fb2, _ = st.columns([1, 1, 5])
        fb1.button("👍  Helpful", key="fb_yes")
        fb2.button("👎  Not helpful", key="fb_no")
    elif search_clicked:
        st.warning("Please type your question before searching.")

# ══ TAB 2: EXCEPTION ANALYSER ═════════════════════════════════════════════════
if tab2 is not None:
    with tab2:
        st.markdown("### Document Exception Analyser")
        st.markdown(
            "Upload a new incoming agreement. OrgMind auto-detects the "
            "document type from the filename and compares it against "
            "CAMP's established practice."
        )
        st.info("Include document type in filename: e.g. `2026-05_RCA_NewCollaborator_Draft.pdf`")
        st.markdown("---")

        uploaded = st.file_uploader("Upload document:", type=["pdf", "docx"])

        if uploaded:
            fname_upper = uploaded.name.upper()
            detected = "RCA"
            for t in ["NDA", "MTA", "LOA", "RCA"]:
                if t in fname_upper:
                    detected = t
                    break

            st.success(f"✅  {uploaded.name}  ({uploaded.size:,} bytes)")
            doc_type = st.selectbox(
                "Document type:",
                ["RCA", "NDA", "MTA", "LOA"],
                index=["RCA", "NDA", "MTA", "LOA"].index(detected)
            )

            if st.button("📋  Run Exception Analysis", type="primary"):
                suffix = ".pdf" if uploaded.name.lower().endswith(".pdf") else ".docx"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded.getvalue())
                    tmp_path = tmp.name

                try:
                    if suffix == ".pdf":
                        import fitz
                        doc = fitz.open(tmp_path)
                        full_text = "\n".join(p.get_text() for p in doc)
                        doc.close()
                    else:
                        from docx import Document as Docx
                        d = Docx(tmp_path)
                        full_text = "\n".join(
                            p.text for p in d.paragraphs if p.text.strip())
                except Exception as e:
                    st.error(f"Could not read: {e}")
                    st.stop()
                finally:
                    os.unlink(tmp_path)

                if len(full_text.strip()) < 200:
                    st.error("Cannot extract text — ensure PDF is not scanned.")
                    st.stop()

                t = len(full_text)
                third = t // 3
                combined = (
                    f"[SECTION A]\n{full_text[:third]}\n\n"
                    f"[SECTION B]\n{full_text[third:2*third]}\n\n"
                    f"[SECTION C]\n{full_text[2*third:]}"
                )

                with st.spinner(f"Analysing {doc_type}... 30-60 seconds."):
                    result = query(
                        build_exception_prompt(doc_type, combined),
                        "Legal & Contracts",
                        doc_type_filter=doc_type,
                        legal_unlocked=True
                    )

                st.markdown("---")
                st.markdown(f"## Exception Report — {doc_type}")
                st.markdown(f"`{uploaded.name}`")
                st.markdown("---")
                st.markdown(result["answer"])

                if result["sources"]:
                    html = " ".join(
                        f'<span class="source-tag">{s}</span>'
                        for s in sorted(set(s for s in result["sources"] if s)))
                    st.markdown(html, unsafe_allow_html=True)

                st.download_button(
                    "📥  Download Report",
                    data=f"EXCEPTION REPORT — {doc_type}\nDocument: {uploaded.name}\n{'='*60}\n\n{result['answer']}",
                    file_name=uploaded.name.replace(
                        ".pdf", f"_{doc_type}_ExceptionReport.txt"
                    ).replace(".docx", f"_{doc_type}_ExceptionReport.txt"),
                    use_container_width=True
                )

# ══ ADMIN TAB ═════════════════════════════════════════════════════════════════
if tab_admin is not None:
    with tab_admin:
        st.markdown("## ⚙️ Admin Panel")
        st.info("Only visible to administrators.")

        # ── 1. Sync ───────────────────────────────────────────────────────
        st.markdown("### 1.  Sync Documents from Dropbox")
        st.markdown("Downloads new or updated files from Dropbox. Run after any change.")

        col1, col2 = st.columns([2, 1])
        with col1:
            if st.button("🔄  Sync from Dropbox", use_container_width=True):
                from dropbox_sync import sync_from_dropbox
                with st.spinner("Syncing from Dropbox..."):
                    synced, skipped, errors = sync_from_dropbox()
                for e in errors:
                    st.warning(e)
                st.success(
                    f"Sync complete: **{synced} new files** downloaded, "
                    f"{skipped} already up to date."
                )
                if synced > 0:
                    st.info("Run Rebuild Knowledge Base below.")
        with col2:
            if st.button("👁  View Dropbox Files", use_container_width=True):
                from dropbox_sync import get_dropbox_file_list
                with st.spinner("Reading Dropbox..."):
                    file_list = get_dropbox_file_list()
                if "error" in file_list:
                    st.error(file_list["error"])
                else:
                    for folder, files in file_list.items():
                        st.markdown(f"**{folder}** ({len(files)} files)")
                        for f in files:
                            st.markdown(f"&nbsp;&nbsp;&nbsp;📄 {f}")

        st.markdown("---")

        # ── 2. Rebuild ────────────────────────────────────────────────────
        st.markdown("### 2.  Rebuild Knowledge Base")
        st.markdown("Run after every Sync. Makes all new documents searchable.")
        st.warning("Takes 2-5 minutes. Users can still query during rebuild.")

        if st.button("⚡  Rebuild Knowledge Base",
                     type="primary", use_container_width=True):
            from ingest import run_ingest
            with st.spinner("Building knowledge base... please wait."):
                result = run_ingest()
            if not result["success"]:
                st.error(f"Rebuild failed: {result['error']}")
            else:
                st.success(
                    f"Done: **{result['total_docs']} documents**, "
                    f"{result['total_chunks']} searchable chunks"
                )
                for label, info in result["details"].items():
                    icon = "✅" if info.get("docs", 0) > 0 else "⏳"
                    st.markdown(
                        f"&nbsp;&nbsp;{icon}  {label}: "
                        f"{info.get('docs',0)} docs, {info.get('chunks',0)} chunks"
                    )

        st.markdown("---")

        # ── 3. Delete ─────────────────────────────────────────────────────
        st.markdown("### 3.  Delete a Document")
        st.markdown("Delete a file locally then Rebuild to remove from search index.")

        from dropbox_sync import get_local_file_list
        local_files = get_local_file_list()
        all_files = []
        for folder, files in local_files.items():
            for f in files:
                all_files.append(f"camp_documents/{folder}/{f}")

        if all_files:
            file_to_delete = st.selectbox(
                "Select file to delete:", ["— select —"] + all_files)
            if file_to_delete != "— select —":
                if st.button("🗑  Delete Selected File"):
                    from dropbox_sync import delete_local_file
                    ok, err = delete_local_file(file_to_delete)
                    if ok:
                        st.success(
                            f"Deleted: {os.path.basename(file_to_delete)}. "
                            "Run Rebuild to update search index."
                        )
                    else:
                        st.error(f"Could not delete: {err}")
        else:
            st.info("No local files found.")

        st.markdown("---")

        # ── 4. Status ─────────────────────────────────────────────────────
        st.markdown("### 4.  Knowledge Base Status")
        if os.path.exists("./chroma_db"):
            try:
                from langchain_openai import OpenAIEmbeddings
                from langchain_chroma import Chroma as ChromaDB
                embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
                for coll, label in [
                    ("camp_legal", "Legal & Contracts"),
                    ("camp_staff", "Staff Related"),
                    ("camp_research_ops", "Research Operations"),
                    ("camp_general", "General CAMP")
                ]:
                    try:
                        vs = ChromaDB(
                            collection_name=coll,
                            persist_directory="./chroma_db",
                            embedding_function=embeddings
                        )
                        count = vs._collection.count()
                        st.markdown(f"&nbsp;&nbsp;📚  {label}: **{count} chunks**")
                    except Exception:
                        st.markdown(f"&nbsp;&nbsp;⏳  {label}: not loaded")
            except Exception:
                st.info("API keys needed to check status.")
        else:
            st.warning("Knowledge base not built yet.")

        st.markdown("---")

        # ── 5. Document Management ────────────────────────────────────────
        st.markdown("### 5.  Document Management")
        st.markdown("""
Manage all documents in your **Dropbox** app or at dropbox.com.

```
OrgMind-CAMP/
├── 01_Legal_Contracts/
│   ├── RCA/            ← Signed RCAs
│   ├── NDA/            ← Non-Disclosure Agreements
│   ├── MTA/            ← Material Transfer Agreements
│   ├── LOA/            ← Letters of Award
│   ├── Miscellaneous/  ← Pre-agreement emails, rationale
│   └── Sub-Contracts/
├── 02_Staff_Related/
│   └── SMART-Policies/
├── 03_Research_Operations/
│   ├── Reports/
│   └── Research-Publications-Presentations-Discussions/
└── 04_General_CAMP/
```

**After any change in Dropbox:** Sync → Rebuild
        """)

        st.markdown("---")
        if st.button("🔒  Sign Out"):
            for key in ["authenticated", "is_admin", "legal_unlocked"]:
                st.session_state[key] = False
            st.rerun()

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### OrgMind @ SMART")
    st.markdown("**CAMP**  ·  v4.2")
    if is_admin:
        st.markdown("🔑  Administrator")
    elif legal_unlocked:
        st.markdown("⚖️  Legal Access")
    else:
        st.markdown("👤  Staff Access")
    st.markdown("---")
    st.markdown("**Knowledge Base:**")
    if os.path.exists("./chroma_db"):
        st.success("Ready")
    else:
        st.warning("Not built yet")
    st.markdown("---")
    st.markdown("**Your folders:**")
    for f in get_folder_options(legal_unlocked):
        icons = {
            "Legal & Contracts": "⚖️",
            "Staff Related": "👥",
            "Research Operations": "🔬",
            "General CAMP": "📋",
            "All (Search Everything)": "🔍"
        }
        st.markdown(f"{icons.get(f,'📁')}  {f}")
    st.markdown("---")
    st.markdown("**Tips:**")
    st.markdown("Be specific. Include document type and context.")
    st.markdown("---")
    if st.button("Sign Out", use_container_width=True):
        for key in ["authenticated", "is_admin", "legal_unlocked"]:
            st.session_state[key] = False
        st.rerun()
    st.caption(
        "All answers grounded in CAMP's own documents. "
        "Verify critical decisions against source files."
    )
