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
                      role: str) -> int:

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
                account_status
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            username,
            email,
            password_hash,
            role,
            "active"
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
    def deleteAccount(user_id: int) -> None:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM users
            WHERE user_id = %s
        """, (user_id,))

        connection.commit()

        cursor.close()
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
