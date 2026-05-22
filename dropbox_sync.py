"""
OrgMind @ SMART — Dropbox Sync Module v4.2
Clean environment variable reading.
"""

import os
import dropbox

DROPBOX_BASE = "/OrgMind-CAMP"

FOLDER_MAP = {
    f"{DROPBOX_BASE}/01_Legal_Contracts/RCA":           "camp_documents/01_Legal_Contracts/RCA",
    f"{DROPBOX_BASE}/01_Legal_Contracts/NDA":           "camp_documents/01_Legal_Contracts/NDA",
    f"{DROPBOX_BASE}/01_Legal_Contracts/MTA":           "camp_documents/01_Legal_Contracts/MTA",
    f"{DROPBOX_BASE}/01_Legal_Contracts/LOA":           "camp_documents/01_Legal_Contracts/LOA",
    f"{DROPBOX_BASE}/01_Legal_Contracts/Miscellaneous": "camp_documents/01_Legal_Contracts/Miscellaneous",
    f"{DROPBOX_BASE}/01_Legal_Contracts/Sub-Contracts": "camp_documents/01_Legal_Contracts/Sub-Contracts",
    f"{DROPBOX_BASE}/02_Staff_Related/SMART-Policies":  "camp_documents/02_Staff_Related/SMART-Policies",
    f"{DROPBOX_BASE}/03_Research_Operations/Reports":   "camp_documents/03_Research_Operations/Reports",
    f"{DROPBOX_BASE}/03_Research_Operations/Research-Publications-Presentations-Discussions":
        "camp_documents/03_Research_Operations/Research-Publications-Presentations-Discussions",
    f"{DROPBOX_BASE}/04_General_CAMP":                  "camp_documents/04_General_CAMP",
    f"{DROPBOX_BASE}/04_General _CAMP":               "camp_documents/04_General_CAMP",
}


def get_dropbox_client():
    """Get Dropbox client using refresh token."""
    refresh_token = os.environ.get("DROPBOX_REFRESH_TOKEN", "")
    app_key = os.environ.get("DROPBOX_APP_KEY", "")
    app_secret = os.environ.get("DROPBOX_APP_SECRET", "")

    if refresh_token and app_key and app_secret:
        return dropbox.Dropbox(
            oauth2_refresh_token=refresh_token,
            app_key=app_key,
            app_secret=app_secret
        )
    raise ValueError(
        "Dropbox credentials not configured. "
        "Add DROPBOX_REFRESH_TOKEN, DROPBOX_APP_KEY and "
        "DROPBOX_APP_SECRET to your environment variables."
    )


def sync_from_dropbox():
    """Download all files from Dropbox using recursive listing."""
    try:
        dbx = get_dropbox_client()
    except ValueError as e:
        return 0, 0, [str(e)]

    synced = skipped = 0
    errors = []

    for _, local_path in FOLDER_MAP.items():
        os.makedirs(local_path, exist_ok=True)

    try:
        result = dbx.files_list_folder(DROPBOX_BASE, recursive=True)
        entries = list(result.entries)
        while result.has_more:
            result = dbx.files_list_folder_continue(result.cursor)
            entries.extend(result.entries)
    except Exception as e:
        return 0, 0, [f"Cannot list Dropbox: {e}"]

    debug_log = []
    for entry in entries:
        if not isinstance(entry, dropbox.files.FileMetadata):
            continue
        fname = entry.name
        if not fname.lower().endswith((".pdf", ".docx", ".xlsx", ".xls")):
            continue
        if fname.startswith(("~", ".")):
            continue

        dropbox_folder = entry.path_display.rsplit("/", 1)[0]
        debug_log.append(f"{fname} -> folder: {dropbox_folder}")
        local_path = FOLDER_MAP.get(dropbox_folder)

        if not local_path:
            for dp, lp in FOLDER_MAP.items():
                if dp.lower() == dropbox_folder.lower():
                    local_path = lp
                    break

        if not local_path:
            dropbox_folder_lower = dropbox_folder.lower()
            for dp, lp in FOLDER_MAP.items():
                if dropbox_folder_lower.startswith(dp.lower()):
                    local_path = lp
                    break

        if not local_path:
            # Last resort — match by folder name alone
            folder_name = dropbox_folder.rstrip("/").split("/")[-1].lower()
            for dp, lp in FOLDER_MAP.items():
                dp_name = dp.rstrip("/").split("/")[-1].lower()
                if folder_name == dp_name:
                    local_path = lp
                    break

        if not local_path:
            continue

        local_file = os.path.join(local_path, fname)
        if os.path.exists(local_file) and os.path.getsize(local_file) == entry.size:
            skipped += 1
            continue

        try:
            dbx.files_download_to_file(local_file, entry.path_display)
            synced += 1
        except Exception as e:
            errors.append(f"Cannot download {fname}: {e}")

    # Write debug log
    try:
        with open("camp_documents/sync_debug.txt", "w") as f:
            f.write("\n".join(debug_log))
    except Exception:
        pass

    return synced, skipped, errors


def get_local_file_list():
    """List all local files per collection."""
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
    """List all Dropbox files."""
    try:
        dbx = get_dropbox_client()
    except ValueError as e:
        return {"error": str(e)}

    file_list = {}
    try:
        result = dbx.files_list_folder(DROPBOX_BASE, recursive=True)
        entries = list(result.entries)
        while result.has_more:
            result = dbx.files_list_folder_continue(result.cursor)
            entries.extend(result.entries)

        for entry in entries:
            if not isinstance(entry, dropbox.files.FileMetadata):
                continue
            if not entry.name.lower().endswith((".pdf", ".docx")):
                continue
            folder = entry.path_lower.replace(
                DROPBOX_BASE.lower() + "/", "")
            folder = "/".join(folder.split("/")[:-1]) or "root"
            if folder not in file_list:
                file_list[folder] = []
            file_list[folder].append(entry.name)

        for folder in file_list:
            file_list[folder] = sorted(file_list[folder])

    except Exception as e:
        return {"error": f"Could not read Dropbox: {str(e)}"}

    return file_list


def delete_local_file(local_path):
    """Delete a file from local camp_documents folder."""
    try:
        if os.path.exists(local_path):
            os.remove(local_path)
            return True, None
    except Exception as e:
        return False, str(e)
    return False, "File not found"
