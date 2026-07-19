# Import pathlib for cross-platform storage-node paths.
from pathlib import Path
# Import type hints used by storage-node records.
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

# Import the application's MySQL connection function.
from db import get_db_connection


# Represent storage nodes and perform node-selection and file operations.
class StorageNode:

    # Count storage nodes currently available for fragment placement.
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

    # Retrieve active nodes ordered from least used to most used.
    @staticmethod
    def getActiveStorageNodes() -> List[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Count available fragments per node to support least-used selection.
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

    # Store one fragment in a file-specific folder on the selected node.
    @staticmethod
    def storeFragment(fragment_data: Dict[str, Any],
                      node_path: str) -> Optional[str]:

        try:
            # Keep fragments grouped by file inside the selected storage node.
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

            # Write the fragment bytes to the permanent node path.
            stored_fragment_path.write_bytes(
                fragment_data["fragment_bytes"]
            )

            return str(stored_fragment_path)

        # Report storage failure without exposing filesystem exceptions.
        except (OSError, KeyError, TypeError):
            return None

    # Retrieve stored fragments from their storage node paths.
    @staticmethod
    def retrieveFragments(fragment_paths: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

        fragment_data = []

        for fragment_path_record in fragment_paths:
            try:
                stored_fragment_path = Path(
                    fragment_path_record["fragment_path"]
                )

                if not stored_fragment_path.exists():
                    continue

                if not stored_fragment_path.is_file():
                    continue

                fragment_data.append({
                    "fragment_id": fragment_path_record["fragment_id"],
                    "file_id": fragment_path_record["file_id"],
                    "fragment_number": fragment_path_record["fragment_number"],
                    "fragment_path": fragment_path_record["fragment_path"],
                    "node_id": fragment_path_record["node_id"],
                    "share_number": fragment_path_record["fragment_number"] - 1,
                    "fragment_bytes": stored_fragment_path.read_bytes()
                })

            # Missing or unreadable fragments are treated as unavailable.
            except (OSError, KeyError, TypeError):
                continue

        return fragment_data

    # Delete multiple stored fragments from their storage node paths.
    @staticmethod
    def deleteStoredFragments(fragment_paths: List[Dict[str, Any]]) -> bool:

        try:
            for fragment_path_record in fragment_paths:
                StorageNode.deleteStoredFragment(
                    fragment_path_record["fragment_path"]
                )

            return True

        except (OSError, KeyError, TypeError):
            return False

    # Delete a stored fragment and remove its folder when it becomes empty.
    @staticmethod
    def deleteStoredFragment(fragment_path: str) -> None:

        stored_fragment_path = Path(fragment_path)

        if stored_fragment_path.exists():
            stored_fragment_path.unlink()

        parent_folder = stored_fragment_path.parent

        # Remove the file-specific folder when no fragments remain inside it.
        if parent_folder.exists() and not any(parent_folder.iterdir()):
            parent_folder.rmdir()
