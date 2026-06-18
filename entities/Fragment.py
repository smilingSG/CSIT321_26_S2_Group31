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

# Import zfec's erasure-coding interface.
from zfec import easyfec

# Import the application's MySQL connection function.
from db import get_db_connection

# Define the folder used while fragments are awaiting node storage.
TEMP_FRAGMENT_FOLDER: str = "temp_fragments"

# Create the temporary fragment folder if it does not already exist.
os.makedirs(TEMP_FRAGMENT_FOLDER, exist_ok=True)


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
            AND fragment_status = 'pending_storage'
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
