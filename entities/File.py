from typing import Optional, Dict, Any

from db import get_db_connection


class File:

    @staticmethod
    def createTempFileRecord(owner_id: int, original_filename: str, stored_filename: str,
                             file_size: int, file_type: str, total_fragments: int,
                             required_fragments: int) -> int:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO files
            (owner_id, original_filename, stored_filename, file_size, file_type,
             total_fragments, required_fragments, file_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            owner_id,
            original_filename,
            stored_filename,
            file_size,
            file_type,
            total_fragments,
            required_fragments,
            "pending_confirmation"
        ))

        connection.commit()
        file_id: int = cursor.lastrowid

        cursor.close()
        connection.close()

        return file_id

    @staticmethod
    def getTempFileById(file_id: int) -> Optional[Dict[str, Any]]:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT file_id, stored_filename, file_status
            FROM files
            WHERE file_id = %s
            AND file_status = 'pending_confirmation'
        """, (file_id,))

        file_record = cursor.fetchone()

        cursor.close()
        connection.close()

        return file_record

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

        count: int = cursor.fetchone()[0]

        cursor.close()
        connection.close()

        return count