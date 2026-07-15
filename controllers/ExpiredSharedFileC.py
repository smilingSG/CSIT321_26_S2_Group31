from flask import Blueprint

from entities.ShareLink import ShareLink


expired_shared_file_bp = Blueprint("expired_shared_file_bp", __name__)


class ExpiredSharedFileC:

    @staticmethod
    def checkLinkExpiry(share_token: str):

        link_record = ShareLink.getLinkExpiryDetails(share_token)

        if link_record is None:
            return None

        if link_record["link_status"] == "active" and link_record["is_expired"]:
            ShareLink.updateLinkStatus(
                share_id=link_record["share_id"],
                link_status="expired",
                required_current_status="active"
            )
            link_record["link_status"] = "expired"

        return link_record
