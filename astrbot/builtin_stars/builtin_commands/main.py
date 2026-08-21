from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.core.star.filter.command import GreedyStr

from .commands import (
    AdminCommands,
    ConversationCommands,
    HelpCommand,
    NameCommand,
    ProviderCommands,
    SetUnsetCommands,
    SIDCommand,
)


class Main(star.Star):
    def __init__(self, context: star.Context) -> None:
        self.context = context

        self.admin_c = AdminCommands(self.context)
        self.conversation_c = ConversationCommands(self.context)
        self.help_c = HelpCommand(self.context)
        self.name_c = NameCommand(self.context)
        self.provider_c = ProviderCommands(self.context)
        self.setunset_c = SetUnsetCommands(self.context)
        self.sid_c = SIDCommand(self.context)

    @filter.command("help")
    async def help(self, event: AstrMessageEvent) -> None:
        """显示帮助信息"""
        await self.help_c.help(event)

    @filter.command("sid")
    async def sid(self, event: AstrMessageEvent) -> None:
        """查看当前 session ID 和相关会话信息"""
        await self.sid_c.sid(event)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("name")
    async def name(self, event: AstrMessageEvent, alias: GreedyStr) -> None:
        """设置当前 UMO 的显示名称"""
        await self.name_c.name(event, alias)

    @filter.command("reset")
    async def reset(self, message: AstrMessageEvent) -> None:
        """重置当前会话历史"""
        await self.conversation_c.reset(message)

    @filter.command("stop")
    async def stop(self, message: AstrMessageEvent) -> None:
        """停止当前 agent 执行"""
        await self.conversation_c.stop(message)

    @filter.regex(r"^停止$")
    async def stop_cn(self, message: AstrMessageEvent) -> None:
        """停止当前 agent 执行"""
        await self.conversation_c.stop(message)

    @filter.command("new")
    async def new_conv(self, message: AstrMessageEvent) -> None:
        """创建一个新对话"""
        await self.conversation_c.new_conv(message)

    @filter.command("stats")
    async def stats(self, message: AstrMessageEvent) -> None:
        """查看当前对话的 token 使用统计"""
        await self.conversation_c.stats(message)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("provider")
    async def provider(
        self,
        event: AstrMessageEvent,
        idx: str | int | None = None,
        idx2: int | None = None,
    ) -> None:
        """查看或切换当前 LLM Provider"""
        await self.provider_c.provider(event, idx, idx2)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("dashboard_update")
    async def update_dashboard(self, event: AstrMessageEvent) -> None:
        """更新 LibsClaw WebUI"""
        await self.admin_c.update_dashboard(event)

    @filter.command("set")
    async def set_variable(self, event: AstrMessageEvent, key: str, value: str) -> None:
        """设置会话变量"""
        await self.setunset_c.set_variable(event, key, value)

    @filter.command("unset")
    async def unset_variable(self, event: AstrMessageEvent, key: str) -> None:
        """删除已设置的会话变量"""
        await self.setunset_c.unset_variable(event, key)
