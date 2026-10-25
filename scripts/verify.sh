#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo_dir"

mvn -q clean package
program_output=$(java -jar target/verify-authenticity-1.0.0.jar)
printf '%s\n' "$program_output"

printf '%s\n' "$program_output" | grep -Fx '演示操作轮次=6' >/dev/null
printf '%s\n' "$program_output" | grep -Fx '源码中手工填写的创建人=张三2026' >/dev/null
# HEAD may be a later maintenance commit; the experiment is anchored below.

verify_round() {
    local commit_ref=$1
    local expected_author=$2
    local expected_email=$3
    local expected_creator=$4
    local actual_author
    local actual_creator

    actual_author=$(git show -s --format='%an <%ae>' "$commit_ref")
    actual_creator=$(git show "$commit_ref":src/main/java/com/example/verify/AuthenticityDemo.java \
        | sed -n 's/.*创建人：\([^<]*\)<.*/\1/p')
    if [[ "$actual_author" != "$expected_author <$expected_email>" || "$actual_creator" != "$expected_creator" ]]; then
        printf '历史提交核验失败: %s\n' "$commit_ref" >&2
        return 1
    fi
}

verify_round 416966f10555d78847e15616fb017095625b0127 '张三2026' 'zhangsan2026@example.invalid' '李四9527'
verify_round c3374b0cc26e00213c3d4f92017dc2b7a8257d8e '李四9527' 'lisi9527@example.invalid' '张三2026'
verify_round d9aea3616ec78e9c239b989e0f5c1633a5f4c96a '张三2026' 'zhangsan2026@example.invalid' '李四9527'
verify_round 7a70ecf2a2c0c93dc3f27081b46143a95f1cbbe8 '李四9527' 'lisi9527@example.invalid' '张三2026'
verify_round cb1769eca11979f95ded56284e4b556e7e3571ae '张三2026' 'zhangsan2026@example.invalid' '李四9527'
verify_round aa002fb59e5505e31143c1b98b29b4e9f55c8653 '李四9527' 'lisi9527@example.invalid' '张三2026'

printf '\n验证通过：\n'
printf '六轮提交的 Git 作者和源码创建人交替关系全部与证据表一致。\n'
