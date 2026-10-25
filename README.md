# Git / GitHub 姓名字段可编辑性验证（Java）

这是一个故意保持简单的 Java 21 演示项目，用可重复实验说明 GitHub 文件页面上两类姓名文字的来源不同：

1. 文件上方的提交作者来自 Git 提交对象中的 `author` / `committer` 字段；
2. Java 注释里的“创建人”只是源码中的普通文字；
3. 两类文字都可以在提交发生前由本地用户填写，单独出现时都不足以唯一证明真实操作者。

> 本仓库只验证技术机制，不判断任何特定截图真假，也不认定任何具体人员实施了某项操作。

## 可复现实验

六轮提交故意反复使用相反的姓名组合：

| 轮次 | 提交 | Git 提交作者 | Java 源码“创建人” |
| --- | --- | --- | --- |
| 1 | `416966f…` | `张三2026` | `李四9527` |
| 2 | `c3374b0…` | `李四9527` | `张三2026` |
| 3 | `d9aea36…` | `张三2026` | `李四9527` |
| 4 | `7a70ecf…` | `李四9527` | `张三2026` |
| 5 | `cb1769e…` | `张三2026` | `李四9527` |
| 6 | `aa002fb…` | `李四9527` | `张三2026` |

六轮操作将姓名反复对调，直接证明两个位置并不互相校验。Git 提交作者来自创建提交时的身份字段；源码“创建人”来自 `AuthenticityDemo.java` 中可编辑的普通文字。

可直接在线查看两次提交：[`416966f…`（张三2026）](https://github.com/opanai404/verify-authenticity/commit/416966f10555d78847e15616fb017095625b0127)和 [`c3374b0…`（李四9527）](https://github.com/opanai404/verify-authenticity/commit/c3374b0cc26e00213c3d4f92017dc2b7a8257d8e)。

这两个姓名都是虚构的演示名称，邮箱使用保留的 `.invalid` 域名，不冒充真实账号。

完整 SHA、时间、作者、提交者、签名状态和源码创建人见 [`evidence/operation-log.txt`](evidence/operation-log.txt)。

实际终端与 GitHub 页面截图、截取时间和 SHA-256 校验值见 [`evidence/SCREENSHOTS.md`](evidence/SCREENSHOTS.md)。

## 一键运行

要求：JDK 21、Maven、Git。

```bash
bash scripts/verify.sh
```

也可以逐步执行：

```bash
mvn clean package
java -jar target/verify-authenticity-1.0.0.jar
git cat-file -p HEAD
git log -p -- src/main/java/com/example/verify/AuthenticityDemo.java
```

`git cat-file -p HEAD` 直接读取 Git 提交对象，其中能看到 `author` 和 `committer` 原始字段；Java 程序同时打印源码中手写的“创建人”。

自动核验以表中六个完整历史 SHA 为准；后续维护提交的作者不会改变六轮实验结果。Java 程序仍显示运行时的当前 `HEAD`。CI 使用完整 Git 历史、JDK 21 和 Maven，并校验已保存截图的哈希。

脚本的终端与维护提交回归测试只需 Python 3 和 Git，不执行 Maven 构建：

```bash
python3 -B -m unittest discover -s tests -v
```

## JSON 核验报告

只需 Python 3.9+、Git 和完整历史即可生成机器可读报告，不执行 Maven 构建：

```bash
python3 -B scripts/verification_report.py
python3 -B scripts/verification_report.py --output verification-report.json
```

`--repo /path/to/checkout` 可核验另一个完整仓库。默认只向标准输出打印 JSON；`--output` 将 JSON 写入指定文件。核验通过退出码为 0，发现缺失对象、字段不一致、缺失截图或哈希不一致时为 1；失败报告仍保留具体差异。CI 生成并上传 `verification-report.json`，供每次运行下载。

报告格式版本为 `schema_version: 1`，主要字段：

- `historical_rounds`：六个固定完整 SHA，各轮 `expected` 来自当前保存的操作日志，`actual` 来自真实历史提交和 Java 源码对象；比较作者、提交者、作者日期、签名状态、主题和源码创建人，并记录源码 blob ID。禁用本地 Git replacement refs，避免替换对象掩盖原始字段。
- `screenshots`：当前三个截图文件的实际 SHA-256、当前清单中的预期 SHA-256，以及逐项结果；日志和清单本身的 SHA-256 也记录在报告中。
- `current_checkout`：当前 HEAD、当前提交元数据、工作区是否有更改、当前源码创建人与源码哈希，仅用于说明报告生成环境。维护提交的作者或当前源码更改不替代历史六轮的结论；当前源码的读取问题列在本字段的 `errors` 中。
- `ok` 和 `errors`：历史字段及截图核验的总体结果和具体失败原因。当前 Git 仓库/HEAD 不可读也会令总体失败。`limitations` 说明报告的证据边界。

哈希一致仅表示文件与当前校验清单相符，日志字段一致仅表示与固定历史对象相符。这不能认证截图所描绘的事件、建立防篡改保管链或证明真实操作者身份；清单和日志本身也不是独立认证的信任来源。Git 签名状态依赖运行机器的 Git/密钥配置。本报告补充一键 Java 核验，不替代实际构建。

## 给非技术人员的简要结论

截图中出现一个姓名，只能证明截图在那个位置显示了这段文字。若要进一步判断真实操作者，至少还应核对原始仓库、完整提交 SHA、提交对象、签名状态、账号邮箱关联、组织审计日志、服务器访问记录及证据保全过程。详见 [EVIDENCE.md](EVIDENCE.md)。

## 官方依据

- [GitHub：Git 提交姓名不等于 GitHub 用户名，且可以使用任意文字](https://docs.github.com/en/get-started/git-basics/setting-your-username-in-git)
- [Git：`GIT_AUTHOR_NAME`、`GIT_COMMITTER_NAME` 可覆盖配置](https://git-scm.com/docs/git)
- [GitHub：签名验证状态用于提高对提交身份的可信度](https://docs.github.com/en/authentication/managing-commit-signature-verification/displaying-verification-statuses-for-all-of-your-commits)
