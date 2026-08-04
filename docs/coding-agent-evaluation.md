# Coding Agent 评测

评测入口为 `scripts/evaluate_coding_agent.py`，数据集为
`tests/evaluation/coding_tasks.json`。每条任务在独立 detached Git worktree 中运行，
不会修改主工作区。

```powershell
.\.venv\Scripts\python.exe .\scripts\evaluate_coding_agent.py
```

评测同时检查：

- 模型补丁能否通过 `git apply --check`；
- 指定 pytest 目标是否通过；
- Git diff 是否覆盖任务预期文件；
- 完成任务所需尝试轮数；
- 整体任务通过率。

默认执行后清理临时 worktree。只有需要人工审查失败补丁时才使用
`--keep-workspaces`。运行真实评测会调用配置的大模型 API，因此不能把尚未执行的
结果写成已验证指标。
