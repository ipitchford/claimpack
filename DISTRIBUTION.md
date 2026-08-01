# Distribution and dissemination guidance

ClaimPack is an evidence-transfer protocol first. Public release
communications are separate operational actions and are **not** part of claim
truth assessment.

## Channels

- **Evidence Press**
  - URL: `https://evidence-press.pages.dev`
  - Purpose: public-facing summaries of candidate releases
  - Required: exact claim identity, archive DOI, summary of support and caveats

- **Direct archive/repository updates**
  - Keep exact archive bytes, manifests, and hashes in repository-linked release
    records.
  - Keep notices short and explicit about status boundaries.

## Press notice workflow

1. Finalize and validate the release artifact.
2. Finalize catalogue, checksum, and provenance updates.
3. Compose one summary paragraph with:
   - principal claim,
   - exact version identifier,
   - public artifact links,
   - exact evidence limits,
   - explicit unresolved caveats.
4. Send via the external mailer if configured.

## Optional email notification

An email is a dissemination side-channel; it does not publish a ClaimPack or
establish delivery unless the receiving system or a delivery event confirms
it. Use `tools/send_press_notice_email.py` with environment credentials only.
The helper calls AgentMail's inbox-scoped send endpoint.

```sh
export AGENTMAIL_API_KEY=...       # never commit this value
export AGENTMAIL_INBOX_ID=sender@example.agentmail-domain
export AGENTMAIL_TO=recipient@example.org

python3 tools/send_press_notice_email.py \
  --title "Candidate result released" \
  --summary "A release is available; status and evidence limits are stated." \
  --release-url "https://example.org/release"
```

The helper sends credentials only to the fixed official API base
`https://api.agentmail.to/v0`.

Use `--dry-run` to print the exact JSON payload without sending it.
