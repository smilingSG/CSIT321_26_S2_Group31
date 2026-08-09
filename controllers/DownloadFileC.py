from io import BytesIO

from flask import Blueprint
from flask import redirect
from flask import send_file
from flask import session
from flask import url_for

from entities.ShareLink import ShareLink
from entities.File import File
from entities.Fragment import Fragment
from entities.StorageNodeOCI import StorageNode


download_file_bp = Blueprint("download_file_bp", __name__)


class DownloadFileC:

    @staticmethod
    def downloadSharedFile(share_token: str,
                           user_id: int):

        link_record = ShareLink.checkLinkExpiry(share_token)
        if link_record is None:
            return None, "Access denied or link invalid."
        status_errors = {
            "expired": "Link expired.", "revoked": "Link revoked.",
            "used": "Link already used."
        }
        if link_record["link_status"] in status_errors:
            return None, status_errors[link_record["link_status"]]
        if user_id != link_record["recipient_id"]:
            return None, "No permission for this shared link."

        file_record = File.getSharedDownloadDetails(link_record["file_id"])
        if file_record is None:
            return None, "Shared file could not be found."
        paths = Fragment.getAvailableFragments(link_record["file_id"])
        fragments = StorageNode.retrieveFragments(paths)
        reconstructed_path = Fragment.reconstructFragments(
            link_record["file_id"], fragments,
            file_record["required_fragments"], file_record["total_fragments"],
            file_record["encrypted_size"]
        )
        if reconstructed_path is None:
            return None, "Shared file fragments could not be reconstructed."
        original_file = File.decryptSharedFile(link_record["file_id"], reconstructed_path)
        if original_file is None:
            return None, "Shared file could not be decrypted."
        if link_record["is_one_time"] and not ShareLink.markLinkAsUsed(share_token):
            return None, "Access denied or link invalid."
        return original_file, None


@download_file_bp.route("/share/<share_token>/download", methods=["GET"])
def downloadSharedFile(share_token: str):

    user_id = session.get("user_id")

    if user_id is None:
        return redirect(url_for("login_bp.login"))

    file_result, error_message = DownloadFileC.downloadSharedFile(
        share_token=share_token,
        user_id=user_id
    )

    if file_result is None:
        return error_message, 404

    return send_file(
        BytesIO(file_result["fileBytes"]),
        as_attachment=True,
        download_name=file_result["fileName"],
        mimetype=file_result["fileType"]
    )
