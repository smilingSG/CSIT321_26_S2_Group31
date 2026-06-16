from db import get_db_connection


class StorageNode:

    @staticmethod
    def getActiveStorageNodeCount() -> int:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT COUNT(*) AS active_node_count
            FROM storage_nodes
            WHERE node_status = 'active'
        """)

        result = cursor.fetchone()

        cursor.close()
        connection.close()

        if result is None:
            return 0

        return result["active_node_count"]
