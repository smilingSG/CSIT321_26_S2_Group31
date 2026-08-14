# Import filesystem utilities and UUID generation for temporary files.
import base64
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

# Define temporary storage folders, environment key name, and permitted upload extensions.
TEMP_UPLOAD_FOLDER: str = "temp_uploads"
ENCRYPTED_TEMP_FOLDER: str = "encrypted_temp_upload"
MASTER_KEY_ENV_NAME: str = "LAZARUS_MASTER_KEY"
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

    # Retrieve the deployment master key used to protect per-file AES keys.
    @staticmethod
    def getMasterKey() -> Optional[bytes]:

        master_key_text = os.environ.get(MASTER_KEY_ENV_NAME)

        if master_key_text is None:
            return None

        try:
            master_key = base64.urlsafe_b64decode(
                master_key_text.encode("utf-8")
            )
        except Exception:
            return None

        if len(master_key) != 32:
            return None

        return master_key

    # Encrypt a generated file key before saving it in the database.
    @staticmethod
    def wrapFileKey(file_key: bytes) -> Optional[bytes]:

        master_key = File.getMasterKey()

        if master_key is None:
            return None

        key_wrap_nonce = os.urandom(12)
        aesgcm = AESGCM(master_key)

        wrapped_file_key = aesgcm.encrypt(
            key_wrap_nonce,
            file_key,
            None
        )

        return key_wrap_nonce + wrapped_file_key

    # Decrypt a stored wrapped file key before file decryption.
    @staticmethod
    def unwrapFileKey(wrapped_file_key: bytes) -> Optional[bytes]:

        master_key = File.getMasterKey()

        if master_key is None or len(wrapped_file_key) <= 12:
            return None

        key_wrap_nonce = wrapped_file_key[:12]
        encrypted_file_key = wrapped_file_key[12:]
        aesgcm = AESGCM(master_key)

        try:
            return aesgcm.decrypt(
                key_wrap_nonce,
                encrypted_file_key,
                None
            )
        except Exception:
            return None

    # Validate and save an upload before creating its temporary database record.
    @staticmethod
    def createTempFileRecord(owner_id: int,
                             uploaded_file) -> Optional[int]:

        original_filename: str = secure_filename(uploaded_file.filename)

        if not File.isAllowedFileType(original_filename):
            return None

        file_extension: str = os.path.splitext(original_filename)[1]
        stored_filename: str = str(uuid.uuid4()) + file_extension
        temp_upload_path: str = os.path.join(
            TEMP_UPLOAD_FOLDER,
            stored_filename
        )

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

    # Retrieve processed files that can be shared by the owner.
    @staticmethod
    def getShareableFilesByOwner(owner_id: int) -> List[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                file_id,
                file_name
            FROM files
            WHERE owner_id = %s
            AND file_status = 'processed'
            ORDER BY uploaded_at DESC
        """, (owner_id,))

        file_records = cursor.fetchall()

        cursor.close()
        connection.close()

        return [
            {
                "fileID": file_record["file_id"],
                "fileName": file_record["file_name"]
            }
            for file_record in file_records
        ]

    # Confirm that a processed file belongs to a user before sharing it.
    @staticmethod
    def verifyFileOwnership(file_id: int,
                            owner_id: int) -> bool:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM files
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status = 'processed'
        """, (
            file_id,
            owner_id
        ))

        file_count = cursor.fetchone()[0]

        cursor.close()
        connection.close()

        return file_count == 1

    # Retrieve metadata needed for a recipient to reconstruct a shared file.
    @staticmethod
    def getSharedDownloadDetails(file_id: int) -> Optional[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                file_id,
                file_name,
                file_type,
                nonce,
                encrypted_file_key,
                encrypted_size,
                total_fragments,
                required_fragments,
                file_status
            FROM files
            WHERE file_id = %s
            AND file_status = 'processed'
        """, (file_id,))

        file_record = cursor.fetchone()

        cursor.close()
        connection.close()

        return file_record

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

    # Rename a processed file without allowing its extension to change.
    @staticmethod
    def updateName(owner_id: int,
                   file_id: int,
                   new_name: str) -> Optional[str]:

        new_name = secure_filename(new_name)

        if new_name == "":
            return "Please enter a file name."

        if not File.isAllowedFileType(new_name):
            return "File name must keep an allowed file extension."

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT file_name
            FROM files
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status = 'processed'
        """, (
            file_id,
            owner_id
        ))

        file_record = cursor.fetchone()

        cursor.close()
        connection.close()

        if file_record is None:
            return "Unable to rename file."

        original_extension = os.path.splitext(
            file_record["file_name"]
        )[1].lower()
        new_extension = os.path.splitext(new_name)[1].lower()

        if original_extension != new_extension:
            return "File extension cannot be changed."

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

        if total_fragments is None:
            return "Please enter total fragments."

        if required_fragments is None:
            return "Please enter required fragments."

        try:
            total_fragments = int(total_fragments)
            required_fragments = int(required_fragments)
        except ValueError:
            return "Fragment values must be numbers."

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
            return True

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

        file_key = AESGCM.generate_key(bit_length=256)
        wrapped_file_key = File.wrapFileKey(file_key)

        if wrapped_file_key is None:
            cursor.close()
            connection.close()
            return False

        aesgcm = AESGCM(file_key)
        nonce = os.urandom(12)

        with open(temp_upload_path, "rb") as input_file:
            file_data = input_file.read()

        encrypted_data = aesgcm.encrypt(
            nonce,
            file_data,
            None
        )

        with open(encrypted_temp_path, "wb") as output_file:
            output_file.write(encrypted_data)

        encrypted_size = os.path.getsize(encrypted_temp_path)

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
            wrapped_file_key,
            encrypted_size,
            file_id,
            owner_id
        ))

        connection.commit()

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

    # Retrieve the k-of-n requirement for reconstructing a processed file.
    @staticmethod
    def getReconstructionRequirement(file_id: int,
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
            AND file_status = 'processed'
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
            "fileStatus": file_record["file_status"].replace("_", " ").title(),
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

    # Authenticate reconstructed ciphertext before accepting a fragment set.
    @staticmethod
    def validateReconstructedFile(file_id: int,
                                  reconstructed_temp_path: str,
                                  owner_id: Optional[int] = None) -> bool:
        """Authenticate reconstructed ciphertext without deleting it."""

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT nonce, encrypted_file_key
            FROM files
            WHERE file_id = %s
            AND file_status = 'processed'
        """
        parameters = [file_id]

        if owner_id is not None:
            query += " AND owner_id = %s"
            parameters.append(owner_id)

        cursor.execute(query, tuple(parameters))
        file_record = cursor.fetchone()
        cursor.close()
        connection.close()

        if file_record is None or not reconstructed_temp_path:
            return False
        if not os.path.exists(reconstructed_temp_path):
            return False

        try:
            file_key = File.unwrapFileKey(
                bytes(file_record["encrypted_file_key"])
            )
            if file_key is None:
                return False

            with open(reconstructed_temp_path, "rb") as encrypted_file:
                encrypted_data = encrypted_file.read()

            AESGCM(file_key).decrypt(
                bytes(file_record["nonce"]),
                encrypted_data,
                None
            )
            return True
        except Exception:
            return False

    # Decrypt a reconstructed encrypted file using the file's AES-GCM metadata.
    @staticmethod
    def decryptFile(file_id: int,
                    owner_id: int,
                    reconstructed_temp_path: str) -> Optional[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                file_name,
                file_type,
                nonce,
                encrypted_file_key
            FROM files
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status = 'processed'
        """, (
            file_id,
            owner_id
        ))

        file_record = cursor.fetchone()

        cursor.close()
        connection.close()

        if file_record is None:
            return None

        if reconstructed_temp_path is None:
            return None

        if not os.path.exists(reconstructed_temp_path):
            return None

        try:
            nonce = bytes(file_record["nonce"])
            wrapped_file_key = bytes(file_record["encrypted_file_key"])
            file_key = File.unwrapFileKey(wrapped_file_key)

            if file_key is None:
                return None

            with open(reconstructed_temp_path, "rb") as encrypted_file:
                encrypted_data = encrypted_file.read()

            aesgcm = AESGCM(file_key)

            original_data = aesgcm.decrypt(
                nonce,
                encrypted_data,
                None
            )

            return {
                "fileName": file_record["file_name"],
                "fileType": file_record["file_type"] or "application/octet-stream",
                "fileBytes": original_data
            }

        except Exception:
            return None

        finally:
            if os.path.exists(reconstructed_temp_path):
                try:
                    os.remove(reconstructed_temp_path)
                except OSError:
                    pass

    # Decrypt reconstructed bytes already held in memory.
    @staticmethod
    def decryptReconstructedData(
        file_record: Dict[str, Any],
        encrypted_data: bytes
    ) -> Optional[Dict[str, Any]]:

        try:
            file_key = File.unwrapFileKey(
                bytes(file_record["encrypted_file_key"])
            )

            if file_key is None:
                return None

            original_data = AESGCM(file_key).decrypt(
                bytes(file_record["nonce"]),
                encrypted_data,
                None
            )

            return {
                "fileName": file_record["file_name"],
                "fileType": (
                    file_record["file_type"]
                    or "application/octet-stream"
                ),
                "fileBytes": original_data
            }

        except Exception:
            return None

    # Retrieve all metadata needed for an owner's combined recovery download.
    @staticmethod
    def getOwnerDownloadDetails(
        file_id: int,
        owner_id: int
    ) -> Optional[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                file_id,
                file_name,
                file_type,
                nonce,
                encrypted_file_key,
                encrypted_size,
                total_fragments,
                required_fragments
            FROM files
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status = 'processed'
        """, (
            file_id,
            owner_id
        ))

        file_record = cursor.fetchone()
        cursor.close()
        connection.close()

        return file_record

    # Decrypt a reconstructed shared file without requiring owner identity.
    @staticmethod
    def decryptSharedFile(file_id: int,
                          reconstructed_temp_path: str) -> Optional[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                file_name,
                file_type,
                nonce,
                encrypted_file_key
            FROM files
            WHERE file_id = %s
            AND file_status = 'processed'
        """, (file_id,))

        file_record = cursor.fetchone()

        cursor.close()
        connection.close()

        if file_record is None:
            return None

        if reconstructed_temp_path is None:
            return None

        if not os.path.exists(reconstructed_temp_path):
            return None

        try:
            nonce = bytes(file_record["nonce"])
            wrapped_file_key = bytes(file_record["encrypted_file_key"])
            file_key = File.unwrapFileKey(wrapped_file_key)

            if file_key is None:
                return None

            with open(reconstructed_temp_path, "rb") as encrypted_file:
                encrypted_data = encrypted_file.read()

            aesgcm = AESGCM(file_key)

            original_data = aesgcm.decrypt(
                nonce,
                encrypted_data,
                None
            )

            return {
                "fileName": file_record["file_name"],
                "fileType": file_record["file_type"] or "application/octet-stream",
                "fileBytes": original_data
            }

        except Exception:
            return None

        finally:
            if os.path.exists(reconstructed_temp_path):
                try:
                    os.remove(reconstructed_temp_path)
                except OSError:
                    pass

    # Retrieve delete details for a processed file belonging to the logged-in user.
    @staticmethod
    def getFileDeleteDetails(file_id: int,
                             owner_id: int) -> Optional[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                file_id,
                owner_id,
                file_name,
                file_status
            FROM files
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status = 'processed'
        """, (
            file_id,
            owner_id
        ))

        file_record = cursor.fetchone()

        cursor.close()
        connection.close()

        return file_record

    # Delete only the selected processed file record from the files table.
    @staticmethod
    def deleteFileRecord(file_id: int,
                         owner_id: int) -> bool:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM files
            WHERE file_id = %s
            AND owner_id = %s
            AND file_status = 'processed'
        """, (
            file_id,
            owner_id
        ))

        deleted = cursor.rowcount == 1
        connection.commit()

        cursor.close()
        connection.close()

        return deleted

    @staticmethod
    def getFileIdsByOwner(owner_id: int) -> list:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            SELECT file_id
            FROM files
            WHERE owner_id = %s
            ORDER BY file_id
        """, (owner_id,))
        file_ids = [record[0] for record in cursor.fetchall()]
        cursor.close()
        connection.close()
        return file_ids

    @staticmethod
    def deleteFilesByOwner(owner_id: int) -> bool:
        connection = None
        cursor = None
        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT temp_upload_path, encrypted_temp_path
                FROM files
                WHERE owner_id = %s
            """, (owner_id,))
            temporary_paths = []
            for record in cursor.fetchall():
                temporary_paths.extend([
                    record["temp_upload_path"],
                    record["encrypted_temp_path"]
                ])
            cursor.execute("""
                DELETE FROM files
                WHERE owner_id = %s
            """, (owner_id,))
            connection.commit()

            for temporary_path in set(temporary_paths):
                if temporary_path is None:
                    continue
                try:
                    if os.path.isfile(temporary_path):
                        os.remove(temporary_path)
                except OSError:
                    pass
            return True
        except Exception:
            return False
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()
