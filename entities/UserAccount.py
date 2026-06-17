from typing import Optional
from typing import Dict
from typing import Any

import bcrypt

from db import get_db_connection


class UserAccount:

    @staticmethod
    def authenticate(login_credential: str,
                     password: str) -> Optional[Dict[str, Any]]:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                user_id,
                username,
                email,
                password_hash,
                role,
                account_status
            FROM users
            WHERE (username = %s OR email = %s)
            AND account_status = 'active'
        """, (
            login_credential,
            login_credential
        ))

        user_record = cursor.fetchone()

        cursor.close()
        connection.close()

        if user_record is None:
            return None

        stored_password_hash: str = user_record["password_hash"]

        if not bcrypt.checkpw(
            password.encode("utf-8"),
            stored_password_hash.encode("utf-8")
        ):
            return None

        return {
            "userID": user_record["user_id"],
            "username": user_record["username"],
            "email": user_record["email"],
            "role": user_record["role"]
        }

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
