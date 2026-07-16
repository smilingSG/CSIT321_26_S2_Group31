from flask import Blueprint
from flask import redirect
from flask import request
from flask import session
from flask import url_for

from entities.ShareLink import ShareLink


set_link_expiry_bp = Blueprint("set_link_expiry_bp", __name__)


class SetLinkExpiryC:

    @staticmethod
    def setLinkExpiry(share_id: int,
                      user_id: int,
                      expiry_datetime_value: str) -> bool:

        return ShareLink.setLinkExpiry(
            share_id=share_id,
            user_id=user_id,
            expiry_datetime_value=expiry_datetime_value
        )


@set_link_expiry_bp.route("/shared/expiry/<int:share_id>", methods=["POST"])
def setLinkExpiry(share_id: int):

    user_id = session.get("user_id")

    if user_id is None:
        return redirect(url_for("login_bp.login"))

    expiry_datetime_value = request.form.get("expiry_datetime", "").strip()

    expiry_set = SetLinkExpiryC.setLinkExpiry(
        share_id=share_id,
        user_id=user_id,
        expiry_datetime_value=expiry_datetime_value
    )

    if expiry_set:
        session["shared_success_message"] = "Link expiry set."
    else:
        session["shared_error_message"] = "Unable to set expiry."

    return redirect(url_for("share_file_bp.sharedFilesPage"))
