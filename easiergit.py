#!/usr/bin/env python3
"""easiergit - An even lazier git TUI: ADD, COMMIT, PUSH, REVERT."""

from __future__ import annotations

import json
import subprocess
import os
import sys
from pathlib import Path
from typing import List, Set, Optional, Tuple

# Early exit if not in a git repo
def _check_git_repo() -> None:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True, text=True, cwd=os.getcwd(), timeout=10,
        )
        if r.returncode != 0:
            print("Not a git repository", file=sys.stderr)
            sys.exit(1)
    except FileNotFoundError:
        print("Not a git repository", file=sys.stderr)
        sys.exit(1)
    except Exception:
        print("Not a git repository", file=sys.stderr)
        sys.exit(1)

_check_git_repo()

from textual.app import App, ComposeResult
from textual.widgets import Button, Static, Input, ListView, ListItem
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.screen import ModalScreen
from textual.binding import Binding


# ── Config ───────────────────────────────────────────────

CONFIG_DIR = Path.home() / ".config" / "easiergit"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {}


def save_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


# ── Git helpers ──────────────────────────────────────────

def git(*args: str) -> Tuple[int, str, str]:
    try:
        r = subprocess.run(["git", *args], capture_output=True, text=True,
                           cwd=os.getcwd(), timeout=30)
        return (r.returncode, r.stdout.rstrip(), r.stderr.strip())
    except Exception as e:
        return (-1, "", str(e))


def is_github_url(url: str) -> bool:
    return "github.com" in url


def remote_url_key(url: str) -> str:
    """Normalize a remote URL to use as a config key."""
    if "@" in url:
        url = url.split("@", 1)[1]
    for prefix in ("https://", "http://", "git@"):
        if url.startswith(prefix):
            url = url[len(prefix):]
    if url.startswith("github.com/"):
        url = url[len("github.com/"):]
    if url.endswith(".git"):
        url = url[:-4]
    return url.strip("/")


def embed_creds_in_url(url: str, username: str, token: str) -> str:
    """Insert username:token into https:// URL."""
    if url.startswith("https://"):
        return f"https://{username}:{token}@{url[8:]}"
    if url.startswith("http://"):
        return f"http://{username}:{token}@{url[7:]}"
    return url


def save_repo_creds(remote_url: str, username: str, token: str) -> None:
    cfg = load_config()
    key = remote_url_key(remote_url)
    cfg.setdefault("repos", {})[key] = {
        "username": username,
        "token": token,
        "url": remote_url,
    }
    save_config(cfg)
    authed = embed_creds_in_url(remote_url, username, token)
    git("remote", "set-url", "origin", authed)


def get_repo_creds(remote_url: str) -> Optional[Tuple[str, str]]:
    cfg = load_config()
    key = remote_url_key(remote_url)
    entry = cfg.get("repos", {}).get(key)
    if entry:
        return (entry["username"], entry["token"])
    return None


def get_clean_url_from_config() -> str:
    """Return the clean (no credentials) URL from config for the current remote."""
    rc, out, _ = git("remote", "get-url", "origin")
    current = out.strip()
    if not current:
        return ""
    key = remote_url_key(current)
    entry = load_config().get("repos", {}).get(key)
    if entry and "url" in entry:
        return entry["url"]
    return current


def get_staged_files() -> List[str]:
    _, out, _ = git("diff", "--cached", "--name-only")
    return out.split("\n") if out else []


def get_all_changed() -> List[str]:
    files: set[str] = set()
    for cmd in [("diff", "--name-only"), ("diff", "--cached", "--name-only"),
                ("ls-files", "--others", "--exclude-standard")]:
        _, out, _ = git(*cmd)
        if out:
            files.update(out.split("\n"))
    return sorted(files)


def get_file_statuses() -> dict[str, str]:
    _, out, _ = git("status", "--porcelain")
    if not out:
        return {}
    statuses = {}
    for line in out.split("\n"):
        line = line.rstrip("\n")
        if not line:
            continue
        code = line[:2]
        rest = line[3:]
        if code.startswith("R"):
            parts = rest.split(" -> ")
            if len(parts) == 2:
                statuses[parts[1].strip()] = code
            continue
        statuses[rest] = code
    return statuses


def get_branches() -> list[tuple[str, bool]]:
    _, out, _ = git("branch")
    if not out:
        return []
    branches = []
    for line in out.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("* "):
            branches.append((line[2:], True))
        else:
            branches.append((line, False))
    return branches


def get_current_branch() -> str:
    _, out, _ = git("rev-parse", "--abbrev-ref", "HEAD")
    return out if out else "HEAD"


def has_commits_to_push(branch: str = "") -> bool:
    if not branch:
        branch = get_current_branch()
    _, out, _ = git("log", f"origin/{branch}..HEAD", "--oneline")
    return bool(out.strip())


def has_remote() -> bool:
    _, out, _ = git("remote")
    return bool(out.strip())


def get_recent_commits(count: int = 30) -> list[tuple[str, str]]:
    rc, out, _ = git("log", f"--max-count={count}", "--format=%H %s")
    if rc != 0 or not out:
        return []
    commits = []
    for line in out.split("\n"):
        line = line.strip()
        if not line:
            continue
        space = line.index(" ")
        commits.append((line[:space], line[space + 1:]))
    return commits


# ── Screens ──────────────────────────────────────────────

class MessageScreen(ModalScreen):
    def __init__(self, message: str) -> None:
        super().__init__()
        self.msg = message

    def compose(self):
        with Vertical():
            yield Static(self.msg, id="msg-content")
            yield Button("OK", id="msg-ok", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()


class ConfirmScreen(ModalScreen):
    def __init__(self, message: str) -> None:
        super().__init__()
        self.msg = message

    def compose(self):
        with Vertical():
            yield Static(self.msg, id="confirm-msg")
            with Horizontal(classes="button-row"):
                yield Button("Yes", id="confirm-yes", variant="primary")
                yield Button("No", id="confirm-no", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-yes")


class CredentialsScreen(ModalScreen):
    def compose(self):
        with Vertical():
            yield Static("GitHub login", id="remote-title")
            yield Static("Enter your GitHub username and a token.", id="remote-desc")
            yield Input(placeholder="Username", id="cred-username")
            yield Input(placeholder="Token (classic PAT or fine-grained)", id="cred-token")
            yield Static(
                "Create a token at: github.com/settings/tokens\n"
                "Enable repo scope for private repos.",
                id="cred-hint")
            with Horizontal(classes="button-row"):
                yield Button("Save", id="cred-save", variant="primary")
                yield Button("Cancel", id="cred-cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cred-cancel":
            self.dismiss(None)
        elif event.button.id == "cred-save":
            user = self.query_one("#cred-username", Input).value.strip()
            token = self.query_one("#cred-token", Input).value.strip()
            if user and token:
                self.dismiss((user, token))


class RemoteUrlScreen(ModalScreen):
    def compose(self):
        with Vertical():
            yield Static("No remote configured", id="remote-title")
            yield Static("Enter the repository URL:", id="remote-desc")
            yield Input(placeholder="https://github.com/user/repo.git", id="remote-url")
            with Horizontal(classes="button-row"):
                yield Button("Add Remote & Push", id="remote-do", variant="primary")
                yield Button("Cancel", id="remote-cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "remote-cancel":
            self.dismiss(None)
        elif event.button.id == "remote-do":
            url = self.query_one("#remote-url", Input).value.strip()
            if url:
                self.dismiss(url)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "remote-url":
            if event.value.strip():
                self.dismiss(event.value.strip())


class FileSelector(ModalScreen):
    BINDINGS = [
        Binding("space", "toggle_item", "Toggle selection"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.selected: Set[str] = set()
        self.statuses: dict[str, str] = {}

    def compose(self):
        with Vertical():
            yield Static("Select changed files:", id="fs-path")
            with ScrollableContainer():
                yield ListView(id="fs-items")
            with Horizontal(classes="button-row"):
                yield Button("\u2713 Add Selected", id="fs-add", variant="primary")
                yield Button("Select All", id="fs-all", variant="primary")
                yield Button("Cancel", id="fs-cancel", variant="default")

    def on_mount(self) -> None:
        self.statuses = get_file_statuses()
        self.render_list()

    def render_list(self) -> None:
        lv = self.query_one("#fs-items", ListView)
        lv.clear()

        entries = sorted(self.statuses.items(),
                         key=lambda x: (x[1] != " D" if len(x[1]) >= 2 else False, x[0]))

        for fpath, code in entries:
            sel = fpath in self.selected
            mark = "\u2611" if sel else "\u2610"
            color = "#f44336" if len(code) >= 2 and code[1] == "D" else "#4caf50"
            label = f"{mark} {code} {fpath}"
            static = Static(label)
            static.styles.color = color
            lv.append(ListItem(static, name=f"file:{fpath}"))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        name = event.item.name if event.item else ""
        if not name:
            return
        _, rel = name.split(":", 1)
        self._toggle(rel)

    def action_toggle_item(self) -> None:
        lv = self.query_one("#fs-items", ListView)
        if lv.index is None:
            return
        child = lv.children[lv.index]
        name = child.name if hasattr(child, 'name') else None
        if not name:
            return
        _, rel = name.split(":", 1)
        self._toggle(rel)

    def _toggle(self, rel: str) -> None:
        if rel in self.selected:
            self.selected.discard(rel)
        else:
            self.selected.add(rel)
        self.render_list()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "fs-cancel":
            self.dismiss(None)
        elif bid == "fs-add":
            self.dismiss((self.selected, self.statuses))
        elif bid == "fs-all":
            self.selected = set(self.statuses.keys())
            self.render_list()


class CommitScreen(ModalScreen):
    def compose(self):
        with Vertical():
            yield Static("Commit message:", id="commit-title")
            yield Input(placeholder="Message (required)", id="commit-msg")
            yield Input(placeholder="Description (optional)", id="commit-desc")
            with Horizontal(classes="button-row"):
                yield Button("\u2713 Commit", id="commit-do", variant="primary")
                yield Button("Cancel", id="commit-cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "commit-cancel":
            self.dismiss(None)
            return
        if event.button.id == "commit-do":
            msg = self.query_one("#commit-msg", Input).value
            if msg:
                desc = self.query_one("#commit-desc", Input).value
                full = msg + ("\n\n" + desc if desc else "")
                self.dismiss(full)
            else:
                self.query_one("#commit-title", Static).update(
                    "\u26a0\ufe0f Message required!")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "commit-msg":
            msg = event.value
            if msg:
                desc = self.query_one("#commit-desc", Input).value
                full = msg + ("\n\n" + desc if desc else "")
                self.dismiss(full)


class PushScreen(ModalScreen):
    def __init__(self) -> None:
        super().__init__()
        self.branches = get_branches()

    def compose(self):
        with Vertical():
            yield Static("Select branch:", id="push-title")
            with ScrollableContainer():
                yield ListView(id="branch-list")
            with Horizontal(classes="button-row"):
                yield Button("\u2191 Push", id="push-do", variant="primary")
                yield Button("Cancel", id="push-cancel", variant="default")

    def on_mount(self) -> None:
        lv = self.query_one("#branch-list", ListView)
        for name, is_current in self.branches:
            marker = "\u2605 " if is_current else "  "
            lv.append(ListItem(Static(f"{marker}{name}")))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "push-cancel":
            self.dismiss(None)
        elif event.button.id == "push-do":
            lv = self.query_one("#branch-list", ListView)
            if lv.index is not None and 0 <= lv.index < len(self.branches):
                self.dismiss(self.branches[lv.index][0])


class RevertScreen(ModalScreen):
    def __init__(self) -> None:
        super().__init__()
        self.commits = get_recent_commits()

    def compose(self):
        with Vertical():
            yield Static("Reset to which commit?", id="push-title")
            with ScrollableContainer():
                yield ListView(id="commit-list")
            with Horizontal(classes="button-row"):
                yield Button("\u21a9 Revert", id="revert-do", variant="primary")
                yield Button("Cancel", id="revert-cancel", variant="default")

    def on_mount(self) -> None:
        lv = self.query_one("#commit-list", ListView)
        for h, subj in self.commits:
            lv.append(ListItem(Static(f"{h[:7]} {subj}")))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "revert-cancel":
            self.dismiss(None)
        elif event.button.id == "revert-do":
            lv = self.query_one("#commit-list", ListView)
            if lv.index is not None and 0 <= lv.index < len(self.commits):
                self.dismiss(self.commits[lv.index][0])


# ── Main app ─────────────────────────────────────────────

class EasierGitApp(App):
    CSS = """
    Screen {
        background: #1a1a2e;
    }

    .big-btn {
        width: 1fr;
        height: 1fr;
        min-width: 10;
        margin: 1 1;
        background: rgb(72, 245, 72);
        color: rgb(45, 45, 45);
        content-align: center middle;
        text-style: bold;
        border: none;
    }

    .big-btn:disabled {
        background: #333;
        color: #666;
    }

    #main-box {
        width: 100%;
        height: 100%;
        align: center middle;
    }

    #title {
        height: 2;
        background: #16213e;
        color: white;
        content-align: center middle;
        text-style: bold;
    }

    #btn-row {
        height: 1fr;
    }

    #status-bar {
        height: 2;
        background: #16213e;
        color: white;
        content-align: center middle;
    }

    ModalScreen {
        background: #1a1a2e;
    }

    #confirm-msg, #msg-content {
        height: auto;
        padding: 2;
        content-align: center middle;
        color: white;
        text-style: bold;
    }

    #remote-title, #remote-desc {
        height: auto;
        content-align: center middle;
        color: white;
        text-style: bold;
    }

    #remote-title {
        padding-top: 2;
    }

    #cred-hint {
        height: auto;
        content-align: center middle;
        color: #888;
        text-style: italic;
    }

    #fs-path {
        height: 2;
        background: #1a1a2e;
        color: #aaa;
        padding: 0 1;
    }

    #commit-title, #push-title {
        height: 3;
        content-align: center middle;
        color: white;
        background: #16213e;
    }

    ListView {
        background: #1a1a2e;
        color: white;
        height: 1fr;
    }

    ListItem {
        padding: 0 1;
    }

    ListItem:hover {
        background: #1a5276;
    }

    Input {
        background: #1a1a2e;
        color: white;
        border: solid #1a5276;
        margin: 1;
    }

    .button-row {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    Button.variant-primary {
        background: blue;
        color: black;
    }

    Button.variant-default {
        background: #555;
        color: white;
    }

    ScrollableContainer {
        height: 1fr;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.did_add = False
        self.did_commit = False
        self._last_remote_url: str = ""

    def compose(self):
        with Vertical(id="main-box"):
            yield Static("EASIER GIT", id="title")
            with Horizontal(id="btn-row"):
                yield self._big_btn("+  ADD", "add-btn")
                yield self._big_btn("\u2713  COMMIT", "commit-btn", disabled=True)
                yield self._big_btn("\u2191  PUSH", "push-btn", disabled=True)
                yield self._big_btn("\u21a9  REVERT", "revert-btn")
            yield Static("", id="status-bar")

    def _big_btn(self, label: str, btn_id: str,
                  disabled: bool = False) -> Button:
        return Button(label, id=btn_id, disabled=disabled,
                      variant="primary", classes="big-btn")

    def on_mount(self) -> None:
        self.refresh_status()

    def refresh_status(self) -> None:
        staged = len(get_staged_files())
        bar = self.query_one("#status-bar", Static)
        branch = get_current_branch()
        parts = []
        if self.did_add:
            parts.append("ADD")
        if self.did_commit:
            parts.append("COMMIT")
        flow = " \u2192 ".join(parts) if parts else "\u2014"
        bar.update(f"Branch: {branch} | Staged: {staged} | Flow: {flow}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "add-btn":
            self.push_screen(FileSelector(), self._on_add_done)
        elif bid == "commit-btn":
            self._start_commit()
        elif bid == "push-btn":
            self._start_push()
        elif bid == "revert-btn":
            self._start_revert()

    def _on_add_done(self, result: Optional[Tuple[Set[str], dict[str, str]]]) -> None:
        if result is None:
            return
        selected, statuses = result
        if not selected:
            return
        to_add = []
        to_rm = []
        for p in sorted(selected):
            code = statuses.get(p, "")
            if len(code) >= 2:
                if code[1] == "D":
                    to_rm.append(p)
                elif code[1] in ("M", "?"):
                    to_add.append(p)
        errs = []
        if to_add:
            rc, _, err = git("add", "--", *to_add)
            if rc != 0:
                errs.append(f"add: {err[:100]}")
        if to_rm:
            rc, _, err = git("rm", *to_rm)
            if rc != 0:
                errs.append(f"rm: {err[:100]}")
        if errs:
            self.push_screen(MessageScreen("\n".join(errs)))
        else:
            self.did_add = True
            self.query_one("#commit-btn", Button).disabled = False
            self.refresh_status()

    def _start_commit(self) -> None:
        staged = get_staged_files()
        if not staged:
            self.push_screen(MessageScreen(
                "Nothing staged.\nUse ADD or git add externally."))
        elif staged and not self.did_add:
            self.push_screen(
                ConfirmScreen(
                    f"{len(staged)} file(s) already staged\n"
                    "from outside easiergit.\nProceed with commit?"),
                self._confirm_commit)
        else:
            self._show_commit_screen()

    def _confirm_commit(self, confirmed: Optional[bool]) -> None:
        if confirmed:
            self._show_commit_screen()

    def _show_commit_screen(self) -> None:
        self.push_screen(CommitScreen(), self._on_commit_done)

    def _on_commit_done(self, msg: Optional[str]) -> None:
        if msg is None:
            return
        rc, _, err = git("commit", "-m", msg)
        if rc == 0:
            self.did_commit = True
            self.query_one("#push-btn", Button).disabled = False
            self.refresh_status()
        else:
            self.push_screen(MessageScreen(f"Commit failed:\n{err[:200]}"))

    def _start_push(self) -> None:
        branch = get_current_branch()
        if not has_remote():
            self.push_screen(RemoteUrlScreen(), self._on_remote_url)
            return
        if not has_commits_to_push(branch) and not self.did_commit:
            self.push_screen(MessageScreen(
                "Nothing to push.\nUse COMMIT or push externally."))
        elif has_commits_to_push(branch) and not self.did_commit:
            self.push_screen(
                ConfirmScreen(
                    f"Unpushed commits on {branch}.\nProceed with push?"),
                self._confirm_push)
        else:
            self._ensure_creds_and_push()

    def _on_remote_url(self, url: Optional[str]) -> None:
        if url is None:
            return
        self._last_remote_url = url
        rc, _, err = git("remote", "add", "origin", url)
        if rc != 0:
            self.push_screen(MessageScreen(f"Failed to add remote:\n{err[:200]}"))
            return
        if is_github_url(url) and not get_repo_creds(url):
            self.push_screen(CredentialsScreen(), self._on_creds_after_remote)
        else:
            self._show_push_screen()

    def _on_creds_after_remote(self, result: Optional[Tuple[str, str]]) -> None:
        if result is None:
            return
        url = self._last_remote_url
        user, token = result
        save_repo_creds(url, user, token)
        self._show_push_screen()

    def _ensure_creds_and_push(self) -> None:
        clean = get_clean_url_from_config()
        if not clean:
            self._show_push_screen()
            return
        git("remote", "set-url", "origin", clean)
        if is_github_url(clean):
            creds = get_repo_creds(clean)
            if creds:
                user, token = creds
                git("remote", "set-url", "origin",
                    embed_creds_in_url(clean, user, token))
                self._show_push_screen()
            else:
                self.push_screen(CredentialsScreen(), self._on_creds_from_push)
        else:
            self._show_push_screen()

    def _on_creds_from_push(self, result: Optional[Tuple[str, str]]) -> None:
        if result is None:
            return
        clean = get_clean_url_from_config()
        user, token = result
        save_repo_creds(clean, user, token)

    def _confirm_push(self, confirmed: Optional[bool]) -> None:
        if confirmed:
            self._ensure_creds_and_push()

    def _show_push_screen(self) -> None:
        self.push_screen(PushScreen(), self._on_push_done)

    def _on_push_done(self, branch: Optional[str]) -> None:
        if branch is None:
            self._restore_clean_url()
            return
        rc, _, err = git("push", "-u", "origin", branch)
        self._restore_clean_url()
        if rc == 0:
            self.refresh_status()
        elif "401" in err or "403" in err or "Authentication failed" in err:
            clean = get_clean_url_from_config()
            if clean and get_repo_creds(clean):
                self.push_screen(
                    ConfirmScreen(
                        "Push failed: bad credentials.\n"
                        "Update your GitHub token?"),
                    self._on_update_creds)
            else:
                self.push_screen(MessageScreen(f"Push failed:\n{err[:200]}"))
        else:
            self.push_screen(MessageScreen(f"Push failed:\n{err[:200]}"))

    def _restore_clean_url(self) -> None:
        clean = get_clean_url_from_config()
        if clean:
            git("remote", "set-url", "origin", clean)

    def _on_update_creds(self, confirmed: Optional[bool]) -> None:
        if confirmed:
            self.push_screen(CredentialsScreen(), self._on_creds_from_push)

    def _start_revert(self) -> None:
        if not get_recent_commits(1):
            self.push_screen(MessageScreen("No commits to revert."))
            return
        self.push_screen(RevertScreen(), self._confirm_revert)

    def _confirm_revert(self, commit_hash: Optional[str]) -> None:
        if commit_hash is None:
            return
        self.push_screen(
            ConfirmScreen(
                f"Reset to {commit_hash[:7]}?\n"
                "This discards all uncommitted\n"
                "changes and deletes untracked files."),
            lambda ok: self._do_revert(commit_hash) if ok else None)

    def _do_revert(self, commit_hash: str) -> None:
        h = commit_hash.strip()
        rc, out, err = git("reset", "--hard", h)
        if rc == 0:
            git("clean", "-fd")
            _, head, _ = git("rev-parse", "--short", "HEAD")
            self.refresh_status()
        else:
            msg = (err or out or "unknown error")[:200]
            self.push_screen(MessageScreen(f"Reset failed:\n{msg}"))


def main() -> None:
    EasierGitApp().run()


if __name__ == "__main__":
    main()
