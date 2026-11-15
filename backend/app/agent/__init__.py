"""Agent 框架（轻量工作流引擎）对外入口。

不引入 LangGraph：`intent` 负责路由，`workflow` 负责编排，
`service` 负责持久化与确认门。详见 `docs/agent-framework.md`。
"""

from app.agent import intent, service, tools, workflow, workflows

__all__ = ["intent", "service", "tools", "workflow", "workflows"]
