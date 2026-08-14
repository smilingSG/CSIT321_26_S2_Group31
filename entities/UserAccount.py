from typing import Optional
from typing import Dict
from typing import Any

import bcrypt
import hashlib
from datetime import datetime

from db import get_db_connection


class UserAccount:

    @staticmethod
    def authenticate(login_credential: str,
                     password: str,
                     max_login_attempts: int) -> Optional[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                user_id,
                username,
                email,
                password_hash,
                role,
                account_status,
                failed_login_attempts
            FROM users
            WHERE (username = %s OR email = %s)
        """, (
            login_credential,
            login_credential
        ))

        user_record = cursor.fetchone()

        cursor.close()
        connection.close()

        if user_record is None:
            return None

        user_account = {
            "userID": user_record["user_id"],
            "username": user_record["username"],
            "email": user_record["email"],
            "role": user_record["role"],
            "accountStatus": user_record["account_status"],
            "failedLoginAttempts": user_record["failed_login_attempts"]
        }

        if user_record["account_status"] == "suspended":
            user_account["authResult"] = "suspended"
            return user_account

        stored_password_hash: str = user_record["password_hash"]

        if not bcrypt.checkpw(
            password.encode("utf-8"),
            stored_password_hash.encode("utf-8")
        ):
            failed_attempts = user_record["failed_login_attempts"] + 1

            UserAccount.recordFailedLogin(
                user_record["user_id"],
                failed_attempts,
                max_login_attempts
            )

            if failed_attempts >= max_login_attempts:
                user_account["accountStatus"] = "suspended"
                user_account["authResult"] = "locked"
                user_account["attemptsRemaining"] = 0
                return user_account

            user_account["authResult"] = "invalid"
            user_account["attemptsRemaining"] = max_login_attempts - failed_attempts
            return user_account

        UserAccount.resetFailedLoginAttempts(
            user_record["user_id"]
        )

        user_account["authResult"] = "success"
        user_account["failedLoginAttempts"] = 0

        return user_account

    @staticmethod
    def recordFailedLogin(user_id: int,
                          failed_attempts: int,
                          max_login_attempts: int) -> None:

        connection = get_db_connection()
        cursor = connection.cursor()

        if failed_attempts >= max_login_attempts:
            cursor.execute("""
                UPDATE users
                SET
                    failed_login_attempts = %s,
                    account_status = 'suspended'
                WHERE user_id = %s
            """, (
                failed_attempts,
                user_id
            ))
        else:
            cursor.execute("""
                UPDATE users
                SET failed_login_attempts = %s
                WHERE user_id = %s
            """, (
                failed_attempts,
                user_id
            ))

        connection.commit()

        cursor.close()
        connection.close()

    @staticmethod
    def resetFailedLoginAttempts(user_id: int) -> None:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE users
            SET failed_login_attempts = 0
            WHERE user_id = %s
        """, (user_id,))

        connection.commit()

        cursor.close()
        connection.close()

    @staticmethod
    def ensurePasswordResetTable() -> None:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                reset_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                token_hash CHAR(64) NOT NULL UNIQUE,
                expires_at DATETIME NOT NULL,
                used_at DATETIME NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        connection.commit()

        cursor.close()
        connection.close()

    @staticmethod
    def getByEmail(email: str) -> Optional[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                user_id,
                username,
                email,
                account_status
            FROM users
            WHERE email = %s
        """, (email,))

        user_record = cursor.fetchone()

        cursor.close()
        connection.close()

        return user_record

    @staticmethod
    def createPasswordResetToken(user_id: int,
                                 token: str,
                                 expires_at: datetime) -> None:

        UserAccount.ensurePasswordResetTable()

        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE password_reset_tokens
            SET used_at = NOW()
            WHERE user_id = %s
            AND used_at IS NULL
        """, (user_id,))

        cursor.execute("""
            INSERT INTO password_reset_tokens
            (
                user_id,
                token_hash,
                expires_at
            )
            VALUES (%s, %s, %s)
        """, (
            user_id,
            token_hash,
            expires_at
        ))

        connection.commit()

        cursor.close()
        connection.close()

    @staticmethod
    def resetPassword(email: str,
                      token: str,
                      new_password: str) -> bool:

        UserAccount.ensurePasswordResetTable()

        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        password_hash = bcrypt.hashpw(
            new_password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                password_reset_tokens.reset_id,
                users.user_id
            FROM password_reset_tokens
            INNER JOIN users
                ON users.user_id = password_reset_tokens.user_id
            WHERE users.email = %s
            AND password_reset_tokens.token_hash = %s
            AND password_reset_tokens.used_at IS NULL
            AND password_reset_tokens.expires_at > NOW()
            AND users.account_status = 'active'
        """, (
            email,
            token_hash
        ))

        reset_record = cursor.fetchone()

        if reset_record is None:
            cursor.close()
            connection.close()
            return False

        cursor.execute("""
            UPDATE users
            SET
                password_hash = %s,
                failed_login_attempts = 0
            WHERE user_id = %s
        """, (
            password_hash,
            reset_record["user_id"]
        ))

        cursor.execute("""
            UPDATE password_reset_tokens
            SET used_at = NOW()
            WHERE reset_id = %s
        """, (reset_record["reset_id"],))

        connection.commit()

        cursor.close()
        connection.close()

        return True

    @staticmethod
    def ensureRegistrationVerificationTable() -> None:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS registration_verification_tokens (
                verification_id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL,
                email VARCHAR(100) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role ENUM('user', 'user_admin', 'system_admin') DEFAULT 'user',
                token_hash CHAR(64) NOT NULL UNIQUE,
                expires_at DATETIME NOT NULL,
                used_at DATETIME NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.commit()

        cursor.close()
        connection.close()

    @staticmethod
    def createRegistrationVerification(username: str,
                                       email: str,
                                       password: str,
                                       role: str,
                                       token: str) -> bool:

        UserAccount.ensureRegistrationVerificationTable()

        password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE registration_verification_tokens
            SET used_at = NOW()
            WHERE email = %s
            AND used_at IS NULL
        """, (email,))

        cursor.execute("""
            INSERT INTO registration_verification_tokens
            (
                username,
                email,
                password_hash,
                role,
                token_hash,
                expires_at
            )
            VALUES (%s, %s, %s, %s, %s, DATE_ADD(NOW(), INTERVAL 30 MINUTE))
        """, (
            username,
            email,
            password_hash,
            role,
            token_hash
        ))

        connection.commit()

        cursor.close()
        connection.close()

        return True

    @staticmethod
    def isRegistrationVerificationValid(username: str,
                                        token: str) -> bool:

        UserAccount.ensureRegistrationVerificationTable()

        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT 1
            FROM registration_verification_tokens
            WHERE username = %s
            AND token_hash = %s
            AND used_at IS NULL
            AND expires_at > NOW()
            LIMIT 1
        """, (
            username,
            token_hash
        ))

        is_valid = cursor.fetchone() is not None

        cursor.close()
        connection.close()

        return is_valid

    @staticmethod
    def verifyRegistration(username: str,
                           token: str) -> bool:

        UserAccount.ensureRegistrationVerificationTable()

        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                verification_id,
                username,
                email,
                password_hash,
                role
            FROM registration_verification_tokens
            WHERE username = %s
            AND token_hash = %s
            AND used_at IS NULL
            AND expires_at > NOW()
        """, (
            username,
            token_hash
        ))

        verification_record = cursor.fetchone()

        if verification_record is None:
            cursor.close()
            connection.close()
            return False

        if UserAccount.checkUserExists(
            username=verification_record["username"],
            email=verification_record["email"]
        ):
            cursor.execute("""
                UPDATE registration_verification_tokens
                SET used_at = NOW()
                WHERE verification_id = %s
            """, (verification_record["verification_id"],))

            connection.commit()
            cursor.close()
            connection.close()
            return False

        cursor.execute("""
            INSERT INTO users
            (
                username,
                email,
                password_hash,
                role,
                account_status,
                failed_login_attempts
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            verification_record["username"],
            verification_record["email"],
            verification_record["password_hash"],
            verification_record["role"],
            "active",
            0
        ))

        cursor.execute("""
            UPDATE registration_verification_tokens
            SET used_at = NOW()
            WHERE verification_id = %s
        """, (verification_record["verification_id"],))

        connection.commit()

        cursor.close()
        connection.close()

        return True

    @staticmethod
    def getAllUserAccounts():

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                user_id,
                username,
                email,
                role,
                account_status
            FROM users
            ORDER BY user_id
        """)

        user_records = cursor.fetchall()

        cursor.close()
        connection.close()

        return user_records

    @staticmethod
    def findUser(query: str):

        search_query = "%" + query + "%"

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                user_id,
                username,
                email,
                role,
                account_status
            FROM users
            WHERE username LIKE %s
            OR email LIKE %s
            OR role LIKE %s
            OR account_status LIKE %s
            ORDER BY user_id
        """, (
            search_query,
            search_query,
            search_query,
            search_query
        ))

        resultsList = cursor.fetchall()

        cursor.close()
        connection.close()

        return resultsList

    @staticmethod
    def checkUserExists(username: str,
                        email: str) -> bool:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM users
            WHERE username = %s
            OR email = %s
        """, (
            username,
            email
        ))

        user_count = cursor.fetchone()[0]

        cursor.close()
        connection.close()

        return user_count > 0

    @staticmethod
    def createAccount(username: str,
                      email: str,
                      password: str,
                      role: str) -> Optional[int]:

        password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO users
            (
                username,
                email,
                password_hash,
                role,
                account_status,
                failed_login_attempts
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            username,
            email,
            password_hash,
            role,
            "active",
            0
        ))

        connection.commit()

        user_id = cursor.lastrowid

        cursor.close()
        connection.close()

        return user_id

    @staticmethod
    def getUserDetails(user_id: int) -> Optional[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                user_id,
                username,
                email,
                role,
                account_status,
                created_at,
                updated_at
            FROM users
            WHERE user_id = %s
        """, (user_id,))

        user_record = cursor.fetchone()

        cursor.close()
        connection.close()

        return user_record

    @staticmethod
    def checkUserExistsById(user_id: int) -> bool:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM users
            WHERE user_id = %s
        """, (user_id,))

        user_count = cursor.fetchone()[0]

        cursor.close()
        connection.close()

        return user_count > 0

    @staticmethod
    def suspendAccount(user_id: int) -> bool:

        if not UserAccount.checkUserExistsById(user_id):
            return False

        account_status = UserAccount.getStatus(user_id)

        if account_status == "suspended":
            return False

        UserAccount.setStatus(
            user_id=user_id,
            account_status="suspended"
        )

        return True

    @staticmethod
    def unsuspendAccount(user_id: int) -> bool:

        if not UserAccount.checkUserExistsById(user_id):
            return False

        account_status = UserAccount.getStatus(user_id)

        if account_status == "active":
            return False

        UserAccount.setStatus(
            user_id=user_id,
            account_status="active"
        )

        return True

    @staticmethod
    def updateAccount(user_id: int,
                      username: str,
                      email: str,
                      role: str) -> None:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE users
            SET
                username = %s,
                email = %s,
                role = %s
            WHERE user_id = %s
        """, (
            username,
            email,
            role,
            user_id
        ))

        connection.commit()

        cursor.close()
        connection.close()

    @staticmethod
    def updateProfile(user_id: int,
                      display_name: str,
                      new_password: str,
                      confirm_password: str) -> tuple[bool, str]:

        display_name = display_name.strip()

        if display_name == "":
            return False, "Display name is required."

        password_change_requested = (
            new_password != ""
            or confirm_password != ""
        )

        if password_change_requested:
            if new_password != confirm_password:
                return False, "Passwords do not match."

        connection = get_db_connection()
        cursor = connection.cursor()

        if password_change_requested:
            password_hash = bcrypt.hashpw(
                new_password.encode("utf-8"),
                bcrypt.gensalt()
            ).decode("utf-8")

            cursor.execute("""
                UPDATE users
                SET
                    username = %s,
                    password_hash = %s,
                    failed_login_attempts = 0
                WHERE user_id = %s
            """, (
                display_name,
                password_hash,
                user_id
            ))
        else:
            cursor.execute("""
                UPDATE users
                SET username = %s
                WHERE user_id = %s
            """, (
                display_name,
                user_id
            ))

        updated = cursor.rowcount == 1

        connection.commit()

        cursor.close()
        connection.close()

        if not updated:
            return False, "Profile could not be updated."

        return True, "Profile updated successfully."

    @staticmethod
    def deleteAccount(user_id: int,
                      replacement_user_id: int) -> bool:

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            cursor.execute("""
                DELETE FROM users
                WHERE user_id = %s
            """, (user_id,))

            if cursor.rowcount != 1:
                connection.rollback()
                return False

            connection.commit()

        except Exception:
            if connection is not None:
                connection.rollback()
            return False

        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

        return True

    @staticmethod
    def deletePasswordResetTokens(user_id: int) -> bool:
        connection = None
        cursor = None
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("""
                DELETE FROM password_reset_tokens
                WHERE user_id = %s
            """, (user_id,))
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
    def getStatus(user_id: int) -> Optional[str]:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT account_status
            FROM users
            WHERE user_id = %s
        """, (user_id,))

        status_record = cursor.fetchone()

        cursor.close()
        connection.close()

        if status_record is None:
            return None

        return status_record[0]

    @staticmethod
    def setStatus(user_id: int,
                  account_status: str) -> None:

        connection = get_db_connection()
        cursor = connection.cursor()

        if account_status == "active":
            cursor.execute("""
                UPDATE users
                SET
                    account_status = %s,
                    failed_login_attempts = 0
                WHERE user_id = %s
            """, (
                account_status,
                user_id
            ))
        else:
            cursor.execute("""
                UPDATE users
                SET account_status = %s
                WHERE user_id = %s
            """, (
                account_status,
                user_id
            ))

        connection.commit()

        cursor.close()
        connection.close()
