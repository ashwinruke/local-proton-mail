"""One sync pass: Bridge -> archive. Safe to re-run; only new or changed mail is fetched."""

from datetime import date

from pmail import archive, bridge, message, settings

ALL_MAIL = "All Mail"
SKIP_FOLDERS = {ALL_MAIL, "Starred"}  # Starred is a flag, not a place
BATCH = 50


def _folder_membership(client, folders: list[str]) -> dict[str, list[str]]:
    """Map Proton internal id -> folders it sits in."""
    member: dict[str, list[str]] = {}
    for name in folders:
        client.select_folder(name, readonly=True)
        uids = client.search("ALL")
        for start in range(0, len(uids), 500):
            chunk = uids[start:start + 500]
            for data in client.fetch(chunk, [b"BODY.PEEK[HEADER.FIELDS (X-PM-INTERNAL-ID)]"]).values():
                raw = next((v for k, v in data.items() if k.startswith(b"BODY[HEADER")), b"")
                internal_id = raw.decode("utf-8", "replace").partition(":")[2].strip()
                if internal_id:
                    member.setdefault(internal_id, []).append(name)
    return member


def _flags(raw_flags) -> list[str]:
    flags = []
    if b"\\Seen" not in raw_flags:
        flags.append("unread")
    if b"\\Flagged" in raw_flags:
        flags.append("starred")
    return flags


def run(log=print) -> dict:
    if warning := archive.cloud_synced_warning():
        log(warning)
    state = archive.load_state()
    if state.get("format") != archive.FORMAT_VERSION:
        log("Email format changed; rebuilding every file.")
        archive.clear_mail()
        state = archive.empty_state()
    since = settings.load()["since"]
    if since != state.get("since"):
        log(f"Date range: {'all mail' if since is None else 'from ' + since}.")
        state["since"] = since
    messages: dict = state["messages"]  # short id -> metadata
    added = removed = updated = 0

    with bridge.connect() as client:
        folders = [name for flags, _d, name in client.list_folders() if b"\\Noselect" not in flags]

        info = client.select_folder(ALL_MAIL, readonly=True)
        uidvalidity = info[b"UIDVALIDITY"]
        if state["uidvalidity"] != uidvalidity:
            if state["uidvalidity"] is not None:
                log("Bridge renumbered its mailbox; re-matching every email.")
            state["uids"] = {}
            state["uidvalidity"] = uidvalidity

        # Emails outside the date range drop out of server_uids and are removed below.
        server_uids = client.search(["SINCE", date.fromisoformat(since)] if since else "ALL")
        flag_data = client.fetch(server_uids, [b"FLAGS"]) if server_uids else {}
        known = {int(uid): mid for uid, mid in state["uids"].items()}
        by_proton = {m["proton_id"]: m["id"] for m in messages.values()}

        new_uids = [uid for uid in server_uids if uid not in known]
        if new_uids:
            log(f"Downloading {len(new_uids)} emails...")
        for start in range(0, len(new_uids), BATCH):
            chunk = new_uids[start:start + BATCH]
            for uid, data in client.fetch(chunk, [b"BODY.PEEK[]", b"INTERNALDATE"]).items():
                meta, body = message.parse(data[b"BODY[]"], data[b"INTERNALDATE"])
                known[uid] = meta["id"]
                if meta["proton_id"] in by_proton:  # already archived (UIDs were reset)
                    continue
                by_proton[meta["proton_id"]] = meta["id"]
                meta.update(path=archive.new_path(meta), folders=[], flags=[], thread=meta["id"],
                            snippet=archive.snippet(body))
                archive.write_message(meta, body)
                messages[meta["id"]] = meta
                added += 1
            log(f"  {min(start + BATCH, len(new_uids))}/{len(new_uids)}")

        # Gone from All Mail (deleted in Proton) or now outside the date range.
        live_ids = {known[uid] for uid in server_uids}
        for mid in [mid for mid in messages if mid not in live_ids]:
            archive.remove_message(messages.pop(mid))
            removed += 1
        state["uids"] = {str(uid): known[uid] for uid in server_uids}

        flags_by_id = {known[uid]: _flags(d[b"FLAGS"]) for uid, d in flag_data.items()}
        membership = _folder_membership(client, [f for f in folders if f not in SKIP_FOLDERS])

    archive.assign_threads(messages)
    for mid, meta in messages.items():
        meta["folders"] = sorted(membership.get(meta["proton_id"], []))
        meta["flags"] = flags_by_id.get(mid, meta["flags"])
        if archive.refresh_header(meta):
            updated += 1

    archive.write_indexes(messages)
    archive.save_state(state)
    return {"added": added, "removed": removed, "updated": updated - added, "total": len(messages)}
