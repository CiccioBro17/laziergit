# easiergit

A simple tool with big buttons to help you add, commit, push, and reset in git.

No terminal commands to remember. Just click.

## How to install

```bash
git clone https://github.com/CiccioBro17/easiergit.git
cd easiergit
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
bash install.sh
```

Then type `easiergit` in any git folder.

## What the buttons do

- **ADD** — pick which files to save. New or changed files show in green, deleted files in red.
- **COMMIT** — write a short message and save your changes.
- **PUSH** — send your changes to the internet (GitHub, etc). If no remote is set, it asks for a URL and credentials (username and token).
- **REVERT** — pick a commit and go back to how things were then.

## How to remove

```bash
bash uninstall.sh
```

## License

This project has no license. That means by default, nobody else can copy, change, or share it. If you want to use it or share it you are free to do so
