"""推送当前分支；若直连推送被 GitHub 边缘节点超时掐断，自动拆成小批量提交分批推送。

用法：python tools/push_safely.py
环境变量 PUSH_SAFELY_FORCE_SPLIT=1 可跳过直连尝试、直接分批（仅用于自测）。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "main"
BATCH_BYTES = 350_000
PUSH_ATTEMPTS = 3
PUSH_TIMEOUT = 300

TRANSIENT_MARKERS = (
    "408",
    "RPC failed",
    "unexpected disconnect",
    "early EOF",
    "timed out",
    "Connection was reset",
    "Could not resolve",
)


class GitError(RuntimeError):
    pass


def find_git() -> str:
    found = shutil.which("git")
    if found:
        return found
    for candidate in (
        Path(r"C:\Program Files\Git\cmd\git.exe"),
        Path(r"C:\Program Files (x86)\Git\cmd\git.exe"),
    ):
        if candidate.exists():
            return str(candidate)
    raise GitError("未找到 git，请确认 Git for Windows 已安装并加入 PATH。")


GIT = find_git()


def git(*args: str, check: bool = True, timeout: int = 120) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        [GIT, *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
    )
    if check and proc.returncode != 0:
        raise GitError((proc.stderr or proc.stdout).strip() or f"git {' '.join(args)} 失败")
    return proc


def count_pending(upstream: str) -> int:
    out = git("rev-list", "--count", f"{upstream}..HEAD").stdout.strip()
    return int(out or 0)


def has_ref(ref: str) -> bool:
    return git("rev-parse", "--verify", "--quiet", ref, check=False).returncode == 0


def try_push() -> tuple[bool, str]:
    try:
        proc = git("push", "origin", BRANCH, check=False, timeout=PUSH_TIMEOUT)
    except subprocess.TimeoutExpired:
        return False, "推送超时"
    output = f"{proc.stderr or ''}{proc.stdout or ''}".strip()
    return proc.returncode == 0, output


def is_transient(output: str) -> bool:
    return any(marker in output for marker in TRANSIENT_MARKERS)


def short(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-1] if lines else "未知错误"


def changed_paths(base: str, head: str) -> list[str]:
    out = git("-c", "core.quotepath=false", "diff", "--name-only", base, head).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def size_of(path: str) -> int:
    target = ROOT / path
    try:
        return target.stat().st_size
    except OSError:
        return 0


def make_batches(paths: list[str]) -> list[list[str]]:
    batches: list[list[str]] = []
    current: list[str] = []
    current_size = 0
    for path in paths:
        size = size_of(path)
        if current and current_size + size > BATCH_BYTES:
            batches.append(current)
            current = []
            current_size = 0
        current.append(path)
        current_size += size
    if current:
        batches.append(current)
    return batches


def push_with_retries(label: str) -> bool:
    for attempt in range(1, PUSH_ATTEMPTS + 1):
        ok, output = try_push()
        if ok:
            print(f"{label} 推送成功。")
            return True
        print(f"{label} 第 {attempt} 次推送失败：{short(output)}")
        if not is_transient(output):
            print("这不是网络超时类错误，已停止自动重试，请手工检查。")
            return False
        if attempt < PUSH_ATTEMPTS:
            time.sleep(3)
    return False


def squash_batches(base: str, tree: str, message: str) -> bool:
    """分批推送完成后，把多条提交合并成一条（对象都已在远端，这次推送只有几 KB）。"""
    tip = git("rev-parse", "HEAD").stdout.strip()
    git("reset", "--soft", base)
    git("commit", "-m", message)
    if git("rev-parse", "HEAD^{tree}").stdout.strip() != tree:
        print("合并后的内容校验不一致，保留分批提交。")
        git("reset", "--soft", tip)
        return False
    try:
        proc = git("push", "--force-with-lease", "origin", BRANCH, check=False, timeout=PUSH_TIMEOUT)
        failed = proc.returncode != 0
    except subprocess.TimeoutExpired:
        failed = True
    if failed:
        print("合并提交记录时推送未成功，已保留分批提交状态。")
        git("reset", "--soft", tip)
        return False
    print("已把分批提交合并为一条记录。")
    return True


def split_and_push() -> int:
    upstream = f"origin/{BRANCH}"
    base = git("rev-parse", upstream).stdout.strip()
    head_tree = git("rev-parse", "HEAD^{tree}").stdout.strip()
    message = git("log", "-1", "--pretty=%s").stdout.strip() or "data: update ranking"

    dirty = git("status", "--porcelain", "--untracked-files=no").stdout.strip()
    if dirty:
        print("工作区还有未提交的改动，无法安全拆分，请先处理后再试。")
        return 1

    paths = changed_paths(base, "HEAD")
    if not paths:
        print("没有检测到需要推送的改动。")
        return 1

    batches = make_batches(paths)
    total = len(batches)
    print(f"开始分批推送：{len(paths)} 个文件，拆成 {total} 批。")

    git("reset", "--soft", base)
    git("reset")

    for index, batch in enumerate(batches, start=1):
        label = f"[{index}/{total}]"
        git("add", "-A", "--", *batch)
        staged = git("diff", "--cached", "--name-only").stdout.strip()
        if not staged:
            print(f"{label} 没有新增内容，跳过。")
            continue
        git("commit", "-m", f"{message} ({index}/{total})")
        if not push_with_retries(label):
            print("分批推送中断，重新运行本脚本会从断点继续。")
            return 1

    final_tree = git("rev-parse", "HEAD^{tree}").stdout.strip()
    if final_tree != head_tree:
        print("警告：分批推送后的文件内容与原始提交不一致，请检查。")
        return 1

    print(f"分批推送完成，共 {total} 批。")
    squash_batches(base, head_tree, message)
    return 0


def main() -> int:
    try:
        upstream = f"origin/{BRANCH}"
        if not has_ref(upstream):
            git("fetch", "origin", check=False)
        if not has_ref(upstream):
            ok, output = try_push()
            if ok:
                print("推送成功。")
                return 0
            print(f"推送失败：{short(output)}")
            return 1

        pending = count_pending(upstream)
        if pending == 0:
            print("没有需要推送的提交。")
            return 0

        if os.environ.get("PUSH_SAFELY_FORCE_SPLIT") != "1":
            for attempt in range(1, PUSH_ATTEMPTS + 1):
                ok, output = try_push()
                if ok:
                    print("推送成功。")
                    return 0
                print(f"第 {attempt} 次推送失败：{short(output)}")
                if not is_transient(output):
                    print("这不是网络超时类错误，已停止自动重试，请手工检查。")
                    return 1
                if attempt < PUSH_ATTEMPTS:
                    time.sleep(3)
            print("直连推送多次超时，改为分批推送。")

        return split_and_push()
    except GitError as exc:
        print(f"推送失败：{exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"推送失败：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
