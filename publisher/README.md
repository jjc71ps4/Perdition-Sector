# Publishing a beta snapshot

Python 3.11+, Git, and the official GitHub CLI are authoring prerequisites.
Players do not need them. Authentication stays outside this repository, in
the author's private local staging folder.

`publish_beta.py` creates the public repository and a draft prerelease, captures
the enabled MO2 player build into a streamed ZIP64, uploads parts smaller than
2 GiB, and verifies each GitHub asset's size and SHA-256 digest. Each local part
is removed only after GitHub confirms it. This keeps peak additional disk use
near one part, rather than duplicating the entire compressed build.

The builder hashes each source file while capturing it, checks source size and
timestamps before/after capture, repeats the complete inventory, and validates
the final ZIP directory and embedded inventory. A full decompression/CRC pass
is additionally covered by small fixtures; the large streamed archive is not
downloaded again solely for that pass. GitHub asset digests verify stored parts.

The installer is built with a pinned `package_source.json`. All expected assets
are checked before the draft is published as a beta. Finally, the public
manifest is downloaded without credentials and compared with the pinned copy.

Run from the authoring machine with the game, Creation Kit and xEdit closed:

```powershell
python publisher/publish_beta.py
```

The defaults target `jjc71ps4/Perdition-Sector`, tag `beta-2026.11.20.1` and
installer `0.2.0-beta.1`. A later snapshot must use a new version, tag and work
folder. Published assets are never overwritten. Failed runs retain the draft,
verified uploads and any unfinished local part for diagnosis. Completed parts
are reused when a deterministic rebuild produces the same hashes.

The publisher locates drafts through the paginated releases collection. It
reuses an existing draft for the requested tag when resuming, including a draft
whose tag has not been published yet. The published-release tag endpoint is not
used for draft lookup.

Each upload prints elapsed time every ten seconds, including the amount already
verified. These are activity messages, not a byte-level transfer percentage.
An attempt has a configurable 30-minute limit (`--upload-timeout` in seconds).
Actual uploader errors are shown and retained privately in upload_errors.log.

Interrupted GitHub assets can report the full declared size while still having
state `starter` and no digest. Those incomplete attempts are removed only from
the matching draft before retrying; completed or mismatched assets are protected.
Uploads retry up to three times and keep the local part if they still fail.
On rerun, already verified parts are reused after deterministic rebuilding and
checksum comparison; those parts are not uploaded again.

`installer/Tools` (7-Zip) and `installer/RootOverlay.zip` are local build inputs,
distributed inside the setup release ZIP rather than committed to Git. Keep
the accepted local build inputs when rebuilding setup. `installer/Build-Payload.ps1`
remains available for an existing full snapshot ZIP and sufficient disk space.

No installer is run against the author's working game during publishing.

