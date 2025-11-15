import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from app.core.config import GoogleSpreadSheets

from dotenv import load_dotenv
load_dotenv(override=True)

gdocs_settings = GoogleSpreadSheets()

class GoogleDocsHelper:
    """A helper class to manage a single, pre-existing Google Doc."""
    def __init__(self):
        self.document_id = gdocs_settings.GOOGLE_DOC_ID
        if not self.document_id:
            raise ValueError("GOOGLE_DOC_ID is not set in the .env file.")
        
        self.doc_url = f"https://docs.google.com/document/d/{self.document_id}/edit"
        
        try:
            scopes = [
                "https://www.googleapis.com/auth/documents",
                "https://www.googleapis.com/auth/drive.file" 
            ]
            creds_path = gdocs_settings.GOOGLE_CREDENTIALS_FP
            self.creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
            self.docs_service = build('docs', 'v1', credentials=self.creds)
            print(f"Successfully connected to Google Docs API. Managing doc: {self.doc_url}")
        except FileNotFoundError:
            raise FileNotFoundError(f"Google credentials file not found at '{creds_path}'")
        except Exception as e:
            raise RuntimeError(f"An error occurred while connecting to Google APIs: {e}")

    def _get_doc_end_index(self) -> int:
        """Helper to get the last index of the document content."""
        document = self.docs_service.documents().get(documentId=self.document_id).execute()
        content = document.get('body', {}).get('content', [])
        if not content:
            return 1
        return content[-1].get('endIndex', 1)

    def write_to_doc(self, text: str, clear_before_writing: bool = False):
        """Writes text to the doc. Can clear the doc first."""
        if clear_before_writing:
            end_index = self._get_doc_end_index()
            if end_index > 2: 
                requests = [{'deleteContentRange': {'range': {'startIndex': 1, 'endIndex': end_index - 1}}}]
                self.docs_service.documents().batchUpdate(documentId=self.document_id, body={'requests': requests}).execute()

        requests = [{'insertText': {'location': {'index': 1}, 'text': text}}]
        self.docs_service.documents().batchUpdate(documentId=self.document_id, body={'requests': requests}).execute()
        print(f"Wrote content to the configured Google Doc.")

    def append_to_doc(self, text: str):
        """Appends text to the end of the document."""
        end_index = self._get_doc_end_index()
        requests = [{'insertText': {'location': {'index': end_index - 1}, 'text': text}}]
        self.docs_service.documents().batchUpdate(documentId=self.document_id, body={'requests': requests}).execute()
        print(f"Appended content to the configured Google Doc.")