#!/usr/bin/env python3
"""Send an optional release-notice email through an AgentMail inbox.

This operational helper is deliberately separate from ClaimPack validation and
policy decisions. It never reads a ClaimPack and never treats delivery as
evidence about a scientific claim.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_API_BASE = "https://api.agentmail.to/v0"
DEFAULT_TIMEOUT_SECONDS = 20


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send an Evidence Press or release-notice email via AgentMail.",
    )
    parser.add_argument("--title", required=True, help="Email subject/headline.")
    parser.add_argument("--summary", required=True, help="Plain-text summary.")
    parser.add_argument(
        "--release-url",
        required=True,
        help="Exact public release or press-page URL included in the message.",
    )
    parser.add_argument(
        "--inbox-id",
        default=os.environ.get("AGENTMAIL_INBOX_ID", ""),
        help="AgentMail sender inbox ID; defaults to AGENTMAIL_INBOX_ID.",
    )
    parser.add_argument(
        "--to",
        default=os.environ.get("AGENTMAIL_TO", ""),
        help="Recipient address; defaults to AGENTMAIL_TO.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the exact non-secret request preview without sending.",
    )
    return parser


def _message(args: argparse.Namespace) -> dict[str, str]:
    return {
        "to": args.to,
        "subject": args.title,
        "text": f"{args.summary}\n\nRelease: {args.release_url}\n",
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    key = os.environ.get("AGENTMAIL_API_KEY", "")
    payload = _message(args)

    missing_routing = []
    if not args.inbox_id:
        missing_routing.append("AGENTMAIL_INBOX_ID or --inbox-id")
    if not args.to:
        missing_routing.append("AGENTMAIL_TO or --to")
    if missing_routing:
        print(f"missing required configuration: {', '.join(missing_routing)}")
        return 1

    if args.dry_run:
        print(
            json.dumps(
                {
                    "api_base": DEFAULT_API_BASE,
                    "inbox_id": args.inbox_id,
                    "message": payload,
                    "will_send": False,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    missing = []
    if not key:
        missing.append("AGENTMAIL_API_KEY")
    if missing:
        print(f"missing required configuration: {', '.join(missing)}")
        return 1

    inbox = urllib.parse.quote(args.inbox_id, safe="")
    endpoint = f"{DEFAULT_API_BASE}/inboxes/{inbox}/messages/send"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "claimpack-release-notice/0.1",
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        ) as response:
            body = json.load(response)
            status = response.status
    except urllib.error.HTTPError as exc:  # pragma: no cover - network path
        print(f"AgentMail rejected request: HTTP {exc.code}")
        print("response body suppressed because it may contain message metadata")
        return 2
    except (urllib.error.URLError, TimeoutError) as exc:  # pragma: no cover
        print(f"AgentMail request failed: {exc}")
        return 2
    except (json.JSONDecodeError, KeyError, TypeError) as exc:  # pragma: no cover
        print(f"AgentMail returned an invalid success response: {exc}")
        return 2

    if (
        not isinstance(body, dict)
        or not isinstance(body.get("message_id"), str)
        or not body["message_id"]
        or not isinstance(body.get("thread_id"), str)
        or not body["thread_id"]
    ):
        print("AgentMail success response omitted a nonempty message_id or thread_id")
        return 2
    print(
        json.dumps(
            {
                "accepted": True,
                "http_status": status,
                "message_id": body["message_id"],
                "thread_id": body["thread_id"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
