import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from app.core.config import GoogleSpreadSheets

from dotenv import load_dotenv
load_dotenv(override=True)

gdocs_settings = GoogleSpreadSheets()

class GoogleDocsHelper:
    """A helper class to manage a collection of Google Docs as if they were 'tabs'.

    NOTE: The Docs API endpoint you're using doesn't accept `insertTab`/`updateTabProperties`
    requests. To stay compatible with the rest of your code we create separate Google Doc
    files for each logical 'tab' (Outline, Chapter 1, Final Manuscript, ...).
    """
    def __init__(self):
        self.document_id = gdocs_settings.GOOGLE_DOC_ID
        if not self.document_id:
            raise ValueError("GOOGLE_DOC_ID is not set in the .env file.")
        
        self.doc_url = f"https://docs.google.com/document/d/{self.document_id}/edit"
        
        try:
            # Add Drive scope because we may create/delete documents.
            scopes = [
                "https://www.googleapis.com/auth/documents",
                "https://www.googleapis.com/auth/drive"
            ]
            creds_path = gdocs_settings.GOOGLE_CREDENTIALS_FP
            self.creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
            self.docs_service = build('docs', 'v1', credentials=self.creds)
            # Drive service used only for file-level operations (e.g., trashing a doc).
            self.drive_service = build('drive', 'v3', credentials=self.creds)
            print(f"Successfully connected to Google Docs API. Managing doc: {self.doc_url}")
        except FileNotFoundError:
            raise FileNotFoundError(f"Google credentials file not found at '{creds_path}'")
        except Exception as e:
            raise RuntimeError(f"An error occurred while connecting to Google APIs: {e}")

    # -----------------------
    # Document helpers
    # -----------------------
    def get_document(self, document_id: str = None, include_tabs_content: bool = False):
        """Fetches a document. By default fetches the primary document_id from config."""
        doc_id = document_id or self.document_id
        # keep include_tabs_content parameter for compatibility with callers, but most docs don't use 'tabs'
        return self.docs_service.documents().get(
            documentId=doc_id,
            includeTabsContent=include_tabs_content
        ).execute()

    def get_first_tab_id(self) -> str:
        """Compatibility helper: returns the primary document id (no real 'tab' concept)."""
        # Historically callers expected a 'tab id'. The safest fallback is to return the main document id.
        return self.document_id

    # -----------------------
    # Tab management (implemented as separate Google Docs)
    # -----------------------
    def create_tab(self, title: str) -> str:
        """Create a NEW Google Document and return its documentId.

        This acts as a 'tab' for your workflow (Outline, Chapter N, Final Manuscript).
        """
        body = {"title": title}
        response = self.docs_service.documents().create(body=body).execute()
        new_doc_id = response.get("documentId")
        print(f"Created new document (tab) '{title}' with ID: {new_doc_id}")
        return new_doc_id

    def delete_tab(self, tab_doc_id: str):
        """Trash the Google Document that represents a 'tab' (uses Drive API)."""
        try:
            # Move the file to trash
            self.drive_service.files().update(fileId=tab_doc_id, body={"trashed": True}).execute()
            print(f"Trashed document (tab) ID {tab_doc_id}")
        except Exception as e:
            # Don't re-raise: keep behavior non-breaking; just surface info.
            print(f"Warning: failed to trash document {tab_doc_id}: {e}")

    # -----------------------
    # Content writing
    # -----------------------
    def clear_and_write_to_tab(self, tab_id: str, text: str):
        """Clear all content from the document indicated by tab_id (documentId) and write new text."""
        # Treat tab_id as a documentId (because each logical tab is a separate Google Doc)
        doc = self.get_document(document_id=tab_id)
        body_content = doc.get('body', {}).get('content', [])

        requests = []

        # Delete previous content if any
        if body_content:
            # last element holds endIndex for the document body
            last_end = body_content[-1].get('endIndex', 1)
            # Only delete if there's content beyond the initial structural element(s)
            if last_end > 1:
                requests.append({
                    'deleteContentRange': {
                        'range': {
                            'startIndex': 1,
                            'endIndex': last_end - 1
                        }
                    }
                })

        # Insert new text at index 1
        requests.append({
            'insertText': {
                'location': {
                    'index': 1
                },
                'text': text
            }
        })

        if requests:
            self.docs_service.documents().batchUpdate(
                documentId=tab_id,
                body={'requests': requests}
            ).execute()
        print(f"Wrote content to document (tab) ID {tab_id}.")
