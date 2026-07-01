# Population grids paper

## Data storage and tracking

This repository uses [DVC](https://dvc.org/) to keep large and generated data
out of Git while still making the project reproducible. Git tracks the DVC
metadata files, and DVC stores the actual tracked data in the configured remote.
Contributors should install the repository's pre-commit hooks so DVC can handle
common synchronization steps automatically.

All project data lives under `data/`:

- `data/raw/` contains the initial source files downloaded from public sources.
  These files are intentionally ignored by DVC through `.dvcignore`, because
  re-uploading public data to the project remote would be wasteful. Scripts in
  this repository should populate this directory so every contributor gets the
  same expected raw-data layout.
- `data/generated/` contains generated artifacts derived from the raw inputs.
  This directory is tracked by DVC and shared through the remote so contributors
  can reproduce or inspect generated outputs without committing large files to
  Git.

The repository currently tracks `data/` through `data.dvc`. Because
`data/raw/` is listed in `.dvcignore`, only the non-ignored contents, such as
`data/generated/`, are stored in the DVC remote.

### One-time setup

1. Clone the repository and install the Python environment as usual:

   ```sh
   uv sync
   ```

2. Install DVC with Azure support if you do not already have a `dvc` command
   available:

   ```sh
   uv tool install "dvc[azure]"
   ```

   If you prefer not to install a persistent `dvc` command, run the examples
   below as `uvx --from "dvc[azure]" dvc <command>`.

3. Install the repository hooks:

   ```sh
   uv run pre-commit install --hook-type pre-commit --hook-type pre-push --hook-type post-checkout
   ```

   The DVC hooks are already declared in `.pre-commit-config.yaml`. Installing
   them enables:

   - `pre-commit`: runs `dvc status` before `git commit`, so DVC changes are
     visible before metadata is committed.
   - `pre-push`: runs `dvc push` before `git push`, so updated generated data is
     uploaded before the Git branch is published.
   - `post-checkout`: runs `dvc checkout` after `git checkout`, so the local
     workspace is updated to match the DVC metadata on the checked-out branch
     when the data is already in the local DVC cache.

4. Make sure you have access to the configured Azure remote:

   ```sh
   dvc remote list
   ```

   The remote is named `azure_remote` and points to
   `azure://paper-data/population_grids_paper`. If `dvc pull` or `dvc push`
   reports an authentication error, authenticate with Azure using the account
   that has access to that storage location.

VS Code users may also want the
[DVC by lakeFS](https://marketplace.visualstudio.com/items?itemName=lakefs.lakefs-dvc)
extension. It adds DVC status, tracked-data views, and sync actions to the IDE.

### Getting data after cloning

After cloning the repository for the first time, pull the DVC-tracked generated
data:

```sh
dvc pull
```

This restores tracked generated artifacts under `data/generated/`. It does not
download `data/raw/`, because raw public source files are excluded from DVC and
should be created by the repository's data-ingestion scripts.

After switching branches, the installed `post-checkout` hook runs `dvc checkout`
to align the workspace with the checked-out DVC metadata. If the required
generated data is not yet in your local DVC cache, run `dvc pull`.

### Updating generated data

When your work changes generated artifacts:

1. Update or regenerate files under `data/generated/`.
2. Record the new DVC state:

   ```sh
   dvc add data
   ```

3. Review what changed:

   ```sh
   git status
   dvc status
   ```

4. Commit the DVC metadata, not the generated files themselves:

   ```sh
   git add data.dvc
   git commit -m "Update generated data"
   ```

   The installed `pre-commit` hook runs `dvc status` during `git commit`. If it
   reports that generated data and DVC metadata are out of sync, update the DVC
   metadata with `dvc add data` before committing.

5. Push your branch as usual. The installed `pre-push` hook runs `dvc push`
   before Git publishes the branch:

   ```sh
   git push
   ```

### DVC workflow tips

- Use `dvc status` to compare local data with the current DVC metadata.
- Use `dvc pull` when a branch references generated data that is missing from
  your local cache.
- Let the `pre-push` hook run `dvc push` when a commit updates `data.dvc`;
  otherwise collaborators may receive metadata for data that is not yet
  available in the remote.
- Do not manually commit files from `data/` to Git. Git should track DVC
  metadata, notebooks, scripts, and documentation; DVC should track generated
  data artifacts.
