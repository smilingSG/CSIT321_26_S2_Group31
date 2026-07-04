# Import filesystem utilities and UUID generation for temporary files.
import os
import uuid

# Import the trusted AES-GCM implementation used for file encryption.
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from werkzeug.utils import secure_filename

# Import type hints used by the entity methods.
from typing import Optional
from typing import Dict
from typing import Any
from typing import List

# Import the application's MySQL connection function.
from db import get_db_connection

# Define temporary storage folders and permitted upload extensions.
TEMP_UPLOAD_FOLDER: str = "temp_uploads"
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

# Create both temporary storage folders if they do not already exist.
os.makedirs(TEMP_UPLOAD_FOLDER, exist_ok=True)
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

    # Validate and save an upload before creating its temporary database record.
    @staticmethod
    def createTempFileRecord(owner_id: int,
                             uploaded_file) -> Optional[int]:

        # Sanitise the supplied filename and reject unsupported extensions.
        original_filename: str = secure_filename(uploaded_file.filename)

        if not File.isAllowedFileType(original_filename):
            return None

        # Generate a unique local filename while preserving the extension.
        file_extension: str = os.path.splitext(original_filename)[1]
        stored_filename: str = str(uuid.uuid4()) + file_extension
        temp_upload_path: str = os.path.join(
            TEMP_UPLOAD_FOLDER,
            stored_filename
        )

        # Save the physical upload and collect the metadata stored in MySQL.
        uploaded_file.save(temp_upload_path)
        file_size: int = os.path.getsize(temp_upload_path)
        file_type: str = uploaded_file.content_type or "Unknown"

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
                owner_id,
                original_filename,
                stored_filename,
                file_size,
                file_type,
                temp_upload_path,
                "pending_confirmation"
            ))

            connection.commit()
            return cursor.lastrowid

        # Remove the physical upload if its metadata cannot be recorded.
        except Exception:
            if os.path.exists(temp_upload_path):
                os.remove(temp_upload_path)
            raise

        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

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

    # Retrieve processed files belonging to a user for file management.
    @staticmethod
    def getManagedFilesByOwner(owner_id: int) -> List[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                file_id,
                file_name,
                file_size,
                file_status,
                uploaded_at
            FROM files
            WHERE owner_id = %s
            AND file_status = 'processed'
            ORDER BY uploaded_at DESC
        """, (
            owner_id,
        ))

        file_records = cursor.fetchall()

        cursor.close()
        connection.close()

        managed_files = []

        for file_record in file_records:
            file_size_mb = file_record["file_size"] / (1024 * 1024)

            managed_files.append({
                "fileID": file_record["file_id"],
                "fileName": file_record["file_name"],
                "fileSize": str(round(file_size_mb, 1)) + " MB",
                "fileStatus": file_record["file_status"].replace("_", " ").title(),
                "uploadedAt": file_record["uploaded_at"].strftime("%Y-%m-%d")
            })

        return managed_files

    # Search processed files belonging to a user by file name.
    @staticmethod
    def searchManagedFilesByName(owner_id: int,
                                 search_query: str) -> List[Dict[str, Any]]:

        search_query = search_query.strip()

        if search_query == "":
            return File.getManagedFilesByOwner(owner_id)

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                file_id,
                file_name,
                file_size,
                file_status,
                uploaded_at
            FROM files
            WHERE owner_id = %s
            AND file_status = 'processed'
            AND file_name LIKE %s
            ORDER BY uploaded_at DESC
        """, (
            owner_id,
            "%" + search_query + "%"
        ))

        file_records = cursor.fetchall()

        cursor.close()
        connection.close()

        managed_files = []

        for file_record in file_records:
            file_size_mb = file_record["file_size"] / (1024 * 1024)

            managed_files.append({
                "fileID": file_record["file_id"],
                "fileName": file_record["file_name"],
                "fileSize": str(round(file_size_mb, 1)) + " MB",
                "fileStatus": file_record["file_status"].replace("_", " ").title(),
                "uploadedAt": file_record["uploaded_at"].strftime("%Y-%m-%d")
            })

        return managed_files

    # Check whether another managed file already uses the requested name.
    @staticmethod
    def checkNameExists(owner_id: int,
                        file_id: int,
                        new_name: str) -> bool:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM files
            WHERE owner_id = %s
            AND file_id != %s
            AND file_name = %s
            AND file_status = 'processed'
        """, (
            owner_id,
            file_id,
            new_name
        ))

        count = cursor.fetchone()[0]

        cursor.close()
        connection.close()

        return count > 0

    # Rename a processed file after checking that the new name is not in use.
    @staticmethod
    def updateName(owner_id: int,
                   file_id: int,
                   new_name: str) -> Optional[str]:

        new_name = secure_filename(new_name)

        if new_name == "":
            return "Please enter a file name."

        if not File.isAllowedFileType(new_name):
            return "File name must keep an allowed file extension."

        if File.checkNameExists(owner_id, file_id, new_name):
            return "Name in use."

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE files
            SET file_name = %s
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status = 'processed'
        """, (
            new_name,
            file_id,
            owner_id
        ))

        updated = cursor.rowcount == 1
        connection.commit()

        cursor.close()
        connection.close()

        if not updated:
            return "Unable to rename file."

        return None

    # Validate and save the selected k-of-n fragment configuration.
    @staticmethod
    def updateFragmentConfiguration(file_id: int,
                                    owner_id: int,
                                    total_fragments,
                                    required_fragments,
                                    active_node_count: int) -> Optional[str]:

        # Ensure both form values were supplied and contain integers.
        if total_fragments is None:
            return "Please enter total fragments."

        if required_fragments is None:
            return "Please enter required fragments."

        try:
            total_fragments = int(total_fragments)
            required_fragments = int(required_fragments)
        except ValueError:
            return "Fragment values must be numbers."

        # Apply the k-of-n rules before updating the database.
        if total_fragments < 2:
            return "Total fragments must be at least 2."

        if required_fragments < 1:
            return "Required fragments must be at least 1."

        if required_fragments > total_fragments:
            return (
                "Required fragments cannot be greater "
                "than total fragments."
            )

        if total_fragments > active_node_count:
            return (
                "Total fragments cannot be greater "
                "than the number of active storage nodes."
            )

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

        updated = cursor.rowcount == 1
        connection.commit()

        cursor.close()
        connection.close()

        if not updated:
            return "File record could not be updated."

        return None

    # Delete an unconfirmed physical file and its database record.
    @staticmethod
    def deleteTempFileRecord(file_id: int,
                             owner_id: int) -> bool:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT temp_upload_path
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

        # Remove the physical temporary upload before deleting its metadata.
        temp_upload_path = file_record["temp_upload_path"]

        if temp_upload_path is not None and os.path.exists(temp_upload_path):
            try:
                os.remove(temp_upload_path)
            except OSError:
                cursor.close()
                connection.close()
                return False

        cursor.execute("""
            DELETE FROM files
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status = 'pending_confirmation'
        """, (
            file_id,
            owner_id
        ))

        deleted = cursor.rowcount == 1
        connection.commit()

        cursor.close()
        connection.close()

        return deleted

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

    # Remove an unconfirmed physical file and its database record.
    @staticmethod
    def removeFile(file_id: int,
                   owner_id: int) -> bool:

        return File.deleteTempFileRecord(
            file_id,
            owner_id
        )

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

    # Retrieve summary information for the processing boundary.
    @staticmethod
    def getProcessingSummary(file_id: int,
                             owner_id: int) -> Optional[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                file_id,
                file_name,
                file_status,
                total_fragments,
                required_fragments,
                encrypted_size
            FROM files
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status IN (
                'encrypted',
                'pending_processing',
                'processed',
                'failed'
            )
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
            "fileStatus": file_record["file_status"],
            "totalFragments": file_record["total_fragments"],
            "requiredFragments": file_record["required_fragments"],
            "encryptedSize": file_record["encrypted_size"]
        }

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

    # Delete incomplete processing data and its encrypted temporary file.
    @staticmethod
    def deleteProcessingFileRecord(file_id: int,
                                   owner_id: int) -> bool:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT encrypted_temp_path
            FROM files
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status IN ('encrypted', 'pending_processing', 'failed')
        """, (
            file_id,
            owner_id
        ))

        file_record = cursor.fetchone()

        if file_record is None:
            cursor.close()
            connection.close()
            return False

        # Remove the temporary ciphertext before deleting its metadata.
        encrypted_temp_path = file_record["encrypted_temp_path"]

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
            DELETE FROM files
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status IN ('encrypted', 'pending_processing', 'failed')
        """, (
            file_id,
            owner_id
        ))

        deleted = cursor.rowcount == 1
        connection.commit()

        cursor.close()
        connection.close()

        return deleted

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

        if encrypted_temp_path is not None and os.path.exists(encrypted_temp_path):
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

        updated = cursor.rowcount == 1
        connection.commit()

        cursor.close()
        connection.close()

        return updated
