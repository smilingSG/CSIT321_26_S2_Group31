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
                'max_password_length',
                'require_password_number',
                'require_password_special_character',
                'min_username_length',
                'max_username_length',
                'max_login_attempts'
            )
        """)

        setting_records = cursor.fetchall()

        cursor.close()
        connection.close()

        settings = {
            "maxLinkExpiryHours": "72",
            "minPasswordLength": "8",
            "maxPasswordLength": "64",
            "requirePasswordNumber": "true",
            "requirePasswordSpecialCharacter": "true",
            "minUsernameLength": "4",
            "maxUsernameLength": "50",
            "maxLoginAttempts": "5"
        }

        for setting_record in setting_records:
            setting_name = setting_record["setting_name"]
            setting_value = setting_record["setting_value"]

            if setting_name == "max_link_expiry_hours":
                settings["maxLinkExpiryHours"] = setting_value
            elif setting_name == "min_password_length":
                settings["minPasswordLength"] = setting_value
            elif setting_name == "max_password_length":
                settings["maxPasswordLength"] = setting_value
            elif setting_name == "require_password_number":
                settings["requirePasswordNumber"] = setting_value
            elif setting_name == "require_password_special_character":
                settings["requirePasswordSpecialCharacter"] = setting_value
            elif setting_name == "min_username_length":
                settings["minUsernameLength"] = setting_value
            elif setting_name == "max_username_length":
                settings["maxUsernameLength"] = setting_value
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

        SystemSetting.updateSettingValue(
            cursor,
            "max_link_expiry_hours",
            str(max_duration),
            updated_by
        )

        connection.commit()

        cursor.close()
        connection.close()

        return True

    @staticmethod
    def updatePasswordPolicy(policy_rules: Dict[str, Any],
                             updated_by: int) -> bool:

        try:
            min_length = int(policy_rules.get("min_length"))
            max_length = int(policy_rules.get("max_length"))
        except (TypeError, ValueError):
            return False

        if min_length < 1:
            return False

        if max_length < min_length:
            return False

        if max_length > 128:
            return False

        require_number = SystemSetting.normaliseBooleanSetting(
            policy_rules.get("require_number")
        )

        require_special = SystemSetting.normaliseBooleanSetting(
            policy_rules.get("require_special")
        )

        connection = get_db_connection()
        cursor = connection.cursor()

        SystemSetting.updateSettingValue(
            cursor,
            "min_password_length",
            str(min_length),
            updated_by
        )

        SystemSetting.updateSettingValue(
            cursor,
            "max_password_length",
            str(max_length),
            updated_by
        )

        SystemSetting.updateSettingValue(
            cursor,
            "require_password_number",
            require_number,
            updated_by
        )

        SystemSetting.updateSettingValue(
            cursor,
            "require_password_special_character",
            require_special,
            updated_by
        )

        connection.commit()

        cursor.close()
        connection.close()

        return True

    @staticmethod
    def updateUsernamePolicy(policy_rules: Dict[str, Any],
                             updated_by: int) -> bool:

        try:
            min_length = int(policy_rules.get("min_length"))
            max_length = int(policy_rules.get("max_length"))
        except (TypeError, ValueError):
            return False

        if min_length < 1:
            return False

        if max_length < min_length:
            return False

        if max_length > 50:
            return False

        connection = get_db_connection()
        cursor = connection.cursor()

        SystemSetting.updateSettingValue(
            cursor,
            "min_username_length",
            str(min_length),
            updated_by
        )

        SystemSetting.updateSettingValue(
            cursor,
            "max_username_length",
            str(max_length),
            updated_by
        )

        connection.commit()

        cursor.close()
        connection.close()

        return True

    @staticmethod
    def validatePasswordAgainstPolicy(password: str) -> bool:

        settings = SystemSetting.getSecuritySettings()

        try:
            min_length = int(settings["minPasswordLength"])
            max_length = int(settings["maxPasswordLength"])
        except (TypeError, ValueError):
            return False

        if len(password) < min_length:
            return False

        if len(password) > max_length:
            return False

        if settings["requirePasswordNumber"] == "true":
            if not any(character.isdigit() for character in password):
                return False

        if settings["requirePasswordSpecialCharacter"] == "true":
            if not any(not character.isalnum() for character in password):
                return False

        return True

    @staticmethod
    def validateUsernameAgainstPolicy(username: str) -> bool:

        settings = SystemSetting.getSecuritySettings()

        try:
            min_length = int(settings["minUsernameLength"])
            max_length = int(settings["maxUsernameLength"])
        except (TypeError, ValueError):
            return False

        if len(username) < min_length:
            return False

        if len(username) > max_length:
            return False

        return True

    @staticmethod
    def updateSettingValue(cursor,
                           setting_name: str,
                           setting_value: str,
                           updated_by: int) -> None:

        cursor.execute("""
            INSERT INTO system_settings
            (
                setting_name,
                setting_value,
                updated_by
            )
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                setting_value = VALUES(setting_value),
                updated_by = VALUES(updated_by)
        """, (
            setting_name,
            setting_value,
            updated_by
        ))

    @staticmethod
    def normaliseBooleanSetting(setting_value) -> str:

        if setting_value in ("true", "on", "1", "yes"):
            return "true"

        return "false"

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
