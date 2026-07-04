# Import filesystem utilities and UUID generation for temporary upload sessions.
import os
import uuid

# Import filename sanitisation for safe local file paths.
from werkzeug.utils import secure_filename

# Import type hints used by the entity methods.
from typing import Optional
from typing import Dict
from typing import Any

# Import the application's MySQL connection function.
from db import get_db_connection

# Import the File entity so upload sessions reuse the same file type rules.
from entities.File import File


# Define the folder used to store temporary upload-session files.
TEMP_UPLOAD_FOLDER: str = "temp_uploads"

# Create the temporary upload folder if it does not already exist.
os.makedirs(TEMP_UPLOAD_FOLDER, exist_ok=True)


# Represent upload-session records and handle resumable upload storage.
class UploadSession:

    # Create a new upload session before the first file chunk is received.
    @staticmethod
    def startUpload(user_id: int,
                    file_name: str,
                    total_size: int) -> Optional[Dict[str, Any]]:

        original_filename: str = secure_filename(file_name)

        if not File.isAllowedFileType(original_filename):
            return None

        file_extension: str = os.path.splitext(original_filename)[1]
        stored_filename: str = str(uuid.uuid4()) + file_extension
        temp_upload_path: str = os.path.join(
            TEMP_UPLOAD_FOLDER,
            stored_filename
        )

        # Create an empty temporary file so chunks can be appended later.
        open(temp_upload_path, "wb").close()

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            cursor.execute("""
                INSERT INTO upload_sessions
                (
                    user_id,
                    file_name,
                    temp_upload_path,
                    total_size,
                    bytes_uploaded,
                    upload_status
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                user_id,
                original_filename,
                temp_upload_path,
                total_size,
                0,
                "uploading"
            ))

            connection.commit()

            return {
                "uploadID": cursor.lastrowid,
                "fileName": original_filename,
                "bytesUploaded": 0,
                "totalSize": total_size
            }

        except Exception:
            if os.path.exists(temp_upload_path):
                os.remove(temp_upload_path)
            raise

        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    # Save the next uploaded chunk and update the stored progress value.
    @staticmethod
    def saveChunk(upload_id: int,
                  user_id: int,
                  chunk_file,
                  chunk_start: int) -> Optional[Dict[str, Any]]:

        upload_session = UploadSession.retrieveProgress(
            upload_id,
            user_id
        )

        if upload_session is None:
            return None

        if upload_session["uploadStatus"] in ["completed", "cancelled"]:
            return None

        if chunk_start != upload_session["bytesUploaded"]:
            return None

        temp_upload_path: str = upload_session["tempUploadPath"]
        chunk_data = chunk_file.read()
        new_bytes_uploaded: int = chunk_start + len(chunk_data)

        with open(temp_upload_path, "ab") as temporary_file:
            temporary_file.write(chunk_data)

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            cursor.execute("""
                UPDATE upload_sessions
                SET
                    bytes_uploaded = %s,
                    upload_status = 'uploading'
                WHERE upload_id = %s
                AND user_id = %s
                AND upload_status IN ('uploading', 'paused')
            """, (
                new_bytes_uploaded,
                upload_id,
                user_id
            ))

            connection.commit()

            if cursor.rowcount == 0:
                return None

            return {
                "uploadID": upload_id,
                "bytesUploaded": new_bytes_uploaded,
                "totalSize": upload_session["totalSize"]
            }

        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    # Save the latest progress when the user pauses the upload.
    @staticmethod
    def saveProgress(upload_id: int,
                     user_id: int) -> bool:

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            cursor.execute("""
                UPDATE upload_sessions
                SET upload_status = 'paused'
                WHERE upload_id = %s
                AND user_id = %s
                AND upload_status = 'uploading'
            """, (
                upload_id,
                user_id
            ))

            connection.commit()
            return cursor.rowcount > 0

        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    # Retrieve the latest upload progress for resume handling.
    @staticmethod
    def retrieveProgress(upload_id: int,
                         user_id: int) -> Optional[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                upload_id,
                user_id,
                file_id,
                file_name,
                temp_upload_path,
                total_size,
                bytes_uploaded,
                upload_status
            FROM upload_sessions
            WHERE upload_id = %s
            AND user_id = %s
        """, (
            upload_id,
            user_id
        ))

        upload_session = cursor.fetchone()

        cursor.close()
        connection.close()

        if upload_session is None:
            return None

        return {
            "uploadID": upload_session["upload_id"],
            "userID": upload_session["user_id"],
            "fileID": upload_session["file_id"],
            "fileName": upload_session["file_name"],
            "tempUploadPath": upload_session["temp_upload_path"],
            "totalSize": upload_session["total_size"],
            "bytesUploaded": upload_session["bytes_uploaded"],
            "uploadStatus": upload_session["upload_status"]
        }

    # Mark a paused upload as uploading again before chunks continue.
    @staticmethod
    def continueUpload(upload_id: int,
                       user_id: int) -> bool:

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            cursor.execute("""
                UPDATE upload_sessions
                SET upload_status = 'uploading'
                WHERE upload_id = %s
                AND user_id = %s
                AND upload_status = 'paused'
            """, (
                upload_id,
                user_id
            ))

            connection.commit()
            return cursor.rowcount > 0

        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    # Convert a completed upload session into the normal temporary file record.
    @staticmethod
    def completeUpload(upload_id: int,
                       user_id: int,
                       file_type: str) -> Optional[int]:

        upload_session = UploadSession.retrieveProgress(
            upload_id,
            user_id
        )

        if upload_session is None:
            return None

        if upload_session["bytesUploaded"] != upload_session["totalSize"]:
            return None

        temp_upload_path: str = upload_session["tempUploadPath"]
        stored_filename: str = os.path.basename(temp_upload_path)
        file_size: int = os.path.getsize(temp_upload_path)

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            cursor.execute("""
                INSERT INTO files
                (
                    owner_id,
                    file_name,
                    stored_filename,
                    file_size,
                    file_type,
                    temp_upload_path,
                    file_status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id,
                upload_session["fileName"],
                stored_filename,
                file_size,
                file_type or "Unknown",
                temp_upload_path,
                "pending_confirmation"
            ))

            file_id = cursor.lastrowid

            cursor.execute("""
                UPDATE upload_sessions
                SET upload_status = 'completed'
                WHERE upload_id = %s
                AND user_id = %s
            """, (
                upload_id,
                user_id
            ))

            connection.commit()
            return file_id

        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    # Cancel an incomplete upload session and remove its temporary file.
    @staticmethod
    def cancelUpload(upload_id: int,
                     user_id: int) -> bool:

        upload_session = UploadSession.retrieveProgress(
            upload_id,
            user_id
        )

        if upload_session is None:
            return False

        temp_upload_path: str = upload_session["tempUploadPath"]

        if os.path.exists(temp_upload_path):
            os.remove(temp_upload_path)

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            cursor.execute("""
                UPDATE upload_sessions
                SET upload_status = 'cancelled'
                WHERE upload_id = %s
                AND user_id = %s
            """, (
                upload_id,
                user_id
            ))

            connection.commit()
            return cursor.rowcount > 0

        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()
