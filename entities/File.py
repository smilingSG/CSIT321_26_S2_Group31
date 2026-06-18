# Import filesystem utilities used to manage temporary files.
import os

# Import the trusted AES-GCM implementation used for file encryption.
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Import type hints used by the entity methods.
from typing import Optional
from typing import Dict
from typing import Any

# Import the application's MySQL connection function.
from db import get_db_connection

# Define the temporary encrypted-file folder and permitted upload extensions.
ENCRYPTED_TEMP_FOLDER: str = "encrypted_temp_upload"
ALLOWED_EXTENSIONS = {
    "pdf",
    "doc",
    "docx",
    "txt",
    "xls",
    "xlsx",
    "csv",
    "ppt",
    "pptx",
    "jpg",
    "jpeg",
    "png",
    "zip"
}

# Create the encrypted temporary-file folder if it does not already exist.
os.makedirs(ENCRYPTED_TEMP_FOLDER, exist_ok=True)


# Represent file records and perform file-related database and storage operations.
class File:

    # Check whether the uploaded filename has an allowed extension.
    @staticmethod
    def isAllowedFileType(file_name: str) -> bool:

        return (
            "." in file_name
            and file_name.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
        )

    # Validate an upload and create its temporary database record.
    @staticmethod
    def createTempFileRecord(owner_id: int,
                             file_name: str,
                             stored_filename: str,
                             file_size: int,
                             file_type: str,
                             temp_upload_path: str) -> Optional[int]:

        # Reject unsupported file types before inserting a database record.
        if not File.isAllowedFileType(file_name):
            return None

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
            owner_id,
            file_name,
            stored_filename,
            file_size,
            file_type,
            temp_upload_path,
            "pending_confirmation"
        ))

        connection.commit()

        file_id = cursor.lastrowid

        cursor.close()
        connection.close()

        return file_id

    # Retrieve and format file information for the preview boundary.
    @staticmethod
    def getFilePreviewDetails(file_id: int,
                              owner_id: int) -> Optional[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                file_id,
                file_name,
                file_size,
                file_type,
                total_fragments,
                required_fragments,
                file_status,
                uploaded_at
            FROM files
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status = 'pending_confirmation'
        """, (
            file_id,
            owner_id
        ))

        file_record = cursor.fetchone()

        cursor.close()
        connection.close()

        if file_record is None:
            return None

        # Convert the stored byte count into a readable kilobyte value.
        file_size_kb = round(
            file_record["file_size"] / 1024,
            2
        )

        return {
            "fileID": file_record["file_id"],
            "fileName": file_record["file_name"],
            "fileSize": str(file_size_kb) + " KB",
            "fileType": file_record["file_type"],
            "totalFragments": file_record["total_fragments"],
            "requiredFragments": file_record["required_fragments"],
            "fileStatus": file_record["file_status"],
            "uploadedAt": str(file_record["uploaded_at"])
        }

    # Retrieve an unconfirmed temporary file belonging to a user.
    @staticmethod
    def getTempFileById(file_id: int,
                        owner_id: int) -> Optional[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                file_id,
                stored_filename,
                temp_upload_path,
                file_status
            FROM files
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status = 'pending_confirmation'
        """, (
            file_id,
            owner_id
        ))

        file_record = cursor.fetchone()

        cursor.close()
        connection.close()

        return file_record

    # Save the selected k-of-n fragment configuration for a file.
    @staticmethod
    def updateFragmentConfiguration(file_id: int,
                                    owner_id: int,
                                    total_fragments: int,
                                    required_fragments: int) -> None:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE files
            SET
                total_fragments = %s,
                required_fragments = %s
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status = 'pending_confirmation'
        """, (
            total_fragments,
            required_fragments,
            file_id,
            owner_id
        ))

        connection.commit()

        cursor.close()
        connection.close()

    # Delete an unconfirmed temporary file record from the database.
    @staticmethod
    def deleteTempFileRecord(file_id: int,
                             owner_id: int) -> None:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM files
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status = 'pending_confirmation'
        """, (
            file_id,
            owner_id
        ))

        connection.commit()

        cursor.close()
        connection.close()

    # Count the successfully processed files belonging to a user.
    @staticmethod
    def countProcessedFilesByOwner(owner_id: int) -> int:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM files
            WHERE owner_id = %s
            AND file_status = 'processed'
        """, (owner_id,))

        count = cursor.fetchone()[0]

        cursor.close()
        connection.close()

        return count

    # Remove an unconfirmed file record belonging to a user.
    @staticmethod
    def removeFile(file_id: int,
                   owner_id: int) -> None:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM files
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status = 'pending_confirmation'
        """, (
            file_id,
            owner_id
        ))

        connection.commit()

        cursor.close()
        connection.close()

    # Encrypt a confirmed temporary file using AES-256-GCM.
    @staticmethod
    def encryptFile(file_id: int,
                    owner_id: int) -> bool:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                file_id,
                stored_filename,
                temp_upload_path,
                file_status
            FROM files
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status = 'pending_confirmation'
        """, (
            file_id,
            owner_id
        ))

        file_record = cursor.fetchone()

        if file_record is None:
            cursor.close()
            connection.close()
            return False

        temp_upload_path = file_record["temp_upload_path"]
        stored_filename = file_record["stored_filename"]

        if temp_upload_path is None:
            cursor.close()
            connection.close()
            return False

        if not os.path.exists(temp_upload_path):
            cursor.close()
            connection.close()
            return False

        encrypted_filename = stored_filename + ".enc"

        encrypted_temp_path = os.path.join(
            ENCRYPTED_TEMP_FOLDER,
            encrypted_filename
        )

        # Generate a new 256-bit AES key for this file.
        file_key = AESGCM.generate_key(bit_length=256)
        aesgcm = AESGCM(file_key)

        # Generate the recommended 12-byte nonce for AES-GCM.
        nonce = os.urandom(12)

        # Read the original temporary file as binary data.
        with open(temp_upload_path, "rb") as input_file:
            file_data = input_file.read()

        # Encrypt the data and append the GCM authentication tag.
        encrypted_data = aesgcm.encrypt(
            nonce,
            file_data,
            None
        )

        # Write the authenticated ciphertext to temporary encrypted storage.
        with open(encrypted_temp_path, "wb") as output_file:
            output_file.write(encrypted_data)

        encrypted_size = os.path.getsize(encrypted_temp_path)

        # Store the encryption metadata and advance the file status.
        # The prototype currently stores the raw file key in MySQL.
        cursor.execute("""
            UPDATE files
            SET
                encrypted_temp_path = %s,
                nonce = %s,
                encrypted_file_key = %s,
                encrypted_size = %s,
                temp_upload_path = NULL,
                file_status = 'encrypted'
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status = 'pending_confirmation'
        """, (
            encrypted_temp_path,
            nonce,
            file_key,
            encrypted_size,
            file_id,
            owner_id
        ))

        connection.commit()

        # Remove the original readable file after encryption succeeds.
        if os.path.exists(temp_upload_path):
            os.remove(temp_upload_path)

        cursor.close()
        connection.close()

        return True

    # Retrieve the encrypted-file path and k-of-n values for fragmentation.
    @staticmethod
    def getEncryptedFileDetails(file_id: int,
                                owner_id: int) -> Optional[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                file_id,
                encrypted_temp_path,
                total_fragments,
                required_fragments,
                file_status
            FROM files
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status = 'encrypted'
        """, (
            file_id,
            owner_id
        ))

        file_record = cursor.fetchone()

        cursor.close()
        connection.close()

        return file_record

    # Retrieve a file that is currently in the processing workflow.
    @staticmethod
    def getProcessingFileDetails(file_id: int,
                                 owner_id: int) -> Optional[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                file_id,
                encrypted_temp_path,
                file_status
            FROM files
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status IN ('encrypted', 'pending_processing', 'failed')
        """, (
            file_id,
            owner_id
        ))

        file_record = cursor.fetchone()

        cursor.close()
        connection.close()

        return file_record

    # Update the current processing status of a file.
    @staticmethod
    def updateFileStatus(file_id: int,
                         owner_id: int,
                         file_status: str) -> None:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE files
            SET file_status = %s
            WHERE file_id = %s
            AND owner_id = %s
        """, (
            file_status,
            file_id,
            owner_id
        ))

        connection.commit()

        cursor.close()
        connection.close()

    # Delete an incomplete or failed processing record.
    @staticmethod
    def deleteProcessingFileRecord(file_id: int,
                                   owner_id: int) -> None:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM files
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status IN ('encrypted', 'pending_processing', 'failed')
        """, (
            file_id,
            owner_id
        ))

        connection.commit()

        cursor.close()
        connection.close()

    # Delete temporary ciphertext after permanent fragment storage succeeds.
    @staticmethod
    def deleteEncryptedTemporaryFile(file_id: int,
                                     owner_id: int) -> bool:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT encrypted_temp_path
            FROM files
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status = 'pending_processing'
        """, (
            file_id,
            owner_id
        ))

        file_record = cursor.fetchone()

        if file_record is None:
            cursor.close()
            connection.close()
            return False

        encrypted_temp_path = file_record["encrypted_temp_path"]

        # Remove the temporary encrypted file when a valid path exists.
        if (
            encrypted_temp_path is not None
            and os.path.exists(encrypted_temp_path)
        ):
            try:
                os.remove(encrypted_temp_path)
            except OSError:
                cursor.close()
                connection.close()
                return False

        cursor.execute("""
            UPDATE files
            SET encrypted_temp_path = NULL
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status = 'pending_processing'
        """, (
            file_id,
            owner_id
        ))

        connection.commit()

        cursor.close()
        connection.close()

        return True

    # Retrieve and format file information for the processing boundary.
    @staticmethod
    def getProcessingSummary(file_id: int,
                             owner_id: int) -> Optional[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                file_id,
                file_name,
                total_fragments,
                required_fragments,
                file_status,
                encrypted_temp_path,
                encrypted_size
            FROM files
            WHERE file_id = %s
            AND owner_id = %s
        """, (
            file_id,
            owner_id
        ))

        file_record = cursor.fetchone()

        cursor.close()
        connection.close()

        if file_record is None:
            return None

        return {
            "fileID": file_record["file_id"],
            "fileName": file_record["file_name"],
            "totalFragments": file_record["total_fragments"],
            "requiredFragments": file_record["required_fragments"],
            "fileStatus": file_record["file_status"],
            "encryptedTempPath": file_record["encrypted_temp_path"],
            "encryptedSize": file_record["encrypted_size"]
        }
