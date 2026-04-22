"""Discord bot — DM signal alerts with one-click grade buttons.

Runs in a background daemon thread with its own asyncio event loop so it
doesn't block the synchronous trading loop.

Required env vars
-----------------
DISCORD_BOT_TOKEN  — bot token from the Discord Developer Portal
DISCORD_USER_ID    — your numeric Discord user ID (right-click your name → Copy User ID)

The bot must be invited to your server with the "bot" scope and the
"Send Messages" + "Read Message History" permissions. No channel is needed —
all messages go directly to you via DM.

If discord.py is not installed the module loads cleanly and all calls are
no-ops — the trading loop will fall back to the webhook alerter.
"""
import asyncio
import logging
import threading
from typing import Optional

try:
    import discord
    _DISCORD_AVAILABLE = True
except ImportError:
    _DISCORD_AVAILABLE = False

from tradegumi import config
from tradegumi.journal import grade_signal

log = logging.getLogger(__name__)

if not _DISCORD_AVAILABLE:
    log.warning(
        "discord.py is not installed — Discord DMs disabled. "
        "Rebuild the container after adding discord.py>=2.4 to requirements.txt."
    )

_bot = None
_loop: Optional[asyncio.AbstractEventLoop] = None
_ready = threading.Event()


# ── Discord classes (only defined when the library is present) ────────────────

if _DISCORD_AVAILABLE:
    class GradeView(discord.ui.View):  # type: ignore[misc]
        """Three-button row attached to each signal DM.

        Uses the Discord message ID to find the journal entry — the view
        carries no per-message state, so it survives bot restarts cleanly.
        """

        def __init__(self):
            super().__init__(timeout=None)

        async def _apply_grade(self, interaction: discord.Interaction, grade: str, label: str):
            msg_id = str(interaction.message.id)
            success = grade_signal(msg_id, grade)
            if success:
                updated = interaction.message.content + f"\n\n**Graded:** {label}"
                await interaction.response.edit_message(content=updated, view=None)
            else:
                await interaction.response.send_message(
                    "Could not locate this signal in the journal. "
                    "It may have been sent before journaling was enabled.",
                    ephemeral=True,
                )

        @discord.ui.button(label="✅ TP Hit", style=discord.ButtonStyle.success, custom_id="tg_grade_tp")
        async def tp_hit(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self._apply_grade(interaction, "TP_HIT", "TP Hit ✅")

        @discord.ui.button(label="❌ SL Hit", style=discord.ButtonStyle.danger, custom_id="tg_grade_sl")
        async def sl_hit(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self._apply_grade(interaction, "SL_HIT", "SL Hit ❌")

        @discord.ui.button(label="⚠️ Manual Close", style=discord.ButtonStyle.secondary, custom_id="tg_grade_manual")
        async def manual_close(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self._apply_grade(interaction, "MANUAL_CLOSE", "Manual Close ⚠️")

    class TradeGumiBot(discord.Client):  # type: ignore[misc]
        def __init__(self):
            intents = discord.Intents.default()
            super().__init__(intents=intents)

        async def setup_hook(self):
            self.add_view(GradeView())

        async def on_ready(self):
            log.info("Discord bot ready: %s (id=%s)", self.user, self.user.id)
            _ready.set()

        async def _dm_user(self, content: str) -> Optional[str]:
            user = await self.fetch_user(int(config.DISCORD_USER_ID))
            dm = await user.create_dm()
            msg = await dm.send(content=content, view=GradeView())
            return str(msg.id)

        async def _dm_plain(self, content: str) -> None:
            user = await self.fetch_user(int(config.DISCORD_USER_ID))
            dm = await user.create_dm()
            await dm.send(content=content)


# ── Thread management ─────────────────────────────────────────────────────────

def _run_bot(token: str):
    global _bot, _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    _bot = TradeGumiBot()
    try:
        _loop.run_until_complete(_bot.start(token))
    except asyncio.CancelledError:
        pass
    except Exception as e:
        log.error("Discord bot exited with error: %s", e)


def start_bot_thread() -> bool:
    """Start the Discord bot in a background daemon thread.

    Returns True if started. Safe to call multiple times. Falls back
    gracefully if discord.py is not installed or env vars are missing.
    """
    if not _DISCORD_AVAILABLE:
        return False
    if _bot is not None:
        return True

    token = config.DISCORD_BOT_TOKEN
    user_id = config.DISCORD_USER_ID

    if not token:
        log.warning("DISCORD_BOT_TOKEN not set — Discord DMs disabled, falling back to webhook")
        return False
    if not user_id:
        log.warning("DISCORD_USER_ID not set — Discord DMs disabled, falling back to webhook")
        return False

    thread = threading.Thread(target=_run_bot, args=(token,), daemon=True, name="discord-bot")
    thread.start()
    log.info("Discord bot thread started")
    return True


# ── Public API (thread-safe) ──────────────────────────────────────────────────

def post_signal_dm(signal, rr: Optional[float] = None) -> Optional[str]:
    """Send a signal DM and return the Discord message ID (for journal linking).

    Thread-safe — designed to be called from the synchronous trading loop.
    Returns None if the bot is not running or the send fails.
    """
    if not _DISCORD_AVAILABLE or _bot is None or _loop is None:
        return None
    if not _ready.is_set():
        log.debug("Discord bot not yet ready — DM skipped")
        return None

    dir_emoji = "📈" if signal.direction == "BUY" else "📉"
    rr_str = f"{rr:.1f}" if rr is not None else "—"
    strategy = getattr(signal, "strategy", "CTI-v1")

    lines = [
        f"{dir_emoji} **{signal.symbol} — {signal.direction}**",
        f"Strategy: **{strategy}** | Confidence: **{round(signal.confidence * 100)}%**",
        f"Entry: `{signal.entry_price}` | SL: `{signal.stop_loss}` | TP: `{signal.take_profit}`",
        f"Lot: `{signal.lot_size}` | ATR: `{round(signal.atr, 5)}` | R:R: `{rr_str}`",
    ]

    future = asyncio.run_coroutine_threadsafe(
        _bot._dm_user("\n".join(lines)),
        _loop,
    )
    try:
        return future.result(timeout=10)
    except Exception as e:
        log.error("Failed to send signal DM: %s", e)
        return None


def send_dm(content: str) -> bool:
    """Send a plain text DM (no grade buttons). Thread-safe.

    Used for watchlist updates, tier changes, and status messages.
    Returns True if sent successfully.
    """
    if not _DISCORD_AVAILABLE or _bot is None or _loop is None:
        return False
    if not _ready.is_set():
        log.debug("Discord bot not yet ready — DM skipped")
        return False
    future = asyncio.run_coroutine_threadsafe(_bot._dm_plain(content), _loop)
    try:
        future.result(timeout=10)
        return True
    except Exception as e:
        log.error("Failed to send plain DM: %s", e)
        return False
