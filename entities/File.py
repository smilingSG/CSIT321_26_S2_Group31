from typing import Optional
from typing import Dict
from typing import Any

from db import get_db_connection


class File:

    @staticmethod
    def createTempFileRecord(owner_id: int,
                             original_filename: str,
                             stored_filename: str,
                             file_size: int,
                             file_type: str) -> int:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO files
            (
                owner_id,
                original_filename,
                stored_filename,
                file_size,
                file_type,
                file_status
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            owner_id,
            original_filename,
            stored_filename,
            file_size,
            file_type,
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
                original_filename,
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
            "fileName": file_record["original_filename"],
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