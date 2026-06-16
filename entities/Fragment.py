import os

from typing import Dict
from typing import Any
from typing import List

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

        encrypted_size = len(encrypted_data)
        base_fragment_size = encrypted_size // total_fragments
        remaining_bytes = encrypted_size % total_fragments

        fragment_list = []
        start_index = 0

        for fragment_number in range(1, total_fragments + 1):

            current_fragment_size = base_fragment_size

            if fragment_number <= remaining_bytes:
                current_fragment_size += 1

            end_index = start_index + current_fragment_size

            fragment_data = encrypted_data[
                start_index:end_index
            ]

            fragment_filename = (
                "fragment_" + str(fragment_number) + ".part"
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
                "fragment_size": len(fragment_data)
            })

            start_index = end_index

        return fragment_list
