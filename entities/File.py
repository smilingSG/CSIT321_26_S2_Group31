import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from typing import Optional
from typing import Dict
from typing import Any

from db import get_db_connection

ENCRYPTED_TEMP_FOLDER: str = "encrypted_temp_upload"

os.makedirs(ENCRYPTED_TEMP_FOLDER, exist_ok=True)

class File:

    @staticmethod
    def createTempFileRecord(owner_id: int,
                            file_name: str,
                            stored_filename: str,
                            file_size: int,
                            file_type: str,
                            temp_upload_path: str) -> int:

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

    @staticmethod
    def getFilePreviewDetails(file_id: int) -> Optional[Dict[str, Any]]:

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
            AND file_status = 'pending_confirmation'
        """, (file_id,))

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

    @staticmethod
    def getTempFileById(file_id: int) -> Optional[Dict[str, Any]]:

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
            AND file_status = 'pending_confirmation'
        """, (file_id,))

        file_record = cursor.fetchone()

        cursor.close()
        connection.close()

        return file_record

    @staticmethod
    def updateFragmentConfiguration(file_id: int,
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
            AND file_status = 'pending_confirmation'
        """, (
            total_fragments,
            required_fragments,
            file_id
        ))

        connection.commit()

        cursor.close()
        connection.close()

    @staticmethod
    def deleteTempFileRecord(file_id: int) -> None:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM files
            WHERE file_id = %s
            AND file_status = 'pending_confirmation'
        """, (file_id,))

        connection.commit()

        cursor.close()
        connection.close()

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
    
    @staticmethod
    def removeFile(file_id: int) -> None:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM files
            WHERE file_id = %s
            AND file_status = 'pending_confirmation'
        """, (file_id,))

        connection.commit()

        cursor.close()
        connection.close()

    @staticmethod
    def encryptFile(file_id: int) -> bool:

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
            AND file_status = 'pending_confirmation'
        """, (file_id,))

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
            AND file_status = 'pending_confirmation'
        """, (
            encrypted_temp_path,
            nonce,
            file_key,
            encrypted_size,
            file_id
        ))

        connection.commit()

        if os.path.exists(temp_upload_path):
            os.remove(temp_upload_path)

        cursor.close()
        connection.close()

        return True
    
    @staticmethod
    def getProcessingSummary(file_id: int) -> Optional[Dict[str, Any]]:

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
        """, (file_id,))

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