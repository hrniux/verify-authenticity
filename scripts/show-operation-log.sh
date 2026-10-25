#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo_dir"

if [[ -t 1 && -n "${TERM:-}" && "${TERM:-}" != dumb ]]; then
    clear || true
fi
printf 'VERIFY-AUTHENTICITY 真实 Git 操作日志\n'
printf '仓库: https://github.com/opanai404/verify-authenticity\n'
printf '生成时间: %s\n\n' "$(date '+%Y-%m-%d %H:%M:%S %z')"

printf '=== 提交历史（SHA | 时间 | Git 作者 | 操作）===\n'
git log --reverse \
    --date=format-local:'%Y-%m-%d %H:%M:%S %z' \
    --format='%h | %ad | %an | %s'

printf '\n=== 六轮姓名交替关系（Git 作者 -> 源码创建人）===\n'
while IFS='|' read -r commit_ref expected_round; do
    author_name=$(git show -s --format='%an' "$commit_ref")
    source_creator=$(git show "$commit_ref":src/main/java/com/example/verify/AuthenticityDemo.java \
        | sed -n 's/.*创建人：\([^<]*\)<.*/\1/p' \
        | head -1)
    printf '第 %s 轮 | %s | %s -> %s\n' "$expected_round" "$commit_ref" "$author_name" "$source_creator"
done <<'ROUNDS'
416966f|1
c3374b0|2
d9aea36|3
7a70ecf|4
cb1769e|5
aa002fb|6
ROUNDS

printf '\n=== Java 构建与六轮自动核验 ===\n'
bash scripts/verify.sh

