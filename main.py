import discord
from discord.ext import commands, tasks
from discord import app_commands

import aiohttp
import json
import os
import random

# ==================================================
# TOKEN
# ==================================================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError("DISCORD_TOKEN が設定されていません")

# ==================================================
# BOT
# ==================================================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

class MyBot(commands.Bot):

    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents
        )
        self.session = None

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        self.render_ping.start()

    async def close(self):
        if self.session:
            await self.session.close()
        await super().close()

bot = MyBot()

# ==================================================
# DATA
# ==================================================

DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==================================================
# Guild init
# ==================================================

def ensure_guild(data, gid):

    if gid not in data:
        data[gid] = {
            "codes": {},
            "scores": {},
            "log_channel": None
        }

    data[gid].setdefault("codes", {})
    data[gid].setdefault("scores", {})
    data[gid].setdefault("log_channel", None)

# ==================================================
# LOG
# ==================================================

async def send_log(guild, msg):

    data = load_data()
    gid = str(guild.id)

    if gid not in data:
        return

    cid = data[gid].get("log_channel")
    if not cid:
        return

    channel = guild.get_channel(int(cid))
    if channel:
        try:
            await channel.send(msg)
        except:
            pass

# ==================================================
# KEEP ALIVE (Render ping only)
# ==================================================

@tasks.loop(minutes=5)
async def render_ping():

    url = os.getenv("RENDER_EXTERNAL_URL")
    if not url:
        return

    try:
        async with bot.session.get(url, timeout=20) as r:
            print("[KEEPALIVE]", r.status)
    except Exception as e:
        print("[KEEPALIVE ERROR]", e)

# ==================================================
# MODAL (FIXED)
# ==================================================

class VerifyModal(discord.ui.Modal, title="認証コード入力"):

    code = discord.ui.TextInput(
        label="コード",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):

        data = load_data()
        gid = str(interaction.guild.id)

        ensure_guild(data, gid)

        codes = data[gid]["codes"]
        input_code = str(self.code.value)

        if input_code not in codes:
            return await interaction.response.send_message(
                "❌ コードが違います",
                ephemeral=True
            )

        role = interaction.guild.get_role(int(codes[input_code]))
        if not role:
            return await interaction.response.send_message(
                "❌ ロールなし",
                ephemeral=True
            )

        if role in interaction.user.roles:
            return await interaction.response.send_message(
                "すでに認証済み",
                ephemeral=True
            )

        await interaction.user.add_roles(role)

        await interaction.response.send_message(
            f"✅ {role.mention} 付与完了",
            ephemeral=True
        )

        await send_log(interaction.guild, f"認証: {interaction.user} → {role.name}")

# ==================================================
# VIEW
# ==================================================

class VerifyView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="認証する",
        style=discord.ButtonStyle.green,
        emoji="✅"
    )
    async def btn(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_modal(VerifyModal())

# ==================================================
# PANEL
# ==================================================

@bot.tree.command(name="パネル")
@app_commands.checks.has_permissions(administrator=True)
async def panel(interaction: discord.Interaction):

    embed = discord.Embed(
        title="認証パネル",
        description="ボタンで認証",
        color=0x3498db
    )

    await interaction.channel.send(embed=embed, view=VerifyView())
    await interaction.response.send_message("送信OK", ephemeral=True)

# ==================================================
# CODE SET
# ==================================================

@bot.tree.command(name="コード設定")
@app_commands.checks.has_permissions(administrator=True)
async def set_code(interaction: discord.Interaction, code: str, role: discord.Role):

    data = load_data()
    gid = str(interaction.guild.id)

    ensure_guild(data, gid)

    data[gid]["codes"][code] = role.id
    save_data(data)

    await interaction.response.send_message(f"OK {code}", ephemeral=True)

# ==================================================
# DELETE CODE
# ==================================================

@bot.tree.command(name="コード削除")
@app_commands.checks.has_permissions(administrator=True)
async def del_code(interaction: discord.Interaction, code: str):

    data = load_data()
    gid = str(interaction.guild.id)

    ensure_guild(data, gid)

    if code in data[gid]["codes"]:
        del data[gid]["codes"][code]
        save_data(data)

        await interaction.response.send_message("削除OK", ephemeral=True)
    else:
        await interaction.response.send_message("なし", ephemeral=True)

# ==================================================
# SCORES
# ==================================================

@bot.tree.command(name="ポイント追加")
@app_commands.checks.has_permissions(administrator=True)
async def add_point(interaction, member: discord.Member, point: int):

    data = load_data()
    gid = str(interaction.guild.id)

    ensure_guild(data, gid)

    uid = str(member.id)

    data[gid]["scores"][uid] = data[gid]["scores"].get(uid, 0) + point

    save_data(data)

    await interaction.response.send_message("追加OK", ephemeral=True)

# --------------------------------------------------

@bot.tree.command(name="ポイント減算")
@app_commands.checks.has_permissions(administrator=True)
async def remove_point(interaction, member: discord.Member, point: int):

    data = load_data()
    gid = str(interaction.guild.id)

    ensure_guild(data, gid)

    uid = str(member.id)

    data[gid]["scores"][uid] = max(
        0,
        data[gid]["scores"].get(uid, 0) - point
    )

    save_data(data)

    await interaction.response.send_message("減算OK", ephemeral=True)

# ==================================================
# SCOREBOARD
# ==================================================

@bot.tree.command(name="スコアボード")
async def scoreboard(interaction: discord.Interaction):

    data = load_data()
    gid = str(interaction.guild.id)

    ensure_guild(data, gid)

    scores = data[gid]["scores"]

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    text = ""

    rank = 1

    for uid, score in sorted_scores:

        if score <= 0:
            continue

        member = interaction.guild.get_member(int(uid))
        if not member:
            continue

        text += f"{rank}位 {member.display_name} - {score}pt\n"
        rank += 1

    await interaction.response.send_message(
        text or "データなし"
    )

# ==================================================
# RESET ALL (FIXED)
# ==================================================

@bot.tree.command(name="全員リセット")
@app_commands.checks.has_permissions(administrator=True)
async def reset_all(interaction: discord.Interaction):

    data = load_data()
    gid = str(interaction.guild.id)

    ensure_guild(data, gid)

    data[gid]["scores"] = {}

    save_data(data)

    await interaction.response.send_message("リセット完了", ephemeral=True)

# ==================================================
# LOG CHANNEL
# ==================================================

@bot.tree.command(name="ログチャンネル")
@app_commands.checks.has_permissions(administrator=True)
async def set_log(interaction: discord.Interaction, channel: discord.TextChannel):

    data = load_data()
    gid = str(interaction.guild.id)

    ensure_guild(data, gid)

    data[gid]["log_channel"] = str(channel.id)

    save_data(data)

    await interaction.response.send_message("ログ設定OK", ephemeral=True)

# ==================================================
# READY
# ==================================================

@bot.event
async def on_ready():

    await bot.tree.sync()

    if not render_ping.is_running():
        render_ping.start()

    print(f"OK {bot.user}")

# ==================================================
# START
# ==================================================

bot.run(TOKEN)
