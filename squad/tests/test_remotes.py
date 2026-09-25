"""One reading of a git remote as `owner/name`, for every caller that scopes `gh -R`.

The two readers this replaced disagreed on the commonest remote there is: the board's
returned nothing for `https://github.com/owner/name.git`, and its test passed only on a
machine whose global git config rewrote HTTPS remotes to SSH.
"""
from __future__ import annotations

import pytest

from squad.remotes import owner_repo


@pytest.mark.parametrize(("url", "expected"), [
    ("https://github.com/owner/name.git", "owner/name"),
    ("https://github.com/owner/name", "owner/name"),
    ("git@github.com:owner/name.git", "owner/name"),
    ("git@github.com:owner/name", "owner/name"),
    ("github-alias:acme/product.git", "acme/product"),
    ("ssh://git@github.com:22/owner/name.git", "owner/name"),
    ("  https://github.com/owner/name.git\n", "owner/name"),
])
def test_every_remote_shape_names_its_repository(url: str, expected: str) -> None:
    assert owner_repo(url) == expected


@pytest.mark.parametrize("url", [
    "/srv/git/bare.git",
    "file:///srv/git/bare.git",
    "./relative/bare.git",
    "not-a-url",
    "",
])
def test_a_remote_that_names_no_hosted_repository_answers_none(url: str) -> None:
    """None, never a guess: a guessed repository would query someone else's tracker."""
    assert owner_repo(url) is None
