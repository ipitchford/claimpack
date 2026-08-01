from __future__ import annotations

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from tools.send_press_notice_email import main


class _Response:
    status = 200

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *unused: object) -> None:
        return None

    def read(self) -> bytes:
        return b'{"message_id":"message-1","thread_id":"thread-1"}'


class DistributionTests(unittest.TestCase):
    def test_dry_run_needs_no_secret_and_does_not_send(self) -> None:
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), patch(
            "urllib.request.urlopen"
        ) as urlopen, redirect_stdout(output):
            result = main(
                [
                    "--dry-run",
                    "--title",
                    "Candidate notice",
                    "--summary",
                    "Evidence-bounded candidate release.",
                    "--inbox-id",
                    "sender@agentmail.to",
                    "--to",
                    "reader@example.org",
                    "--release-url",
                    "https://example.org/release",
                ]
            )

        preview = json.loads(output.getvalue())
        self.assertEqual(result, 0)
        self.assertFalse(preview["will_send"])
        self.assertNotIn("Authorization", output.getvalue())
        urlopen.assert_not_called()

    def test_live_mode_requires_key_inbox_and_recipient(self) -> None:
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), redirect_stdout(output):
            result = main(
                [
                    "--title",
                    "Candidate notice",
                    "--summary",
                    "Evidence-bounded candidate release.",
                    "--release-url",
                    "https://example.org/release",
                ]
            )

        self.assertEqual(result, 1)
        self.assertIn("AGENTMAIL_INBOX_ID", output.getvalue())
        self.assertIn("AGENTMAIL_TO", output.getvalue())

    def test_live_mode_requires_key_after_routing_is_present(self) -> None:
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), redirect_stdout(output):
            result = main(
                [
                    "--title",
                    "Candidate notice",
                    "--summary",
                    "Evidence-bounded candidate release.",
                    "--release-url",
                    "https://example.org/release",
                    "--inbox-id",
                    "sender@agentmail.to",
                    "--to",
                    "reader@example.org",
                ]
            )

        self.assertEqual(result, 1)
        self.assertIn("AGENTMAIL_API_KEY", output.getvalue())

    def test_send_uses_inbox_scoped_endpoint_and_redacts_key(self) -> None:
        output = io.StringIO()
        environment = {
            "AGENTMAIL_API_KEY": "test-secret",
            "AGENTMAIL_INBOX_ID": "sender@agentmail.to",
            "AGENTMAIL_TO": "reader@example.org",
        }
        with patch.dict(os.environ, environment, clear=True), patch(
            "urllib.request.urlopen",
            return_value=_Response(),
        ) as urlopen, redirect_stdout(output):
            result = main(
                [
                    "--title",
                    "Candidate notice",
                    "--summary",
                    "Evidence-bounded candidate release.",
                    "--release-url",
                    "https://example.org/release",
                ]
            )

        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        response = json.loads(output.getvalue())
        self.assertEqual(result, 0)
        self.assertEqual(
            request.full_url,
            "https://api.agentmail.to/v0/inboxes/"
            "sender%40agentmail.to/messages/send",
        )
        self.assertEqual(body["to"], "reader@example.org")
        self.assertEqual(response["message_id"], "message-1")
        self.assertNotIn("test-secret", output.getvalue())


if __name__ == "__main__":
    unittest.main()
