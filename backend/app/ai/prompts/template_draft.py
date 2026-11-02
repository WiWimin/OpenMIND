"""会议模板草稿生成 prompt（`meeting_template_service.generate_template_draft` 使用）。"""

from __future__ import annotations


def build_template_draft(requirement: str) -> str:
    return (
        "你是会议模板设计助手。请根据用户需求设计一个会议文档模板。要求：\n"
        "1. name：简短的模板名称（不超过 20 字）；\n"
        "2. description：一句话说明模板适用场景；\n"
        "3. category：从「会前」「会后」「通用」中选择一个；\n"
        "4. content_text：模板正文，用编号列表给出文档应包含的结构要点，"
        "每条说明该部分要写什么、有什么要求，语言与用户需求一致。\n"
        f"用户需求：{requirement}"
    )
