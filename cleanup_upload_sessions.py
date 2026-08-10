from datetime import datetime, timedelta
from pathlib import Path

from db import get_db_connection


RETENTION_DAYS = 30


def cleanup_old_upload_sessions():
    cutoff_time = datetime.now() - timedelta(days=RETENTION_DAYS)

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                upload_id,
                temp_upload_path
            FROM upload_sessions
            WHERE upload_status IN ('cancelled', 'failed')
            AND updated_at < %s
        """, (
            cutoff_time,
        ))

        old_sessions = cursor.fetchall()

        for session_record in old_sessions:
            temp_upload_path = session_record["temp_upload_path"]

            if temp_upload_path:
                temp_file = Path(temp_upload_path)

                if temp_file.exists():
                    temp_file.unlink()

            cursor.execute("""
                DELETE FROM upload_sessions
                WHERE upload_id = %s
            """, (
                session_record["upload_id"],
            ))

        connection.commit()

        print("Cleanup completed. Removed", len(old_sessions), "old upload session records.")

    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    cleanup_old_upload_sessions()