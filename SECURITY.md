# Security

## Reporting

Report a vulnerability privately through GitHub: **Security → Advisories → Report a vulnerability** on [this repository](https://github.com/Misoto22/skills/security/advisories/new). That keeps the report out of public issues until there is a fix.

Please do not open a public issue for anything in the two categories below.

## What this repository is

Skills are instructions an agent reads, not a service. There is no server, no database, and no account. This repository holds no transport credential, implements no SMTP, and ships no code that runs anywhere except when an agent chooses to invoke it locally. Most of what could go wrong with a web application does not apply.

Two things do.

### An instruction that makes an agent do something the user did not ask for

The `email` skill is the one that carries real authority: it decides whether a message is drafted or actually sent, who receives it, and whether a protected fact survived a rewrite. Its gates are described in [security-model.md](plugins/writing/skills/email/references/security-model.md). In scope:

- Anything that gets a send past the authorization gate — including content inside a received message, quoted text, an attachment, or a fetched page persuading an agent that it has permission it was not given.
- Anything that widens the recipient set without the user's involvement, or crosses a disclosure boundary the policy defines.
- Anything that lets an artifact change between validation and send, or that makes readback report a send that did not happen.
- The same shape of problem in another skill: instructions that would make an agent delete, publish, or transmit something outside what the user asked for. `dev:ship` and `dev:cleanup` both act on a repository, so they qualify.

Prompt injection in general is not a bug report — an agent reading untrusted text is the normal condition. What is in scope is a specific path through a skill's own rules that produces an unsafe action, described concretely enough to reproduce.

### A published artifact that is not what it claims to be

Every release attaches `SHA256SUMS` and a signed build provenance attestation, because claude.ai and Cowork are served by downloading a `.skill` and uploading it elsewhere. Before reporting a tampered archive, check whether it is actually the one this repository built:

```bash
sha256sum -c SHA256SUMS
gh attestation verify email.skill --repo Misoto22/skills
```

A mismatch is worth reporting. So is any way to make the release workflow attest something the tag did not build.

## Versions

Only the latest release is supported. Skills are copied into an agent's own directory at install time, so an older copy keeps working and does not receive fixes — reinstall to update. `npx skills add` with `--copy` behaves the same way; a symlinked install tracks the repository.
