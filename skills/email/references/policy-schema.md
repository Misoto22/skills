# Policy and message schemas

## Policy discovery

The loader checks an explicit task path, `EMAIL_SKILL_POLICY`, `.agents/email-policy.json` in the current project, then safe built-in defaults. JSON is UTF-8, `schema_version` is `1`, and unknown fields are rejected.

## Policy fields

`identity`:

- `sender_name`: string. Required for send mode.
- `sender_address`: valid mailbox. Required for send mode and must match the bundle sender.
- `internal_domains`: domain array, normalized to lowercase. At least one is required for send mode.

`composition`:

- `greeting_style`: `first-name`, `full-name`, or `none`.
- `target_words`: positive integer or `null`.
- `max_words`: positive integer or `null`; cannot be below `target_words`.
- `signature_file`: absolute path, policy-relative path, or `null`. A configured file must exist.
- `humanizer`: `optional`, `disabled`, or `required`.

`recipients`:

- `allowed_external_domains`: domains permitted as external recipients.
- `reply_all`: `review` or `never`.
- `required_cc_rules`: objects containing `address`, nonempty `recipient_domains`, and optional `sensitivity` values (`normal` or `sensitive`). A matching rule reports a missing CC but never adds it. A new unapproved disclosure domain blocks send.

`authorization`:

- `default_mode`: must be `draft`.
- `allow_automated_send`: boolean; safe default is `false`.
- `automated_send_scopes`: narrow scopes with unique `name`, nonempty `recipient_domains`, positive `max_recipients`, `allow_attachments`, and nonempty `allowed_sensitivity`. A scope authorizes only an exact matching bundle.

`style`: object or `null`. `null` is the default and renders bare semantic HTML. A supplied object is completed from neutral defaults, so a policy may override one token without restating the profile.

- `font_family`: letters, digits, spaces, commas, periods, apostrophes, hyphens, and underscores only.
- `font_size_px`, `paragraph_spacing_px`: positive and non-negative integers.
- `line_height`: positive number.
- `text_color`: hex colour such as `#222222`.
- `list_style`: `semantic` renders `<ul>`/`<ol>`; `paragraph` renders each authored line as its own paragraph, for composers that mangle pasted list indentation.
- `table`: `border_color` hex colour, positive `font_size_px`, and `cell_padding_px` as `[vertical, horizontal]` non-negative integers.
- `status_colors`: hex colours for the `ok`, `warn`, and `bad` markers. All three are required.

Every token is shape-checked because it is interpolated into an inline `style` attribute. Message content is never a source of style: cells recognize only the closed `[!ok]`, `[!warn]`, and `[!bad]` markers, and any other bracketed text stays literal.

Start from `../policy.example.json`. The shipped example uses reserved `.test` domains, automated send remains disabled, and no style profile is configured.

## Message bundle

`message.json` is a strict object with all of these fields:

```json
{
  "schema_version": 1,
  "mode": "draft",
  "sender": {"name": "Example Sender", "address": "sender@example.test"},
  "recipients": {"to": [], "cc": [], "bcc": []},
  "subject_file": "subject.txt",
  "text_body_file": "body.txt",
  "html_body_file": "body.html",
  "authorization": {"source": "none", "scope": null},
  "protected_facts": [],
  "sensitivity": "normal",
  "reply": {"message_id": null, "thread_id": null, "candidate_recipients": []},
  "transport": {"supports_readback": true, "supports_attachment_readback": true},
  "attachments": []
}
```

Allowed modes are `draft` and `send`. Authorization sources are `none`, `direct_user`, `policy`, and `untrusted_content`. Files must be relative paths contained in the bundle. Each attachment contains `path`, `name`, nonnegative `size`, and lowercase SHA-256. Sensitivity is `normal` or `sensitive`.

The validator returns `schema_version`, `status`, `findings`, normalized fields, and `artifact_sha256`. A `send_ready` report binds transport execution to the exact manifest and artifact bytes.

## Readback report

After transport retrieval, write a strict version 1 JSON object containing `message_id`, `thread_id`, `from`, `to`, `cc`, `bcc`, `subject`, `text_body`, `html_body`, and `attachments`. Each observed attachment contains exactly `name`, `size`, and `sha256`.

The verifier normalizes mailbox addresses and CRLF text, then compares the current bundle hashes before trusting content. HTML is compared exactly. A requested thread ID must match. A nonempty message ID is retrieval evidence only.
