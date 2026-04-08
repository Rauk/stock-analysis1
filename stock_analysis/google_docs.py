"""Google Docs integration: create/update per-stock analysis documents."""

import json
import os

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    _GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    _GOOGLE_LIBS_AVAILABLE = False

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

DOC_NAME_PREFIX = "Stock Analysis"
SEPARATOR_CHAR = "─"
SEPARATOR_WIDTH = 80


def _build_services():
    """Build and return authenticated Google Docs and Drive service clients."""
    if not _GOOGLE_LIBS_AVAILABLE:
        raise EnvironmentError(
            "Google API packages are not installed. Run:\n"
            "  pip install google-api-python-client google-auth"
        )

    json_env = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not json_env:
        raise EnvironmentError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is not set. "
            "Set it to the path of your service account JSON key file or its raw JSON content."
        )

    # Accept either a file path or raw JSON content
    if os.path.isfile(json_env):
        with open(json_env, "r", encoding="utf-8") as f:
            info = json.load(f)
    else:
        try:
            info = json.loads(json_env)
        except json.JSONDecodeError as exc:
            raise EnvironmentError(
                f"GOOGLE_SERVICE_ACCOUNT_JSON is neither a valid file path nor valid JSON: {exc}"
            ) from exc

    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    docs_service  = build("docs",  "v1", credentials=creds, cache_discovery=False)
    drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)
    return docs_service, drive_service


def _doc_title(symbol: str) -> str:
    return f"{DOC_NAME_PREFIX} - {symbol.upper()}"


def _find_existing_doc(drive_service, symbol: str, folder_id: str | None) -> str | None:
    """Search Drive for an existing doc with the stock's title. Returns doc ID or None."""
    title = _doc_title(symbol)
    # Escape single quotes in title for Drive query
    safe_title = title.replace("'", "\\'")
    query = f"name = '{safe_title}' and mimeType = 'application/vnd.google-apps.document' and trashed = false"
    if folder_id:
        query += f" and '{folder_id}' in parents"

    result = drive_service.files().list(
        q=query,
        spaces="drive",
        fields="files(id, name)",
        pageSize=1,
    ).execute()

    files = result.get("files", [])
    if files:
        return files[0]["id"]
    return None


def _create_doc(docs_service, drive_service, symbol: str, folder_id: str | None) -> str:
    """Create a new empty Google Doc for the stock. Returns the new doc ID."""
    title = _doc_title(symbol)
    doc = docs_service.documents().create(body={"title": title}).execute()
    doc_id = doc["documentId"]

    # Move to specified folder if provided
    if folder_id:
        # Get current parents to remove them
        file_meta = drive_service.files().get(
            fileId=doc_id, fields="parents"
        ).execute()
        previous_parents = ",".join(file_meta.get("parents", []))
        drive_service.files().update(
            fileId=doc_id,
            addParents=folder_id,
            removeParents=previous_parents,
            fields="id, parents",
        ).execute()

    return doc_id


def _doc_url(doc_id: str) -> str:
    return f"https://docs.google.com/document/d/{doc_id}/edit"


def _get_doc_end_index(docs_service, doc_id: str) -> int:
    """Return the end index of the document body (i.e. current content length)."""
    doc = docs_service.documents().get(documentId=doc_id).execute()
    return doc["body"]["endIndex"]


def _prepend_text(docs_service, doc_id: str, text: str) -> None:
    """Insert text at the very beginning (index 1) of the document."""
    requests = [
        {
            "insertText": {
                "location": {"index": 1},
                "text": text,
            }
        }
    ]
    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": requests},
    ).execute()


def _explain_http_error(exc) -> str:
    """Return a human-readable fix for common Google API HttpErrors."""
    status = exc.resp.status if hasattr(exc, "resp") else 0
    if status == 403:
        return (
            "403 Permission denied. To fix:\n"
            "  1. Go to https://console.cloud.google.com/apis/library\n"
            "     and enable both 'Google Docs API' and 'Google Drive API'\n"
            "     for your project.\n"
            "  2. The service account must also have access to Google Drive.\n"
            "     Since service accounts have their own isolated Drive, you must\n"
            "     EITHER share a Drive folder with the service account email\n"
            "     and set GOOGLE_DRIVE_FOLDER_ID to that folder's ID,\n"
            "     OR share an existing doc directly with the service account email.\n"
            "  3. Grant the service account 'Editor' access on the folder/doc.\n"
            f"  Service account email is shown in your JSON key as 'client_email'."
        )
    if status == 404:
        return (
            "404 Not found. The document or folder ID may be wrong.\n"
            "  Check GOOGLE_DRIVE_FOLDER_ID is the correct folder ID."
        )
    if status == 401:
        return (
            "401 Unauthorized. The service account credentials may be expired or invalid.\n"
            "  Re-download the JSON key from Google Cloud Console."
        )
    return str(exc)


def get_or_create_doc(symbol: str, company_name: str) -> tuple[str, str]:
    """
    Find an existing Google Doc for the given stock symbol, or create a new one.

    Returns:
        (doc_id, doc_url)
    """
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip() or None
    docs_service, drive_service = _build_services()

    try:
        doc_id = _find_existing_doc(drive_service, symbol, folder_id)
        if doc_id:
            print(f"  [gdocs] Found existing doc for {symbol}: {_doc_url(doc_id)}")
        else:
            doc_id = _create_doc(docs_service, drive_service, symbol, folder_id)
            print(f"  [gdocs] Created new doc for {symbol}: {_doc_url(doc_id)}")
    except HttpError as exc:
        raise RuntimeError(_explain_http_error(exc)) from exc

    return doc_id, _doc_url(doc_id)


def prepend_analysis_to_doc(doc_id: str, analysis_text: str, report_date: str) -> None:
    """
    Prepend new analysis to the top of the Google Doc.

    New content is placed first; a dated separator line divides it from any
    previously stored analysis below.
    """
    docs_service, _ = _build_services()

    try:
        end_index = _get_doc_end_index(docs_service, doc_id)
        doc_is_empty = end_index <= 2  # A brand-new doc has endIndex == 1 or 2

        if doc_is_empty:
            # Document is empty — just insert the analysis text directly
            insert_text = analysis_text + "\n"
        else:
            # Document has existing content — prepend new analysis and add separator
            sep_line = SEPARATOR_CHAR * SEPARATOR_WIDTH
            separator = (
                f"\n\n{sep_line}\n"
                f"Analysis above generated on: {report_date}\n"
                f"{sep_line}\n\n"
            )
            insert_text = analysis_text + separator

        _prepend_text(docs_service, doc_id, insert_text)
        print(f"  [gdocs] Analysis prepended to doc (date: {report_date})")

    except HttpError as exc:
        raise RuntimeError(_explain_http_error(exc)) from exc
