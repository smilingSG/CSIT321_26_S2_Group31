from typing import Any
from typing import Dict
from typing import Optional

from db import get_db_connection


class SystemSetting:

    @staticmethod
    def getSecuritySettings() -> Dict[str, Any]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT setting_name, setting_value
            FROM system_settings
            WHERE setting_name IN (
                'max_link_expiry_hours',
                'min_password_length',
                'require_password_special_character',
                'min_username_length',
                'max_login_attempts'
            )
        """)

        setting_records = cursor.fetchall()

        cursor.close()
        connection.close()

        settings = {
            "maxLinkExpiryHours": "72",
            "minPasswordLength": "8",
            "requirePasswordSpecialCharacter": "true",
            "minUsernameLength": "4",
            "maxLoginAttempts": "5"
        }

        for setting_record in setting_records:
            setting_name = setting_record["setting_name"]
            setting_value = setting_record["setting_value"]

            if setting_name == "max_link_expiry_hours":
                settings["maxLinkExpiryHours"] = setting_value
            elif setting_name == "min_password_length":
                settings["minPasswordLength"] = setting_value
            elif setting_name == "require_password_special_character":
                settings["requirePasswordSpecialCharacter"] = setting_value
            elif setting_name == "min_username_length":
                settings["minUsernameLength"] = setting_value
            elif setting_name == "max_login_attempts":
                settings["maxLoginAttempts"] = setting_value

        return settings

    @staticmethod
    def updateMaxExpiryDuration(max_duration,
                                updated_by: int) -> bool:

        try:
            max_duration = int(max_duration)
        except (TypeError, ValueError):
            return False

        if max_duration < 1:
            return False

        if max_duration > 168:
            return False

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE system_settings
            SET
                setting_value = %s,
                updated_by = %s
            WHERE setting_name = 'max_link_expiry_hours'
        """, (
            str(max_duration),
            updated_by
        ))

        if cursor.rowcount == 0:
            cursor.execute("""
                INSERT INTO system_settings
                (
                    setting_name,
                    setting_value,
                    updated_by
                )
                VALUES (%s, %s, %s)
            """, (
                "max_link_expiry_hours",
                str(max_duration),
                updated_by
            ))

        connection.commit()

        cursor.close()
        connection.close()

        return True

    @staticmethod
    def getMaxExpiryDuration() -> Optional[int]:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT setting_value
            FROM system_settings
            WHERE setting_name = 'max_link_expiry_hours'
        """)

        setting_record = cursor.fetchone()

        cursor.close()
        connection.close()

        if setting_record is None:
            return None

        try:
            return int(setting_record[0])
        except (TypeError, ValueError):
            return None
