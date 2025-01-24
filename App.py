import discord
from discord import app_commands
from discord.ext import commands
import json
import os

# 봇 설정
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix='/', intents=intents)

# 데이터 저장 경로
DATA_FILE = "product_links.json"

# 관리자 역할 ID 설정
ADMIN_ROLE_ID = 1321743605496283174  # 관리자 역할 ID로 변경
LOG_CHANNEL_ID = 1332187628682084422  # 로그를 보낼 채널 ID로 변경

# 제품 목록 로드 함수
def load_products():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# 제품 목록 저장 함수
def save_products():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(product_links, f, ensure_ascii=False, indent=4)

# 제품 목록 불러오기
product_links = load_products()

# 지급된 메시지를 추적하는 전역 변수
product_messages = {}  # {user_id: {product_name: message_id}}

@bot.event
async def on_ready():
    await bot.tree.sync()  # 슬래시 명령어 동기화
    print(f'봇이 로그인되었습니다. {bot.user}')

# 권한 체크 데코레이터
def admin_only(interaction: discord.Interaction):
    role_ids = [role.id for role in interaction.user.roles]
    if ADMIN_ROLE_ID in role_ids:
        return True
    return False

# /제품등록 명령어 (관리자 전용)
@bot.tree.command(name="제품등록", description="새로운 제품을 등록합니다. (관리자 전용)")
async def register_product(interaction: discord.Interaction, product_name: str, download_link: str):
    if not admin_only(interaction):
        embed = discord.Embed(
            title="권한 부족",
            description="이 명령어는 관리자만 사용할 수 있습니다.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    product_links[product_name] = download_link
    save_products()
    embed = discord.Embed(
        title="제품 등록 완료",
        description=f"제품 이름: `{product_name}`\n다운로드 링크: {download_link}",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        log_embed = discord.Embed(
            title="제품 등록 로그",
            description=f"🛠️ {interaction.user}님이 `{product_name}` 제품을 등록했습니다.",
            color=discord.Color.blue()
        )
        await log_channel.send(embed=log_embed)

# /제품지급 명령어 (관리자 전용)
@bot.tree.command(name="제품지급", description="특정 유저에게 제품을 지급합니다. (관리자 전용)")
async def give_product(interaction: discord.Interaction, member: discord.Member, product_name: str):
    if not admin_only(interaction):
        embed = discord.Embed(
            title="권한 부족",
            description="이 명령어는 관리자만 사용할 수 있습니다.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    link = product_links.get(product_name)
    if link:
        embed = discord.Embed(
            title=f"'{product_name}' 아이템 지급",
            description=f"아이템 다운로드 링크:\n[여기 클릭]({link})",
            color=discord.Color.blue()
        )
        try:
            sent_message = await member.send(embed=embed)

            # 메시지 정보 저장
            if member.id not in product_messages:
                product_messages[member.id] = {}
            product_messages[member.id][product_name] = sent_message.id

            confirm_embed = discord.Embed(
                title="제품 지급 완료",
                description=f"{member.mention}님에게 '{product_name}' 아이템을 지급했습니다.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=confirm_embed)

        except discord.Forbidden:
            error_embed = discord.Embed(
                title="DM 전송 실패",
                description=f"{member.mention}님에게 DM을 보낼 수 없습니다. DM이 비활성화된 것 같습니다.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed)
    else:
        embed = discord.Embed(
            title="제품 지급 실패",
            description=f"'{product_name}'은(는) 등록되지 않은 제품입니다.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

# /제품목록 명령어 (누구나 사용 가능)
@bot.tree.command(name="제품목록", description="등록된 모든 제품의 목록을 확인합니다.")
async def product_list(interaction: discord.Interaction):
    if product_links:
        embed = discord.Embed(
            title="등록된 제품 목록",
            description="\n".join([f"- `{name}`" for name in product_links.keys()]),
            color=discord.Color.gold()
        )
    else:
        embed = discord.Embed(
            title="등록된 제품 없음",
            description="현재 등록된 제품이 없습니다.",
            color=discord.Color.red()
        )
    await interaction.response.send_message(embed=embed)

# /지급취소 명령어 (관리자 전용)
@bot.tree.command(name="지급취소", description="특정 유저에게 지급된 제품을 취소합니다. (관리자 전용)")
async def cancel_give_product(interaction: discord.Interaction, member: discord.Member, product_name: str):
    if not admin_only(interaction):
        embed = discord.Embed(
            title="권한 부족",
            description="이 명령어는 관리자만 사용할 수 있습니다.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    user_messages = product_messages.get(member.id, {})
    message_id = user_messages.get(product_name)

    if message_id:
        try:
            dm_channel = await member.create_dm()
            message = await dm_channel.fetch_message(message_id)
            await message.delete()  # 메시지 삭제

            # 기록에서 제거
            del user_messages[product_name]
            if not user_messages:
                del product_messages[member.id]

            cancel_embed = discord.Embed(
                title="제품 지급 취소",
                description=f"{member.mention}님에게 지급된 '{product_name}'이(가) 취소되었습니다.",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=cancel_embed)

            dm_embed = discord.Embed(
                title="제품 지급 취소 알림",
                description=f"'{product_name}' 제품의 지급이 취소되었습니다.",
                color=discord.Color.red()
            )
            await member.send(embed=dm_embed)

        except discord.NotFound:
            error_embed = discord.Embed(
                title="메시지 삭제 실패",
                description=f"'{product_name}' 메시지를 찾을 수 없습니다. 이미 삭제되었을 수 있습니다.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed)
    else:
        embed = discord.Embed(
            title="제품 지급 취소 실패",
            description=f"'{product_name}'에 대한 지급 기록이 없습니다.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

# 봇 실행
bot.run('봇 토큰')  # Discord 개발자 포털에서 얻은 토큰 입력
