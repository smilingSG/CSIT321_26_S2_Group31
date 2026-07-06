# Import the application's MySQL connection function.
from db import get_db_connection


# Represent shared file links and perform share-link database operations.
class ShareLink:

    # Delete all share links that belong to the selected file.
    @staticmethod
    def deleteShareLinks(file_id: int) -> bool:

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            cursor.execute("""
                DELETE FROM share_links
                WHERE file_id = %s
            """, (file_id,))

            connection.commit()
            return True

        except Exception:
            return False

        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()
