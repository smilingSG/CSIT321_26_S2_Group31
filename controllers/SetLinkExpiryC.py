from datetime import datetime
from datetime import timedelta

from flask import Blueprint
from flask import redirect
from flask import request
from flask import session
from flask import url_for

from entities.ShareLink import ShareLink
from entities.SystemSetting import SystemSetting


set_link_expiry_bp = Blueprint("set_link_expiry_bp", __name__)


class SetLinkExpiryC:

    @staticmethod
    def setLinkExpiry(share_id: int,
                      user_id: int,
                      expiry_datetime_value: str) -> bool:

        if not ShareLink.verifyLinkOwner(
            share_id=share_id,
            user_id=user_id
        ):
            return False

        try:
            expiry_datetime = datetime.strptime(
                expiry_datetime_value,
                "%Y-%m-%dT%H:%M"
            )
        except (TypeError, ValueError):
            return False

        current_time = datetime.now()
        max_expiry_hours = SystemSetting.getMaxExpiryDuration() or 72
        max_expiry_datetime = current_time + timedelta(hours=max_expiry_hours)

        if expiry_datetime <= current_time:
            return False

        if expiry_datetime > max_expiry_datetime:
            return False

        return ShareLink.updateExpiryDateTime(
            share_id=share_id,
            expiry_datetime=expiry_datetime
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
