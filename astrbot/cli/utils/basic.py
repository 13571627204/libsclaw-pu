from pathlib import Path

import click

# Static assets bundled inside the installed wheel (built by hatch_build.py).
_BUNDLED_DIST = Path(__file__).parent.parent.parent / "dashboard" / "dist"


def check_astrbot_root(path: str | Path) -> bool:
    """Check if the path is an LibsClaw root directory"""
    if not isinstance(path, Path):
        path = Path(path)
    if not path.exists() or not path.is_dir():
        return False
    if not (path / ".astrbot").exists():
        return False
    return True


def get_astrbot_root() -> Path:
    """Get the LibsClaw root directory path"""
    return Path.cwd()


async def check_dashboard(astrbot_root: Path) -> None:
    """Check if the dashboard is installed"""
    from astrbot.core.utils.io import get_dashboard_version

    # If the wheel ships bundled dashboard assets, no network download is needed.
    if _BUNDLED_DIST.exists():
        click.echo("Dashboard is bundled with the package – skipping download.")
        return

    # WebUI 在线下载已在此发行版中禁用，仅检查本地面板是否存在。
    try:
        dashboard_version = await get_dashboard_version()
    except FileNotFoundError:
        dashboard_version = None
    if dashboard_version is None:
        click.echo(
            "Dashboard is not installed. Online download is disabled in this "
            "distribution. Build it locally: `cd dashboard && pnpm install && "
            "pnpm build`, then copy dashboard/dist to data/dist."
        )
        return
    click.echo(f"Dashboard version: {dashboard_version}")
