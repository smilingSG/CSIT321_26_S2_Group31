# Import an in-memory byte stream for returning decrypted file downloads.
from io import BytesIO

# Import Flask components used for routing, sessions, redirects, and downloads.
from flask import Blueprint
from flask import jsonify
from flask import redirect
from flask import send_file
from flask import session
from flask import url_for

# Import the File entity used to decrypt reconstructed files.
from entities.File import File


# Create the blueprint containing the decryption route.
decrypt_file_bp = Blueprint(
    "decrypt_file_bp",
    __name__
)


# Decrypt a reconstructed encrypted file and return the original file as a download.
@decrypt_file_bp.route(
    "/files/decrypt/<int:file_id>",
    methods=["GET"]
)
def decryptFile(file_id: int):

    # Retrieve the logged-in user's ID from the session.
    owner_id = session.get("user_id")

    # Redirect unauthenticated users to the login page.
    if owner_id is None:
        return redirect(url_for("login_bp.login"))

    reconstructed_file_id = session.get("reconstructed_file_id")
    reconstructed_temp_path = session.get("reconstructed_temp_path")

    if reconstructed_file_id != file_id or reconstructed_temp_path is None:
        return jsonify({
            "success": False,
            "message": "Decryption failed. Reconstructed file could not be found."
        }), 400

    # Ask the File entity to decrypt the reconstructed encrypted file.
    original_file = File.decryptFile(
        file_id,
        owner_id,
        reconstructed_temp_path
    )

    session.pop("reconstructed_temp_path", None)
    session.pop("reconstructed_file_id", None)

    if original_file is None:
        return jsonify({
            "success": False,
            "message": "Decryption failed. The file may be corrupted or tampered with."
        }), 400

    return send_file(
        BytesIO(original_file["fileBytes"]),
        as_attachment=True,
        download_name=original_file["fileName"],
        mimetype=original_file["fileType"]
    )
