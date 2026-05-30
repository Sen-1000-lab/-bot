import discord
from discord.ext import commands, tasks
from discord import app_commands
from flask import Flask
from threading import Thread
import aiohttp
import json
import os

# ==========================================
# Flask / Render
# ==========================================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is Alive"

def run_web():

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        use_reloader=False
    )

def keep_alive():

    Thread(
        target=run_web,
        daemon=True
    ).start()

# ==========================================
# Token
# ==========================================

TOKEN = os.getenv(
    "DISCORD_TOKEN"
)

if not TOKEN:

    raise ValueError(
        "DISCORD_TOKEN が設定されていません"
    )

# ==========================================
# Discord
# ==========================================

intents = discord.Intents.default()

intents.guilds = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# ==========================================
# Data
# ==========================================

DATA_FILE = "settings.json"

def load_data():

    if not os.path.exists(
        DATA_FILE
    ):

        with open(
            DATA_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                {},
                f,
                ensure_ascii=False,
                indent=4
            )

    try:

        with open(
            DATA_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except:

        return {}

def save_data(data):

    with open(
        DATA_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=4
        )

# ==========================================
# Guild Data
# ==========================================

def ensure_guild_data(
    data,
    guild_id
):

    if guild_id not in data:

        data[guild_id] = {

            "codes": {},

            "scores": {},

            "log_channel": None
        }

    if "codes" not in data[guild_id]:

        data[guild_id]["codes"] = {}

    if "scores" not in data[guild_id]:

        data[guild_id]["scores"] = {}

    if "log_channel" not in data[guild_id]:

        data[guild_id]["log_channel"] = None

# ==========================================
# Logs
# ==========================================

async def send_log(
    guild,
    message
):

    data = load_data()

    guild_id = str(
        guild.id
    )

    if guild_id not in data:
        return

    channel_id = data[guild_id].get(
        "log_channel"
    )

    if not channel_id:
        return

    channel = guild.get_channel(
        int(channel_id)
    )

    if channel:

        try:

            await channel.send(
                message
            )

        except:
            pass

# ==========================================
# Render Self Ping
# ==========================================

@tasks.loop(minutes=5)
async def render_ping():

    try:

        url = os.getenv(
            "RENDER_EXTERNAL_URL"
        )

        if not url:
            return

        async with aiohttp.ClientSession() as session:

            async with session.get(
                url,
                timeout=30
            ) as response:

                print(
                    f"[KEEPALIVE] {response.status}"
                )

    except Exception as e:

        print(
            f"[KEEPALIVE ERROR] {e}"
        )

# ==========================================
# Verify Modal
# ==========================================

class VerifyModal(
    discord.ui.Modal,
    title="認証コード入力"
):

    code = discord.ui.TextInput(
        label="コード",
        placeholder="コードを入力",
        required=True,
        max_length=100
    )
