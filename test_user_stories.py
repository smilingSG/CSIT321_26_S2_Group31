"""Route/controller integration tests for the 41 user stories.

External database, OCI, cryptographic, fragmentation, and filesystem services
are mocked here (ran locally) so route behavior can be tested deterministically. Algorithm
implementation tests belong in separate entity-level test modules.
"""

import re
import sys
import types
import unittest
from contextlib import ExitStack
from unittest.mock import patch


zfec_module = types.ModuleType("zfec")
easyfec_module = types.ModuleType("zfec.easyfec")


class DummyEncoder:
    def __init__(self, *args, **kwargs):
        pass

    def encode(self, data):
        return [data]


easyfec_module.Encoder = DummyEncoder
zfec_module.easyfec = easyfec_module
sys.modules.setdefault("zfec", zfec_module)
sys.modules.setdefault("zfec.easyfec", easyfec_module)

bcrypt_module = types.ModuleType("bcrypt")


def _fake_hashpw(password, salt):
    return b"hash"


def _fake_checkpw(password, hashed_password):
    return True


def _fake_gensalt():
    return b"salt"


bcrypt_module.hashpw = _fake_hashpw
bcrypt_module.checkpw = _fake_checkpw
bcrypt_module.gensalt = _fake_gensalt
sys.modules.setdefault("bcrypt", bcrypt_module)

mysql_module = types.ModuleType("mysql")
connector_module = types.ModuleType("mysql.connector")


class _DummyConnection:
    def cursor(self, *args, **kwargs):
        return self

    def execute(self, *args, **kwargs):
        return None

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def commit(self):
        return None

    def close(self):
        return None


connector_module.connect = lambda *args, **kwargs: _DummyConnection()
mysql_module.connector = connector_module
sys.modules.setdefault("mysql", mysql_module)
sys.modules.setdefault("mysql.connector", connector_module)

# OCI uses compiled Windows extensions that are irrelevant to these isolated
# route tests.  A lightweight import stub keeps tests local and prevents any
# cloud connection from being attempted.
oci_module = types.ModuleType("oci")
oci_module.config = types.SimpleNamespace(from_file=lambda *args, **kwargs: {})
oci_module.auth = types.SimpleNamespace(
    signers=types.SimpleNamespace(InstancePrincipalsSecurityTokenSigner=lambda: None)
)
oci_module.object_storage = types.SimpleNamespace(
    ObjectStorageClient=lambda *args, **kwargs: None
)
sys.modules.setdefault("oci", oci_module)

import app as app_module


class UserStoryRouteTests(unittest.TestCase):
    """Happy-path smoke tests retained from the repository's original suite."""

    @classmethod
    def setUpClass(cls):
        cls.client = app_module.app.test_client()
        cls.client.testing = True

    def setUp(self):
        with self.client.session_transaction() as session:
            session.clear()

    def _set_session(self, user_id=1, username="testuser", role="user"):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id
            session["username"] = username
            session["role"] = role

    # 1. As a user, I want to log in so that I can access the system.
    @patch("controllers.LoginC.UserAccount.authenticate")
    def test_us01_main_user_can_login_and_access_dashboard(self, authenticate_mock):
        authenticate_mock.return_value = {
            "userID": 1,
            "username": "testuser",
            "role": "user",
            "authResult": "success"
        }

        response = self.client.post(
            "/login",
            data={
                "login_credential": "testuser",
                "password": "Secret123!",
                "selected_role": "user"
            },
            follow_redirects=False
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/dashboard")

        with self.client.session_transaction() as session:
            self.assertEqual(session["role"], "user")

    # 2. As a user admin, I want to log in so that I can access the system.
    @patch("controllers.LoginC.UserAccount.authenticate")
    def test_us02_main_admin_can_login_and_access_admin_dashboard(self, authenticate_mock):
        authenticate_mock.return_value = {
            "userID": 2,
            "username": "admin",
            "role": "user_admin",
            "authResult": "success"
        }

        response = self.client.post(
            "/login",
            data={
                "login_credential": "admin",
                "password": "Admin123!",
                "selected_role": "user_admin"
            },
            follow_redirects=False
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/user-admin-dashboard")

    # 3. As a system admin, I want to log in so that I can access the system.
    @patch("controllers.LoginC.UserAccount.authenticate")
    def test_us03_main_system_admin_can_login_and_access_settings(self, authenticate_mock):
        authenticate_mock.return_value = {
            "userID": 3,
            "username": "sysadmin",
            "role": "system_admin",
            "authResult": "success"
        }

        response = self.client.post(
            "/login",
            data={
                "login_credential": "sysadmin",
                "password": "Sysadmin123!",
                "selected_role": "system_admin"
            },
            follow_redirects=False
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/system-admin/settings")

        with self.client.session_transaction() as session:
            self.assertEqual(session["role"], "system_admin")

    # 7. As a user, I want to upload a file so that I can store it securely in the system.
    @patch("controllers.uploadFileC.UploadSession.startUpload")
    def test_us07_main_user_can_start_an_upload_session(self, start_upload_mock):
        self._set_session(user_id=1, username="testuser", role="user")
        start_upload_mock.return_value = {
            "uploadID": 10,
            "bytesUploaded": 0,
            "totalSize": 100
        }

        response = self.client.post(
            "/upload/start",
            data={
                "file_name": "example.txt",
                "total_size": 100
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        self.assertEqual(response.get_json()["upload_id"], 10)

    # 8. As a user, I want to pause file upload so that I can manage interruptions.
    @patch("controllers.PauseUploadC.UploadSession.saveProgress")
    def test_us08_main_user_can_pause_an_upload_session(self, save_progress_mock):
        self._set_session(user_id=1, username="testuser", role="user")
        save_progress_mock.return_value = True

        response = self.client.post(
            "/upload/pause",
            data={"upload_id": 10}
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

    # 9. As a user, I want to resume file upload so that I can continue from where I stopped.
    @patch("controllers.ResumeUploadC.UploadSession.retrieveProgress")
    @patch("controllers.ResumeUploadC.UploadSession.continueUpload")
    def test_us09_main_user_can_resume_an_upload_session(self, continue_upload_mock, retrieve_progress_mock):
        self._set_session(user_id=1, username="testuser", role="user")
        retrieve_progress_mock.return_value = {
            "uploadID": 10,
            "bytesUploaded": 50,
            "totalSize": 100
        }
        continue_upload_mock.return_value = True

        response = self.client.post(
            "/upload/resume",
            data={"upload_id": 10}
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

    # 10. As a user, I want to cancel file upload so that I can stop unwanted uploads.
    @patch("controllers.uploadFileC.File.getTempFileById")
    @patch("controllers.uploadFileC.File.deleteTempFileRecord")
    def test_us10_main_user_can_cancel_a_temp_upload(self, delete_temp_mock, get_temp_mock):
        self._set_session(user_id=1, username="testuser", role="user")
        get_temp_mock.return_value = {"file_id": 5}
        delete_temp_mock.return_value = True

        response = self.client.post("/upload/cancel/5")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

    # 11. As a user, I want to rename a file so that I can organize my files easily.
    @patch("controllers.fileManagementC.File.updateName")
    def test_us11_main_user_can_rename_a_managed_file(self, update_name_mock):
        self._set_session(user_id=1, username="testuser", role="user")
        update_name_mock.return_value = None

        response = self.client.post(
            "/files/rename/7",
            data={"new_name": "renamed-report.pdf"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

    # 12. As a user, I want to search my uploaded files so that I can quickly find a specific file to manage.
    @patch("controllers.SearchFileC.File.searchManagedFilesByName")
    def test_us12_main_user_can_search_for_a_managed_file(self, search_mock):
        self._set_session(user_id=1, username="testuser", role="user")
        search_mock.return_value = [{
            "fileID": 7,
            "fileName": "report.pdf",
            "fileStatus": "Processed",
            "fileSize": "1.2 MB",
            "uploadedAt": "2026-07-11"
        }]

        response = self.client.get("/files/search?query=report")

        self.assertEqual(response.status_code, 200)
        self.assertIn("report.pdf", response.get_data(as_text=True))

    # 16. As a user admin, I want to create user accounts so that new users can access the system.
    @patch("controllers.AdminC.UserAccount.checkUserExists")
    @patch("controllers.AdminC.UserAccount.createAccount")
    def test_us16_main_admin_can_create_new_user_accounts(self, create_account_mock, check_user_exists_mock):
        self._set_session(user_id=2, username="admin", role="user_admin")
        check_user_exists_mock.return_value = False
        create_account_mock.return_value = 42

        response = self.client.post(
            "/user-management/create",
            data={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "StrongPass123!",
                "role": "user"
            },
            follow_redirects=False
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/user-management")

    # 17. As a user admin, I want to view user accounts so that I can monitor user details.
    @patch("controllers.AdminSearchC.UserAccount.getAllUserAccounts")
    def test_us17_main_admin_can_view_and_search_user_accounts(self, get_all_accounts_mock):
        self._set_session(user_id=2, username="admin", role="user_admin")
        get_all_accounts_mock.return_value = [
            {
                "user_id": 1,
                "username": "alice",
                "email": "alice@example.com",
                "role": "user",
                "account_status": "active"
            }
        ]

        response = self.client.get("/user-management")

        self.assertEqual(response.status_code, 200)
        self.assertIn("alice", response.get_data(as_text=True))

    # 18. As a user admin, I want to update user accounts so that I can maintain accurate information.
    @patch("controllers.AdminUpdateC.UserAccount.getUserDetails")
    @patch("controllers.AdminUpdateC.UserAccount.checkUserExistsById")
    @patch("controllers.AdminUpdateC.UserAccount.updateAccount")
    def test_us18_main_admin_can_update_user_account_details(self, update_account_mock, check_user_exists_mock, get_user_details_mock):
        self._set_session(user_id=2, username="admin", role="user_admin")
        get_user_details_mock.return_value = {
            "user_id": 1,
            "username": "alice",
            "email": "alice@example.com",
            "role": "user"
        }
        check_user_exists_mock.return_value = True
        update_account_mock.return_value = None

        response = self.client.post(
            "/user-management/update/1",
            data={
                "username": "alice2",
                "email": "alice2@example.com",
                "role": "user"
            },
            follow_redirects=False
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/user-management")

    # 21. As a user admin, I want to suspend user accounts so that I can block access for users when necessary.
    @patch("controllers.AdminSuspendC.UserAccount.checkUserExistsById")
    @patch("controllers.AdminSuspendC.UserAccount.getStatus")
    @patch("controllers.AdminSuspendC.UserAccount.setStatus")
    def test_us21_main_admin_can_suspend_and_unsuspend_user_accounts(self, set_status_mock, get_status_mock, check_user_exists_mock):
        self._set_session(user_id=2, username="admin", role="user_admin")
        check_user_exists_mock.return_value = True
        get_status_mock.side_effect = ["active", "suspended"]

        suspend_response = self.client.post("/user-management/suspend/1", follow_redirects=False)
        unsuspend_response = self.client.post("/user-management/unsuspend/1", follow_redirects=False)

        self.assertEqual(suspend_response.status_code, 302)
        self.assertEqual(unsuspend_response.status_code, 302)
        self.assertEqual(set_status_mock.call_count, 2)

    # 23. As a user, I want my file to be automatically encrypted before splitting so that the content is protected even if fragments are intercepted.
    @patch("controllers.encryptFileC.File.encryptFile")
    @patch("controllers.encryptFileC.File.getProcessingSummary")
    def test_us23_main_uploaded_file_is_encrypted_before_splitting(self, get_processing_summary_mock, encrypt_file_mock):
        self._set_session(user_id=1, username="testuser", role="user")
        encrypt_file_mock.return_value = True
        get_processing_summary_mock.return_value = {
            "fileName": "example.txt",
            "fileType": "text/plain"
        }

        response = self.client.get("/upload/process/7")

        self.assertEqual(response.status_code, 200)
        self.assertIn("example.txt", response.get_data(as_text=True))

    # 32. As a user, I want to download and reconstruct a shared file only when I have valid access so that I can securely retrieve the original content on my device.
    @patch("controllers.DownloadFileC.DownloadFileC.downloadSharedFile")
    def test_us32_main_user_can_download_and_reconstruct_a_shared_file(
        self, download_shared_file_mock
    ):
        self._set_session(user_id=1, username="testuser", role="user")
        download_shared_file_mock.return_value = (
            {
                "fileBytes": b"shared original data",
                "fileName": "shared.txt",
                "fileType": "text/plain",
            },
            None,
        )

        response = self.client.get("/share/valid-token/download")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"shared original data")
        self.assertEqual(response.mimetype, "text/plain")
        download_shared_file_mock.assert_called_once_with(
            share_token="valid-token",
            user_id=1,
        )


    # 27. As a user, I want my file to be automatically reconstructed and decrypted so that I can access the original content without manual steps.
    @patch(
        "controllers.ReconstructAndDecryptFileC.ReconstructAndDecryptFileC.recoverFile"
    )
    def test_us27_main_file_is_reconstructed_and_decrypted_automatically(
        self, recover_file_mock
    ):
        self._set_session(user_id=1, username="testuser", role="user")
        recover_file_mock.return_value = {
            "fileBytes": b"original data",
            "fileName": "example.txt",
            "fileType": "text/plain",
        }

        response = self.client.get("/files/download/7")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"original data")
        self.assertEqual(response.mimetype, "text/plain")
        recover_file_mock.assert_called_once_with(7, 1)

    # 35. As a system admin, I want to define a maximum expiry duration so that link sharing remains secure and controlled.
    @patch("controllers.MaxExpirySettingsC.SystemSetting.updateMaxExpiryDuration")
    @patch("controllers.MaxExpirySettingsC.SystemSetting.getSecuritySettings")
    def test_us35_main_system_admin_can_set_max_expiry_duration(self, get_security_settings_mock, update_max_expiry_mock):
        self._set_session(user_id=3, username="sysadmin", role="system_admin")
        get_security_settings_mock.return_value = {"maxExpiryDuration": 24}
        update_max_expiry_mock.return_value = True

        response = self.client.post(
            "/system-admin/settings/max-expiry",
            data={"max_duration": "24"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Max expiry duration set.", response.get_data(as_text=True))

    # 39. As a system admin, I want to enforce password requirements so that user accounts meet security standards.
    @patch("controllers.PasswordPolicyC.SystemSetting.updatePasswordPolicy")
    @patch("controllers.PasswordPolicyC.SystemSetting.getSecuritySettings")
    @patch("controllers.UsernamePolicyC.SystemSetting.updateUsernamePolicy")
    @patch("controllers.UsernamePolicyC.SystemSetting.getSecuritySettings")
    @patch("controllers.AuthPolicyC.SystemSetting.updateAuthPolicy")
    @patch("controllers.AuthPolicyC.SystemSetting.getSecuritySettings")
    def test_us39_main_system_admin_can_enforce_security_policies(self, auth_get_settings_mock, auth_update_policy_mock, username_get_settings_mock, username_update_policy_mock, password_get_settings_mock, password_update_policy_mock):
        self._set_session(user_id=3, username="sysadmin", role="system_admin")

        password_get_settings_mock.return_value = {}
        password_update_policy_mock.return_value = True
        username_get_settings_mock.return_value = {}
        username_update_policy_mock.return_value = True
        auth_get_settings_mock.return_value = {}
        auth_update_policy_mock.return_value = True

        password_response = self.client.post(
            "/system-admin/settings/password-policy",
            data={
                "min_length": "8",
                "max_length": "32",
                "require_number": "on",
                "require_special": "on"
            }
        )
        username_response = self.client.post(
            "/system-admin/settings/username-policy",
            data={
                "min_length": "3",
                "max_length": "20"
            }
        )
        auth_response = self.client.post(
            "/system-admin/settings/auth-policy",
            data={"max_login_attempts": "5"}
        )

        self.assertEqual(password_response.status_code, 200)
        self.assertEqual(username_response.status_code, 200)
        self.assertEqual(auth_response.status_code, 200)

    # 36. As a user, I want to preview my uploaded file before encryption so that I can confirm it is the correct file.
    @patch("controllers.previewUploadedFileC.File.getFilePreviewDetails")
    def test_us36_main_user_can_preview_an_uploaded_file_before_encryption(self, get_preview_details_mock):
        self._set_session(user_id=1, username="testuser", role="user")
        get_preview_details_mock.return_value = {
            "fileID": 7,
            "fileName": "draft.pdf",
            "fileType": "application/pdf"
        }

        response = self.client.get("/upload/preview/7")

        self.assertEqual(response.status_code, 200)
        self.assertIn("draft.pdf", response.get_data(as_text=True))

    # 37. As a user, I want to replace my uploaded file before encryption so that I can upload the correct version if I selected the wrong file.
    @patch("controllers.replaceUploadedFileC.File.deleteTempFileRecord")
    def test_us37_main_user_can_replace_a_temp_upload_before_encryption(self, delete_temp_mock):
        self._set_session(user_id=1, username="testuser", role="user")
        delete_temp_mock.return_value = True

        response = self.client.post("/upload/replace/7")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])


# Route metadata used by detailed cases to confirm that their real Flask
# endpoints and required HTTP methods are registered.
STORY_ROUTE_CASES = {
    1: ("User login", "/login", "POST", "/login"),
    2: ("User-admin login", "/login", "POST", "/login"),
    3: ("System-admin login", "/login", "POST", "/login"),
    4: ("User logout", "/logout", "GET", "/login"),
    5: ("User-admin logout", "/logout", "GET", "/login"),
    6: ("System-admin logout", "/logout", "GET", "/login"),
    7: ("Start file upload", "/upload/start", "POST", "/upload/start"),
    8: ("Pause file upload", "/upload/pause", "POST", "/upload/pause"),
    9: ("Resume file upload", "/upload/resume", "POST", "/upload/resume"),
    10: ("Cancel file upload", "/upload/cancel/<int:file_id>", "POST", "/upload/cancel/1"),
    11: ("Rename managed file", "/files/rename/<int:file_id>", "POST", "/files/rename/1"),
    12: ("Search uploaded files", "/files/search", "GET", "/files/search?query=report"),
    13: ("Delete stored file", "/files/delete/<int:file_id>", "POST", "/files/delete/1"),
    14: ("Register account", "/register", "POST", "/register"),
    15: ("Reset password", "/reset-password", "POST", "/reset-password"),
    16: ("Create user account", "/user-management/create", "POST", "/user-management/create"),
    17: ("View user accounts", "/user-management", "GET", "/user-management"),
    18: ("Update user account", "/user-management/update/<int:user_id>", "POST", "/user-management/update/1"),
    19: ("Delete user account", "/user-management/delete/<int:user_id>", "POST", "/user-management/delete/1"),
    20: ("Search user accounts", "/user-management", "GET", "/user-management?query=alice"),
    21: ("Suspend user account", "/user-management/suspend/<int:user_id>", "POST", "/user-management/suspend/1"),
    22: ("Unsuspend user account", "/user-management/unsuspend/<int:user_id>", "POST", "/user-management/unsuspend/1"),
    23: ("Encrypt before splitting", "/upload/process/<int:file_id>", "GET", "/upload/process/1"),
    24: ("Split encrypted file", "/upload/split/<int:file_id>", "POST", "/upload/split/1"),
    25: ("Configure k-of-n fragments", "/upload/fragments/<int:file_id>", "POST", "/upload/fragments/1"),
    26: ("Store fragments separately", "/upload/store-fragments/<int:file_id>", "POST", "/upload/store-fragments/1"),
    27: ("Reconstruct and decrypt automatically", "/files/download/<int:file_id>", "GET", "/files/download/1"),
    28: ("Create secure share link", "/shared", "POST", "/shared"),
    29: ("Revoke share link", "/shared/revoke/<int:share_id>", "POST", "/shared/revoke/1"),
    30: ("View shared users", "/shared/users/<int:file_id>", "GET", "/shared/users/1"),
    31: ("Use one-time link", "/share/<share_token>", "GET", "/share/example-token"),
    32: ("Download shared file with access", "/share/<share_token>/download", "GET", "/share/example-token/download"),
    33: ("Set link expiry", "/shared/expiry/<int:share_id>", "POST", "/shared/expiry/1"),
    34: ("Reject expired link", "/share/<share_token>", "GET", "/share/expired-token"),
    35: ("Set maximum expiry", "/system-admin/settings/max-expiry", "POST", "/system-admin/settings/max-expiry"),
    36: ("Preview upload", "/upload/preview/<int:file_id>", "GET", "/upload/preview/1"),
    37: ("Replace upload", "/upload/replace/<int:file_id>", "POST", "/upload/replace/1"),
    38: ("Delete upload before encryption", "/upload/delete/<int:file_id>", "POST", "/upload/delete/1"),
    39: ("Enforce password policy", "/system-admin/settings/password-policy", "POST", "/system-admin/settings/password-policy"),
    40: ("Enforce username policy", "/system-admin/settings/username-policy", "POST", "/system-admin/settings/username-policy"),
    41: ("Enforce authentication policy", "/system-admin/settings/auth-policy", "POST", "/system-admin/settings/auth-policy"),
}

def _registered_rule(test_case, rule_text, required_method):
    matches = [
        rule for rule in app_module.app.url_map.iter_rules()
        if str(rule) == rule_text
    ]
    test_case.assertTrue(matches, f"Expected route {rule_text} to be registered")
    matching_method = [rule for rule in matches if required_method in rule.methods]
    test_case.assertTrue(
        matching_method,
        f"Expected {rule_text} to accept {required_method}",
    )
    test_case.assertTrue(
        callable(app_module.app.view_functions[matching_method[0].endpoint])
    )


class DetailedUserStoryCases(unittest.TestCase):
    """Full main, validation, and alternate user-story behavior matrix."""

    @classmethod
    def setUpClass(cls):
        cls.client = app_module.app.test_client()
        cls.client.testing = True

    def setUp(self):
        with self.client.session_transaction() as session:
            session.clear()

    def _run(self, scenario):
        _, route_rule, required_method, _ = STORY_ROUTE_CASES[scenario["story"]]
        _registered_rule(self, route_rule, required_method)

        role = scenario.get("role")
        if role:
            with self.client.session_transaction() as session:
                session["user_id"] = {"user": 1, "user_admin": 2, "system_admin": 3}[role]
                session["username"] = role
                session["role"] = role
                session.update(scenario.get("session", {}))
        with ExitStack() as stack:
            mocks = {}
            for target, value in scenario.get("patches", ()):
                mocks[target] = stack.enter_context(
                    patch(target, return_value=value)
                )
            response = self.client.open(
                scenario["path"],
                method=scenario.get("method", "GET"),
                data=scenario.get("data"),
                follow_redirects=scenario.get("follow", False),
            )
        self.assertEqual(response.status_code, scenario["status"])
        if scenario.get("contains") is not None:
            self.assertIn(scenario["contains"], response.get_data(as_text=True))
        if scenario.get("json") is not None:
            for key, value in scenario["json"].items():
                self.assertEqual(response.get_json()[key], value)
        if scenario.get("location") is not None:
            self.assertEqual(response.headers.get("Location"), scenario["location"])
        if scenario.get("flash_contains") is not None:
            with self.client.session_transaction() as session:
                flashed_messages = [
                    message for _, message in session.get("_flashes", [])
                ]
            self.assertIn(scenario["flash_contains"], flashed_messages)
        if scenario.get("session_values") is not None:
            with self.client.session_transaction() as session:
                for key, value in scenario["session_values"].items():
                    self.assertEqual(session.get(key), value)
        for target in scenario.get("called", ()):
            mocks[target].assert_called()
        for target, expectation in scenario.get("called_with", {}).items():
            mocks[target].assert_called_with(
                *expectation.get("args", ()),
                **expectation.get("kwargs", {}),
            )


    def test_us04_main_user_logs_out(self):
        """US4 main: user securely ends an authenticated session."""
        self._run(
            _scenario(
                story=4,
                kind='main',
                title='user securely ends an authenticated session',
                path='/logout',
                status=302,
                role=USER,
                location='/login',
                session_values={
                    'user_id': None,
                    'username': None,
                    'role': None,
                },
            )
        )

    def test_us05_main_user_admin_logs_out(self):
        """US5 main: user admin securely ends an authenticated session."""
        self._run(
            _scenario(
                story=5,
                kind='main',
                title='user admin securely ends an authenticated session',
                path='/logout',
                status=302,
                role=ADMIN,
                location='/login',
                session_values={
                    'user_id': None,
                    'username': None,
                    'role': None,
                },
            )
        )

    def test_us06_main_system_admin_logs_out(self):
        """US6 main: system admin securely ends an authenticated session."""
        self._run(
            _scenario(
                story=6,
                kind='main',
                title='system admin securely ends an authenticated session',
                path='/logout',
                status=302,
                role=SYSTEM_ADMIN,
                location='/login',
                session_values={
                    'user_id': None,
                    'username': None,
                    'role': None,
                },
            )
        )

    def test_us13_main_user_deletes_a_stored_file(self):
        """US13 main: user deletes a stored file and its related records."""
        self._run(
            _scenario(
                story=13,
                kind='main',
                title='user deletes a stored file and its related records',
                path='/files/delete/7',
                status=200,
                method='POST',
                role=USER,
                patches=(
                    P('controllers.deleteFromFileMgmtC.File.getFileDeleteDetails', {'fileID': 7}),
                    P('controllers.deleteFromFileMgmtC.Fragment.getStoredFragmentPaths', ['fragment-1']),
                    P('controllers.deleteFromFileMgmtC.ShareLink.deleteShareLinks', True),
                    P('controllers.deleteFromFileMgmtC.UploadSession.deleteUploadSessions', True),
                    P('controllers.deleteFromFileMgmtC.StorageNode.deleteStoredFragments', True),
                    P('controllers.deleteFromFileMgmtC.Fragment.deleteFragments', True),
                    P('controllers.deleteFromFileMgmtC.File.deleteFileRecord', True),
                ),
                json={
                    'success': True,
                    'message': 'File deleted successfully.',
                },
                called=(
                    'controllers.deleteFromFileMgmtC.File.deleteFileRecord',
                ),
            )
        )

    def test_us14_main_registration_request_succeeds(self):
        """US14 main: registration request succeeds."""
        self._run(
            _scenario(
                story=14,
                kind='main',
                title='registration request succeeds',
                path='/register',
                status=200,
                method='POST',
                follow=True,
                data={
                        'username': 'newuser',
                        'email': 'new@example.com',
                        'password': 'Strong123!',
                        'confirm_password': 'Strong123!',
                    },
                patches=(
                        P(
                            'controllers.RegisterC.RegisterC.register',
                            (
                            True,
                            None,
                        ),
                        ),
                    ),
                contains='verification code has been sent',
            )
        )

    def test_us15_main_password_resets_with_a_valid_code(self):
        """US15 main: password resets with a valid code."""
        self._run(
            _scenario(
                story=15,
                kind='main',
                title='password resets with a valid code',
                path='/reset-password',
                status=200,
                method='POST',
                data={
                        'email': 'user@example.com',
                        'token': 'valid-code',
                        'new_password': 'NewStrong123!',
                    },
                patches=(
                        P(
                            'controllers.PasswordResetC.PasswordResetC.updatePassword',
                            (
                            True,
                            None,
                        ),
                        ),
                    ),
                contains='Password updated successfully',
            )
        )

    def test_us19_main_admin_deletes_an_existing_account(self):
        """US19 main: admin deletes an existing account."""
        self._run(
            _scenario(
                story=19,
                kind='main',
                title='admin deletes an existing account',
                path='/user-management/delete/7',
                status=302,
                method='POST',
                role=ADMIN,
                patches=(
                        P(
                            'controllers.AdminDeleteC.AdminDeleteC.deleteUser',
                            True,
                        ),
                    ),
                called=(
                        'controllers.AdminDeleteC.AdminDeleteC.deleteUser',
                    ),
            )
        )

    def test_us20_main_admin_searches_for_a_matching_account(self):
        """US20 main: admin searches for a matching account."""
        self._run(
            _scenario(
                story=20,
                kind='main',
                title='admin searches for a matching account',
                path='/user-management?query=alice',
                status=200,
                role=ADMIN,
                patches=(
                        P(
                            'controllers.AdminSearchC.UserAccount.findUser',
                            [
                            {
                                'user_id': 7,
                                'username': 'alice',
                                'email': 'alice@example.com',
                                'role': 'user',
                                'account_status': 'active',
                            },
                        ],
                        ),
                    ),
                contains='alice',
            )
        )

    def test_us22_main_admin_unsuspends_an_account(self):
        """US22 main: admin unsuspends an account."""
        self._run(
            _scenario(
                story=22,
                kind='main',
                title='admin unsuspends an account',
                path='/user-management/unsuspend/7',
                status=302,
                method='POST',
                role=ADMIN,
                patches=(
                        P(
                            'controllers.AdminUnsuspendC.AdminUnsuspendC.unsuspendUser',
                            True,
                        ),
                    ),
                called=(
                        'controllers.AdminUnsuspendC.AdminUnsuspendC.unsuspendUser',
                    ),
            )
        )

    def test_us24_main_encrypted_file_is_split(self):
        """US24 main: encrypted file is split."""
        self._run(
            _scenario(
                story=24,
                kind='main',
                title='encrypted file is split',
                path='/upload/split/7',
                status=200,
                method='POST',
                role=USER,
                patches=(
                        P(
                            'controllers.splitFileC.File.getEncryptedFileDetails',
                            {
                            'file_id': 7,
                            'encrypted_temp_path': 'file.enc',
                            'total_fragments': 3,
                            'required_fragments': 2,
                        },
                        ),
                        P(
                            'controllers.splitFileC.Fragment.splitIntoFragments',
                            [
                            1,
                            2,
                            3,
                        ],
                        ),
                        P(
                            'controllers.splitFileC.File.updateFileStatus',
                            True,
                        ),
                        P(
                            'controllers.splitFileC.File.getProcessingSummary',
                            {
                            'fileName': 'file.txt',
                        },
                        ),
                    ),
                contains='File split successfully',
            )
        )

    def test_us25_main_valid_k_of_n_configuration_is_accepted(self):
        """US25 main: valid k-of-n configuration is accepted."""
        self._run(
            _scenario(
                story=25,
                kind='main',
                title='valid k-of-n configuration is accepted',
                path='/upload/fragments/7',
                status=302,
                method='POST',
                role=USER,
                data={
                        'total_fragments': '5',
                        'required_fragments': '3',
                    },
                patches=(
                        P(
                            'controllers.configureFragmentsC.StorageNode.getActiveStorageNodeCount',
                            5,
                        ),
                        P(
                            'controllers.configureFragmentsC.File.updateFragmentConfiguration',
                            None,
                        ),
                    ),
            )
        )

    def test_us26_main_fragments_are_stored_separately(self):
        """US26 main: fragments are stored separately."""
        self._run(
            _scenario(
                story=26,
                kind='main',
                title='fragments are stored separately',
                path='/upload/store-fragments/7',
                status=200,
                method='POST',
                role=USER,
                patches=(
                        P(
                            'controllers.storeFragmentC.File.getProcessingFileDetails',
                            {
                            'file_status': 'pending_processing',
                        },
                        ),
                        P(
                            'controllers.storeFragmentC.Fragment.getFragmentList',
                            [],
                        ),
                        P(
                            'controllers.storeFragmentC.File.getProcessingSummary',
                            {
                            'totalFragments': 0,
                        },
                        ),
                        P(
                            'controllers.storeFragmentC.StorageNode.getActiveStorageNodes',
                            [],
                        ),
                        P(
                            'controllers.storeFragmentC.Fragment.deleteTemporaryFragmentFiles',
                            None,
                        ),
                        P(
                            'controllers.storeFragmentC.File.deleteEncryptedTemporaryFile',
                            None,
                        ),
                        P(
                            'controllers.storeFragmentC.File.updateFileStatus',
                            True,
                        ),
                    ),
                contains='Fragments stored separately',
            )
        )


    def test_us28_main_secure_share_link_is_created(self):
        """US28 main: secure share link is created."""
        self._run(
            _scenario(
                story=28,
                kind='main',
                title='secure share link is created',
                path='/shared',
                status=200,
                method='POST',
                role=USER,
                data={
                        'file_id': '7',
                        'recipient_email': 'friend@example.com',
                        'expiry_hours': '24',
                    },
                patches=(
                        P(
                            'controllers.ShareFileC.ShareFileC.createShareLink',
                            (
                            'secure-token',
                            None,
                        ),
                        ),
                        P(
                            'controllers.ShareFileC.ShareFileC.getShareData',
                            {
                            'shareableFiles': [],
                            'shareLinks': [],
                        },
                        ),
                        P(
                            'controllers.ShareFileC.UserAccount.getByEmail',
                            {'username': 'friend'},
                        ),
                        P(
                            'controllers.ShareFileC.ShareFileC.sendShareLinkEmail',
                            (True, None),
                        ),
                    ),
                contains='Secure link created',
            )
        )

    def test_us29_main_owner_revokes_a_share_link(self):
        """US29 main: owner revokes a share link."""
        self._run(
            _scenario(
                story=29,
                kind='main',
                title='owner revokes a share link',
                path='/shared/revoke/5',
                status=302,
                method='POST',
                role=USER,
                patches=(
                        P(
                            'controllers.RevokeShareLinkC.RevokeShareLinkC.revokeShareLink',
                            True,
                        ),
                    ),
            )
        )

    def test_us30_main_owner_views_recipients(self):
        """US30 main: owner views recipients."""
        self._run(
            _scenario(
                story=30,
                kind='main',
                title='owner views recipients',
                path='/shared/users/7',
                status=200,
                role=USER,
                patches=(
                        P(
                            'controllers.ViewSharedUsersC.ViewSharedUsersC.viewSharedUsers',
                            (
                            [
                                {
                                    'username': 'friend',
                                    'email': 'friend@example.com',
                                    'accountStatus': 'Registered',
                                    'statusKey': 'active',
                                    'status': 'Active',
                                    'oneTimeLabel': 'No',
                                    'expiry': 'Tomorrow',
                                    'sharedAt': 'Today',
                                },
                            ],
                            None,
                        ),
                        ),
                    ),
                contains='friend@example.com',
            )
        )

    def test_us31_main_valid_one_time_link_can_be_viewed(self):
        """US31 main: valid one-time link can be viewed."""
        self._run(
            _scenario(
                story=31,
                kind='main',
                title='valid one-time link can be viewed',
                path='/share/token',
                status=200,
                role=USER,
                patches=(
                        P(
                            'controllers.AccessSharedFileC.AccessSharedFileC.accessSharedLink',
                            (
                            {
                                'file_name': 'shared.txt',
                                'is_one_time': True,
                            },
                            None,
                            'active',
                        ),
                        ),
                    ),
                contains='shared.txt',
            )
        )

    def test_us33_main_owner_sets_link_expiry(self):
        """US33 main: owner sets link expiry."""
        self._run(
            _scenario(
                story=33,
                kind='main',
                title='owner sets link expiry',
                path='/shared/expiry/5',
                status=302,
                method='POST',
                role=USER,
                data={
                        'expiry_datetime': '2026-08-03T12:00',
                    },
                patches=(
                        P(
                            'controllers.SetLinkExpiryC.SetLinkExpiryC.setLinkExpiry',
                            True,
                        ),
                    ),
            )
        )

    def test_us34_main_expired_link_is_inaccessible(self):
        """US34 main: expired link is inaccessible."""
        self._run(
            _scenario(
                story=34,
                kind='main',
                title='expired link is inaccessible',
                path='/share/expired',
                status=404,
                role=USER,
                patches=(
                        P(
                            'controllers.AccessSharedFileC.AccessSharedFileC.accessSharedLink',
                            (
                            None,
                            'Link expired.',
                            'expired',
                        ),
                        ),
                    ),
                contains='Link expired',
            )
        )

    def test_us38_main_temporary_upload_is_deleted(self):
        """US38 main: temporary upload is deleted."""
        self._run(
            _scenario(
                story=38,
                kind='main',
                title='temporary upload is deleted',
                path='/upload/delete/7',
                status=200,
                method='POST',
                role=USER,
                patches=(
                        P(
                            'controllers.deleteFileC.File.getTempFileById',
                            {
                            'file_id': 7,
                        },
                        ),
                        P(
                            'controllers.deleteFileC.File.removeFile',
                            True,
                        ),
                    ),
                json={
                        'success': True,
                    },
            )
        )

    def test_us40_main_username_policy_is_updated(self):
        """US40 main: username policy is updated."""
        self._run(
            _scenario(
                story=40,
                kind='main',
                title='username policy is updated',
                path='/system-admin/settings/username-policy',
                status=200,
                method='POST',
                role=SYSADMIN,
                data={
                        'min_length': '3',
                        'max_length': '20',
                    },
                patches=(
                        P(
                            'controllers.UsernamePolicyC.SystemSetting.updateUsernamePolicy',
                            True,
                        ),
                        P(
                            'controllers.UsernamePolicyC.SystemSetting.getSecuritySettings',
                            {},
                        ),
                    ),
                contains='Username policy updated',
            )
        )

    def test_us41_main_authentication_policy_is_updated(self):
        """US41 main: authentication policy is updated."""
        self._run(
            _scenario(
                story=41,
                kind='main',
                title='authentication policy is updated',
                path='/system-admin/settings/auth-policy',
                status=200,
                method='POST',
                role=SYSADMIN,
                data={
                        'max_login_attempts': '5',
                    },
                patches=(
                        P(
                            'controllers.AuthPolicyC.SystemSetting.updateAuthPolicy',
                            True,
                        ),
                        P(
                            'controllers.AuthPolicyC.SystemSetting.getSecuritySettings',
                            {},
                        ),
                    ),
                contains='Authentication policy updated',
            )
        )

    def test_us01_validation_empty_login_fields_are_rejected(self):
        """US1 validation: empty login fields are rejected."""
        self._run(
            _scenario(
                story=1,
                kind='validation',
                title='empty login fields are rejected',
                path='/login',
                status=400,
                method='POST',
                data={},
                contains='Invalid input format.',
            )
        )

    def test_us02_validation_wrong_role_is_rejected(self):
        """US2 validation: wrong role is rejected."""
        self._run(
            _scenario(
                story=2,
                kind='validation',
                title='wrong role is rejected',
                path='/login',
                status=401,
                method='POST',
                data={
                        'login_credential': 'admin',
                        'password': 'pass',
                        'selected_role': 'user_admin',
                    },
                patches=(
                        P(
                            'controllers.LoginC.UserAccount.authenticate',
                            {
                            'userID': 1,
                            'username': 'user',
                            'role': 'user',
                            'authResult': 'success',
                        },
                        ),
                    ),
                contains='Invalid login credentials.',
            )
        )

    def test_us03_validation_wrong_role_cannot_login_as_system_admin(self):
        """US3 validation: a non-system-admin account cannot use the system-admin role."""
        self._run(
            _scenario(
                story=3,
                kind='validation',
                title='wrong role cannot login as system admin',
                path='/login',
                status=401,
                method='POST',
                data={
                    'login_credential': 'admin',
                    'password': 'Admin123!',
                    'selected_role': 'system_admin',
                },
                patches=(
                    P(
                        'controllers.LoginC.UserAccount.authenticate',
                        {
                            'userID': 2,
                            'username': 'admin',
                            'role': 'user_admin',
                            'authResult': 'success',
                        },
                    ),
                ),
                contains='Invalid login credentials.',
            )
        )

    def test_us04_validation_logout_without_a_session_remains_safe(self):
        """US4 validation: user logout without a session remains safe."""
        self._run(
            _scenario(
                story=4,
                kind='validation',
                title='user logout without a session remains safe',
                path='/logout',
                status=302,
                location='/login',
            )
        )

    def test_us05_validation_user_admin_logout_clears_the_complete_session(self):
        """US5 validation: user-admin logout removes all identity values."""
        self._run(
            _scenario(
                story=5,
                kind='validation',
                title='user-admin logout clears the complete session',
                path='/logout',
                status=302,
                role=ADMIN,
                location='/login',
                session_values={
                    'user_id': None,
                    'username': None,
                    'role': None,
                },
            )
        )

    def test_us06_validation_system_admin_logout_clears_the_complete_session(self):
        """US6 validation: system-admin logout removes all identity values."""
        self._run(
            _scenario(
                story=6,
                kind='validation',
                title='system-admin logout clears the complete session',
                path='/logout',
                status=302,
                role=SYSTEM_ADMIN,
                location='/login',
                session_values={
                    'user_id': None,
                    'username': None,
                    'role': None,
                },
            )
        )

    def test_us07_validation_missing_upload_details_are_rejected(self):
        """US7 validation: missing upload details are rejected."""
        self._run(
            _scenario(
                story=7,
                kind='validation',
                title='missing upload details are rejected',
                path='/upload/start',
                status=400,
                method='POST',
                role=USER,
                data={},
                json={
                    'success': False,
                    'message': 'Upload details are incomplete.',
                },
            )
        )

    def test_us08_validation_missing_paused_upload_id_is_rejected(self):
        """US8 validation: missing paused upload id is rejected."""
        self._run(
            _scenario(
                story=8,
                kind='validation',
                title='missing paused upload id is rejected',
                path='/upload/pause',
                status=400,
                method='POST',
                role=USER,
                data={},
                json={
                    'success': False,
                    'message': 'Upload session could not be found.',
                },
            )
        )

    def test_us09_validation_missing_resumed_upload_id_is_rejected(self):
        """US9 validation: missing resumed upload id is rejected."""
        self._run(
            _scenario(
                story=9,
                kind='validation',
                title='missing resumed upload id is rejected',
                path='/upload/resume',
                status=400,
                method='POST',
                role=USER,
                data={},
                json={
                    'success': False,
                    'message': 'Upload session could not be found.',
                },
            )
        )

    def test_us10_validation_unknown_temporary_upload_is_rejected(self):
        """US10 validation: unknown temporary upload is rejected."""
        self._run(
            _scenario(
                story=10,
                kind='validation',
                title='unknown temporary upload is rejected',
                path='/upload/cancel/99',
                status=404,
                method='POST',
                role=USER,
                patches=(
                        P(
                            'controllers.uploadFileC.File.getTempFileById',
                            None,
                        ),
                    ),
                json={
                    'success': False,
                    'message': 'Temporary file record not found.',
                },
            )
        )

    def test_us11_validation_missing_rename_value_is_rejected(self):
        """US11 validation: missing rename value is rejected."""
        self._run(
            _scenario(
                story=11,
                kind='validation',
                title='missing rename value is rejected',
                path='/files/rename/7',
                status=400,
                method='POST',
                role=USER,
                data={},
                json={
                    'success': False,
                    'message': 'Please enter a file name.',
                },
            )
        )

    def test_us12_validation_empty_search_is_handled(self):
        """US12 validation: empty search is handled."""
        self._run(
            _scenario(
                story=12,
                kind='validation',
                title='empty search is handled',
                path='/files/search?query=',
                status=200,
                role=USER,
                patches=(
                        P(
                            'controllers.SearchFileC.File.searchManagedFilesByName',
                            [],
                        ),
                    ),
                called_with={
                    'controllers.SearchFileC.File.searchManagedFilesByName': {
                        'args': (1, ''),
                    },
                },
            )
        )

    def test_us13_validation_unknown_stored_file_cannot_be_deleted(self):
        """US13 validation: an unknown stored file is rejected."""
        self._run(
            _scenario(
                story=13,
                kind='validation',
                title='unknown stored file cannot be deleted',
                path='/files/delete/999',
                status=404,
                method='POST',
                role=USER,
                patches=(
                    P('controllers.deleteFromFileMgmtC.File.getFileDeleteDetails', None),
                ),
                json={
                    'success': False,
                    'message': 'Unable to delete file.',
                },
            )
        )

    def test_us14_validation_mismatched_registration_passwords_are_rejected(self):
        """US14 validation: mismatched registration passwords are rejected."""
        self._run(
            _scenario(
                story=14,
                kind='validation',
                title='mismatched registration passwords are rejected',
                path='/register',
                status=400,
                method='POST',
                data={
                        'username': 'new',
                        'email': 'new@example.com',
                        'password': 'Password1!',
                        'confirm_password': 'Different1!',
                    },
                contains='Passwords do not match',
            )
        )

    def test_us15_validation_short_reset_password_is_rejected(self):
        """US15 validation: short reset password is rejected."""
        self._run(
            _scenario(
                story=15,
                kind='validation',
                title='short reset password is rejected',
                path='/reset-password',
                status=400,
                method='POST',
                data={
                        'email': 'user@example.com',
                        'token': 'code',
                        'new_password': 'short',
                    },
                contains='Password does not meet the current password policy.',
            )
        )

    def test_us16_validation_admin_account_creation_requires_all_fields(self):
        """US16 validation: admin account creation requires all fields."""
        self._run(
            _scenario(
                story=16,
                kind='validation',
                title='admin account creation requires all fields',
                path='/user-management/create',
                status=302,
                method='POST',
                role=ADMIN,
                data={},
                location='/user-management/create',
                flash_contains='Please enter valid account details.',
            )
        )

    def test_us17_validation_ordinary_user_cannot_view_account_management(self):
        """US17 validation: ordinary user cannot view account management."""
        self._run(
            _scenario(
                story=17,
                kind='validation',
                title='ordinary user cannot view account management',
                path='/user-management',
                status=302,
                role=USER,
                location='/dashboard',
            )
        )

    def test_us18_validation_invalid_update_details_are_rejected(self):
        """US18 validation: invalid update details are rejected."""
        self._run(
            _scenario(
                story=18,
                kind='validation',
                title='invalid update details are rejected',
                path='/user-management/update/7',
                status=302,
                method='POST',
                role=ADMIN,
                data={
                        'username': '',
                        'email': '',
                        'role': 'invalid',
                    },
                location='/user-management/update/7',
                flash_contains='Please enter valid user details.',
            )
        )

    def test_us19_validation_nonexistent_account_cannot_be_deleted(self):
        """US19 validation: nonexistent account cannot be deleted."""
        self._run(
            _scenario(
                story=19,
                kind='validation',
                title='nonexistent account cannot be deleted',
                path='/user-management/delete/99',
                status=302,
                method='POST',
                role=ADMIN,
                patches=(
                        P(
                            'controllers.AdminDeleteC.AdminDeleteC.deleteUser',
                            False,
                        ),
                    ),
                location='/user-management',
                flash_contains='User could not be deleted.',
            )
        )

    def test_us20_validation_search_with_no_matches_is_handled(self):
        """US20 validation: search with no matches is handled."""
        self._run(
            _scenario(
                story=20,
                kind='validation',
                title='search with no matches is handled',
                path='/user-management?query=missing',
                status=200,
                role=ADMIN,
                patches=(
                        P(
                            'controllers.AdminSearchC.UserAccount.findUser',
                            [],
                        ),
                    ),
                called_with={
                    'controllers.AdminSearchC.UserAccount.findUser': {
                        'args': ('missing',),
                    },
                },
            )
        )

    def test_us21_validation_already_suspended_account_is_rejected(self):
        """US21 validation: already suspended account is rejected."""
        self._run(
            _scenario(
                story=21,
                kind='validation',
                title='already suspended account is rejected',
                path='/user-management/suspend/7',
                status=302,
                method='POST',
                role=ADMIN,
                patches=(
                        P(
                            'controllers.AdminSuspendC.AdminSuspendC.suspendUser',
                            False,
                        ),
                    ),
                location='/user-management',
                flash_contains='User not found or already suspended.',
            )
        )

    def test_us22_validation_already_active_account_cannot_be_unsuspended(self):
        """US22 validation: already active account cannot be unsuspended."""
        self._run(
            _scenario(
                story=22,
                kind='validation',
                title='already active account cannot be unsuspended',
                path='/user-management/unsuspend/7',
                status=302,
                method='POST',
                role=ADMIN,
                patches=(
                        P(
                            'controllers.AdminUnsuspendC.AdminUnsuspendC.unsuspendUser',
                            False,
                        ),
                    ),
                location='/user-management',
                flash_contains='User not found or already active.',
            )
        )

    def test_us23_validation_failed_encryption_stops_processing(self):
        """US23 validation: failed encryption stops processing."""
        self._run(
            _scenario(
                story=23,
                kind='validation',
                title='failed encryption stops processing',
                path='/upload/process/7',
                status=400,
                role=USER,
                patches=(
                        P(
                            'controllers.encryptFileC.File.encryptFile',
                            False,
                        ),
                    ),
                contains='encryption failed',
            )
        )


    def test_us24_validation_split_rejects_missing_encrypted_details(self):
        """US24 validation: split rejects missing encrypted details."""
        self._run(
            _scenario(
                story=24,
                kind='validation',
                title='split rejects missing encrypted details',
                path='/upload/split/7',
                status=400,
                method='POST',
                role=USER,
                patches=(
                        P(
                            'controllers.splitFileC.File.getEncryptedFileDetails',
                            None,
                        ),
                        P(
                            'controllers.splitFileC.File.getProcessingSummary',
                            {},
                        ),
                    ),
                contains='Encrypted file details',
            )
        )

    def test_us25_validation_invalid_k_of_n_is_redisplayed(self):
        """US25 validation: invalid k-of-n is redisplayed."""
        self._run(
            _scenario(
                story=25,
                kind='validation',
                title='invalid k-of-n is redisplayed',
                path='/upload/fragments/7',
                status=200,
                method='POST',
                role=USER,
                data={
                        'total_fragments': '2',
                        'required_fragments': '3',
                    },
                patches=(
                        P(
                            'controllers.configureFragmentsC.StorageNode.getActiveStorageNodeCount',
                            5,
                        ),
                        P(
                            'controllers.configureFragmentsC.File.updateFragmentConfiguration',
                            'Required fragments cannot exceed total fragments.',
                        ),
                        P(
                            'controllers.configureFragmentsC.File.getFilePreviewDetails',
                            {},
                        ),
                    ),
                contains='cannot exceed',
            )
        )

    def test_us26_validation_storage_rejects_file_in_wrong_state(self):
        """US26 validation: storage rejects file in wrong state."""
        self._run(
            _scenario(
                story=26,
                kind='validation',
                title='storage rejects file in wrong state',
                path='/upload/store-fragments/7',
                status=400,
                method='POST',
                role=USER,
                patches=(
                        P(
                            'controllers.storeFragmentC.File.getProcessingFileDetails',
                            {
                            'file_status': 'uploaded',
                        },
                        ),
                        P(
                            'controllers.storeFragmentC.File.updateFileStatus',
                            True,
                        ),
                        P(
                            'controllers.storeFragmentC.File.getProcessingSummary',
                            {},
                        ),
                    ),
                contains='not ready',
            )
        )


    def test_us27_validation_failed_fragment_recovery_is_rejected(self):
        """US27 validation: failed reconstruction or decryption is rejected."""
        self._run(
            _scenario(
                story=27,
                kind='validation',
                title='failed fragment recovery is rejected',
                path='/files/download/7',
                status=400,
                role=USER,
                patches=(
                    P(
                        'controllers.ReconstructAndDecryptFileC.ReconstructAndDecryptFileC.recoverFile',
                        None,
                    ),
                ),
                json={
                    'success': False,
                    'message': 'Unable to recover file. All available fragment combinations failed.',
                },
            )
        )

    def test_us28_validation_sharing_requires_file_and_recipient(self):
        """US28 validation: sharing requires file and recipient."""
        self._run(
            _scenario(
                story=28,
                kind='validation',
                title='sharing requires file and recipient',
                path='/shared',
                status=200,
                method='POST',
                role=USER,
                data={
                        'file_id': '0',
                        'recipient_email': '',
                    },
                patches=(
                        P(
                            'controllers.ShareFileC.ShareFileC.getShareData',
                            {
                            'shareableFiles': [],
                            'shareLinks': [],
                        },
                        ),
                        P(
                            'controllers.ShareFileC.UserAccount.getByEmail',
                            {'username': 'friend'},
                        ),
                        P(
                            'controllers.ShareFileC.ShareFileC.sendShareLinkEmail',
                            (True, None),
                        ),
                    ),
                contains='Select a file',
            )
        )

    def test_us29_validation_failed_revocation_records_an_error(self):
        """US29 validation: failed revocation records an error."""
        self._run(
            _scenario(
                story=29,
                kind='validation',
                title='failed revocation records an error',
                path='/shared/revoke/5',
                status=302,
                method='POST',
                role=USER,
                patches=(
                        P(
                            'controllers.RevokeShareLinkC.RevokeShareLinkC.revokeShareLink',
                            False,
                        ),
                    ),
                location='/shared',
                session_values={
                    'shared_error_message': 'Unable to revoke link.',
                },
            )
        )

    def test_us30_validation_unowned_file_returns_sharing_error(self):
        """US30 validation: unowned file returns sharing error."""
        self._run(
            _scenario(
                story=30,
                kind='validation',
                title='unowned file returns sharing error',
                path='/shared/users/99',
                status=200,
                role=USER,
                patches=(
                        P(
                            'controllers.ViewSharedUsersC.ViewSharedUsersC.viewSharedUsers',
                            (
                            [],
                            'File not found.',
                        ),
                        ),
                    ),
                contains='File not found',
            )
        )

    def test_us31_validation_invalid_one_time_token_is_denied(self):
        """US31 validation: invalid one-time token is denied."""
        self._run(
            _scenario(
                story=31,
                kind='validation',
                title='invalid one-time token is denied',
                path='/share/bad-token',
                status=404,
                role=USER,
                patches=(
                        P(
                            'controllers.AccessSharedFileC.AccessSharedFileC.accessSharedLink',
                            (
                            None,
                            'Access denied.',
                            'no_permission',
                        ),
                        ),
                    ),
                contains='Access denied',
            )
        )

    def test_us32_validation_download_without_valid_access_is_denied(self):
        """US32 validation: download without valid access is denied."""
        self._run(
            _scenario(
                story=32,
                kind='validation',
                title='download without valid access is denied',
                path='/share/bad/download',
                status=404,
                role=USER,
                patches=(
                        P(
                            'controllers.DownloadFileC.DownloadFileC.downloadSharedFile',
                            (
                            None,
                            'Access denied.',
                        ),
                        ),
                    ),
                contains='Access denied',
            )
        )

    def test_us33_validation_invalid_expiry_is_not_saved(self):
        """US33 validation: invalid expiry is not saved."""
        self._run(
            _scenario(
                story=33,
                kind='validation',
                title='invalid expiry is not saved',
                path='/shared/expiry/5',
                status=302,
                method='POST',
                role=USER,
                data={
                        'expiry_datetime': '',
                    },
                patches=(
                        P(
                            'controllers.SetLinkExpiryC.SetLinkExpiryC.setLinkExpiry',
                            False,
                        ),
                    ),
                location='/shared',
                session_values={
                    'shared_error_message': 'Unable to set expiry.',
                },
            )
        )

    def test_us34_validation_expired_token_returns_expired_status(self):
        """US34 validation: expired token returns expired status."""
        self._run(
            _scenario(
                story=34,
                kind='validation',
                title='expired token returns expired status',
                path='/share/expired',
                status=404,
                role=USER,
                patches=(
                        P(
                            'controllers.AccessSharedFileC.AccessSharedFileC.accessSharedLink',
                            (
                            None,
                            'This link has expired.',
                            'expired',
                        ),
                        ),
                    ),
                contains='expired',
            )
        )

    def test_us35_validation_out_of_range_maximum_expiry_is_rejected(self):
        """US35 validation: out-of-range maximum expiry is rejected."""
        self._run(
            _scenario(
                story=35,
                kind='validation',
                title='out-of-range maximum expiry is rejected',
                path='/system-admin/settings/max-expiry',
                status=400,
                method='POST',
                role=SYSADMIN,
                data={
                        'max_duration': '999',
                    },
                patches=(
                        P(
                            'controllers.MaxExpirySettingsC.SystemSetting.updateMaxExpiryDuration',
                            False,
                        ),
                        P(
                            'controllers.MaxExpirySettingsC.SystemSetting.getSecuritySettings',
                            {},
                        ),
                    ),
                contains='Invalid max expiry',
            )
        )

    def test_us36_validation_missing_preview_record_returns_not_found(self):
        """US36 validation: missing preview record returns not found."""
        self._run(
            _scenario(
                story=36,
                kind='validation',
                title='missing preview record returns not found',
                path='/upload/preview/99',
                status=404,
                role=USER,
                patches=(
                        P(
                            'controllers.previewUploadedFileC.File.getFilePreviewDetails',
                            None,
                        ),
                    ),
                contains='could not be found',
            )
        )

    def test_us37_validation_replacement_reports_deletion_failure(self):
        """US37 validation: replacement reports deletion failure."""
        self._run(
            _scenario(
                story=37,
                kind='validation',
                title='replacement reports deletion failure',
                path='/upload/replace/7',
                status=500,
                method='POST',
                role=USER,
                patches=(
                        P(
                            'controllers.replaceUploadedFileC.File.deleteTempFileRecord',
                            False,
                        ),
                    ),
                json={
                        'success': False,
                    },
            )
        )

    def test_us38_validation_unknown_temporary_file_cannot_be_deleted(self):
        """US38 validation: unknown temporary file cannot be deleted."""
        self._run(
            _scenario(
                story=38,
                kind='validation',
                title='unknown temporary file cannot be deleted',
                path='/upload/delete/99',
                status=404,
                method='POST',
                role=USER,
                patches=(
                        P(
                            'controllers.deleteFileC.File.getTempFileById',
                            None,
                        ),
                    ),
                json={
                    'success': False,
                    'message': 'File not found.',
                },
            )
        )

    def test_us39_validation_invalid_password_policy_is_rejected(self):
        """US39 validation: invalid password policy is rejected."""
        self._run(
            _scenario(
                story=39,
                kind='validation',
                title='invalid password policy is rejected',
                path='/system-admin/settings/password-policy',
                status=400,
                method='POST',
                role=SYSADMIN,
                data={
                        'min_length': '40',
                        'max_length': '8',
                    },
                patches=(
                        P(
                            'controllers.PasswordPolicyC.SystemSetting.updatePasswordPolicy',
                            False,
                        ),
                        P(
                            'controllers.PasswordPolicyC.SystemSetting.getSecuritySettings',
                            {},
                        ),
                    ),
                contains='Unable to update password policy',
            )
        )

    def test_us40_validation_invalid_username_policy_is_rejected(self):
        """US40 validation: invalid username policy is rejected."""
        self._run(
            _scenario(
                story=40,
                kind='validation',
                title='invalid username policy is rejected',
                path='/system-admin/settings/username-policy',
                status=400,
                method='POST',
                role=SYSADMIN,
                data={
                        'min_length': '20',
                        'max_length': '3',
                    },
                patches=(
                        P(
                            'controllers.UsernamePolicyC.SystemSetting.updateUsernamePolicy',
                            False,
                        ),
                        P(
                            'controllers.UsernamePolicyC.SystemSetting.getSecuritySettings',
                            {},
                        ),
                    ),
                contains='Unable to update username policy',
            )
        )

    def test_us41_validation_invalid_authentication_policy_is_rejected(self):
        """US41 validation: invalid authentication policy is rejected."""
        self._run(
            _scenario(
                story=41,
                kind='validation',
                title='invalid authentication policy is rejected',
                path='/system-admin/settings/auth-policy',
                status=400,
                method='POST',
                role=SYSADMIN,
                data={
                        'max_login_attempts': '0',
                    },
                patches=(
                        P(
                            'controllers.AuthPolicyC.SystemSetting.updateAuthPolicy',
                            False,
                        ),
                        P(
                            'controllers.AuthPolicyC.SystemSetting.getSecuritySettings',
                            {},
                        ),
                    ),
                contains='Unable to update authentication policy',
            )
        )

    def test_us01_alternate_locked_user_is_denied_login(self):
        """US1 alternate: locked user is denied login."""
        self._run(
            _scenario(
                story=1,
                kind='alternate',
                title='locked user is denied login',
                path='/login',
                status=403,
                method='POST',
                data={
                        'login_credential': 'user',
                        'password': 'bad',
                        'selected_role': 'user',
                    },
                patches=(
                        P(
                            'controllers.LoginC.UserAccount.authenticate',
                            {
                            'authResult': 'locked',
                            'role': 'user',
                        },
                        ),
                    ),
                contains='suspended',
            )
        )

    def test_us02_alternate_admin_can_open_login_page_before_signing_in(self):
        """US2 alternate: admin can open login page before signing in."""
        self._run(
            _scenario(
                story=2,
                kind='alternate',
                title='admin can open login page before signing in',
                path='/login',
                status=200,
                contains='User Admin',
            )
        )

    def test_us03_alternate_suspended_system_admin_is_denied_login(self):
        """US3 alternate: a suspended system admin cannot log in."""
        self._run(
            _scenario(
                story=3,
                kind='alternate',
                title='suspended system admin is denied login',
                path='/login',
                status=403,
                method='POST',
                data={
                    'login_credential': 'sysadmin',
                    'password': 'Sysadmin123!',
                    'selected_role': 'system_admin',
                },
                patches=(
                    P(
                        'controllers.LoginC.UserAccount.authenticate',
                        {
                            'userID': 3,
                            'username': 'sysadmin',
                            'role': 'system_admin',
                            'authResult': 'suspended',
                        },
                    ),
                ),
                contains='This account is suspended.',
            )
        )

    def test_us04_alternate_logout_removes_an_existing_user_session(self):
        """US4 alternate: logout removes an existing user session."""
        self._run(
            _scenario(
                story=4,
                kind='alternate',
                title='logout removes an existing user session',
                path='/logout',
                status=302,
                role=USER,
                location='/login',
                session_values={
                    'user_id': None,
                    'username': None,
                    'role': None,
                },
            )
        )

    def test_us05_alternate_user_admin_logout_without_a_session_is_safe(self):
        """US5 alternate: repeated user-admin logout remains safe."""
        self._run(
            _scenario(
                story=5,
                kind='alternate',
                title='repeated user-admin logout remains safe',
                path='/logout',
                status=302,
                location='/login',
            )
        )

    def test_us06_alternate_system_admin_logout_ignores_a_next_query_safely(self):
        """US6 alternate: system-admin logout still returns to login."""
        self._run(
            _scenario(
                story=6,
                kind='alternate',
                title='system-admin logout ignores a next query safely',
                path='/logout?next=/system-admin/settings',
                status=302,
                role=SYSTEM_ADMIN,
                location='/login',
                session_values={
                    'user_id': None,
                    'username': None,
                    'role': None,
                },
            )
        )

    def test_us07_alternate_disallowed_file_type_is_rejected(self):
        """US7 alternate: disallowed file type is rejected."""
        self._run(
            _scenario(
                story=7,
                kind='alternate',
                title='disallowed file type is rejected',
                path='/upload/start',
                status=400,
                method='POST',
                role=USER,
                data={
                        'file_name': 'malware.exe',
                        'total_size': '100',
                    },
                patches=(
                        P(
                            'controllers.uploadFileC.UploadSession.startUpload',
                            None,
                        ),
                    ),
                json={
                        'success': False,
                    },
            )
        )

    def test_us08_alternate_pause_entity_failure_is_reported(self):
        """US8 alternate: pause entity failure is reported."""
        self._run(
            _scenario(
                story=8,
                kind='alternate',
                title='pause entity failure is reported',
                path='/upload/pause',
                status=400,
                method='POST',
                role=USER,
                data={
                        'upload_id': '10',
                    },
                patches=(
                        P(
                            'controllers.PauseUploadC.UploadSession.saveProgress',
                            False,
                        ),
                    ),
                json={
                        'success': False,
                    },
            )
        )

    def test_us09_alternate_resume_reports_missing_saved_progress(self):
        """US9 alternate: resume reports missing saved progress."""
        self._run(
            _scenario(
                story=9,
                kind='alternate',
                title='resume reports missing saved progress',
                path='/upload/resume',
                status=404,
                method='POST',
                role=USER,
                data={
                        'upload_id': '10',
                    },
                patches=(
                        P(
                            'controllers.ResumeUploadC.UploadSession.retrieveProgress',
                            None,
                        ),
                    ),
                json={
                        'success': False,
                    },
            )
        )

    def test_us10_alternate_temporary_file_deletion_failure_is_reported(self):
        """US10 alternate: temporary file deletion failure is reported."""
        self._run(
            _scenario(
                story=10,
                kind='alternate',
                title='temporary file deletion failure is reported',
                path='/upload/cancel/7',
                status=500,
                method='POST',
                role=USER,
                patches=(
                        P(
                            'controllers.uploadFileC.File.getTempFileById',
                            {
                            'file_id': 7,
                        },
                        ),
                        P(
                            'controllers.uploadFileC.File.deleteTempFileRecord',
                            False,
                        ),
                    ),
                json={
                        'success': False,
                    },
            )
        )

    def test_us11_alternate_duplicate_rename_is_rejected(self):
        """US11 alternate: duplicate rename is rejected."""
        self._run(
            _scenario(
                story=11,
                kind='alternate',
                title='duplicate rename is rejected',
                path='/files/rename/7',
                status=400,
                method='POST',
                role=USER,
                data={
                        'new_name': 'existing.pdf',
                    },
                patches=(
                        P(
                            'controllers.fileManagementC.File.updateName',
                            'A file with this name already exists.',
                        ),
                    ),
                json={
                        'success': False,
                    },
            )
        )

    def test_us12_alternate_search_with_no_match_displays_empty_results(self):
        """US12 alternate: search with no match displays empty results."""
        self._run(
            _scenario(
                story=12,
                kind='alternate',
                title='search with no match displays empty results',
                path='/files/search?query=missing',
                status=200,
                role=USER,
                patches=(
                        P(
                            'controllers.SearchFileC.File.searchManagedFilesByName',
                            [],
                        ),
                    ),
                contains='missing',
            )
        )

    def test_us13_alternate_cleanup_failure_prevents_stored_file_deletion(self):
        """US13 alternate: related-record cleanup failure prevents deletion."""
        self._run(
            _scenario(
                story=13,
                kind='alternate',
                title='cleanup failure prevents stored file deletion',
                path='/files/delete/7',
                status=400,
                method='POST',
                role=USER,
                patches=(
                    P('controllers.deleteFromFileMgmtC.File.getFileDeleteDetails', {'fileID': 7}),
                    P('controllers.deleteFromFileMgmtC.Fragment.getStoredFragmentPaths', ['fragment-1']),
                    P('controllers.deleteFromFileMgmtC.ShareLink.deleteShareLinks', False),
                    P('controllers.deleteFromFileMgmtC.UploadSession.deleteUploadSessions', True),
                    P('controllers.deleteFromFileMgmtC.StorageNode.deleteStoredFragments', True),
                    P('controllers.deleteFromFileMgmtC.Fragment.deleteFragments', True),
                    P('controllers.deleteFromFileMgmtC.File.deleteFileRecord', False),
                ),
                json={
                    'success': False,
                    'message': 'Unable to delete file.',
                },
            )
        )

    def test_us14_alternate_valid_verification_code_creates_account(self):
        """US14 alternate: valid verification code creates account."""
        self._run(
            _scenario(
                story=14,
                kind='alternate',
                title='valid verification code creates account',
                path='/register/verify',
                status=200,
                method='POST',
                data={
                        'username': 'newuser',
                        'token': 'valid',
                    },
                patches=(
                        P(
                            'controllers.RegisterC.RegisterC.verifyRegistration',
                            True,
                        ),
                    ),
                contains='Account verified',
            )
        )

    def test_us15_alternate_reset_request_does_not_reveal_unknown_email(self):
        """US15 alternate: reset request does not reveal unknown email."""
        self._run(
            _scenario(
                story=15,
                kind='alternate',
                title='reset request does not reveal unknown email',
                path='/reset-password',
                status=200,
                method='POST',
                data={
                        'action': 'send_code',
                        'email': 'unknown@example.com',
                    },
                patches=(
                        P(
                            'controllers.PasswordResetC.PasswordResetC.requestReset',
                            (
                            True,
                            None,
                        ),
                        ),
                    ),
                contains='If that email belongs',
            )
        )

    def test_us16_alternate_duplicate_admin_created_account_is_rejected(self):
        """US16 alternate: duplicate admin-created account is rejected."""
        self._run(
            _scenario(
                story=16,
                kind='alternate',
                title='duplicate admin-created account is rejected',
                path='/user-management/create',
                status=302,
                method='POST',
                role=ADMIN,
                data={
                        'username': 'existing',
                        'email': 'existing@example.com',
                        'password': 'Password1!',
                        'role': 'user',
                    },
                patches=(
                        P(
                            'controllers.AdminC.AdminC.createUser',
                            'Account exists.',
                        ),
                    ),
            )
        )

    def test_us17_alternate_admin_views_one_account_in_detail(self):
        """US17 alternate: admin views one account in detail."""
        self._run(
            _scenario(
                story=17,
                kind='alternate',
                title='admin views one account in detail',
                path='/user-management/view/7',
                status=200,
                role=ADMIN,
                patches=(
                        P(
                            'controllers.AdminViewC.AdminViewC.viewUser',
                            {
                            'userID': 7,
                            'username': 'alice',
                            'email': 'alice@example.com',
                            'role': 'User',
                            'accountStatus': 'Active',
                            'createdAt': 'now',
                            'updatedAt': 'now',
                        },
                        ),
                    ),
                contains='alice',
            )
        )

    def test_us18_alternate_update_of_missing_account_redirects_safely(self):
        """US18 alternate: update of missing account redirects safely."""
        self._run(
            _scenario(
                story=18,
                kind='alternate',
                title='update of missing account redirects safely',
                path='/user-management/update/99',
                status=302,
                method='POST',
                role=ADMIN,
                data={
                        'username': 'alice',
                        'email': 'alice@example.com',
                        'role': 'user',
                    },
                patches=(
                        P(
                            'controllers.AdminUpdateC.AdminUpdateC.updateUser',
                            False,
                        ),
                    ),
            )
        )

    def test_us19_alternate_ordinary_user_cannot_delete_accounts(self):
        """US19 alternate: ordinary user cannot delete accounts."""
        self._run(
            _scenario(
                story=19,
                kind='alternate',
                title='ordinary user cannot delete accounts',
                path='/user-management/delete/7',
                status=302,
                method='POST',
                role=USER,
            )
        )

    def test_us20_alternate_blank_search_lists_all_accounts(self):
        """US20 alternate: blank search lists all accounts."""
        self._run(
            _scenario(
                story=20,
                kind='alternate',
                title='blank search lists all accounts',
                path='/user-management',
                status=200,
                role=ADMIN,
                patches=(
                        P(
                            'controllers.AdminSearchC.UserAccount.getAllUserAccounts',
                            [],
                        ),
                    ),
            )
        )

    def test_us21_alternate_ordinary_user_cannot_suspend_accounts(self):
        """US21 alternate: ordinary user cannot suspend accounts."""
        self._run(
            _scenario(
                story=21,
                kind='alternate',
                title='ordinary user cannot suspend accounts',
                path='/user-management/suspend/7',
                status=302,
                method='POST',
                role=USER,
            )
        )

    def test_us22_alternate_ordinary_user_cannot_unsuspend_accounts(self):
        """US22 alternate: ordinary user cannot unsuspend accounts."""
        self._run(
            _scenario(
                story=22,
                kind='alternate',
                title='ordinary user cannot unsuspend accounts',
                path='/user-management/unsuspend/7',
                status=302,
                method='POST',
                role=USER,
            )
        )

    def test_us23_alternate_missing_processing_summary_is_reported(self):
        """US23 alternate: missing processing summary is reported."""
        self._run(
            _scenario(
                story=23,
                kind='alternate',
                title='missing processing summary is reported',
                path='/upload/process/7',
                status=404,
                role=USER,
                patches=(
                        P(
                            'controllers.encryptFileC.File.encryptFile',
                            True,
                        ),
                        P(
                            'controllers.encryptFileC.File.getProcessingSummary',
                            None,
                        ),
                    ),
                contains='summary could not be found',
            )
        )


    def test_us24_alternate_incorrect_fragment_count_marks_split_failed(self):
        """US24 alternate: incorrect fragment count marks split failed."""
        self._run(
            _scenario(
                story=24,
                kind='alternate',
                title='incorrect fragment count marks split failed',
                path='/upload/split/7',
                status=400,
                method='POST',
                role=USER,
                patches=(
                        P(
                            'controllers.splitFileC.File.getEncryptedFileDetails',
                            {
                            'file_id': 7,
                            'encrypted_temp_path': 'file.enc',
                            'total_fragments': 3,
                            'required_fragments': 2,
                        },
                        ),
                        P(
                            'controllers.splitFileC.Fragment.splitIntoFragments',
                            [
                            1,
                        ],
                        ),
                        P(
                            'controllers.splitFileC.File.updateFileStatus',
                            True,
                        ),
                        P(
                            'controllers.splitFileC.File.getProcessingSummary',
                            {},
                        ),
                    ),
                contains='File splitting failed',
            )
        )

    def test_us25_alternate_alternative_valid_2_of_3_configuration_works(self):
        """US25 alternate: alternative valid 2-of-3 configuration works."""
        self._run(
            _scenario(
                story=25,
                kind='alternate',
                title='alternative valid 2-of-3 configuration works',
                path='/upload/fragments/7',
                status=302,
                method='POST',
                role=USER,
                data={
                        'total_fragments': '3',
                        'required_fragments': '2',
                    },
                patches=(
                        P(
                            'controllers.configureFragmentsC.StorageNode.getActiveStorageNodeCount',
                            3,
                        ),
                        P(
                            'controllers.configureFragmentsC.File.updateFragmentConfiguration',
                            None,
                        ),
                    ),
            )
        )

    def test_us26_alternate_insufficient_storage_nodes_prevents_storage(self):
        """US26 alternate: insufficient storage nodes prevents storage."""
        self._run(
            _scenario(
                story=26,
                kind='alternate',
                title='insufficient storage nodes prevents storage',
                path='/upload/store-fragments/7',
                status=400,
                method='POST',
                role=USER,
                patches=(
                        P(
                            'controllers.storeFragmentC.File.getProcessingFileDetails',
                            {
                            'file_status': 'pending_processing',
                        },
                        ),
                        P(
                            'controllers.storeFragmentC.Fragment.getFragmentList',
                            [
                            {
                                'fragment_id': 1,
                            },
                            {
                                'fragment_id': 2,
                            },
                        ],
                        ),
                        P(
                            'controllers.storeFragmentC.File.getProcessingSummary',
                            {
                            'totalFragments': 2,
                        },
                        ),
                        P(
                            'controllers.storeFragmentC.StorageNode.getActiveStorageNodes',
                            [],
                        ),
                        P(
                            'controllers.storeFragmentC.File.updateFileStatus',
                            True,
                        ),
                    ),
                contains='not enough active storage nodes',
            )
        )


    def test_us27_alternate_unauthenticated_recovery_redirects_to_login(self):
        """US27 alternate: unauthenticated recovery redirects to login."""
        self._run(
            _scenario(
                story=27,
                kind='alternate',
                title='unauthenticated recovery redirects to login',
                path='/files/download/7',
                status=302,
                location='/login',
            )
        )

    def test_us28_alternate_one_time_option_is_passed_when_sharing(self):
        """US28 alternate: one-time option is passed when sharing."""
        self._run(
            _scenario(
                story=28,
                kind='alternate',
                title='one-time option is passed when sharing',
                path='/shared',
                status=200,
                method='POST',
                role=USER,
                data={
                        'file_id': '7',
                        'recipient_email': 'friend@example.com',
                        'expiry_hours': '24',
                        'is_one_time': 'on',
                    },
                patches=(
                        P(
                            'controllers.ShareFileC.ShareFileC.createShareLink',
                            (
                            'token',
                            None,
                        ),
                        ),
                        P(
                            'controllers.ShareFileC.ShareFileC.getShareData',
                            {
                            'shareableFiles': [],
                            'shareLinks': [],
                        },
                        ),
                        P(
                            'controllers.ShareFileC.UserAccount.getByEmail',
                            {
                                'username': 'friend',
                            },
                        ),
                        P(
                            'controllers.ShareFileC.ShareFileC.sendShareLinkEmail',
                            (
                                True,
                                None,
                            ),
                        ),
                    ),
                contains='Secure link created',
            )
        )

    def test_us29_alternate_unauthenticated_revocation_redirects_to_login(self):
        """US29 alternate: unauthenticated revocation redirects to login."""
        self._run(
            _scenario(
                story=29,
                kind='alternate',
                title='unauthenticated revocation redirects to login',
                path='/shared/revoke/5',
                status=302,
                method='POST',
            )
        )

    def test_us30_alternate_file_with_no_recipients_shows_an_empty_list(self):
        """US30 alternate: file with no recipients shows an empty list."""
        self._run(
            _scenario(
                story=30,
                kind='alternate',
                title='file with no recipients shows an empty list',
                path='/shared/users/7',
                status=200,
                role=USER,
                patches=(
                        P(
                            'controllers.ViewSharedUsersC.ViewSharedUsersC.viewSharedUsers',
                            (
                            [],
                            None,
                        ),
                        ),
                    ),
            )
        )

    def test_us31_alternate_used_one_time_link_is_denied(self):
        """US31 alternate: used one-time link is denied."""
        self._run(
            _scenario(
                story=31,
                kind='alternate',
                title='used one-time link is denied',
                path='/share/used',
                status=404,
                role=USER,
                patches=(
                        P(
                            'controllers.AccessSharedFileC.AccessSharedFileC.accessSharedLink',
                            (
                            None,
                            'This one-time link has already been used.',
                            'used',
                        ),
                        ),
                    ),
                contains='already been used',
            )
        )

    def test_us32_alternate_valid_shared_download_returns_original_bytes(self):
        """US32 alternate: valid shared download returns original bytes."""
        self._run(
            _scenario(
                story=32,
                kind='alternate',
                title='valid shared download returns original bytes',
                path='/share/token/download',
                status=200,
                role=USER,
                patches=(
                        P(
                            'controllers.DownloadFileC.DownloadFileC.downloadSharedFile',
                            (
                            {
                                'fileBytes': b'hello',
                                'fileName': 'hello.txt',
                                'fileType': 'text/plain',
                            },
                            None,
                        ),
                        ),
                    ),
                contains='hello',
            )
        )

    def test_us33_alternate_unauthenticated_expiry_update_redirects(self):
        """US33 alternate: unauthenticated expiry update redirects."""
        self._run(
            _scenario(
                story=33,
                kind='alternate',
                title='unauthenticated expiry update redirects',
                path='/shared/expiry/5',
                status=302,
                method='POST',
                data={
                        'expiry_datetime': '2026-08-03T12:00',
                    },
            )
        )

    def test_us34_alternate_revoked_link_is_also_inaccessible(self):
        """US34 alternate: revoked link is also inaccessible."""
        self._run(
            _scenario(
                story=34,
                kind='alternate',
                title='revoked link is also inaccessible',
                path='/share/revoked',
                status=404,
                role=USER,
                patches=(
                        P(
                            'controllers.AccessSharedFileC.AccessSharedFileC.accessSharedLink',
                            (
                            None,
                            'Link revoked.',
                            'revoked',
                        ),
                        ),
                    ),
                contains='revoked',
            )
        )

    def test_us35_alternate_ordinary_user_cannot_configure_maximum_expiry(self):
        """US35 alternate: ordinary user cannot configure maximum expiry."""
        self._run(
            _scenario(
                story=35,
                kind='alternate',
                title='ordinary user cannot configure maximum expiry',
                path='/system-admin/settings/max-expiry',
                status=302,
                method='POST',
                role=USER,
                data={
                        'max_duration': '24',
                    },
            )
        )

    def test_us36_alternate_unauthenticated_preview_redirects_to_login(self):
        """US36 alternate: unauthenticated preview redirects to login."""
        self._run(
            _scenario(
                story=36,
                kind='alternate',
                title='unauthenticated preview redirects to login',
                path='/upload/preview/7',
                status=302,
            )
        )

    def test_us37_alternate_unauthenticated_replacement_is_rejected(self):
        """US37 alternate: unauthenticated replacement is rejected."""
        self._run(
            _scenario(
                story=37,
                kind='alternate',
                title='unauthenticated replacement is rejected',
                path='/upload/replace/7',
                status=401,
                method='POST',
                json={
                        'success': False,
                    },
            )
        )

    def test_us38_alternate_temporary_file_removal_failure_is_reported(self):
        """US38 alternate: temporary file removal failure is reported."""
        self._run(
            _scenario(
                story=38,
                kind='alternate',
                title='temporary file removal failure is reported',
                path='/upload/delete/7',
                status=500,
                method='POST',
                role=USER,
                patches=(
                        P(
                            'controllers.deleteFileC.File.getTempFileById',
                            {
                            'file_id': 7,
                        },
                        ),
                        P(
                            'controllers.deleteFileC.File.removeFile',
                            False,
                        ),
                    ),
                json={
                        'success': False,
                    },
            )
        )

    def test_us39_alternate_ordinary_user_cannot_change_password_policy(self):
        """US39 alternate: ordinary user cannot change password policy."""
        self._run(
            _scenario(
                story=39,
                kind='alternate',
                title='ordinary user cannot change password policy',
                path='/system-admin/settings/password-policy',
                status=302,
                method='POST',
                role=USER,
                data={
                        'min_length': '8',
                        'max_length': '32',
                    },
            )
        )

    def test_us40_alternate_ordinary_user_cannot_change_username_policy(self):
        """US40 alternate: ordinary user cannot change username policy."""
        self._run(
            _scenario(
                story=40,
                kind='alternate',
                title='ordinary user cannot change username policy',
                path='/system-admin/settings/username-policy',
                status=302,
                method='POST',
                role=USER,
                data={
                        'min_length': '3',
                        'max_length': '20',
                    },
            )
        )

    def test_us41_alternate_ordinary_user_cannot_change_authentication_policy(self):
        """US41 alternate: ordinary user cannot change authentication policy."""
        self._run(
            _scenario(
                story=41,
                kind='alternate',
                title='ordinary user cannot change authentication policy',
                path='/system-admin/settings/auth-policy',
                status=302,
                method='POST',
                role=USER,
                data={
                        'max_login_attempts': '5',
                    },
            )
        )


def _scenario(story, kind, title, path, status, method="GET", role=None,
              data=None, patches=(), contains=None, json=None, session=None,
              follow=False, called=(), location=None, flash_contains=None,
              called_with=None, session_values=None):
    return {
        "story": story, "kind": kind, "title": title, "path": path,
        "status": status, "method": method, "role": role, "data": data,
        "patches": patches, "contains": contains, "json": json,
        "session": session or {}, "follow": follow, "called": called,
        "location": location, "flash_contains": flash_contains,
        "called_with": called_with or {},
        "session_values": session_values,
    }


P = lambda target, value: (target, value)
USER = "user"
ADMIN = "user_admin"
SYSTEM_ADMIN = "system_admin"
SYSADMIN = "system_admin"


class AdminDeleteControllerTests(unittest.TestCase):

    @patch("controllers.AdminDeleteC.UserAccount.deleteAccount", return_value=True)
    @patch("controllers.AdminDeleteC.SystemSetting.reassignUpdatedBy", return_value=True)
    @patch("controllers.AdminDeleteC.UserAccount.deletePasswordResetTokens", return_value=True)
    @patch("controllers.AdminDeleteC.File.deleteFilesByOwner", return_value=True)
    @patch("controllers.AdminDeleteC.Fragment.deleteFragmentsByFileIds", return_value=True)
    @patch("controllers.AdminDeleteC.StorageNode.deleteStoredFragments", return_value=True)
    @patch("controllers.AdminDeleteC.UploadSession.deleteUploadSessionsForUser", return_value=True)
    @patch("controllers.AdminDeleteC.ShareLink.deleteShareLinksForUser", return_value=True)
    @patch("controllers.AdminDeleteC.StorageNode.getStorageNodePaths")
    @patch("controllers.AdminDeleteC.Fragment.getStoredFragmentPathsByFileIds")
    @patch("controllers.AdminDeleteC.File.getFileIdsByOwner")
    @patch("controllers.AdminDeleteC.UserAccount.checkUserExistsById", return_value=True)
    def test_delete_user_coordinates_entity_cleanup_and_oci_deletion(
        self,
        user_exists,
        get_file_ids,
        get_fragment_paths,
        get_node_paths,
        delete_share_links,
        delete_upload_sessions,
        delete_stored_fragments,
        delete_fragments,
        delete_files,
        delete_reset_tokens,
        reassign_settings,
        delete_account
    ):
        from controllers.AdminDeleteC import AdminDeleteC

        get_file_ids.return_value = [11, 12]
        get_fragment_paths.return_value = [
            {"fragment_id": 21, "fragment_path": "file_11/fragment_1.fec", "node_id": 3}
        ]
        get_node_paths.return_value = {3: "lazarus-node-03"}

        self.assertTrue(AdminDeleteC.deleteUser(7, 2))
        user_exists.assert_called_once_with(7)
        delete_share_links.assert_called_once_with(7, [11, 12])
        delete_upload_sessions.assert_called_once_with(7, [11, 12])
        delete_stored_fragments.assert_called_once_with([
            {
                "fragment_id": 21,
                "fragment_path": "file_11/fragment_1.fec",
                "node_id": 3,
                "node_path": "lazarus-node-03"
            }
        ])
        delete_fragments.assert_called_once_with([11, 12])
        delete_files.assert_called_once_with(7)
        delete_reset_tokens.assert_called_once_with(7)
        reassign_settings.assert_called_once_with(7, 2)
        delete_account.assert_called_once_with(
            user_id=7,
            replacement_user_id=2
        )

    @patch("controllers.AdminDeleteC.Fragment.deleteFragmentsByFileIds")
    @patch("controllers.AdminDeleteC.StorageNode.deleteStoredFragments", return_value=False)
    @patch("controllers.AdminDeleteC.UploadSession.deleteUploadSessionsForUser", return_value=True)
    @patch("controllers.AdminDeleteC.ShareLink.deleteShareLinksForUser", return_value=True)
    @patch("controllers.AdminDeleteC.StorageNode.getStorageNodePaths", return_value={1: "bucket"})
    @patch("controllers.AdminDeleteC.Fragment.getStoredFragmentPathsByFileIds", return_value=[
        {"fragment_id": 1, "fragment_path": "object.fec", "node_id": 1}
    ])
    @patch("controllers.AdminDeleteC.File.getFileIdsByOwner", return_value=[10])
    @patch("controllers.AdminDeleteC.UserAccount.checkUserExistsById", return_value=True)
    def test_delete_user_stops_database_deletion_when_oci_cleanup_fails(
        self,
        _user_exists,
        _get_file_ids,
        _get_fragment_paths,
        _get_node_paths,
        _delete_share_links,
        _delete_upload_sessions,
        _delete_stored_fragments,
        delete_fragments
    ):
        from controllers.AdminDeleteC import AdminDeleteC

        self.assertFalse(AdminDeleteC.deleteUser(7, 2))
        delete_fragments.assert_not_called()


def load_tests(loader, discovered_tests, pattern):
    """Run the suite in US01-US41 order, with all three cases together."""

    def flatten(suite):
        for item in suite:
            if isinstance(item, unittest.TestSuite):
                yield from flatten(item)
            else:
                yield item

    case_order = {"main": 0, "validation": 1, "alternate": 2}

    def order_key(test):
        method_name = test.id().rsplit(".", 1)[-1]
        match = re.match(r"test_us(\d+)_(main|validation|alternate)_", method_name)
        if match is None:
            return (999, 999, method_name)
        return (
            int(match.group(1)),
            case_order[match.group(2)],
            method_name,
        )

    return unittest.TestSuite(sorted(flatten(discovered_tests), key=order_key))

if __name__ == "__main__":
    unittest.main()

