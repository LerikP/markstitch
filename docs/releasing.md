# Releasing Markstitch

## One-time setup

The release workflow uses [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
with GitHub Actions. No long-lived PyPI API token is needed.

1. Create a GitHub environment named `pypi` in
   [the repository settings](https://github.com/LerikP/markstitch/settings/environments).
2. Before the first release, sign in to PyPI and add a pending GitHub publisher at
   <https://pypi.org/manage/account/publishing/> with these exact values:

   | Field | Value |
   | --- | --- |
   | PyPI project name | `markstitch` |
   | GitHub owner | `LerikP` |
   | Repository name | `markstitch` |
   | Workflow filename | `publish.yml` |
   | Environment name | `pypi` |

   If the project already exists under your account, add the same publisher under
   the project's Publishing settings instead.

The workflow filename is `publish.yml`, not the reusable `ci.yml`: the publishing job
runs directly in `publish.yml`. A pending publisher creates the PyPI project on the
first successful upload; registering it does not reserve the package name.

## Release procedure

1. Set the new version in `pyproject.toml` and run `uv lock`.
2. Commit and push the version change to `main`, then wait for CI to pass.
3. Create a GitHub Release from that commit with tag `v<version>`, for example `v0.1.0`.
4. Publish the release. The **Publish to PyPI** workflow will:
   - run the full CI checks against the release tag;
   - verify that the tag matches `pyproject.toml`;
   - build, validate, and smoke-test the wheel and source distribution;
   - transfer the distributions to a separate publishing job;
   - publish to PyPI using OIDC and generate package attestations.
5. Check the workflow result and the release on <https://pypi.org/project/markstitch/>.

Draft releases, ordinary pushes, and standalone tag pushes do not publish packages.
Published prereleases use the same workflow and must have a matching PEP 440 version,
such as `0.2.0rc1` with tag `v0.2.0rc1`.

PyPI does not allow replacing an uploaded distribution. Use a new version for changes
after publication. The workflow intentionally does not skip existing files, so a
partially uploaded release must be inspected before retrying.
