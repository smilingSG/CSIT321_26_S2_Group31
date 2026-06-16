import os
import json

from typing import Dict
from typing import Any
from typing import List

from zfec import easyfec

from db import get_db_connection

TEMP_FRAGMENT_FOLDER: str = "temp_fragments"

os.makedirs(TEMP_FRAGMENT_FOLDER, exist_ok=True)


class Fragment:

    @staticmethod
    def splitIntoFragments(file_id: int,
                           encrypted_temp_path: str,
                           total_fragments: int,
                           required_fragments: int) -> List[Dict[str, Any]]:

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

        file_fragment_folder = os.path.join(
            TEMP_FRAGMENT_FOLDER,
            "file_" + str(file_id)
        )

        os.makedirs(file_fragment_folder, exist_ok=True)

        for existing_filename in os.listdir(file_fragment_folder):
            existing_path = os.path.join(
                file_fragment_folder,
                existing_filename
            )

            if os.path.isfile(existing_path):
                os.remove(existing_path)

        with open(encrypted_temp_path, "rb") as encrypted_file:
            encrypted_data = encrypted_file.read()

        encoder = easyfec.Encoder(
            required_fragments,
            total_fragments
        )

        encoded_fragments = encoder.encode(
            encrypted_data
        )

        if len(encoded_fragments) != total_fragments:
            return []

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

        Fragment.replacePendingFragmentRecords(
            file_id,
            fragment_list
        )

        return fragment_list

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
