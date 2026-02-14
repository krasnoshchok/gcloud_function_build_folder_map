import os
import io
import json
import re
import functions_framework
import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from typing import Dict

# --- CONFIGURATION ---
# It is still good practice to keep these as simple Env Vars (non-sensitive)
# or you can hardcode them if they never change.
SHARED_DRIVE_FOLDER = os.environ.get("SHARED_DRIVE_FOLDER")
SHARED_DRIVE_ID = os.environ.get("SHARED_DRIVE_ID")
SCOPES = ['https://www.googleapis.com/auth/drive']

class GoogleDriveRPA:
    def __init__(self):
        """
        Initializes the Drive service using the identity assigned 
        to the Cloud Function/Cloud Run resource.
        """
        try:
            # This line automatically picks up the service account from the 'Security' tab
            self._creds, self.project_id = google.auth.default(scopes=SCOPES)
            self._service = build('drive', 'v3', credentials=self._creds)
            print("Successfully authenticated using Ambient Service Account Identity")
        except Exception as e:
            print(f"Failed to initialize Google Drive client: {e}")
            raise

    def build_folder_path_map(self) -> Dict[str, Dict]:
        print(f"Building folder map for drive ID: {SHARED_DRIVE_ID}")
        folder_map = {}
        page_token = None
        query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
        
        while True:
            results = self._service.files().list(
                q=query,
                corpora="drive",
                driveId=SHARED_DRIVE_ID,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                fields="nextPageToken, files(id, name, parents)",
                pageSize=1000,
                pageToken=page_token
            ).execute()

            folders = results.get('files', [])
            for folder in folders:
                parent_id = folder.get('parents', [None])[0]
                folder_map[folder['id']] = {'name': folder['name'], 'parent': parent_id}

            page_token = results.get('nextPageToken', None)
            if page_token is None:
                break

        print(f"Built folder map with {len(folder_map)} folders")
        return folder_map

    def upload_map_to_drive(self, folder_id: str, filename: str, map_data: Dict):
        print(f"Preparing to upload map to folder: {folder_id}")

        content_str = json.dumps(map_data, indent=4)
        fh = io.BytesIO(content_str.encode('utf-8'))
        media = MediaIoBaseUpload(fh, mimetype='text/plain', resumable=True)

        # Check if file already exists
        query = f"name = '{filename}' and '{folder_id}' in parents and trashed = false"
        search_response = self._service.files().list(
            q=query,
            fields='files(id)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        existing_files = search_response.get('files', [])

        if existing_files:
            file_id = existing_files[0]['id']
            print(f"Updating existing file: {file_id}")
            updated_file = self._service.files().update(
                fileId=file_id,
                media_body=media,
                fields='id',
                supportsAllDrives=True
            ).execute()
            return updated_file.get('id')
        else:
            print(f"Creating new file '{filename}'")
            file_metadata = {
                'name': filename,
                'parents': [folder_id],
                'mimeType': 'text/plain'
            }
            created_file = self._service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id',
                supportsAllDrives=True
            ).execute()
            return created_file.get('id')

@functions_framework.http
def main(request):
    """
    HTTP Cloud Function Entry Point.
    """
    print("Cloud Function execution started.")
    
    try:
        # Initialize with Ambient Credentials
        gdrive = GoogleDriveRPA()

        # Build the map
        gdrive_folder_map = gdrive.build_folder_path_map()

        # Upload the map
        file_id = gdrive.upload_map_to_drive(
            folder_id=SHARED_DRIVE_FOLDER,
            filename="folder_map.txt",
            map_data=gdrive_folder_map
        )
        
        return {
            "status": "success",
            "message": f"Map updated successfully",
            "file_id": file_id
        }, 200

    except Exception as e:
        print(f"Error executing function: {str(e)}")
        return {"status": "error", "message": str(e)}, 500
