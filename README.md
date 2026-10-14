# local-proton-mail

Keeps a local, AI-agent-readable copy of a Proton Mail account, synced through
[Proton Mail Bridge](https://proton.me/mail/bridge). Works on Windows and macOS.

The mail itself is saved in `archive/`, which is gitignored: this repo only ever
holds the tool. Each device builds its own copy from Bridge.

## Why local

Your inbox doesn't need to be handed to another company for AI to be useful with it.

- **No third-party mailbox access.** No OAuth grant, no cloud connector, no
  service holding a copy of your mail. It goes from Proton to your disk through
  Proton's own Bridge, and nowhere else.
- **You choose what an AI sees.** Agents read plain files on your machine, so
  you can point a cloud model (Claude, Hugging Face, other APIs) at one
  conversation instead of a whole account, or use a local model and keep
  everything offline.
- **No lock-in.** Plain text and JSONL that any tool, script or future AI can read.
- **Drafts, never sends.** Agents can prepare replies in your Drafts folder; the
  tool has no code that sends mail, so you press send yourself.
- **Open source.** Read every line that touches your mail.

Note: when you ask a cloud AI about an email, the text you give it is sent to
that provider, just like pasting it into a chat. The difference is that you
decide what goes, per question.

## Set up a device (Windows or macOS)

1. Install Proton Mail Bridge and sign in to your Proton account.
2. Install [uv](https://docs.astral.sh/uv/), clone this repo and run `uv sync` inside it.
3. Save the Bridge IMAP credentials to this device's keychain: `uv run python -m pmail setup`
4. Optional, pick a date range: `uv run python -m pmail range today` (or `all`, or `2026-01-01`)
5. Download and strip your mail: `uv run python -m pmail sync` (re-run any time; only changes are fetched)

Agents: see `archive/README.md` for the layout of the mail files.

## How emails are stripped, and why

AI models need the words, not the presentation. Formatting costs tokens,
adds noise to search and confuses chunking, so every email is reduced to
plain text before it is saved. This is the step before chunking, embedding
or putting mail into a RAG index.

- HTML, styling, layout tables, images and invisible preview padding are removed.
- Links are kept as `text (url)`, minus tracking parameters like `utm_*`.
- Quoted copies of earlier replies are cut, since the thread already has them.
- Signatures (after `-- `) and "Sent with Proton Mail" lines are cut.
- Newsletters and automated mail are marked `Bulk: yes` so later AI steps can skip them.
- Attachments are listed by name, type and size, not saved.

The rules live in `pmail/clean.py` with tests in `tests/test_clean.py`.

## Status

- [x] Phase 1: Bridge connection and credentials
- [x] Phase 2: download, stripping, date range, tests and CI
- [ ] Phase 3: live sync while running
- [ ] Phase 4: attachments on demand
- [ ] Phase 5: drafts written by agents (never sent)
