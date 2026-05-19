"""
OrgMind @ SMART — Dropbox Sync Module v4.1
Matches exact Dropbox folder structure created by administrator.
"""

import os
import dropbox

DROPBOX_BASE = "/OrgMind-CAMP"

FOLDER_MAP = {
    # Legal & Contracts — all subfolders
    f"{DROPBOX_BASE}/01_Legal_Contracts/RCA":           "camp_documents/01_Legal_Contracts/RCA",
    f"{DROPBOX_BASE}/01_Legal_Contracts/NDA":           "camp_documents/01_Legal_Contracts/NDA",
    f"{DROPBOX_BASE}/01_Legal_Contracts/MTA":           "camp_documents/01_Legal_Contracts/MTA",
    f"{DROPBOX_BASE}/01_Legal_Contracts/LOA":           "camp_documents/01_Legal_Contracts/LOA",
    f"{DROPBOX_BASE}/01_Legal_Contracts/Miscellaneous": "camp_documents/01_Legal_Contracts/Miscellaneous",
    f"{DROPBOX_BASE}/01_Legal_Contracts/Sub-Contracts": "camp_documents/01_Legal_Contracts/Sub-Contracts",
    # Staff Related
    f"{DROPBOX_BASE}/02_Staff_Related/SMART-Policies":  "camp_documents/02_Staff_Related/SMART-Policies",
    # Research Operations
    f"{DROPBOX_BASE}/03_Research_Operations/Reports":                               "camp_documents/03_Research_Operations/Reports",
    f"{DROPBOX_BASE}/03_Research_Operations/Lab-Inventory":                         "camp_documents/03_Research_Operations/Lab-Inventory",
    f"{DROPBOX_BASE}/03_Research_Operations/Equipment":                             "camp_documents/03_Research_Operations/Equipment",
    f"{DROPBOX_BASE}/03_Research_Operations/Research-Publications-Presentations-Discussions": "camp_documents/03_Research_Operations/Research-Publications-Presentations-Discussions",
    # General CAMP
    f"{DROPBOX_BASE}/04_General_CAMP":                  "camp_documents/04_General_CAMP",
}


def get_dropbox_client():
    token = os.getenv("DROPBOX_ACCESS_TOKEN", "")
    try:
        import streamlit as st
        token = st.secrets.get("DROPBOX_ACCESS_TOKEN", token)
    except Exception:
        pass
    if not token or token.startswith("paste-your"):
        raise ValueError(
            "Dropbox access token not configured. "
            "Add DROPBOX_ACCESS_TOKEN to your Streamlit secrets."
        )
    return dropbox.Dropbox(token)


def sync_from_dropbox():
    """Download new/updated files from Dropbox. Returns (synced, skipped, errors)."""
    try:
        dbx = get_dropbox_client()
    except ValueError as e:
        return 0, 0, [str(e)]

    synced = skipped = 0
    errors = []

    for dropbox_path, local_path in FOLDER_MAP.items():
        os.makedirs(local_path, exist_ok=True)
        try:
            result = dbx.files_list_folder(dropbox_path)
            entries = list(result.entries)
            while result.has_more:
                result = dbx.files_list_folder_continue(result.cursor)
                entries.extend(result.entries)
        except dropbox.exceptions.ApiError as e:
            if "not_found" in str(e):
                continue
            errors.append(f"Cannot list {dropbox_path}: {e}")
            continue

        for entry in entries:
            if not isinstance(entry, dropbox.files.FileMetadata):
                continue
            fname = entry.name
            if not fname.lower().endswith((".pdf", ".docx")):
                continue
            if fname.startswith(("~", ".")):
                continue
            local_file = os.path.join(local_path, fname)
            if os.path.exists(local_file) and os.path.getsize(local_file) == entry.size:
                skipped += 1
                continue
            try:
                dbx.files_download_to_file(local_file, f"{dropbox_path}/{fname}")
                synced += 1
            except Exception as e:
                errors.append(f"Cannot download {fname}: {e}")

    return synced, skipped, errors


def delete_local_file(local_path):
    """Delete a file from local camp_documents folder."""
    try:
        if os.path.exists(local_path):
            os.remove(local_path)
            return True, None
    except Exception as e:
        return False, str(e)
    return False, "File not found"


def get_local_file_list():
    """List all local files per collection for admin display."""
    file_list = {}
    for _, local_path in FOLDER_MAP.items():
        label = local_path.replace("camp_documents/", "")
        if not os.path.exists(local_path):
            continue
        files = [
            f for f in sorted(os.listdir(local_path))
            if f.lower().endswith((".pdf", ".docx"))
            and not f.startswith(("~", "."))
        ]
        if files:
            file_list[label] = files
    return file_list


def get_dropbox_file_list():
    """List all Dropbox files per folder for admin display."""
    try:
        dbx = get_dropbox_client()
    except ValueError as e:
        return {"error": str(e)}

    file_list = {}
    for dropbox_path, _ in FOLDER_MAP.items():
        label = dropbox_path.replace(DROPBOX_BASE + "/", "")
        try:
            result = dbx.files_list_folder(dropbox_path)
            files = [
                e.name for e in result.entries
                if isinstance(e, dropbox.files.FileMetadata)
                and e.name.lower().endswith((".pdf", ".docx"))
            ]
            if files:
                file_list[label] = sorted(files)
        except Exception:
            pass
    return file_list
