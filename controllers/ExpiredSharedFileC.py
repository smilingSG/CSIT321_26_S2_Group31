from flask import Blueprint

from entities.ShareLink import ShareLink


expired_shared_file_bp = Blueprint("expired_shared_file_bp", __name__)


class ExpiredSharedFileC:

    @staticmethod
    def checkLinkExpiry(share_token: str):

        return ShareLink.checkLinkExpiry(share_token)
