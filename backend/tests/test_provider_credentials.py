import os
import tempfile
import unittest
from datetime import datetime, timezone
from uuid import uuid4

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.core.security import (
    EncryptionConfigurationError,
    EncryptionError,
    decrypt_api_key,
    encrypt_api_key,
    mask_api_key,
)
from app.domain.entities import ProviderCredential, User
from app.infrastructure.answer_generator_factory import DynamicAnswerGeneratorFactory
from app.infrastructure.gemini_answer_generator import GeminiAnswerGenerator
from app.infrastructure.sqlite_store import (
    SqliteProviderCredentialRepository,
    SqliteStore,
    SqliteUserRepository,
)
from app.application.errors import AnswerGenerationError
from app.main import create_app


class TestSecurityEncryption(unittest.TestCase):
    def setUp(self) -> None:
        self.test_key = Fernet.generate_key().decode()

    def test_encrypt_and_decrypt_round_trip(self) -> None:
        secret = "AIzaSyDummyGeminiKey1234567890"
        encrypted = encrypt_api_key(secret, encryption_key=self.test_key)
        self.assertNotEqual(secret, encrypted)
        self.assertNotIn(secret, encrypted)

        decrypted = decrypt_api_key(encrypted, encryption_key=self.test_key)
        self.assertEqual(secret, decrypted)

    def test_decrypt_with_tampered_token_raises_error(self) -> None:
        secret = "AIzaSyDummyGeminiKey1234567890"
        encrypted = encrypt_api_key(secret, encryption_key=self.test_key)
        tampered = encrypted[:-4] + "AAAA"
        with self.assertRaises(EncryptionError):
            decrypt_api_key(tampered, encryption_key=self.test_key)

    def test_missing_encryption_key_raises_configuration_error(self) -> None:
        # Pass empty string to simulate missing key
        with self.assertRaises(EncryptionConfigurationError):
            encrypt_api_key("secret", encryption_key="")

    def test_mask_api_key(self) -> None:
        key = "fake_gemini_test_key_abcdef_sample_1234"
        masked = mask_api_key(key)
        self.assertTrue(masked.startswith("fake"))
        self.assertTrue(masked.endswith("1234"))
        self.assertIn("••••••••", masked)
        self.assertNotIn("test_key_abcdef", masked)
        self.assertNotEqual(key, masked)

    def test_mask_short_key(self) -> None:
        short = "12345"
        masked = mask_api_key(short)
        self.assertEqual("••••45", masked)


class TestProviderCredentialRepository(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "test_rag.sqlite3")
        self.store = SqliteStore(self.db_path)
        self.user_repo = SqliteUserRepository(self.store)
        self.repo = SqliteProviderCredentialRepository(self.store)

        self.user1 = self.user_repo.create("User 1", "user1@example.com", "hash1")
        self.user2 = self.user_repo.create("User 2", "user2@example.com", "hash2")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_save_and_get_credential(self) -> None:
        now = datetime.now(timezone.utc)
        cred = ProviderCredential(
            id=str(uuid4()),
            user_id=self.user1.id,
            provider="gemini",
            masked_key="fake••••••••1234",
            encrypted_key="enc_secret_key_1",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.repo.save(cred)

        fetched = self.repo.get(self.user1.id, "gemini")
        self.assertIsNotNone(fetched)
        assert fetched is not None
        self.assertEqual(fetched.masked_key, "fake••••••••1234")
        self.assertEqual(fetched.encrypted_key, "enc_secret_key_1")

    def test_upsert_credential_updates_existing(self) -> None:
        now = datetime.now(timezone.utc)
        cred1 = ProviderCredential(
            id=str(uuid4()),
            user_id=self.user1.id,
            provider="gemini",
            masked_key="fake••••••••1234",
            encrypted_key="enc_secret_1",
            created_at=now,
            updated_at=now,
        )
        self.repo.save(cred1)

        cred2 = ProviderCredential(
            id=str(uuid4()),
            user_id=self.user1.id,
            provider="gemini",
            masked_key="fake••••••••9999",
            encrypted_key="enc_secret_2",
            created_at=now,
            updated_at=now,
        )
        self.repo.save(cred2)

        fetched = self.repo.get(self.user1.id, "gemini")
        self.assertIsNotNone(fetched)
        assert fetched is not None
        self.assertEqual(fetched.masked_key, "fake••••••••9999")
        self.assertEqual(fetched.encrypted_key, "enc_secret_2")
        self.assertEqual(len(self.repo.list(self.user1.id)), 1)

    def test_user_isolation(self) -> None:
        now = datetime.now(timezone.utc)
        cred1 = ProviderCredential(
            id=str(uuid4()),
            user_id=self.user1.id,
            provider="gemini",
            masked_key="fake••••••••1234",
            encrypted_key="enc_secret_1",
            created_at=now,
            updated_at=now,
        )
        self.repo.save(cred1)

        # User 2 should NOT see User 1's credential
        self.assertIsNone(self.repo.get(self.user2.id, "gemini"))
        self.assertEqual(len(self.repo.list(self.user2.id)), 0)

    def test_delete_credential(self) -> None:
        now = datetime.now(timezone.utc)
        cred = ProviderCredential(
            id=str(uuid4()),
            user_id=self.user1.id,
            provider="gemini",
            masked_key="fake••••••••1234",
            encrypted_key="enc_secret_1",
            created_at=now,
            updated_at=now,
        )
        self.repo.save(cred)
        self.repo.delete(self.user1.id, "gemini")
        self.assertIsNone(self.repo.get(self.user1.id, "gemini"))

    def test_cascade_delete_when_user_is_deleted(self) -> None:
        now = datetime.now(timezone.utc)
        cred = ProviderCredential(
            id=str(uuid4()),
            user_id=self.user1.id,
            provider="gemini",
            masked_key="fake••••••••1234",
            encrypted_key="enc_secret_1",
            created_at=now,
            updated_at=now,
        )
        self.repo.save(cred)

        with self.store.connect() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (self.user1.id,))

        self.assertIsNone(self.repo.get(self.user1.id, "gemini"))


class TestDynamicAnswerGeneratorFactory(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "test_rag.sqlite3")
        self.store = SqliteStore(self.db_path)
        self.user_repo = SqliteUserRepository(self.store)
        self.repo = SqliteProviderCredentialRepository(self.store)
        self.user = self.user_repo.create("User", "u@example.com", "hash")

        self.test_enc_key = Fernet.generate_key().decode()
        # Mock settings.provider_encryption_key during test
        from app.core.config import settings
        self.orig_enc_key = settings.provider_encryption_key
        settings.provider_encryption_key = self.test_enc_key

    def tearDown(self) -> None:
        from app.core.config import settings
        settings.provider_encryption_key = self.orig_enc_key
        self.temp_dir.cleanup()

    def test_factory_uses_user_custom_key(self) -> None:
        custom_raw_key = "AIzaSyCustomKey999999"
        encrypted = encrypt_api_key(custom_raw_key, encryption_key=self.test_enc_key)

        now = datetime.now(timezone.utc)
        self.repo.save(
            ProviderCredential(
                id=str(uuid4()),
                user_id=self.user.id,
                provider="gemini",
                masked_key="AIza••••••••9999",
                encrypted_key=encrypted,
                created_at=now,
                updated_at=now,
            )
        )

        factory = DynamicAnswerGeneratorFactory(
            credentials=self.repo,
            fallback_gemini_api_key="system_fallback_key",
            gemini_model="gemini-2.5-flash",
            gemini_temperature=0.2,
            gemini_max_output_tokens=1024,
        )

        generator = factory.get_generator_for_user(self.user.id)
        self.assertIsInstance(generator, GeminiAnswerGenerator)
        assert isinstance(generator, GeminiAnswerGenerator)
        self.assertEqual(generator._api_key, custom_raw_key)

    def test_factory_falls_back_to_system_key_when_no_user_key(self) -> None:
        factory = DynamicAnswerGeneratorFactory(
            credentials=self.repo,
            fallback_gemini_api_key="system_fallback_key",
            gemini_model="gemini-2.5-flash",
            gemini_temperature=0.2,
            gemini_max_output_tokens=1024,
        )

        generator = factory.get_generator_for_user(self.user.id)
        self.assertIsInstance(generator, GeminiAnswerGenerator)
        assert isinstance(generator, GeminiAnswerGenerator)
        self.assertEqual(generator._api_key, "system_fallback_key")

    def test_factory_raises_when_no_user_key_and_no_fallback(self) -> None:
        factory = DynamicAnswerGeneratorFactory(
            credentials=self.repo,
            fallback_gemini_api_key=None,
            gemini_model="gemini-2.5-flash",
            gemini_temperature=0.2,
            gemini_max_output_tokens=1024,
        )

        with self.assertRaises(AnswerGenerationError):
            factory.get_generator_for_user(self.user.id)


class TestProviderSettingsRoutes(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "test_rag.sqlite3")

        from app.core.config import settings
        self.orig_db = settings.database_path
        self.orig_enc_key = settings.provider_encryption_key
        settings.database_path = self.db_path
        settings.provider_encryption_key = Fernet.generate_key().decode()

        # Clear dependencies cache so new DB is used
        from app.api.dependencies import get_store, get_auth_service, get_provider_credential_repository, get_provider_service, get_rag_service, get_answer_generator_factory
        get_store.cache_clear()
        get_auth_service.cache_clear()
        get_provider_credential_repository.cache_clear()
        get_provider_service.cache_clear()
        get_rag_service.cache_clear()
        get_answer_generator_factory.cache_clear()

        app = create_app()
        self.client = TestClient(app)

        # Register User 1
        res1 = self.client.post(
            "/api/auth/register",
            json={"name": "Alice", "email": "alice@example.com", "password": "Password123!"},
        )
        self.assertEqual(res1.status_code, 201)
        self.token1 = res1.json()["access_token"]

        # Register User 2
        res2 = self.client.post(
            "/api/auth/register",
            json={"name": "Bob", "email": "bob@example.com", "password": "Password123!"},
        )
        self.assertEqual(res2.status_code, 201)
        self.token2 = res2.json()["access_token"]

    def tearDown(self) -> None:
        from app.core.config import settings
        settings.database_path = self.orig_db
        settings.provider_encryption_key = self.orig_enc_key
        from app.api.dependencies import get_store, get_auth_service, get_provider_credential_repository, get_provider_service, get_rag_service, get_answer_generator_factory
        get_store.cache_clear()
        get_auth_service.cache_clear()
        get_provider_credential_repository.cache_clear()
        get_provider_service.cache_clear()
        get_rag_service.cache_clear()
        get_answer_generator_factory.cache_clear()
        self.temp_dir.cleanup()

    def test_unauthenticated_returns_401(self) -> None:
        res = self.client.get("/api/settings/providers")
        self.assertEqual(res.status_code, 401)

    def test_save_and_list_provider_key(self) -> None:
        raw_key = "fake_gemini_route_test_key_9876543210"

        # Save key for Alice
        put_res = self.client.put(
            "/api/settings/providers",
            headers={"Authorization": f"Bearer {self.token1}"},
            json={"provider": "gemini", "api_key": raw_key},
        )
        self.assertEqual(put_res.status_code, 200)
        data = put_res.json()
        self.assertEqual(data["provider"], "gemini")
        self.assertTrue(data["is_custom"])
        self.assertTrue(data["is_configured"])
        self.assertIn("••••••••", data["masked_key"])
        # Crucial security check: plaintext key must NOT be in response
        self.assertNotIn(raw_key, str(data))

        # List providers for Alice
        get_res = self.client.get(
            "/api/settings/providers",
            headers={"Authorization": f"Bearer {self.token1}"},
        )
        self.assertEqual(get_res.status_code, 200)
        providers = get_res.json()
        self.assertEqual(len(providers), 1)
        self.assertEqual(providers[0]["provider"], "gemini")
        self.assertTrue(providers[0]["is_custom"])
        self.assertNotIn(raw_key, str(providers))

        # User isolation: Bob must NOT see Alice's custom key
        bob_res = self.client.get(
            "/api/settings/providers",
            headers={"Authorization": f"Bearer {self.token2}"},
        )
        self.assertEqual(bob_res.status_code, 200)
        bob_providers = bob_res.json()
        self.assertFalse(bob_providers[0]["is_custom"])
        self.assertIsNone(bob_providers[0]["masked_key"])

        # Delete key for Alice
        del_res = self.client.delete(
            "/api/settings/providers/gemini",
            headers={"Authorization": f"Bearer {self.token1}"},
        )
        self.assertEqual(del_res.status_code, 204)

        # Confirm reverted
        get_res2 = self.client.get(
            "/api/settings/providers",
            headers={"Authorization": f"Bearer {self.token1}"},
        )
        providers2 = get_res2.json()
        self.assertFalse(providers2[0]["is_custom"])
        self.assertIsNone(providers2[0]["masked_key"])


if __name__ == "__main__":
    unittest.main()
