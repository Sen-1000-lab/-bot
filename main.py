import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
from threading import Thread
import json
import os

# ==========================================
# Render Keep Alive
# ==========================================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    Thread(target=run_web).start()

# ==========================================
# TOKEN
# ==========================================

TOKEN = os.getenv("DISCORD_TOKEN")

# ==========================================
# Discord設定
# ==========================================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# ==========================================
# データファイル
# ==========================================

DATA_FILE = "settings.json"

# ==========================================
# データ読み込み
# ==========================================

def load_data():

    if not os.path.exists(DATA_FILE):
        return {}

    with open(DATA_FILE, "r", encoding="utf-8") as f:

        try:
            return json.load(f)

        except:
            return {}

# ==========================================
# データ保存
# ==========================================

def save_data(data):

    with open(DATA_FILE, "w", encoding="utf-8") as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=4
        )

# ==========================================
# コード入力モーダル
# ==========================================

class CodeModal(discord.ui.Modal, title="認証コード入力"):

    code = discord.ui.TextInput(
        label="コードを入力してください",
        placeholder="例: ABC123",
        required=True,
        max_length=100
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        data = load_data()

        guild_id = str(interaction.guild.id)

        # サーバーデータ確認

        if guild_id not in data:

            await interaction.response.send_message(
                "コード設定がありません。",
                ephemeral=True
            )
            return

        codes = data[guild_id].get(
            "codes",
            {}
        )

        input_code = str(self.code.value)

        # コード存在確認

        if input_code not in codes:

            await interaction.response.send_message(
                "コードが違います。",
                ephemeral=True
            )
            return

        role_id = codes[input_code]

        role = interaction.guild.get_role(
            int(role_id)
        )

        # ロール確認

        if role is None:

            await interaction.response.send_message(
                "ロールが見つかりません。",
                ephemeral=True
            )
            return

        member = interaction.user

        # 既に所持

        if role in member.roles:

            await interaction.response.send_message(
                f"既に {role.mention} を持っています。",
                ephemeral=True
            )
            return

        # ロール付与

        try:

            await member.add_roles(role)

            await interaction.response.send_message(
                f"{role.mention} を付与しました！",
                ephemeral=True
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "BOTにロール管理権限がありません。",
                ephemeral=True
            )

        except Exception as e:

            await interaction.response.send_message(
                f"エラー: {e}",
                ephemeral=True
            )

# ==========================================
# ボタンView
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
            CodeModal()
        )

# ==========================================
# 起動時
# ==========================================

@bot.event
async def on_ready():

    print("--------------------")
    print(f"ログイン: {bot.user}")
    print("--------------------")

    try:

        synced = await bot.tree.sync()

        print(
            f"同期コマンド数: {len(synced)}"
        )

    except Exception as e:

        print(e)

    bot.add_view(VerifyView())

# ==========================================
# /パネル
# ==========================================

@bot.tree.command(
    name="パネル",
    description="認証パネルを送信"
)
@app_commands.default_permissions(
    administrator=True
)

async def panel(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="認証パネル",
        description=(
            "下のボタンを押して\n"
            "認証コードを入力してください。"
        ),
        color=discord.Color.blue()
    )

    embed.set_footer(
        text="コード認証システム"
    )

    await interaction.channel.send(
        embed=embed,
        view=VerifyView()
    )

    await interaction.response.send_message(
        "認証パネルを送信しました。",
        ephemeral=True
    )

# ==========================================
# /コード設定
# ==========================================

@bot.tree.command(
    name="コード設定",
    description="コードとロールを設定"
)
@app_commands.default_permissions(
    administrator=True
)

@app_commands.describe(
    code="認証コード",
    role="付与するロール"
)

async def set_code(
    interaction: discord.Interaction,
    code: str,
    role: discord.Role
):

    data = load_data()

    guild_id = str(interaction.guild.id)

    # サーバーデータ作成

    if guild_id not in data:

        data[guild_id] = {
            "codes": {}
        }

    # コード保存

    data[guild_id]["codes"][code] = role.id

    save_data(data)

    await interaction.response.send_message(
        f"✅ コード `{code}` → {role.mention} を設定しました。",
        ephemeral=True
    )

# ==========================================
# /コード削除
# ==========================================

@bot.tree.command(
    name="コード削除",
    description="コード設定を削除"
)
@app_commands.default_permissions(
    administrator=True
)

@app_commands.describe(
    code="削除するコード"
)

async def delete_code(
    interaction: discord.Interaction,
    code: str
):

    data = load_data()

    guild_id = str(interaction.guild.id)

    if guild_id not in data:

        await interaction.response.send_message(
            "設定がありません。",
            ephemeral=True
        )
        return

    codes = data[guild_id].get(
        "codes",
        {}
    )

    if code not in codes:

        await interaction.response.send_message(
            "そのコードは存在しません。",
            ephemeral=True
        )
        return

    del codes[code]

    save_data(data)

    await interaction.response.send_message(
        f"🗑️ `{code}` を削除しました。",
        ephemeral=True
    )

# ==========================================
# /コード一覧
# ==========================================

@bot.tree.command(
    name="コード一覧",
    description="登録コード一覧"
)
@app_commands.default_permissions(
    administrator=True
)

async def list_codes(
    interaction: discord.Interaction
):

    data = load_data()

    guild_id = str(interaction.guild.id)

    if guild_id not in data:

        await interaction.response.send_message(
            "コード設定がありません。",
            ephemeral=True
        )
        return

    codes = data[guild_id].get(
        "codes",
        {}
    )

    if not codes:

        await interaction.response.send_message(
            "コードが登録されていません。",
            ephemeral=True
        )
        return

    description = ""

    for code, role_id in codes.items():

        role = interaction.guild.get_role(
            int(role_id)
        )

        if role:

            description += (
                f"`{code}` → {role.mention}\n"
            )

    embed = discord.Embed(
        title="コード一覧",
        description=description,
        color=discord.Color.green()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )

# ==========================================
# 起動
# ==========================================

if __name__ == "__main__":

    keep_alive()

    bot.run(TOKEN)
