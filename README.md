# local-proton-mail

Keeps a local, AI-agent-readable copy of a Proton Mail account, synced through
[Proton Mail Bridge](https://proton.me/mail/bridge). Works on Windows and macOS.

The mail itself is saved in `archive/`, which is gitignored: this repo only ever
holds the tool. Each device builds its own copy from Bridge.

## Set up a device

1. Install Proton Mail Bridge and sign in to your Proton account.
2. Install Python 3.11+ and the dependencies:
   ```
   python -m venv .venv
   .venv\Scripts\activate        # Windows
   source .venv/bin/activate     # macOS
   pip install -r requirements.txt
   ```
3. Save the Bridge IMAP credentials to this device's keychain:
   `python -m pmail setup`
4. Test the connection: `python -m pmail check`
5. Download your mail: `python -m pmail sync` (re-run any time; only changes are fetched)

Agents: see `archive/README.md` for the layout of the mail files.

## Status

- [x] Phase 1: Bridge connection and credentials
- [x] Phase 2: full download to `archive/` (`python -m pmail sync`)
- [ ] Phase 3: live sync while running
- [ ] Phase 4: attachments on demand
- [ ] Phase 5: drafts written by agents (never sent)
