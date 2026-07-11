import sys
import types
import os
import json


# Python 3.13 / 3.14 audioop対策
try:
    import audioop
except ModuleNotFoundError:
    audioop = types.ModuleType("audioop")
    sys.modules["audioop"] = audioop


import aiohttp
import discord

from discord.ext import commands, tasks
from discord import app_commands

from flask import Flask
from threading import Thread


# =====================================
# Python 3.13 / 3.14 audioop対策
# =====================================
try:
    import audioop
except ModuleNotFoundError:
    audioop = types.ModuleType("audioop")
    sys.modules["audioop"] = audioop


# =====================================
# Flask Keep Alive
# =====================================
app = Flask(__name__)


@app.route("/")
def home():
    return "Bot is Alive"


def run_web():
    port = int(os.environ.get("PORT", 10000))
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


# =====================================
# Discord設定
# =====================================
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    print("DISCORD_TOKEN がありません")
    sys.exit(1)


RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")

DATA_FILE = "data.json"


# =====================================
# データ管理
# =====================================
def load_data():

    if not os.path.exists(DATA_FILE):
        return {}

    try:
        with open(
            DATA_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)

    except Exception:
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
            indent=2
        )



def ensure_guild(data, guild_id):

    gid = str(guild_id)

    if gid not in data:
        data[gid] = {}

    data[gid].setdefault(
        "codes",
        {}
    )

    data[gid].setdefault(
        "scores",
        {}
    )

    data[gid].setdefault(
        "log_channel",
        None
    )

    data[gid].setdefault(
        "category_perms",
        {}
    )


# =====================================
# Bot本体
# =====================================
intents = discord.Intents.default()

intents.guilds = True
intents.members = True
intents.message_content = True


bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =====================================
# 管理者チェック
# =====================================
def is_admin(interaction):

    return (
        interaction.user.guild_permissions.administrator
    )


# =====================================
# ログ送信
# =====================================
async def send_log(guild, text):

    data = load_data()

    gid = str(guild.id)

    if gid not in data:
        return

    channel_id = data[gid].get(
        "log_channel"
    )

    if not channel_id:
        return


    channel = guild.get_channel(
        int(channel_id)
    )

    if channel:

        try:
            await channel.send(text)

        except:
            pass


# =====================================
# 認証モーダル
# =====================================
class VerifyModal(
    discord.ui.Modal,
    title="認証コード入力"
):

    code = discord.ui.TextInput(
        label="コード",
        required=True
    )


    async def on_submit(
        self,
        interaction
    ):

        data = load_data()

        gid = str(
            interaction.guild.id
        )

        ensure_guild(
            data,
            gid
        )


        codes = data[gid]["codes"]


        if self.code.value not in codes:

            await interaction.response.send_message(
                "コードが違います",
                ephemeral=True
            )

            return
        role = interaction.guild.get_role(
            int(codes[self.code.value])
        )

        if not role:

            await interaction.response.send_message(
                "ロールが見つかりません",
                ephemeral=True
            )

            return


        try:

            await interaction.user.add_roles(
                role
            )


            await interaction.response.send_message(
                "認証完了しました",
                ephemeral=True
            )


            await send_log(
                interaction.guild,
                f"{interaction.user} が認証しました → {role.name}"
            )


        except discord.Forbidden:

            await interaction.response.send_message(
                "Botの権限が不足しています",
                ephemeral=True
            )



# =====================================
# 認証ボタン
# =====================================
class VerifyView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )


    @discord.ui.button(
        label="認証",
        style=discord.ButtonStyle.green,
        custom_id="verify_button"
    )
    async def verify_button(
        self,
        interaction,
        button
    ):

        await interaction.response.send_modal(
            VerifyModal()
        )



# =====================================
# 起動イベント
# =====================================
@bot.event
async def on_ready():

    print(
        f"ログイン成功: {bot.user}"
    )


    bot.add_view(
        VerifyView()
    )


    try:

        await bot.tree.sync()

        print(
            "スラッシュコマンド同期完了"
        )

    except Exception as e:

        print(
            f"同期エラー: {e}"
        )


    if not render_ping.is_running():

        render_ping.start()



# =====================================
# Render Keep Alive
# =====================================
@tasks.loop(minutes=5)
async def render_ping():

    if not RENDER_URL:
        return


    try:

        async with aiohttp.ClientSession() as session:

            await session.get(
                RENDER_URL,
                timeout=20
            )

    except:

        pass



# =====================================
# コマンド
# =====================================

@bot.tree.command(
    name="パネル",
    description="認証パネルを表示"
)
@app_commands.check(is_admin)
async def panel(interaction):

    embed = discord.Embed(
        title="認証パネル",
        description="ボタンを押して認証してください",
        color=discord.Color.green()
    )


    await interaction.channel.send(
        embed=embed,
        view=VerifyView()
    )


    await interaction.response.send_message(
        "送信しました",
        ephemeral=True
    )



@bot.tree.command(
    name="コード設定",
    description="認証コードを設定"
)
@app_commands.check(is_admin)
async def set_code(
    interaction,
    code: str,
    role: discord.Role
):

    data = load_data()

    gid = str(
        interaction.guild.id
    )

    ensure_guild(
        data,
        gid
    )


    data[gid]["codes"][code] = str(
        role.id
    )


    save_data(data)


    await interaction.response.send_message(
        f"{code} → {role.name} を設定しました",
        ephemeral=True
    )



@bot.tree.command(
    name="ログ設定",
    description="ログ送信先を設定"
)
@app_commands.check(is_admin)
async def set_log(
    interaction,
    channel: discord.TextChannel
):

    data = load_data()

    gid = str(
        interaction.guild.id
    )

    ensure_guild(
        data,
        gid
    )


    data[gid]["log_channel"] = str(
        channel.id
    )


    save_data(data)


    await interaction.response.send_message(
        "ログ設定しました",
        ephemeral=True
    )
@bot.tree.command(
    name="認証確認",
    description="自分の認証状態を確認"
)
async def check_role(interaction):

    data = load_data()

    gid = str(
        interaction.guild.id
    )

    ensure_guild(
        data,
        gid
    )


    codes = data[gid]["codes"]

    result = []


    for code, role_id in codes.items():

        role = interaction.guild.get_role(
            int(role_id)
        )


        if role and role in interaction.user.roles:

            result.append(
                f"{code} → {role.name}"
            )


    if result:

        text = "\n".join(result)

    else:

        text = "認証済みロールはありません"



    await interaction.response.send_message(
        text,
        ephemeral=True
    )



@bot.tree.command(
    name="ポイント追加",
    description="ポイントを追加"
)
@app_commands.check(is_admin)
async def add_point(
    interaction,
    member: discord.Member,
    point: int
):

    data = load_data()

    gid = str(
        interaction.guild.id
    )

    ensure_guild(
        data,
        gid
    )


    uid = str(
        member.id
    )


    data[gid]["scores"][uid] = (
        data[gid]["scores"].get(uid, 0)
        + point
    )


    save_data(data)


    await interaction.response.send_message(
        f"{member.mention} に {point}pt 追加しました",
        ephemeral=True
    )



@bot.tree.command(
    name="ポイント確認",
    description="ポイント確認"
)
async def point_check(interaction):

    data = load_data()

    gid = str(
        interaction.guild.id
    )

    ensure_guild(
        data,
        gid
    )


    point = data[gid]["scores"].get(
        str(interaction.user.id),
        0
    )


    await interaction.response.send_message(
        f"{point}pt",
        ephemeral=True
    )



@bot.tree.command(
    name="カテゴリー権限設定",
    description="認証後カテゴリー権限設定"
)
@app_commands.check(is_admin)
async def category_permission(
    interaction,
    category: discord.CategoryChannel,
    view_permission: bool
):

    data = load_data()

    gid = str(
        interaction.guild.id
    )

    ensure_guild(
        data,
        gid
    )


    data[gid]["category_perms"][
        str(category.id)
    ] = view_permission


    save_data(data)


    await interaction.response.send_message(
        "カテゴリー権限を保存しました",
        ephemeral=True
    )



# =====================================
# エラーハンドリング
# =====================================
@bot.tree.error
async def command_error(
    interaction,
    error
):

    if isinstance(
        error,
        app_commands.CheckFailure
    ):

        await interaction.response.send_message(
            "管理者のみ使用できます",
            ephemeral=True
        )

    else:

        print(error)



# =====================================
# 起動
# =====================================
if __name__ == "__main__":

    print("BOT START")

    keep_alive()

    bot.run(TOKEN)
