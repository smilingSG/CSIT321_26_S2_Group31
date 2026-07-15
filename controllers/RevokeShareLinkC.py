from flask import Blueprint
from flask import redirect
from flask import session
from flask import url_for

from entities.ShareLink import ShareLink


revoke_share_link_bp = Blueprint("revoke_share_link_bp", __name__)


class RevokeShareLinkC:

    @staticmethod
    def revokeShareLink(share_id: int,
                        user_id: int) -> bool:

        link_valid = ShareLink.verifyLinkOwner(
            share_id=share_id,
            user_id=user_id
        )

        if not link_valid:
            return False

        return ShareLink.updateLinkStatus(
            share_id=share_id,
            link_status="revoked",
            required_current_status="active"
        )


@revoke_share_link_bp.route("/shared/revoke/<int:share_id>", methods=["POST"])
def revokeShareLink(share_id: int):

    user_id = session.get("user_id")

    if user_id is None:
        return redirect(url_for("login_bp.login"))

    revoke_success = RevokeShareLinkC.revokeShareLink(
        share_id=share_id,
        user_id=user_id
    )

    if revoke_success:
        session["shared_success_message"] = "Link revoked."
    else:
        session["shared_error_message"] = "Unable to revoke link."

    return redirect(url_for("share_file_bp.sharedFilesPage"))
