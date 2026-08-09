from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for

from entities.ShareLink import ShareLink
from entities.File import File
from entities.Fragment import Fragment
from entities.StorageNodeOCI import StorageNode


access_shared_file_bp = Blueprint("access_shared_file_bp", __name__)


class AccessSharedFileC:

    @staticmethod
    def extractShareToken(shared_link: str) -> str:

        shared_link = shared_link.strip()

        if shared_link == "":
            return ""

        if "/share/" not in shared_link:
            return shared_link

        share_token = shared_link.rsplit("/share/", 1)[1]

        if "/" in share_token:
            share_token = share_token.split("/", 1)[0]

        if "?" in share_token:
            share_token = share_token.split("?", 1)[0]

        return share_token

    @staticmethod
    def accessSharedLink(share_token: str,
                         user_id: int):

        link_record = ShareLink.checkLinkExpiry(share_token)
        if link_record is None:
            return None, "Access denied or link invalid.", "no_permission"
        status_errors = {
            "expired": ("Link expired.", "expired"),
            "revoked": ("Link revoked.", "revoked"),
            "used": ("Link already used.", "used")
        }
        if link_record["link_status"] in status_errors:
            message, status = status_errors[link_record["link_status"]]
            return None, message, status
        if user_id != link_record["recipient_id"]:
            return None, "No permission for this shared link.", "no_permission"

        file_record = File.getSharedDownloadDetails(link_record["file_id"])
        if file_record is None:
            return None, "Shared file fragments could not be found.", "no_fragments"
        paths = Fragment.getAvailableFragments(link_record["file_id"])
        fragments = StorageNode.retrieveFragments(paths)
        reconstructed_path = Fragment.reconstructFragments(
            link_record["file_id"], fragments,
            file_record["required_fragments"], file_record["total_fragments"],
            file_record["encrypted_size"]
        )
        if reconstructed_path is None:
            return None, "Shared file fragments could not be reconstructed.", "no_fragments"
        if os.path.exists(reconstructed_path):
            try:
                os.remove(reconstructed_path)
            except OSError:
                pass
        return link_record, None, "valid"


@access_shared_file_bp.route("/download", methods=["GET", "POST"])
def downloadPage():

    user_id = session.get("user_id")

    if user_id is None:
        return redirect(url_for("login_bp.login"))

    if request.method == "POST":
        share_token = AccessSharedFileC.extractShareToken(
            request.form.get("shared_link", "")
        )

        if share_token == "":
            return render_template(
                "sharedDownload.html",
                errorMessage="Access denied or link invalid.",
                activeStatus="no_permission",
                sharedLinkValue=""
            ), 400

        return redirect(url_for(
            "access_shared_file_bp.viewSharedFile",
            share_token=share_token
        ))

    return render_template(
        "sharedDownload.html",
        sharedLinkValue=""
    )


@access_shared_file_bp.route("/share/<share_token>", methods=["GET"])
def viewSharedFile(share_token: str):

    user_id = session.get("user_id")

    if user_id is None:
        return redirect(url_for("login_bp.login"))

    link_record, error_message, active_status = AccessSharedFileC.accessSharedLink(
        share_token=share_token,
        user_id=user_id
    )

    if link_record is None:
        return render_template(
            "sharedDownload.html",
            errorMessage=error_message,
            activeStatus=active_status,
            shareToken=share_token,
            sharedLinkValue=request.url
        ), 404

    return render_template(
        "sharedDownload.html",
        sharedFile=link_record,
        activeStatus=active_status,
        shareToken=share_token,
        sharedLinkValue=request.url
    )
import os
