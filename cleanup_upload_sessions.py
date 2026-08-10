from datetime import datetime, timedelta
import os

from db import get_db_connection


PENDING_FILE_RETENTION_DAYS = 1
CANCELLED_UPLOAD_SESSION_RETENTION_DAYS = 30


def get_table_columns(cursor, table_name):
    cursor.execute(f"SHOW COLUMNS FROM {table_name}")
    return [column["Field"] for column in cursor.fetchall()]


def get_timestamp_column(columns):
    possible_columns = [
        "created_at",
        "uploaded_at",
        "upload_started_at",
        "updated_at"
    ]

    for column in possible_columns:
        if column in columns:
            return column

    return None


def delete_file_if_exists(file_path):
    if file_path is not None and file_path != "" and os.path.exists(file_path):
        os.remove(file_path)


def cleanup_pending_confirmation_files(cursor, connection):
    file_columns = get_table_columns(cursor, "files")
    file_timestamp_column = get_timestamp_column(file_columns)

    if file_timestamp_column is None:
        print("Skipped pending_confirmation cleanup: no timestamp column found in files table.")
        return

    cutoff_time = datetime.now() - timedelta(days=PENDING_FILE_RETENTION_DAYS)

    select_columns = ["file_id"]

    if "temp_upload_path" in file_columns:
        select_columns.append("temp_upload_path")

    if "encrypted_temp_path" in file_columns:
        select_columns.append("encrypted_temp_path")

    cursor.execute(f"""
        SELECT {", ".join(select_columns)}
        FROM files
        WHERE file_status = 'pending_confirmation'
        AND {file_timestamp_column} < %s
    """, (
        cutoff_time,
    ))

    pending_files = cursor.fetchall()

    upload_session_columns = get_table_columns(cursor, "upload_sessions")

    for file_record in pending_files:
        file_id = file_record["file_id"]

        delete_file_if_exists(file_record.get("temp_upload_path"))
        delete_file_if_exists(file_record.get("encrypted_temp_path"))

        cursor.execute("""
            DELETE FROM fragments
            WHERE file_id = %s
        """, (
            file_id,
        ))

        if "file_id" in upload_session_columns:
            cursor.execute("""
                DELETE FROM upload_sessions
                WHERE file_id = %s
            """, (
                file_id,
            ))

        if (
            "temp_upload_path" in upload_session_columns
            and file_record.get("temp_upload_path") is not None
        ):
            cursor.execute("""
                DELETE FROM upload_sessions
                WHERE temp_upload_path = %s
            """, (
                file_record["temp_upload_path"],
            ))

        cursor.execute("""
            DELETE FROM files
            WHERE file_id = %s
            AND file_status = 'pending_confirmation'
        """, (
            file_id,
        ))

    connection.commit()

    print(f"Cleaned {len(pending_files)} pending_confirmation file record(s).")


def cleanup_cancelled_upload_sessions(cursor, connection):
    upload_session_columns = get_table_columns(cursor, "upload_sessions")
    upload_session_timestamp_column = get_timestamp_column(upload_session_columns)

    if upload_session_timestamp_column is None:
        print("Skipped cancelled upload session cleanup: no timestamp column found in upload_sessions table.")
        return

    cutoff_time = datetime.now() - timedelta(
        days=CANCELLED_UPLOAD_SESSION_RETENTION_DAYS
    )

    select_columns = ["upload_id"]

    if "temp_upload_path" in upload_session_columns:
        select_columns.append("temp_upload_path")

    cursor.execute(f"""
        SELECT {", ".join(select_columns)}
        FROM upload_sessions
        WHERE upload_status = 'cancelled'
        AND {upload_session_timestamp_column} < %s
    """, (
        cutoff_time,
    ))

    cancelled_sessions = cursor.fetchall()

    for upload_session in cancelled_sessions:
        delete_file_if_exists(upload_session.get("temp_upload_path"))

        cursor.execute("""
            DELETE FROM upload_sessions
            WHERE upload_id = %s
            AND upload_status = 'cancelled'
        """, (
            upload_session["upload_id"],
        ))

    connection.commit()

    print(f"Cleaned {len(cancelled_sessions)} cancelled upload session record(s).")


def main():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cleanup_pending_confirmation_files(cursor, connection)
        cleanup_cancelled_upload_sessions(cursor, connection)

        print("Cleanup completed successfully.")

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()


if __name__ == "__main__":
    main()