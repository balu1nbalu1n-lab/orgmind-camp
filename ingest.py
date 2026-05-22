"""
OrgMind @ SMART — Document Ingestion v4.2
Clean environment variable reading.
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

import fitz
from docx import Document as Docx
from langchain_text_splitters import RecursiveCharacterTextSplitter
try:
    import openpyxl
    EXCEL_SUPPORTED = True
except ImportError:
    EXCEL_SUPPORTED = False
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

CHROMA_PATH = "./chroma_db"

DEPT_CONFIG = {
    "camp_legal": {
        "label": "Legal & Contracts",
        "folders": [
            "camp_documents/01_Legal_Contracts/RCA",
            "camp_documents/01_Legal_Contracts/NDA",
            "camp_documents/01_Legal_Contracts/MTA",
            "camp_documents/01_Legal_Contracts/LOA",
            "camp_documents/01_Legal_Contracts/Miscellaneous",
            "camp_documents/01_Legal_Contracts/Sub-Contracts",
            "camp_documents/01_Legal_Contracts",
        ]
    },
    "camp_staff": {
        "label": "Staff Related",
        "folders": [
            "camp_documents/02_Staff_Related/SMART-Policies",
            "camp_documents/02_Staff_Related",
        ]
    },
    "camp_research_ops": {
        "label": "Research Operations",
        "folders": [
            "camp_documents/03_Research_Operations/Reports",
            "camp_documents/03_Research_Operations/Lab_Inventory",
            "camp_documents/03_Research_Operations/Research-Publications-Presentations-Discussions",
            "camp_documents/03_Research_Operations",
        ]
    },
    "camp_general": {
        "label": "General CAMP",
        "folders": [
            "camp_documents/04_General_CAMP",
        ]
    },
}


def read_excel(path):
    """Convert Excel file to searchable text."""
    if not EXCEL_SUPPORTED:
        return ""
    try:
        wb = openpyxl.load_workbook(path, data_only=True)
        lines = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            lines.append(f"[Sheet: {sheet_name}]")
            for row in ws.iter_rows():
                row_values = []
                for cell in row:
                    if cell.value is not None:
                        row_values.append(str(cell.value).strip())
                if row_values:
                    lines.append("  |  ".join(row_values))
        return "\n".join(lines)
    except Exception as e:
        raise Exception(f"Could not read Excel: {e}")


def read_pdf(path):
    doc = fitz.open(path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def read_docx(path):
    doc = Docx(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def load_folder(folder_path, collection_name, seen_files):
    docs = []
    if not os.path.exists(folder_path):
        return docs
    for fname in sorted(os.listdir(folder_path)):
        if not fname.lower().endswith((".pdf", ".docx", ".xlsx", ".xls")):
            continue
        if fname.startswith(("~", ".")):
            continue
        fpath = os.path.join(folder_path, fname)
        if fpath in seen_files:
            continue
        seen_files.add(fpath)
        try:
            if fname.lower().endswith(".pdf"):
                text = read_pdf(fpath)
            elif fname.lower().endswith((".xlsx", ".xls")):
                text = read_excel(fpath)
            else:
                text = read_docx(fpath)
            if len(text.strip()) < 100:
                print(f"    SKIPPED (too short/scanned): {fname}")
                continue
            fname_upper = fname.upper()
            doc_type = "GENERAL"
            for t in ["RCA", "NDA", "MTA", "LOA"]:
                if t in fname_upper:
                    doc_type = t
                    break
            docs.append(Document(
                page_content=text,
                metadata={
                    "source": fname,
                    "collection": collection_name,
                    "doc_type": doc_type,
                    "filepath": fpath
                }
            ))
        except Exception as e:
            print(f"    ERROR {fname}: {e}")
    return docs


def run_ingest():
    try:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    except Exception as e:
        return {"success": False, "error": str(e),
                "total_docs": 0, "total_chunks": 0, "details": {}}

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " "]
    )

    total_docs = total_chunks = 0
    details = {}

    for collection_name, config in DEPT_CONFIG.items():
        label = config["label"]
        seen_files = set()
        all_docs = []
        for folder in config["folders"]:
            all_docs.extend(
                load_folder(folder, collection_name, seen_files))

        if not all_docs:
            details[label] = {"docs": 0, "chunks": 0}
            continue

        chunks = splitter.split_documents(all_docs)
        try:
            Chroma.from_documents(
                documents=chunks,
                embedding=embeddings,
                collection_name=collection_name,
                persist_directory=CHROMA_PATH
            )
            details[label] = {
                "docs": len(all_docs), "chunks": len(chunks)}
            total_docs += len(all_docs)
            total_chunks += len(chunks)
        except Exception as e:
            details[label] = {"docs": 0, "chunks": 0, "error": str(e)}

    return {
        "success": True,
        "total_docs": total_docs,
        "total_chunks": total_chunks,
        "details": details
    }


if __name__ == "__main__":
    print("\n" + "="*56)
    print("  OrgMind @ CAMP — Document Ingestion")
    print("="*56)
    result = run_ingest()
    if not result["success"]:
        print(f"\n ERROR: {result['error']}")
    else:
        for label, info in result["details"].items():
            if info["docs"] > 0:
                print(f"\n[{label}] {info['docs']} docs → {info['chunks']} chunks")
        print(f"\n  Done! {result['total_docs']} documents")
        print(f"        {result['total_chunks']} searchable chunks")
    print("="*56 + "\n")
