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
# ==========================================
# Verify View（ボタン）
# ==========================================

class VerifyView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="認証する",
        style=discord.ButtonStyle.green,
        emoji="✅",
        custom_id="verify_button"
    )
    async def verify_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_modal(
            VerifyModal()
        )

# ==========================================
# Verify 処理（Modalの続き）
# ==========================================

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        data = load_data()

        guild_id = str(interaction.guild.id)

        ensure_guild_data(data, guild_id)

        codes = data[guild_id]["codes"]

        input_code = str(self.code.value)

        if input_code not in codes:

            await interaction.response.send_message(
                "❌ コードが違います",
                ephemeral=True
            )

            return

        role_id = int(codes[input_code])

        role = interaction.guild.get_role(role_id)

        if role is None:

            await interaction.response.send_message(
                "❌ ロールが見つかりません",
                ephemeral=True
            )

            return

        member = interaction.user

        if role in member.roles:

            await interaction.response.send_message(
                "すでに認証済みです",
                ephemeral=True
            )

            return

        try:

            await member.add_roles(role)

            await interaction.response.send_message(
                f"✅ {role.mention} を付与しました",
                ephemeral=True
            )

            await send_log(
                interaction.guild,
                f"✅ 認証成功: {member} → {role.name}"
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ BOTに権限がありません",
                ephemeral=True
            )

# ==========================================
# /パネル
# ==========================================

@bot.tree.command(
    name="パネル",
    description="認証パネル送信"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def panel(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="認証パネル",
        description="下のボタンから認証してください",
        color=discord.Color.blue()
    )

    await interaction.channel.send(
        embed=embed,
        view=VerifyView()
    )

    await interaction.response.send_message(
        "送信しました",
        ephemeral=True
    )

# ==========================================
# /コード設定
# ==========================================

@bot.tree.command(
    name="コード設定"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def set_code(
    interaction: discord.Interaction,
    code: str,
    role: discord.Role
):

    data = load_data()

    guild_id = str(interaction.guild.id)

    ensure_guild_data(data, guild_id)

    data[guild_id]["codes"][code] = role.id

    save_data(data)

    await interaction.response.send_message(
        f"✅ {code} → {role.mention}",
        ephemeral=True
    )

# ==========================================
# /コード削除
# ==========================================

@bot.tree.command(
    name="コード削除"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def delete_code(
    interaction: discord.Interaction,
    code: str
):

    data = load_data()

    guild_id = str(interaction.guild.id)

    ensure_guild_data(data, guild_id)

    if code in data[guild_id]["codes"]:

        del data[guild_id]["codes"][code]

        save_data(data)

        await interaction.response.send_message(
            "🗑️ 削除しました",
            ephemeral=True
        )

    else:

        await interaction.response.send_message(
            "❌ コードが存在しません",
            ephemeral=True
        )

# ==========================================
# /コード一覧
# ==========================================

@bot.tree.command(
    name="コード一覧"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def code_list(
    interaction: discord.Interaction
):

    data = load_data()

    guild_id = str(interaction.guild.id)

    codes = data.get(guild_id, {}).get("codes", {})

    text = ""

    for code, role_id in codes.items():

        role = interaction.guild.get_role(role_id)

        if role:
            text += f"{code} → {role.name}\n"

    await interaction.response.send_message(
        text or "なし",
        ephemeral=True
    )
    # ==========================================
# ポイント追加
# ==========================================

@bot.tree.command(
    name="ポイント追加"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def add_point(
    interaction: discord.Interaction,
    member: discord.Member,
    point: int
):

    data = load_data()

    guild_id = str(interaction.guild.id)

    ensure_guild_data(data, guild_id)

    scores = data[guild_id]["scores"]

    user_id = str(member.id)

    scores[user_id] = scores.get(user_id, 0) + point

    save_data(data)

    await interaction.response.send_message(
        f"✅ {member.mention} +{point}pt",
        ephemeral=True
    )

    await send_log(
        interaction.guild,
        f"📈 {member} +{point}pt"
    )

# ==========================================
# ポイント減算
# ==========================================

@bot.tree.command(
    name="ポイント減算"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def remove_point(
    interaction: discord.Interaction,
    member: discord.Member,
    point: int
):

    data = load_data()

    guild_id = str(interaction.guild.id)

    ensure_guild_data(data, guild_id)

    scores = data[guild_id]["scores"]

    user_id = str(member.id)

    scores[user_id] = scores.get(user_id, 0) - point

    save_data(data)

    await interaction.response.send_message(
        f"❌ {member.mention} -{point}pt",
        ephemeral=True
    )

    await send_log(
        interaction.guild,
        f"📉 {member} -{point}pt"
    )

# ==========================================
# ポイント確認
# ==========================================

@bot.tree.command(
    name="ポイント確認"
)
async def my_point(
    interaction: discord.Interaction
):

    data = load_data()

    guild_id = str(interaction.guild.id)

    score = data.get(guild_id, {}).get("scores", {}).get(str(interaction.user.id), 0)

    await interaction.response.send_message(
        f"🏆 あなたのポイント: {score}pt",
        ephemeral=True
    )

# ==========================================
# スコアボード
# ==========================================

@bot.tree.command(
    name="スコアボード"
)
async def scoreboard(
    interaction: discord.Interaction
):

    data = load_data()

    guild_id = str(interaction.guild.id)

    scores = data.get(guild_id, {}).get("scores", {})

    ranking = sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    text = ""

    rank = 1

    for user_id, point in ranking:

        if point <= 0:
            continue

        member = interaction.guild.get_member(int(user_id))

        if member:

            text += f"{rank}位 {member.mention} - {point}pt\n"
            rank += 1

    if text == "":
        text = "まだデータなし"

    embed = discord.Embed(
        title="🏆 スコアボード",
        description=text,
        color=discord.Color.gold()
    )

    await interaction.response.send_message(embed=embed)

# ==========================================
# 全員ポイント追加（BOT除外）
# ==========================================

@bot.tree.command(
    name="全員ポイント追加"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def add_all(
    interaction: discord.Interaction,
    point: int
):

    data = load_data()

    guild_id = str(interaction.guild.id)

    ensure_guild_data(data, guild_id)

    scores = data[guild_id]["scores"]

    for member in interaction.guild.members:

        if member.bot:
            continue

        uid = str(member.id)

        scores[uid] = scores.get(uid, 0) + point

    save_data(data)

    await interaction.response.send_message(
        f"全員に +{point}pt",
        ephemeral=True
    )

# ==========================================
# 全員リセット（BOT除外）
# ==========================================

@bot.tree.command(
    name="全員リセット"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def reset_all(
    interaction: discord.Interaction
):

    data = load_data()

    guild_id = str(interaction.guild.id)

    ensure_guild_data(data, guild_id)

    data[guild_id]["scores"] = {}

    save_data(data)

    await interaction.response.send_message(
        "全員リセット完了",
        ephemeral=True
    )

# ==========================================
# ログチャンネル設定
# ==========================================

@bot.tree.command(
    name="ログチャンネル"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def set_log(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):

    data = load_data()

    guild_id = str(interaction.guild.id)

    ensure_guild_data(data, guild_id)

    data[guild_id]["log_channel"] = channel.id

    save_data(data)

    await interaction.response.send_message(
        f"ログ → {channel.mention}",
        ephemeral=True
    )

# ==========================================
# 起動処理
# ==========================================

@bot.event
async def on_ready():

    if not render_ping.is_running():
        render_ping.start()

    await bot.tree.sync()

    print(f"✅ {bot.user} 起動完了")

# ==========================================
# 起動
# ==========================================

if __name__ == "__main__":

    keep_alive()

    bot.run(TOKEN)
