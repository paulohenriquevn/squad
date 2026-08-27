# Operating procedures

What this kit does repeatedly, written down so the next person does not have to
reconstruct it from a script header.

- [Port a fix between the Squad and the Cycle](/sops/port-fix-between-kits.md) —
  measure the receiving kit first, adapt what encodes its contract, and never
  name a mechanism the receiving kit does not have.

## Not written yet

Three procedures with a script and no document. Each is a real gap, not a
placeholder: the steps live in a header comment, where nothing verifies them.

- [ ] Install the kit into a consumer — `scripts/install.sh`
- [ ] Patch an existing install — `scripts/patch_install.sh`
- [ ] Propagate a delta across consumers — `scripts/sync_consumers.py`
