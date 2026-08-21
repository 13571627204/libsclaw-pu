from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, MessageChain


class AdminCommands:
    def __init__(self, context: star.Context) -> None:
        self.context = context

    async def update_dashboard(self, event: AstrMessageEvent) -> None:
        """更新管理面板"""
        await event.send(
            MessageChain().message(
                "ℹ️ WebUI 在线更新已在此发行版中禁用。请本地构建 dashboard 后替换 data/dist。"
            )
        )
