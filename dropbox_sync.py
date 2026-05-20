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


def _read_config(key):
    """Read from config files or environment variable."""
    config_paths = [
        "/tmp/apikeys.txt",
        "/app/config.txt",
        "./config.txt",
        "/mount/src/orgmind-camp/config.txt"
    ]
    for path in config_paths:
        if os.path.exists(path):
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
    return os.environ.get(key, "")


def get_dropbox_client():
    """Get Dropbox client using refresh token (permanent) or access token."""
    # Try refresh token first (permanent — never expires)
    refresh_token = _read_config("DROPBOX_REFRESH_TOKEN")
    if refresh_token and not refresh_token.startswith("replace_with"):
        app_key = _read_config("DROPBOX_APP_KEY")
        app_secret = _read_config("DROPBOX_APP_SECRET")
        if app_key and app_secret:
            return dropbox.Dropbox(
                oauth2_refresh_token=refresh_token,
                app_key=app_key,
                app_secret=app_secret
            )

    # Fall back to access token
    token = _read_config("DROPBOX_ACCESS_TOKEN")
    if not token or token.startswith("replace_with"):
        raise ValueError(
            "Dropbox not configured. "
            "Add DROPBOX_REFRESH_TOKEN, DROPBOX_APP_KEY and "
            "DROPBOX_APP_SECRET to your config.txt file."
        )
    return dropbox.Dropbox(token)


def sync_from_dropbox():
    """Download all files from Dropbox using recursive listing."""
    try:
        dbx = get_dropbox_client()
    except ValueError as e:
        return 0, 0, [str(e)]

    synced = skipped = 0
    errors = []

    # Create all local folders
    for _, local_path in FOLDER_MAP.items():
        os.makedirs(local_path, exist_ok=True)

    try:
        # One recursive call instead of per-folder calls
        result = dbx.files_list_folder(DROPBOX_BASE, recursive=True)
        entries = list(result.entries)
        while result.has_more:
            result = dbx.files_list_folder_continue(result.cursor)
            entries.extend(result.entries)
    except Exception as e:
        return 0, 0, [f"Cannot list Dropbox: {e}"]

    for entry in entries:
        if not isinstance(entry, dropbox.files.FileMetadata):
            continue
        fname = entry.name
        if not fname.lower().endswith((".pdf", ".docx")):
            continue
        if fname.startswith(("~", ".")):
            continue

        # Match to local folder using FOLDER_MAP
        dropbox_folder = entry.path_display.rsplit("/", 1)[0]
        local_path = FOLDER_MAP.get(dropbox_folder)

        if not local_path:
            # Try case-insensitive match
            for dp, lp in FOLDER_MAP.items():
                if dp.lower() == dropbox_folder.lower():
                    local_path = lp
                    break

        if not local_path:
            # Try partial match — find closest parent folder
            dropbox_folder_lower = dropbox_folder.lower()
            for dp, lp in FOLDER_MAP.items():
                if dropbox_folder_lower.startswith(dp.lower()):
                    local_path = lp
                    break

        if not local_path:
            continue  # Still no match — skip

        local_file = os.path.join(local_path, fname)

        if os.path.exists(local_file) and os.path.getsize(local_file) == entry.size:
            skipped += 1
            continue

        try:
            dbx.files_download_to_file(local_file, entry.path_display)
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
    """List all files under OrgMind-CAMP root for admin display."""
    try:
        dbx = get_dropbox_client()
    except ValueError as e:
        return {"error": str(e)}

    file_list = {}
    try:
        # List recursively from root in one call — faster than per-folder
        result = dbx.files_list_folder(DROPBOX_BASE, recursive=True)
        entries = list(result.entries)

        # Keep paginating if needed
        while result.has_more:
            result = dbx.files_list_folder_continue(result.cursor)
            entries.extend(result.entries)

        for entry in entries:
            if not isinstance(entry, dropbox.files.FileMetadata):
                continue
            if not entry.name.lower().endswith((".pdf", ".docx")):
                continue
            # Get folder label from path
            folder = entry.path_lower.replace(
                DROPBOX_BASE.lower() + "/", ""
            )
            folder = "/".join(folder.split("/")[:-1]) or "root"
            if folder not in file_list:
                file_list[folder] = []
            file_list[folder].append(entry.name)

        # Sort files in each folder
        for folder in file_list:
            file_list[folder] = sorted(file_list[folder])

    except Exception as e:
        return {"error": f"Could not read Dropbox: {str(e)}"}

    return file_list
