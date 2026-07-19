import sys
import types
import unittest
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

import app as app_module


class UserStoryRouteTests(unittest.TestCase):

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
    def test_user_can_login_and_access_dashboard(self, authenticate_mock):
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
    def test_admin_can_login_and_access_admin_dashboard(self, authenticate_mock):
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

    # 3. As a user, I want to log out so that I can securely end my session.
    def test_user_can_logout_and_clear_session(self):
        self._set_session(user_id=1, username="testuser", role="user")

        response = self.client.get("/logout", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/login")

        with self.client.session_transaction() as session:
            self.assertNotIn("user_id", session)
            self.assertNotIn("role", session)

    # 5. As a user, I want to upload a file so that I can store it securely in the system.
    @patch("controllers.uploadFileC.UploadSession.startUpload")
    def test_user_can_start_an_upload_session(self, start_upload_mock):
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

    # 6. As a user, I want to pause file upload so that I can manage interruptions.
    @patch("controllers.PauseUploadC.UploadSession.saveProgress")
    def test_user_can_pause_an_upload_session(self, save_progress_mock):
        self._set_session(user_id=1, username="testuser", role="user")
        save_progress_mock.return_value = True

        response = self.client.post(
            "/upload/pause",
            data={"upload_id": 10}
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

    # 7. As a user, I want to resume file upload so that I can continue from where I stopped.
    @patch("controllers.ResumeUploadC.UploadSession.retrieveProgress")
    @patch("controllers.ResumeUploadC.UploadSession.continueUpload")
    def test_user_can_resume_an_upload_session(self, continue_upload_mock, retrieve_progress_mock):
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

    # 8. As a user, I want to cancel file upload so that I can stop unwanted uploads.
    @patch("controllers.uploadFileC.File.getTempFileById")
    @patch("controllers.uploadFileC.File.deleteTempFileRecord")
    def test_user_can_cancel_a_temp_upload(self, delete_temp_mock, get_temp_mock):
        self._set_session(user_id=1, username="testuser", role="user")
        get_temp_mock.return_value = {"file_id": 5}
        delete_temp_mock.return_value = True

        response = self.client.post("/upload/cancel/5")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

    # 9. As a user, I want to rename a file so that I can organize my files easily.
    @patch("controllers.fileManagementC.File.updateName")
    def test_user_can_rename_a_managed_file(self, update_name_mock):
        self._set_session(user_id=1, username="testuser", role="user")
        update_name_mock.return_value = None

        response = self.client.post(
            "/files/rename/7",
            data={"new_name": "renamed-report.pdf"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

    # 11. As a user, I want to search my uploaded files so that I can quickly find a specific file to manage.
    @patch("controllers.SearchFileC.File.searchManagedFilesByName")
    def test_user_can_search_for_a_managed_file(self, search_mock):
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

    # 10. As a user, I want to delete my uploaded file after encryption so that it is no longer in the system.
    @patch("controllers.deleteFileC.ShareLink.deleteShareLinks")
    @patch("controllers.deleteFileC.UploadSession.deleteUploadSessions")
    @patch("controllers.deleteFileC.Fragment.deleteFragments")
    @patch("controllers.deleteFileC.File.deleteFileRecord")
    @patch("controllers.deleteFileC.File.getFileDeleteDetails")
    def test_user_can_delete_a_processed_file(self, get_delete_details_mock, delete_file_record_mock, delete_fragments_mock, delete_upload_sessions_mock, delete_share_links_mock):
        self._set_session(user_id=1, username="testuser", role="user")
        get_delete_details_mock.return_value = {"file_id": 7}
        delete_share_links_mock.return_value = True
        delete_upload_sessions_mock.return_value = True
        delete_fragments_mock.return_value = True
        delete_file_record_mock.return_value = True

        response = self.client.post("/files/delete/7")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

    # 14. As a user admin, I want to create user accounts so that new users can access the system.
    @patch("controllers.AdminC.UserAccount.checkUserExists")
    @patch("controllers.AdminC.UserAccount.createAccount")
    def test_admin_can_create_new_user_accounts(self, create_account_mock, check_user_exists_mock):
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

    # 15. As a user admin, I want to view user accounts so that I can monitor user details.
    @patch("controllers.AdminSearchC.UserAccount.getAllUserAccounts")
    def test_admin_can_view_and_search_user_accounts(self, get_all_accounts_mock):
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

    # 16. As a user admin, I want to update user accounts so that I can maintain accurate information.
    @patch("controllers.AdminUpdateC.UserAccount.getUserDetails")
    @patch("controllers.AdminUpdateC.UserAccount.checkUserExistsById")
    @patch("controllers.AdminUpdateC.UserAccount.updateAccount")
    def test_admin_can_update_user_account_details(self, update_account_mock, check_user_exists_mock, get_user_details_mock):
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

    # 19. As a user admin, I want to suspend user accounts so that I can block access for users when necessary.
    @patch("controllers.AdminSuspendC.UserAccount.checkUserExistsById")
    @patch("controllers.AdminSuspendC.UserAccount.getStatus")
    @patch("controllers.AdminSuspendC.UserAccount.setStatus")
    def test_admin_can_suspend_and_unsuspend_user_accounts(self, set_status_mock, get_status_mock, check_user_exists_mock):
        self._set_session(user_id=2, username="admin", role="user_admin")
        check_user_exists_mock.return_value = True
        get_status_mock.side_effect = ["active", "suspended"]

        suspend_response = self.client.post("/user-management/suspend/1", follow_redirects=False)
        unsuspend_response = self.client.post("/user-management/unsuspend/1", follow_redirects=False)

        self.assertEqual(suspend_response.status_code, 302)
        self.assertEqual(unsuspend_response.status_code, 302)
        self.assertEqual(set_status_mock.call_count, 2)

    # 21. As a user, I want my file to be automatically encrypted before splitting so that the content is protected even if fragments are intercepted.
    @patch("controllers.encryptFileC.File.encryptFile")
    @patch("controllers.encryptFileC.File.getProcessingSummary")
    def test_uploaded_file_is_encrypted_before_splitting(self, get_processing_summary_mock, encrypt_file_mock):
        self._set_session(user_id=1, username="testuser", role="user")
        encrypt_file_mock.return_value = True
        get_processing_summary_mock.return_value = {
            "fileName": "example.txt",
            "fileType": "text/plain"
        }

        response = self.client.get("/upload/process/7")

        self.assertEqual(response.status_code, 200)
        self.assertIn("example.txt", response.get_data(as_text=True))

    # 31. As a user, I want to download and reconstruct a shared file only when I have valid access so that I can securely retrieve the original content on my device.
    @patch("controllers.ReconstructFileC.File.getReconstructionRequirement")
    @patch("controllers.ReconstructFileC.Fragment.getAvailableFragments")
    @patch("controllers.ReconstructFileC.StorageNode.retrieveFragments")
    @patch("controllers.ReconstructFileC.Fragment.reconstructFragments")
    def test_user_can_reconstruct_encrypted_file_for_download(self, reconstruct_fragments_mock, retrieve_fragments_mock, get_available_fragments_mock, get_reconstruction_requirement_mock):
        self._set_session(user_id=1, username="testuser", role="user")
        get_reconstruction_requirement_mock.return_value = {
            "requiredFragments": 2,
            "totalFragments": 3,
            "encryptedSize": 256
        }
        get_available_fragments_mock.return_value = ["fragment-1"]
        retrieve_fragments_mock.return_value = [b"fragment-data"]
        reconstruct_fragments_mock.return_value = "/tmp/reconstructed.enc"

        response = self.client.get("/files/reconstruct/7")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

    # 22. As a user, I want my file to be automatically decrypted after reconstruction so that I can access the original content without manual steps.
    @patch("controllers.DecryptFileC.File.decryptFile")
    def test_user_can_decrypt_reconstructed_file_for_download(self, decrypt_file_mock):
        self._set_session(user_id=1, username="testuser", role="user")
        decrypt_file_mock.return_value = {
            "fileBytes": b"plain data",
            "fileName": "example.txt",
            "fileType": "text/plain"
        }

        with self.client.session_transaction() as session:
            session["reconstructed_file_id"] = 7
            session["reconstructed_temp_path"] = "/tmp/reconstructed.enc"

        response = self.client.get("/files/decrypt/7")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/plain")

    # 34. As a system admin, I want to define a maximum expiry duration so that link sharing remains secure and controlled.
    @patch("controllers.MaxExpirySettingsC.SystemSetting.updateMaxExpiryDuration")
    @patch("controllers.MaxExpirySettingsC.SystemSetting.getSecuritySettings")
    def test_system_admin_can_set_max_expiry_duration(self, get_security_settings_mock, update_max_expiry_mock):
        self._set_session(user_id=3, username="sysadmin", role="system_admin")
        get_security_settings_mock.return_value = {"maxExpiryDuration": 24}
        update_max_expiry_mock.return_value = True

        response = self.client.post(
            "/system-admin/settings/max-expiry",
            data={"max_duration": "24"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Max expiry duration set.", response.get_data(as_text=True))

    # 38. As a system admin, I want to enforce password requirements so that user accounts meet security standards.
    @patch("controllers.PasswordPolicyC.SystemSetting.updatePasswordPolicy")
    @patch("controllers.PasswordPolicyC.SystemSetting.getSecuritySettings")
    @patch("controllers.UsernamePolicyC.SystemSetting.updateUsernamePolicy")
    @patch("controllers.UsernamePolicyC.SystemSetting.getSecuritySettings")
    @patch("controllers.AuthPolicyC.SystemSetting.updateAuthPolicy")
    @patch("controllers.AuthPolicyC.SystemSetting.getSecuritySettings")
    def test_system_admin_can_enforce_security_policies(self, auth_get_settings_mock, auth_update_policy_mock, username_get_settings_mock, username_update_policy_mock, password_get_settings_mock, password_update_policy_mock):
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

    # 35. As a user, I want to preview my uploaded file before encryption so that I can confirm it is the correct file.
    @patch("controllers.previewUploadedFileC.File.getFilePreviewDetails")
    def test_user_can_preview_an_uploaded_file_before_encryption(self, get_preview_details_mock):
        self._set_session(user_id=1, username="testuser", role="user")
        get_preview_details_mock.return_value = {
            "fileID": 7,
            "fileName": "draft.pdf",
            "fileType": "application/pdf"
        }

        response = self.client.get("/upload/preview/7")

        self.assertEqual(response.status_code, 200)
        self.assertIn("draft.pdf", response.get_data(as_text=True))

    # 36. As a user, I want to replace my uploaded file before encryption so that I can upload the correct version if I selected the wrong file.
    @patch("controllers.replaceUploadedFileC.File.deleteTempFileRecord")
    def test_user_can_replace_a_temp_upload_before_encryption(self, delete_temp_mock):
        self._set_session(user_id=1, username="testuser", role="user")
        delete_temp_mock.return_value = True

        response = self.client.post("/upload/replace/7")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])


if __name__ == "__main__":
    unittest.main()
