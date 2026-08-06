import os
import secrets
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from db import get_db_connection
from entities.File import File
from entities.Fragment import Fragment
from entities.SystemSetting import SystemSetting
from entities.UserAccount import UserAccount

# local
# from entities.StorageNodeLocal import StorageNode

# OCI
from entities.StorageNodeOCI import StorageNode


class ShareLink:

    @staticmethod
    def accessSharedLink(share_token: str,
                         user_id: int):

        link_record = ShareLink.checkLinkExpiry(share_token)

        if link_record is None:
            return None, "Access denied or link invalid.", "no_permission"

        link_status = link_record["link_status"]

        if link_status == "expired":
            return None, "Link expired.", "expired"

        if link_status == "revoked":
            return None, "Link revoked.", "revoked"

        if link_status == "used":
            return None, "Link already used.", "used"

        if user_id != link_record["recipient_id"]:
            return None, "No permission for this shared link.", "no_permission"

        file_record = File.getSharedDownloadDetails(link_record["file_id"])

        if file_record is None:
            return None, "Shared file fragments could not be found.", "no_fragments"

        available_fragment_paths = Fragment.getAvailableFragments(
            link_record["file_id"]
        )
        available_fragments = StorageNode.retrieveFragments(
            available_fragment_paths
        )

        reconstructed_path = Fragment.reconstructFragments(
            link_record["file_id"],
            available_fragments,
            file_record["required_fragments"],
            file_record["total_fragments"],
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

    @staticmethod
    def downloadSharedFile(share_token: str,
                           user_id: int):

        link_record = ShareLink.checkLinkExpiry(share_token)

        if link_record is None:
            return None, "Access denied or link invalid."

        link_status = link_record["link_status"]

        if link_status == "expired":
            return None, "Link expired."

        if link_status == "revoked":
            return None, "Link revoked."

        if link_status == "used":
            return None, "Link already used."

        if user_id != link_record["recipient_id"]:
            return None, "No permission for this shared link."

        file_record = File.getSharedDownloadDetails(link_record["file_id"])

        if file_record is None:
            return None, "Shared file could not be found."

        available_fragment_paths = Fragment.getAvailableFragments(
            link_record["file_id"]
        )
        available_fragments = StorageNode.retrieveFragments(
            available_fragment_paths
        )

        reconstructed_path = Fragment.reconstructFragments(
            link_record["file_id"],
            available_fragments,
            file_record["required_fragments"],
            file_record["total_fragments"],
            file_record["encrypted_size"]
        )

        if reconstructed_path is None:
            return None, "Shared file fragments could not be reconstructed."

        original_file = File.decryptSharedFile(
            file_id=link_record["file_id"],
            reconstructed_temp_path=reconstructed_path
        )

        if original_file is None:
            return None, "Shared file could not be decrypted."

        if link_record["is_one_time"]:
            link_marked_used = ShareLink.markLinkAsUsed(share_token)

            if not link_marked_used:
                return None, "Access denied or link invalid."

        return original_file, None

    @staticmethod
    def createShareLinkForRecipient(file_id: int,
                                    recipient_email: str,
                                    user_id: int,
                                    is_one_time: bool,
                                    expiry_hours: int):

        max_expiry_hours = SystemSetting.getMaxExpiryDuration() or 72

        if expiry_hours < 1 or expiry_hours > max_expiry_hours:
            return None, "Expiry must be between 1 and " + str(max_expiry_hours) + " hours."

        file_valid = File.verifyFileOwnership(
            file_id=file_id,
            owner_id=user_id
        )

        if not file_valid:
            return None, "Unable to create secure link."

        recipient = UserAccount.getByEmail(recipient_email)

        if recipient is None or recipient["account_status"] != "active":
            return None, "Recipient account could not be found."

        if recipient["user_id"] == user_id:
            return None, "Select another user as the recipient."

        secure_token = ShareLink.createShareLink(
            file_id=file_id,
            created_by=user_id,
            recipient_id=recipient["user_id"],
            is_one_time=is_one_time,
            expiry_hours=expiry_hours
        )

        return secure_token, None

    @staticmethod
    def regenerateShareLink(share_id: int,
                            user_id: int) -> bool:

        link_record = ShareLink.getLinkForRenewal(
            share_id=share_id,
            created_by=user_id
        )

        if link_record is None:
            return False

        max_expiry_hours = SystemSetting.getMaxExpiryDuration() or 72
        renewal_expiry_hours = min(72, max_expiry_hours)

        ShareLink.createShareLink(
            file_id=link_record["file_id"],
            created_by=user_id,
            recipient_id=link_record["recipient_id"],
            is_one_time=bool(link_record["is_one_time"]),
            expiry_hours=renewal_expiry_hours
        )

        return True

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

    @staticmethod
    def viewSharedUsersForOwnedFile(file_id: int,
                                    user_id: int):

        file_valid = File.verifyFileOwnership(
            file_id=file_id,
            owner_id=user_id
        )

        if not file_valid:
            return None, "Unable to view shared users for this file."

        return ShareLink.getSharedUsers(file_id), None

    @staticmethod
    def deleteShareLinks(file_id: int) -> bool:

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            cursor.execute("""
                DELETE FROM share_links
                WHERE file_id = %s
            """, (file_id,))

            connection.commit()
            return True

        except Exception:
            return False

        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    @staticmethod
    def createShareLink(file_id: int,
                        created_by: int,
                        recipient_id: int,
                        is_one_time: bool,
                        expiry_hours: int) -> str:

        share_token = secrets.token_urlsafe(32)
        expiry_datetime = datetime.now() + timedelta(hours=expiry_hours)

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO share_links
            (
                file_id,
                created_by,
                recipient_id,
                share_token,
                is_one_time,
                expiry_datetime,
                link_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            file_id,
            created_by,
            recipient_id,
            share_token,
            is_one_time,
            expiry_datetime,
            "active"
        ))

        connection.commit()

        cursor.close()
        connection.close()

        return share_token

    @staticmethod
    def getLinksCreatedBy(user_id: int) -> List[Dict[str, Any]]:

        ShareLink.expireOldLinks()

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                share_links.share_id,
                share_links.file_id,
                files.file_name,
                recipient.email AS recipient_email,
                share_links.share_token,
                share_links.is_one_time,
                share_links.expiry_datetime,
                share_links.link_status
            FROM share_links
            INNER JOIN files
                ON files.file_id = share_links.file_id
            INNER JOIN users AS recipient
                ON recipient.user_id = share_links.recipient_id
            WHERE share_links.created_by = %s
            ORDER BY share_links.created_at DESC
        """, (user_id,))

        link_records = cursor.fetchall()

        cursor.close()
        connection.close()

        return [
            ShareLink.formatLinkRecord(link_record)
            for link_record in link_records
        ]

    @staticmethod
    def getSharedUsers(file_id: int) -> List[Dict[str, Any]]:

        ShareLink.expireOldLinks()

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                share_links.share_id,
                share_links.file_id,
                users.user_id,
                users.username,
                users.email,
                users.account_status,
                share_links.is_one_time,
                share_links.expiry_datetime,
                share_links.link_status,
                share_links.created_at
            FROM share_links
            INNER JOIN users
                ON users.user_id = share_links.recipient_id
            WHERE share_links.file_id = %s
            ORDER BY share_links.created_at DESC
        """, (file_id,))

        recipient_records = cursor.fetchall()

        cursor.close()
        connection.close()

        return [
            ShareLink.formatSharedUserRecord(recipient_record)
            for recipient_record in recipient_records
        ]

    @staticmethod
    def getActiveLinkByToken(share_token: str) -> Optional[Dict[str, Any]]:

        link_record = ShareLink.checkLinkExpiry(share_token)

        if link_record is None:
            return None

        if link_record["link_status"] != "active":
            return None

        return link_record

    @staticmethod
    def getLinkByToken(share_token: str) -> Optional[Dict[str, Any]]:

        return ShareLink.checkLinkExpiry(share_token)

    @staticmethod
    def checkLinkExpiry(share_token: str) -> Optional[Dict[str, Any]]:

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

    @staticmethod
    def getLinkExpiryDetails(share_token: str) -> Optional[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                share_links.share_id,
                share_links.file_id,
                share_links.recipient_id,
                share_links.is_one_time,
                files.file_name,
                share_links.expiry_datetime,
                share_links.link_status,
                CASE
                    WHEN share_links.expiry_datetime IS NOT NULL
                    AND share_links.expiry_datetime <= NOW()
                    THEN TRUE
                    ELSE FALSE
                END AS is_expired
            FROM share_links
            INNER JOIN files
                ON files.file_id = share_links.file_id
            WHERE share_links.share_token = %s
        """, (share_token,))

        link_record = cursor.fetchone()

        cursor.close()
        connection.close()

        return link_record

    @staticmethod
    def validateLink(share_token: str) -> Optional[Dict[str, Any]]:

        return ShareLink.getActiveLinkByToken(share_token)

    @staticmethod
    def revokeLink(share_id: int,
                   created_by: int) -> bool:

        if not ShareLink.verifyLinkOwner(
            share_id=share_id,
            user_id=created_by
        ):
            return False

        return ShareLink.updateLinkStatus(
            share_id=share_id,
            link_status="revoked",
            required_current_status="active"
        )

    @staticmethod
    def verifyLinkOwner(share_id: int,
                        user_id: int) -> bool:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM share_links
            WHERE share_id = %s
            AND created_by = %s
        """, (
            share_id,
            user_id
        ))

        link_count = cursor.fetchone()[0]

        cursor.close()
        connection.close()

        return link_count == 1

    @staticmethod
    def updateLinkStatus(share_id: int,
                         link_status: str,
                         required_current_status: Optional[str] = None) -> bool:

        connection = get_db_connection()
        cursor = connection.cursor()

        if required_current_status is None:
            cursor.execute("""
                UPDATE share_links
                SET link_status = %s
                WHERE share_id = %s
            """, (
                link_status,
                share_id
            ))
        else:
            cursor.execute("""
                UPDATE share_links
                SET link_status = %s
                WHERE share_id = %s
                AND link_status = %s
            """, (
                link_status,
                share_id,
                required_current_status
            ))

        updated = cursor.rowcount == 1

        connection.commit()

        cursor.close()
        connection.close()

        return updated

    @staticmethod
    def updateExpiryDateTime(share_id: int,
                             expiry_datetime: datetime) -> bool:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE share_links
            SET
                expiry_datetime = %s,
                link_status = 'active'
            WHERE share_id = %s
            AND link_status = 'active'
        """, (
            expiry_datetime,
            share_id
        ))

        updated = cursor.rowcount == 1

        connection.commit()

        cursor.close()
        connection.close()

        return updated

    @staticmethod
    def getLinkForRenewal(share_id: int,
                          created_by: int) -> Optional[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                file_id,
                recipient_id,
                is_one_time
            FROM share_links
            WHERE share_id = %s
            AND created_by = %s
        """, (
            share_id,
            created_by
        ))

        link_record = cursor.fetchone()

        cursor.close()
        connection.close()

        return link_record

    @staticmethod
    def markUsed(share_id: int) -> bool:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE share_links
            SET link_status = 'used'
            WHERE share_id = %s
            AND is_one_time = TRUE
            AND link_status = 'active'
        """, (share_id,))

        marked = cursor.rowcount == 1

        connection.commit()

        cursor.close()
        connection.close()

        return marked

    @staticmethod
    def markLinkAsUsed(share_token: str) -> bool:

        link_record = ShareLink.validateLink(share_token)

        if link_record is None:
            return False

        if not link_record["is_one_time"]:
            return True

        return ShareLink.markUsed(link_record["share_id"])

    @staticmethod
    def countActiveLinksByOwner(user_id: int) -> int:

        ShareLink.expireOldLinks()

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM share_links
            WHERE created_by = %s
            AND link_status = 'active'
        """, (user_id,))

        count = cursor.fetchone()[0]

        cursor.close()
        connection.close()

        return count

    @staticmethod
    def expireOldLinks() -> None:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE share_links
            SET link_status = 'expired'
            WHERE link_status = 'active'
            AND expiry_datetime IS NOT NULL
            AND expiry_datetime <= NOW()
        """)

        connection.commit()

        cursor.close()
        connection.close()

    @staticmethod
    def formatLinkRecord(link_record: Dict[str, Any]) -> Dict[str, Any]:

        expiry_datetime = link_record["expiry_datetime"]

        if expiry_datetime is None:
            expiry_label = "No expiry"
        else:
            expiry_label = expiry_datetime.strftime("%Y-%m-%d %H:%M")

        return {
            "shareID": link_record["share_id"],
            "fileID": link_record["file_id"],
            "fileName": link_record["file_name"],
            "recipientEmail": link_record["recipient_email"],
            "shareToken": link_record["share_token"],
            "status": link_record["link_status"].title(),
            "statusKey": link_record["link_status"],
            "isOneTime": bool(link_record["is_one_time"]),
            "oneTimeLabel": "Yes" if link_record["is_one_time"] else "No",
            "expiry": expiry_label
        }

    @staticmethod
    def formatSharedUserRecord(recipient_record: Dict[str, Any]) -> Dict[str, Any]:

        expiry_datetime = recipient_record["expiry_datetime"]
        created_at = recipient_record["created_at"]

        if expiry_datetime is None:
            expiry_label = "No expiry"
        else:
            expiry_label = expiry_datetime.strftime("%Y-%m-%d %H:%M")

        if created_at is None:
            created_label = ""
        else:
            created_label = created_at.strftime("%Y-%m-%d %H:%M")

        return {
            "shareID": recipient_record["share_id"],
            "fileID": recipient_record["file_id"],
            "recipientID": recipient_record["user_id"],
            "username": recipient_record["username"],
            "email": recipient_record["email"],
            "accountStatus": recipient_record["account_status"].title(),
            "status": recipient_record["link_status"].title(),
            "statusKey": recipient_record["link_status"],
            "oneTimeLabel": "Yes" if recipient_record["is_one_time"] else "No",
            "expiry": expiry_label,
            "sharedAt": created_label
        }
