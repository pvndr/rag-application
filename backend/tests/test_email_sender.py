import io
import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from app.infrastructure.email_sender import (
    EmailDeliveryError,
    PasswordResetEmail,
    SendGridEmailSender,
)

TEST_API_KEY = "SG.test-key.test-secret"


def _fake_response(status: int) -> MagicMock:
    response = MagicMock()
    response.status = status
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    return response


def _http_error(status: int, body: bytes) -> HTTPError:
    return HTTPError(
        "https://api.sendgrid.com/v3/mail/send",
        status,
        "Bad Request",
        hdrs=None,
        fp=io.BytesIO(body),
    )


class SendGridEmailSenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.email = PasswordResetEmail(
            to_email="user@example.com",
            reset_url="http://127.0.0.1:5173/reset-password?token=abc.def",
        )

    def test_missing_api_key_raises_without_network_call(self) -> None:
        for key in (None, ""):
            with self.subTest(api_key=key):
                sender = SendGridEmailSender(api_key=key, from_email="App <a@b.c>", app_name="RAG")
                with patch("app.infrastructure.email_sender.urlopen") as mock_open:
                    with self.assertRaises(EmailDeliveryError) as ctx:
                        sender.send_password_reset(self.email)
                mock_open.assert_not_called()
                self.assertIn("SENDGRID_API_KEY", str(ctx.exception))

    def test_successful_send_posts_expected_payload(self) -> None:
        sender = SendGridEmailSender(
            api_key=TEST_API_KEY,
            from_email="RAG Starter <noreply@example.com>",
            app_name="RAG Starter",
        )
        with patch("app.infrastructure.email_sender.urlopen") as mock_open:
            mock_open.return_value = _fake_response(202)
            sender.send_password_reset(self.email)

        request = mock_open.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.sendgrid.com/v3/mail/send")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), f"Bearer {TEST_API_KEY}")
        self.assertEqual(request.get_header("Content-type"), "application/json")

        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["personalizations"][0]["to"], [{"email": "user@example.com"}])
        self.assertEqual(payload["from"], {"email": "noreply@example.com", "name": "RAG Starter"})
        self.assertEqual(payload["subject"], "Reset your RAG Starter password")

        content = {item["type"]: item["value"] for item in payload["content"]}
        self.assertEqual(set(content), {"text/plain", "text/html"})
        self.assertIn(self.email.reset_url, content["text/plain"])
        self.assertIn(self.email.reset_url, content["text/html"])

    def test_plain_address_without_display_name(self) -> None:
        sender = SendGridEmailSender(
            api_key=TEST_API_KEY, from_email="noreply@example.com", app_name="RAG"
        )
        with patch("app.infrastructure.email_sender.urlopen") as mock_open:
            mock_open.return_value = _fake_response(202)
            sender.send_password_reset(self.email)

        payload = json.loads(mock_open.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload["from"]["email"], "noreply@example.com")
        self.assertEqual(payload["from"]["name"], "noreply@example.com")

    def test_http_error_is_wrapped_without_leaking_key(self) -> None:
        sender = SendGridEmailSender(
            api_key=TEST_API_KEY, from_email="App <a@b.c>", app_name="RAG"
        )
        error = _http_error(400, b'{"errors": [{"message": "Invalid sender"}]}')
        self.addCleanup(error.close)
        with patch(
            "app.infrastructure.email_sender.urlopen",
            side_effect=error,
        ):
            with self.assertRaises(EmailDeliveryError) as ctx:
                sender.send_password_reset(self.email)
        self.assertIn("SendGrid rejected", str(ctx.exception))
        self.assertIn("Invalid sender", str(ctx.exception))
        self.assertNotIn(TEST_API_KEY, str(ctx.exception))

    def test_connection_failure_is_wrapped(self) -> None:
        sender = SendGridEmailSender(
            api_key=TEST_API_KEY, from_email="App <a@b.c>", app_name="RAG"
        )
        with patch(
            "app.infrastructure.email_sender.urlopen",
            side_effect=URLError("connection refused"),
        ):
            with self.assertRaises(EmailDeliveryError) as ctx:
                sender.send_password_reset(self.email)
        self.assertIn("Could not connect to SendGrid", str(ctx.exception))
        self.assertNotIn(TEST_API_KEY, str(ctx.exception))

    def test_connection_failure_reports_failure_category(self) -> None:
        import ssl

        sender = SendGridEmailSender(
            api_key=TEST_API_KEY, from_email="App <a@b.c>", app_name="RAG"
        )
        tls_failure = URLError(
            ssl.SSLCertVerificationError(
                "certificate verify failed: unable to get local issuer certificate"
            )
        )
        with patch(
            "app.infrastructure.email_sender.urlopen",
            side_effect=tls_failure,
        ):
            with self.assertRaises(EmailDeliveryError) as ctx:
                sender.send_password_reset(self.email)
        self.assertIn("SSLCertVerificationError", str(ctx.exception))
        self.assertNotIn(TEST_API_KEY, str(ctx.exception))

    def test_requests_use_a_certificate_context(self) -> None:
        sender = SendGridEmailSender(
            api_key=TEST_API_KEY, from_email="App <a@b.c>", app_name="RAG"
        )
        with patch("app.infrastructure.email_sender.urlopen") as mock_open:
            mock_open.return_value = _fake_response(202)
            sender.send_password_reset(self.email)
        self.assertIsNotNone(mock_open.call_args.kwargs.get("context"))


if __name__ == "__main__":
    unittest.main()
