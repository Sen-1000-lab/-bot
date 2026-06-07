# ==================================================
# 【最重要】Python 3.13 / 3.14 音声バグ強制回避対策（最上部に配置）
# ==================================================
import sys
import types

try:
    import audioop
except ModuleNotFoundError:
    # discord.pyが読み込まれる前にダミーのaudioopをシステムに登録する
    dummy_audioop = types.ModuleType("audioop")
    sys.modules["audioop"] = dummy_audioop

# ==================================================
# 必要なライブラリのインポート
# ==================================================
import discord
from discord.ext import commands, tasks
from discord import app_commands

from flask import Flask
from threading import Thread
import aiohttp
import json
import os

# ==================================================
# Flask KeepAlive
# ==================================================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is Alive"

def run_web():
    try:
        port = int(os.environ.get("PORT", 10000))
        app.run(host="0.0.0.0", port=port, use_reloader=False)
    except Exception as e:
        print(f"Web server failed: {e}", file=sys.stderr)

def keep_alive():
    Thread(target=run_web, daemon=True).start()

# ==================================================
# CONFIG & DATA MANAGEMENT
# ==================================================
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("DISCORD_TOKEN is missing!", file=sys.stderr)
    sys.exit(1)

RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")
DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Load failed: {e}", file=sys.stderr)
        return {}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Save failed: {e}", file=sys.stderr)

def ensure_guild(data, guild_id):
    gid = str(guild_id)
    if gid not in data:
        data[gid] = {"codes": {}, "scores": {}, "log_channel": None}
    data[gid].setdefault("codes", {})
    data[gid].setdefault("scores", {})
    data[gid].setdefault("log_channel", None)

async def send_log(guild, text):
    data = load_data()
    gid = str(guild.id)
    if gid not in data:
        return
    channel_id = data[gid].get("log_channel")
    if not channel_id:
        return
    channel = guild.get_channel(int(channel_id))
    if channel:
        try:
            await channel.send(text)
        except:
            pass

    async def on_submit(self, interaction: discord.Interaction):
        data = load_data()
        gid = str(interaction.guild.id)
        ensure_guild(data, gid)
        codes = data[gid]["codes"]

        if self.code.value not in codes:
            await interaction.response.send_message("コード違い", ephemeral=True)
            return

        # コードに対応するロールを取得（権限を変更する対象のロールとして使用）
        role = interaction.guild.get_role(int(codes[self.code.value]))
        if not role:
            await interaction.response.send_message("ロールなし", ephemeral=True)
            return

        try:
            # 【変更】ロール付与（add_roles）は行わず、カテゴリー権限の変更のみ実行
            category_perms = data[gid].get("category_perms", {})
            perm_log_text = ""
            
            for cat_id_str, view_permission in category_perms.items():
                category = interaction.guild.get_channel(int(cat_id_str))
                if isinstance(category, discord.CategoryChannel):
                    # view_permissionがTrueなら表示(許可)、Falseなら非表示(禁止)
                    overwrite = discord.PermissionOverwrite(
                        read_messages=view_permission, 
                        send_messages=view_permission
                    )
                    # 対象のロールに対してカテゴリーの権限を上書き
                    await category.set_permissions(role, overwrite=overwrite)
                    action_name = "表示・送信許可" if view_permission else "非表示"
                    perm_log_text += f"\n- カテゴリー「{category.name}」を【{action_name}】に設定"

            await interaction.response.send_message("認証完了（カテゴリー権限を更新しました）", ephemeral=True)
            await send_log(interaction.guild, f"認証コード適用: {interaction.user} がコードを使用して「{role.name}」向けのカテゴリー権限を更新しました。{perm_log_text}")
        except discord.Forbidden:
            await interaction.response.send_message("権限なし: Botのロール順位を上げて再試行してください", ephemeral=True)

# ==================================================
# カテゴリーごとの権限設定用コマンド群（新規追加）
# ==================================================
@bot.tree.command(name="カテゴリー権限設定", description="認証成功時に自動変更するカテゴリーの権限を設定します")
@app_commands.check(is_admin)
@app_commands.describe(category="設定したいカテゴリーチャンネル", view_permission="認証した人にこのカテゴリーを見せる(True)か、隠す(False)か")
async def set_category_permission(interaction: discord.Interaction, category: discord.CategoryChannel, view_permission: bool):
    data = load_data()
    gid = str(interaction.guild.id)
    ensure_guild(data, gid)

    data[gid]["category_perms"][str(category.id)] = view_permission
    save_data(data)

    action_text = "表示（許可）" if view_permission else "非表示（禁止）"
    await interaction.response.send_message(
        f"カテゴリー「{category.name}」を、認証成功時に【{action_text}】にするよう設定しました。", 
        ephemeral=True
    )

@bot.tree.command(name="カテゴリー権限一覧", description="現在登録されているカテゴリー自動権限設定の一覧を表示します")
@app_commands.check(is_admin)
async def list_category_permissions(interaction: discord.Interaction):
    data = load_data()
    gid = str(interaction.guild.id)
    ensure_guild(data, gid)
    
    cat_perms = data[gid].get("category_perms", {})
    if not cat_perms:
        await interaction.response.send_message("設定されているカテゴリー権限はありません。", ephemeral=True)
        return
        
    text = "【認証時のカテゴリー権限設定一覧】\n"
    for cat_id_str, view_perm in cat_perms.items():
        category = interaction.guild.get_channel(int(cat_id_str))
        cat_name = category.name if category else f"削除されたカテゴリー(ID:{cat_id_str})"
        status = "🟢 表示許可" if view_perm else "🔴 非表示"
        text += f"・{cat_name}: {status}\n"
        
    await interaction.response.send_message(text, ephemeral=True)

@bot.tree.command(name="カテゴリー権限削除", description="カテゴリーの自動権限設定を解除します")
@app_commands.check(is_admin)
@app_commands.describe(category="設定を削除したいカテゴリーチャンネル")
async def delete_category_permission(interaction: discord.Interaction, category: discord.CategoryChannel):
    data = load_data()
    gid = str(interaction.guild.id)
    ensure_guild(data, gid)
    
    cat_perms = data[gid].get("category_perms", {})
    if str(category.id) in cat_perms:
        del data[gid]["category_perms"][str(category.id)]
        save_data(data)
        await interaction.response.send_message(f"カテゴリー「{category.name}」の設定を削除しました。", ephemeral=True)
    else:
        await interaction.response.send_message("このカテゴリーには設定が登録されていません。", ephemeral=True)

# ==================================================
# VERIFY MODAL & VIEW
# ==================================================
class VerifyModal(discord.ui.Modal, title="認証コード入力"):
    code = discord.ui.TextInput(label="コード", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        data = load_data()
        gid = str(interaction.guild.id)
        ensure_guild(data, gid)
        codes = data[gid]["codes"]

        if self.code.value not in codes:
            await interaction.response.send_message("コード違い", ephemeral=True)
            return

        role = interaction.guild.get_role(int(codes[self.code.value]))
        if not role:
            await interaction.response.send_message("ロールなし", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.response.send_message("既に認証済み", ephemeral=True)
            return

        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("認証完了", ephemeral=True)
            await send_log(interaction.guild, f"認証: {interaction.user} から {role.name}")
        except discord.Forbidden:
            await interaction.response.send_message("権限なし: Botのロール順位を上げて再試行してください", ephemeral=True)

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="認証", style=discord.ButtonStyle.green, custom_id="persistent_verify_btn")
    async def btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VerifyModal())

# ==================================================
# BOT SETUP
# ==================================================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True 

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    try:
        bot.add_view(VerifyView())
        await bot.tree.sync()
        if not render_ping.is_running():
            render_ping.start()
        print(f"Logged in successfully as {bot.user}")
    except Exception as e:
        print(f"on_ready failed: {e}", file=sys.stderr)

@tasks.loop(minutes=5)
async def render_ping():
    if not RENDER_URL:
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(RENDER_URL, timeout=20):
                pass
    except:
        pass

def is_admin(interaction: discord.Interaction):
    return interaction.user.guild_permissions.administrator

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("このコマンドは管理者のみ実行できます", ephemeral=True)
    else:
        await interaction.response.send_message("エラーが発生しました", ephemeral=True)

# ==================================================
# COMMANDS
# ==================================================
@bot.tree.command(name="ログ設定")
@app_commands.check(is_admin)
async def set_log_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    data = load_data()
    gid = str(interaction.guild.id)
    ensure_guild(data, gid)
    data[gid]["log_channel"] = str(channel.id)
    save_data(data)
    await interaction.response.send_message(f"ログ送信先を {channel.mention} に設定しました", ephemeral=True)

@bot.tree.command(name="認証確認")
async def check_my_roles(interaction: discord.Interaction):
    data = load_data()
    gid = str(interaction.guild.id)
    ensure_guild(data, gid)
    codes = data[gid].get("codes", {})
    user_roles = interaction.user.roles
    verified_roles = []

    for code, role_id in codes.items():
        role = interaction.guild.get_role(int(role_id))
        if role and role in user_roles:
            verified_roles.append(f"コード {code} から {role.mention}")

    if verified_roles:
        text = "あなたが既に認証を完了しているロール一覧です：\n\n" + "\n".join(verified_roles)
    else:
        text = "認証済みのロールは見つかりませんでした。"
    await interaction.response.send_message(text, ephemeral=True)

@bot.tree.command(name="ポイント追加")
@app_commands.check(is_admin)
async def add_point(interaction: discord.Interaction, member: discord.Member, point: int):
    data = load_data()
    gid = str(interaction.guild.id)
    ensure_guild(data, gid)
    scores = data[gid]["scores"]
    uid = str(member.id)
    scores[uid] = scores.get(uid, 0) + point
    save_data(data)
    await interaction.response.send_message(f"{member.mention} に +{point}pt 付与しました", ephemeral=True)

@bot.tree.command(name="ポイント確認")
async def my_point(interaction: discord.Interaction):
    data = load_data()
    gid = str(interaction.guild.id)
    ensure_guild(data, gid)
    score = data[gid]["scores"].get(str(interaction.user.id), 0)
    await interaction.response.send_message(f"あなた: {score}pt", ephemeral=True)

@bot.tree.command(name="スコアボード")
async def scoreboard(interaction: discord.Interaction):
    data = load_data()
    gid = str(interaction.guild.id)
    ensure_guild(data, gid)
    scores = data[gid]["scores"]
    ranking = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    text = ""
    rank = 1

    for uid, pt in ranking:
        if pt <= 0:
            continue
        member = interaction.guild.get_member(int(uid))
        if not member or member.bot:
            continue
        text += f"{rank}位 {member.mention} - {pt}pt\n"
        rank += 1

    if not text:
        text = "データなし"
    embed = discord.Embed(title="スコアボード", description=text, color=discord.Color.blue())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="全員ポイント追加")
@app_commands.check(is_admin)
async def add_all(interaction: discord.Interaction, point: int):
    data = load_data()
    gid = str(interaction.guild.id)
    ensure_guild(data, gid)

    for m in interaction.guild.members:
        if m.bot:
            continue
        uid = str(m.id)
        data[gid]["scores"][uid] = data[gid]["scores"].get(uid, 0) + point

    save_data(data)
    await interaction.response.send_message(f"全員に {point}pt 追加しました", ephemeral=True)

@bot.tree.command(name="全員リreset")
@app_commands.check(is_admin)
async def reset_all(interaction: discord.Interaction):
    data = load_data()
    gid = str(interaction.guild.id)
    ensure_guild(data, gid)
    data[gid]["scores"] = {}
    save_data(data)
    await interaction.response.send_message("スコアボードをリセットしました", ephemeral=True)

@bot.tree.command(name="パネル")
@app_commands.check(is_admin)
async def panel(interaction: discord.Interaction):
    embed = discord.Embed(title="認証パネル", description="下のボタンを押してコードを入力してください", color=discord.Color.green())
    await interaction.channel.send(embed=embed, view=VerifyView())
    await interaction.response.send_message("パネルを送信しました", ephemeral=True)

@bot.tree.command(name="コード設定")
@app_commands.check(is_admin)
async def set_code(interaction: discord.Interaction, code: str, role: discord.Role):
    data = load_data()
    gid = str(interaction.guild.id)
    ensure_guild(data, gid)
    data[gid]["codes"][code] = str(role.id)
    save_data(data)
    await interaction.response.send_message(f"コード {code} にロール {role.mention} を紐付けました", ephemeral=True)

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
