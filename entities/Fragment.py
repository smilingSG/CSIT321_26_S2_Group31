# Import utilities for temporary fragment files and directories.
import os
# Import JSON support for writing reconstruction metadata.
import json
# Import directory cleanup utilities.
import shutil

# Import type hints used by fragment records.
from typing import Dict
from typing import Any
from typing import List
from typing import Optional

# Import zfec's erasure-coding interface.
from zfec import easyfec

# Import the application's MySQL connection function.
from db import get_db_connection


# Define the folder used while fragments are awaiting node storage.
TEMP_FRAGMENT_FOLDER: str = "temp_fragments"
# Define the folder used for reconstructed encrypted files.
RECONSTRUCTED_TEMP_FOLDER: str = "reconstructed_temp"

# Create temporary folders if they do not already exist.
os.makedirs(TEMP_FRAGMENT_FOLDER, exist_ok=True)
os.makedirs(RECONSTRUCTED_TEMP_FOLDER, exist_ok=True)


# Represent fragment records and perform erasure-coding and cleanup operations.
class Fragment:

    # Split encrypted data into n fragments recoverable from any k fragments.
    @staticmethod
    def splitIntoFragments(file_id: int,
                           encrypted_temp_path: str,
                           total_fragments: int,
                           required_fragments: int) -> List[Dict[str, Any]]:

        # Reject missing files and invalid k-of-n configurations.
        if encrypted_temp_path is None:
            return []

        if not os.path.exists(encrypted_temp_path):
            return []

        if total_fragments < 2:
            return []

        if required_fragments < 1:
            return []

        if required_fragments > total_fragments:
            return []

        # Create a separate temporary fragment folder for this file.
        file_fragment_folder = os.path.join(
            TEMP_FRAGMENT_FOLDER,
            "file_" + str(file_id)
        )

        os.makedirs(file_fragment_folder, exist_ok=True)

        # Remove fragments left by an earlier processing attempt.
        for existing_filename in os.listdir(file_fragment_folder):
            existing_path = os.path.join(
                file_fragment_folder,
                existing_filename
            )

            if os.path.isfile(existing_path):
                os.remove(existing_path)

        # Read the complete authenticated ciphertext before encoding.
        with open(encrypted_temp_path, "rb") as encrypted_file:
            encrypted_data = encrypted_file.read()

        # Configure zfec using the required k value and total n value.
        encoder = easyfec.Encoder(
            required_fragments,
            total_fragments
        )

        # Generate the erasure-coded fragment bytes.
        encoded_fragments = encoder.encode(
            encrypted_data
        )

        if len(encoded_fragments) != total_fragments:
            return []

        # Record the information needed for future reconstruction.
        metadata_path = os.path.join(
            file_fragment_folder,
            "fragment_metadata.json"
        )

        with open(metadata_path, "w") as metadata_file:
            json.dump({
                "file_id": file_id,
                "required_fragments": required_fragments,
                "total_fragments": total_fragments,
                "encrypted_size": len(encrypted_data),
                "erasure_algorithm": "zfec"
            }, metadata_file)

        fragment_list = []

        # Write each generated fragment to its own temporary .fec file.
        for fragment_index, fragment_data in enumerate(encoded_fragments):

            fragment_number = fragment_index + 1

            fragment_filename = (
                "fragment_" + str(fragment_number) + ".fec"
            )

            fragment_path = os.path.join(
                file_fragment_folder,
                fragment_filename
            )

            with open(fragment_path, "wb") as fragment_file:
                fragment_file.write(fragment_data)

            fragment_list.append({
                "file_id": file_id,
                "fragment_number": fragment_number,
                "fragment_path": fragment_path,
                "fragment_size": len(fragment_data),
                "share_number": fragment_index
            })

        # Synchronise the generated temporary fragments with MySQL metadata.
        Fragment.replacePendingFragmentRecords(
            file_id,
            fragment_list
        )

        return fragment_list

    # Replace pending database records with the latest generated fragments.
    @staticmethod
    def replacePendingFragmentRecords(file_id: int,
                                      fragment_list: List[Dict[str, Any]]) -> None:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM fragments
            WHERE file_id = %s
        """, (file_id,))

        for fragment in fragment_list:
            cursor.execute("""
                INSERT INTO fragments
                (
                    file_id,
                    node_id,
                    fragment_number,
                    fragment_path,
                    fragment_status
                )
                VALUES (%s, %s, %s, %s, %s)
            """, (
                fragment["file_id"],
                None,
                fragment["fragment_number"],
                fragment["fragment_path"],
                "pending_storage"
            ))

        connection.commit()

        cursor.close()
        connection.close()

    # Load pending fragment records and their bytes for node storage.
    @staticmethod
    def getFragmentList(file_id: int) -> List[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                fragment_id,
                file_id,
                fragment_number,
                fragment_path
            FROM fragments
            WHERE file_id = %s
            AND fragment_status = 'pending_storage'
            ORDER BY fragment_number
        """, (file_id,))

        fragment_records = cursor.fetchall()

        cursor.close()
        connection.close()

        fragment_list = []

        for fragment_record in fragment_records:
            fragment_path = fragment_record["fragment_path"]

            # Fail the complete operation if any expected fragment is missing.
            if not os.path.exists(fragment_path):
                return []

            with open(fragment_path, "rb") as fragment_file:
                fragment_bytes = fragment_file.read()

            fragment_list.append({
                "fragment_id": fragment_record["fragment_id"],
                "file_id": fragment_record["file_id"],
                "fragment_number": fragment_record["fragment_number"],
                "fragment_path": fragment_path,
                "fragment_bytes": fragment_bytes
            })

        return fragment_list

    # Retrieve available fragment paths on active storage nodes for reconstruction.
    @staticmethod
    def getAvailableFragments(file_id: int) -> List[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                fragments.fragment_id,
                fragments.file_id,
                fragments.fragment_number,
                fragments.fragment_path,
                fragments.node_id,
                storage_nodes.node_path
            FROM fragments
            INNER JOIN storage_nodes
                ON storage_nodes.node_id = fragments.node_id
            WHERE fragments.file_id = %s
            AND fragments.fragment_status = 'available'
            AND storage_nodes.node_status = 'active'
            ORDER BY fragments.fragment_number
        """, (file_id,))

        available_fragment_paths = cursor.fetchall()

        cursor.close()
        connection.close()

        return available_fragment_paths

    # Reconstruct the encrypted file from at least k available fragments.
    @staticmethod
    def reconstructFragments(file_id: int,
                             available_fragments: List[Dict[str, Any]],
                             required_fragments: int,
                             total_fragments: int,
                             encrypted_size: int) -> Optional[str]:

        if len(available_fragments) < required_fragments:
            return None

        selected_fragments = available_fragments[:required_fragments]

        fragment_bytes = [
            fragment["fragment_bytes"]
            for fragment in selected_fragments
        ]

        share_numbers = [
            fragment["share_number"]
            for fragment in selected_fragments
        ]

        try:
            decoder = easyfec.Decoder(
                required_fragments,
                total_fragments
            )

            padding_size = (
                required_fragments - (encrypted_size % required_fragments)
            ) % required_fragments

            try:
                reconstructed_data = decoder.decode(
                    fragment_bytes,
                    share_numbers,
                    padding_size
                )
            except TypeError:
                reconstructed_data = decoder.decode(
                    fragment_bytes,
                    share_numbers
                )

            # Trim any erasure-coding padding back to the original encrypted size.
            reconstructed_data = reconstructed_data[:encrypted_size]

            reconstructed_path = os.path.join(
                RECONSTRUCTED_TEMP_FOLDER,
                "file_" + str(file_id) + "_reconstructed.enc"
            )

            with open(reconstructed_path, "wb") as reconstructed_file:
                reconstructed_file.write(reconstructed_data)

            return reconstructed_path

        # Failed decoding means the selected fragments could not reconstruct data.
        except Exception:
            return None

    # Assign a stored fragment to its node and mark it as available.
    @staticmethod
    def updateFragmentStorage(fragment_id: int,
                              node_id: int,
                              fragment_path: str) -> bool:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE fragments
            SET
                node_id = %s,
                fragment_path = %s,
                fragment_status = 'available'
            WHERE fragment_id = %s
            AND fragment_status = 'pending_storage'
        """, (
            node_id,
            fragment_path,
            fragment_id
        ))

        updated = cursor.rowcount == 1

        connection.commit()

        cursor.close()
        connection.close()

        return updated

    # Restore fragment metadata after a partial node-storage failure.
    @staticmethod
    def restorePendingFragmentStorage(
        fragment_list: List[Dict[str, Any]]
    ) -> None:

        connection = get_db_connection()
        cursor = connection.cursor()

        for fragment in fragment_list:
            cursor.execute("""
                UPDATE fragments
                SET
                    node_id = NULL,
                    fragment_path = %s,
                    fragment_status = 'pending_storage'
                WHERE fragment_id = %s
            """, (
                fragment["fragment_path"],
                fragment["fragment_id"]
            ))

        connection.commit()

        cursor.close()
        connection.close()

    # Delete the temporary directory containing a file's fragments.
    @staticmethod
    def deleteTemporaryFragmentFiles(file_id: int) -> None:

        file_fragment_folder = os.path.join(
            TEMP_FRAGMENT_FOLDER,
            "file_" + str(file_id)
        )

        if os.path.exists(file_fragment_folder):
            shutil.rmtree(file_fragment_folder)

    # Remove pending fragment files and their database records.
    @staticmethod
    def deletePendingFragments(file_id: int) -> None:

        Fragment.deleteTemporaryFragmentFiles(file_id)

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM fragments
            WHERE file_id = %s
            AND fragment_status = 'pending_storage'
        """, (file_id,))

        connection.commit()

        cursor.close()
        connection.close()

    # Retrieve stored fragment paths and bucket names for controller-led cleanup.
    @staticmethod
    def getStoredFragmentPaths(file_id: int) -> List[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                fragments.fragment_id,
                fragments.fragment_path,
                storage_nodes.node_path
            FROM fragments
            LEFT JOIN storage_nodes
                ON fragments.node_id = storage_nodes.node_id
            WHERE fragments.file_id = %s
            ORDER BY fragments.fragment_number
        """, (file_id,))

        fragment_paths = cursor.fetchall()

        cursor.close()
        connection.close()

        return fragment_paths

    # Delete fragment database records for a processed file.
    @staticmethod
    def deleteFragments(file_id: int) -> bool:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM fragments
            WHERE file_id = %s
        """, (file_id,))

        connection.commit()

        cursor.close()
        connection.close()

        return True
