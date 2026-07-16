from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for

from entities.File import File
from entities.ShareLink import ShareLink


share_file_bp = Blueprint("share_file_bp", __name__)


class ShareFileC:

    @staticmethod
    def createShareLink(file_id: int,
                        recipient_email: str,
                        user_id: int,
                        is_one_time: bool,
                        expiry_hours: int):

        return ShareLink.createShareLinkForRecipient(
            file_id=file_id,
            recipient_email=recipient_email,
            user_id=user_id,
            is_one_time=is_one_time,
            expiry_hours=expiry_hours
        )

    @staticmethod
    def getShareData(user_id: int):

        return {
            "shareableFiles": File.getShareableFilesByOwner(user_id),
            "shareLinks": ShareLink.getLinksCreatedBy(user_id)
        }


@share_file_bp.route("/shared", methods=["GET", "POST"])
def sharedFilesPage():

    user_id = session.get("user_id")

    if user_id is None:
        return redirect(url_for("login_bp.login"))

    success_message = None
    error_message = None
    secure_link = None

    if request.method == "GET":
        success_message = session.pop("shared_success_message", None)
        error_message = session.pop("shared_error_message", None)

    if request.method == "POST":
        try:
            file_id = int(request.form.get("file_id", "0"))
        except ValueError:
            file_id = 0

        recipient_email = request.form.get("recipient_email", "").strip()
        is_one_time = request.form.get("is_one_time") == "on"

        try:
            expiry_hours = int(request.form.get("expiry_hours", "72"))
        except ValueError:
            expiry_hours = 72

        if file_id <= 0 or recipient_email == "":
            error_message = "Select a file and enter a recipient email."
        elif expiry_hours < 1 or expiry_hours > 720:
            error_message = "Expiry must be between 1 and 720 hours."
        else:
            secure_token, error_message = ShareFileC.createShareLink(
                file_id=file_id,
                recipient_email=recipient_email,
                user_id=user_id,
                is_one_time=is_one_time,
                expiry_hours=expiry_hours
            )

            if secure_token is not None:
                secure_link = url_for(
                    "access_shared_file_bp.viewSharedFile",
                    share_token=secure_token,
                    _external=True
                )
                success_message = "Secure link created."

    share_data = ShareFileC.getShareData(user_id)

    return render_template(
        "sharedFiles.html",
        shareableFiles=share_data["shareableFiles"],
        shareLinks=share_data["shareLinks"],
        successMessage=success_message,
        errorMessage=error_message,
        secureLink=secure_link
    )


@share_file_bp.route("/shared/regenerate/<int:share_id>", methods=["POST"])
def regenerateSharedLink(share_id: int):

    user_id = session.get("user_id")

    if user_id is None:
        return redirect(url_for("login_bp.login"))

    ShareLink.regenerateShareLink(
        share_id=share_id,
        user_id=user_id
    )

    return redirect(url_for("share_file_bp.sharedFilesPage"))
