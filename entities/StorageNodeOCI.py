import oci
from typing import Any, Dict, List, Optional
from db import get_db_connection

# Initialize the OCI Object Storage Client using the Instance Principal
# This assumes your OCI instance has been granted permission to access Object Storage.
try:
    signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
    oci_client = oci.object_storage.ObjectStorageClient(config={}, signer=signer)
    
    # Dynamically fetch the tenancy namespace so you don't have to hardcode it
    NAMESPACE = oci_client.get_namespace().data
except Exception as e:
    print(f"Warning: Failed to initialize OCI client. Ensure Instance Principal is configured. Error: {e}")
    oci_client = None
    NAMESPACE = None


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
        return result["active_node_count"] if result else 0

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
        """
        Stores a fragment in an OCI Object Storage Bucket.
        node_path is now treated as the bucket_name.
        """
        if not oci_client:
            return None

        # Create the object name (equivalent to the file path in the bucket)
        # e.g., "file_12/fragment_3.fec"
        object_name = f"file_{fragment_data['file_id']}/fragment_{fragment_data['fragment_number']}.fec"
        bucket_name = node_path 

        try:
            # Upload the bytes directly to the OCI bucket
            oci_client.put_object(
                namespace_name=NAMESPACE,
                bucket_name=bucket_name,
                object_name=object_name,
                put_object_body=fragment_data["fragment_bytes"]
            )
            
            # Return the object_name so it can be saved in the database's fragment_path column
            return object_name
            
        except oci.exceptions.ServiceError as e:
            print(f"OCI Put Error: {e}")
            return None

    @staticmethod
    def retrieveFragments(fragment_paths: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Retrieves stored fragments directly from OCI Object Storage Buckets into memory.
        """
        if not oci_client:
            return []

        fragment_data = []

        for fragment_path_record in fragment_paths:
            # Reconstruct the bucket_name from the node_id if necessary, 
            # though usually you would join the storage_nodes table in your SQL 
            # to pass the node_path (bucket name) alongside the fragment data.
            # Assuming 'node_path' is included in fragment_path_record for this example:
            bucket_name = fragment_path_record.get("node_path") 
            object_name = fragment_path_record["fragment_path"]

            if not bucket_name:
                continue

            try:
                # Fetch the object from OCI
                response = oci_client.get_object(
                    namespace_name=NAMESPACE,
                    bucket_name=bucket_name,
                    object_name=object_name
                )
                
                # The raw bytes are stored in the response.data.content
                raw_bytes = response.data.content

                fragment_data.append({
                    "fragment_id": fragment_path_record["fragment_id"],
                    "file_id": fragment_path_record["file_id"],
                    "fragment_number": fragment_path_record["fragment_number"],
                    "fragment_path": fragment_path_record["fragment_path"],
                    "node_id": fragment_path_record["node_id"],
                    "share_number": fragment_path_record["fragment_number"] - 1,
                    "fragment_bytes": raw_bytes
                })

            except oci.exceptions.ServiceError:
                # If a bucket is unreachable or a fragment is missing, skip it
                continue

        return fragment_data

    @staticmethod
    def deleteStoredFragments(fragment_paths: List[Dict[str, Any]]) -> bool:
        """
        Deletes multiple fragments from OCI.
        """
        success = True
        for fragment_path_record in fragment_paths:
            bucket_name = fragment_path_record.get("node_path")
            object_name = fragment_path_record["fragment_path"]
            
            if bucket_name and object_name:
                if not StorageNode.deleteStoredFragment(bucket_name, object_name):
                    success = False
        return success

    @staticmethod
    def deleteStoredFragment(bucket_name: str, object_name: str) -> bool:
        """
        Deletes a single fragment from an OCI bucket.
        """
        if not oci_client:
            return False

        try:
            oci_client.delete_object(
                namespace_name=NAMESPACE,
                bucket_name=bucket_name,
                object_name=object_name
            )
            return True
            
        except oci.exceptions.ServiceError as e:
            # If the object doesn't exist (404), we can consider it successfully "deleted"
            if e.status == 404:
                return True
            return False