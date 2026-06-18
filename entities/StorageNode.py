from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

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

    @staticmethod
    def getActiveStorageNodes() -> List[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                storage_nodes.node_id,
                storage_nodes.node_name,
                storage_nodes.node_path,
                COUNT(fragments.fragment_id) AS stored_fragment_count
            FROM storage_nodes
            LEFT JOIN fragments
                ON fragments.node_id = storage_nodes.node_id
                AND fragments.fragment_status = 'available'
            WHERE storage_nodes.node_status = 'active'
            GROUP BY
                storage_nodes.node_id,
                storage_nodes.node_name,
                storage_nodes.node_path
            ORDER BY
                stored_fragment_count ASC,
                storage_nodes.node_id ASC
        """)

        active_nodes = cursor.fetchall()

        cursor.close()
        connection.close()

        return active_nodes

    @staticmethod
    def storeFragment(fragment_data: Dict[str, Any],
                      node_path: str) -> Optional[str]:

        try:
            file_folder = Path(node_path) / (
                "file_" + str(fragment_data["file_id"])
            )

            file_folder.mkdir(
                parents=True,
                exist_ok=True
            )

            stored_fragment_path = file_folder / (
                "fragment_"
                + str(fragment_data["fragment_number"])
                + ".fec"
            )

            stored_fragment_path.write_bytes(
                fragment_data["fragment_bytes"]
            )

            return str(stored_fragment_path)

        except (OSError, KeyError, TypeError):
            return None

    @staticmethod
    def deleteStoredFragment(fragment_path: str) -> None:

        stored_fragment_path = Path(fragment_path)

        if stored_fragment_path.exists():
            stored_fragment_path.unlink()

        parent_folder = stored_fragment_path.parent

        if parent_folder.exists() and not any(parent_folder.iterdir()):
            parent_folder.rmdir()
