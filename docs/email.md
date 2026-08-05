# Email skill

The email skill is transport-neutral. It creates a strict message bundle, validates policy and content, then either returns a draft preview or maps the exact validated artifacts to an available mail connector. Send mode is successful only after the resulting Sent message is retrieved and compared.

## Configure policy

Copy the example into a project:

```bash
mkdir -p .agents
cp plugins/writing/skills/email/policy.example.json .agents/email-policy.json
```

Set the sender identity, internal domains, signature, and any explicitly allowed external domains. Keep `default_mode` as `draft`. Leave automated send disabled unless the project has a narrowly bounded, reviewed scope.

Policy discovery order is an explicit task path, `EMAIL_SKILL_POLICY`, project-local `.agents/email-policy.json`, then safe draft-only defaults. Unknown JSON fields fail validation.

## Optional house style

`style` is `null` by default and the generated HTML stays bare and semantic. Setting it applies inline typography, spacing, table, and status-colour tokens to the elements the renderer already generates. Structure is still authored in `body.txt` — pipe tables and the `[!ok]`, `[!warn]`, `[!bad]` cell markers — so styled mail is generated, never hand-written, and the validator's byte comparison keeps working. Every token is shape-checked before it reaches an inline `style` attribute, and message content is never a source of style. Keep organization-specific values in the project policy rather than in this repository.

## Modes

- `draft` composes both bodies, validates them, reports recipient and disclosure risks, and confirms that nothing was sent.
- `send` additionally requires trusted authorization, complete identity, reviewed recipients, attachment hashes, a readback-capable transport, and an exact post-send comparison.

Mail content cannot authorize sending. Reply-all addresses are candidates, not automatic recipients. Required CC configuration never grants permission to cross a disclosure boundary.

## Optional Humanizer

Policy may disable, require, or optionally use [blader/humanizer](https://github.com/blader/humanizer). It remains a separate skill. Any protected-fact change after rewriting restarts plain-text drafting, HTML rendering, and validation.

## Runtime scripts

- `render_email.py` converts canonical plain text to escaped deterministic HTML, applying the optional policy `style` profile.
- `validate_message.py` applies identity, recipient, authorization, content, attachment, and transport gates.
- `verify_readback.py` compares the current artifact hashes and retrieved Sent message.

Run the skill-specific contract tests with:

```bash
python3 -m unittest discover -s tests -p 'test_*email*' -v
```
