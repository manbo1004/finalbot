import discord
from discord.ext import commands, tasks
import os
import random
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

# ===== 환경 변수 =====
load_dotenv()
MONGO_URL = os.getenv("MONGO_URL")
TOKEN = os.getenv("TOKEN")

# ===== MongoDB =====
client = MongoClient(MONGO_URL)
db = client['discord_bot']
users_col = db['users']

# ===== Discord Bot =====
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# ===== 시간대 =====
KST = timezone(timedelta(hours=9))

# ===== 도박 / 포인트 정책 =====
MAX_BET = 1000
MIN_BET = 100
BET_UNIT = 100
DAILY_EARN_LIMIT = 10000

# ===== 유틸 =====
def today_str():
    return datetime.now(KST).strftime('%Y-%m-%d')

def get_user_data(user):
    uid = str(user.id) if hasattr(user, "id") else str(user)
    data = users_col.find_one({"_id": uid})
    if not data:
        data = {
            "_id": uid,
            "points": 0,
            "attended": False,
            "last_attend_date": None,
            "streak": 0,
            "daily_earnings": 0,
            "last_earn_date": None,
            "used_coupons": []
        }
        users_col.insert_one(data)
    return data

def update_user_data(uid, data):
    users_col.update_one({"_id": uid}, {"$set": data}, upsert=True)

# ===== 봇 시작 =====
@bot.event
async def on_ready():
    print(f'✅ 봇 실행됨: {bot.user.name}')
    reset_schedulers.start()

# ===== 자정/주간 스케줄러 =====
@tasks.loop(minutes=1)
async def reset_schedulers():
    now = datetime.now(KST)

    # 매일 00:00 → 출석/일일수익 리셋
    if now.hour == 0 and now.minute == 0:
        users_col.update_many({}, {"$set": {"attended": False, "daily_earnings": 0, "last_earn_date": today_str()}})
        print("🕛 자정 출석/일일수익 초기화 완료")

    # 매주 월요일 00:00 → 열혈팬 주간 보너스 +1000P
    if now.weekday() == 0 and now.hour == 0 and now.minute == 0:
        awarded = 0
        for guild in bot.guilds:
            role = discord.utils.get(guild.roles, name='열혈팬') or discord.utils.get(guild.roles, name='열혈')
            if not role:
                continue
            for member in role.members:
                u = get_user_data(member)
                u['points'] = u.get('points', 0) + 1000
                update_user_data(str(member.id), u)
                awarded += 1
        print(f"🎁 열혈팬 주간 보너스 지급 완료 (+1000P) 대상 수: {awarded}")

# ===== 출석 =====
@bot.command()
async def 출석(ctx):
    user = get_user_data(ctx.author)
    if user.get("attended") and user.get("last_attend_date") == today_str():
        await ctx.send("이미 오늘 출석하셨습니다!")
        return

    last = user.get("last_attend_date")
    streak = user.get("streak", 0)
    yesterday = (datetime.now(KST) - timedelta(days=1)).strftime('%Y-%m-%d')
    if last == yesterday:
        streak += 1
    else:
        streak = 1

    base = 100
    bonus = 0
    if streak % 7 == 0:
        bonus += 500
    if streak % 30 == 0:
        bonus += 3000

    user["points"] = user.get("points", 0) + base + bonus
    user["attended"] = True
    user["last_attend_date"] = today_str()
    user["streak"] = streak
    update_user_data(str(ctx.author.id), user)

    msg = f"{ctx.author.display_name}님 출석 완료! ⭐ +{base}P"
    if bonus:
        msg += f" (연속 보너스 +{bonus}P)"
    await ctx.send(msg)

# ===== 포인트 확인 =====
@bot.command()
async def 포인트(ctx):
    user = get_user_data(ctx.author)
    await ctx.send(f"{ctx.author.display_name}님의 포인트: 💰 {user.get('points',0):,}P")

# ===== 포인트 지급/차감 (관리자) =====
@bot.command()
@commands.has_permissions(administrator=True)
async def 지급(ctx, member: discord.Member, amount: int):
    user = get_user_data(member)
    user['points'] = user.get('points', 0) + amount
    update_user_data(str(member.id), user)
    await ctx.send(f"{member.display_name}님께 💸 {amount:,}포인트를 지급했습니다!")

@bot.command()
@commands.has_permissions(administrator=True)
async def 차감(ctx, member: discord.Member, amount: int):
    user = get_user_data(member)
    if amount <= 0:
        await ctx.send("❌ 차감할 금액은 1 이상이어야 합니다.")
        return
    if user.get('points',0) < amount:
        await ctx.send("⚠️ 해당 유저의 포인트가 부족합니다.")
        return
    user['points'] -= amount
    update_user_data(str(member.id), user)
    await ctx.send(f"🚫 {member.display_name}님의 포인트에서 {amount:,}P 차감했습니다!")

# ===== 랭킹 =====
@bot.command()
async def 랭킹(ctx):
    top_users = users_col.find().sort("points", -1).limit(10)
    result = []
    i = 1
    for user in top_users:
        try:
            member_id = int(user['_id'])
            member = await ctx.guild.fetch_member(member_id)
            name = member.display_name
        except:
            continue
        result.append(f"{i}위 🏆 {name} - {user.get('points',0):,}P")
        i += 1
    await ctx.send("🏅 포인트 랭킹\n" + ("\n".join(result) if result else "데이터가 없어요."))

# ===== 도박 공통 로직 =====
async def run_gamble_game(ctx, 금액: int, 승리확률: float, 보상배수: int):
    user = get_user_data(ctx.author)
    today = today_str()
    if user.get('last_earn_date') != today:
        user['daily_earnings'] = 0
        user['last_earn_date'] = today

    if 금액 < MIN_BET or 금액 > MAX_BET or 금액 % BET_UNIT != 0:
        await ctx.send(f"⚠️ 베팅은 {BET_UNIT}P 단위이며, {MIN_BET}P 이상 {MAX_BET}P 이하만 가능합니다!")
        return

    if user.get('points',0) < 금액:
        await ctx.send("❌ 보유한 포인트가 부족합니다!")
        return

    if user.get('daily_earnings',0) + 금액 > DAILY_EARN_LIMIT:
        await ctx.send(f"⛔ 오늘은 더 이상 수익을 얻을 수 없습니다. (일일 제한 {DAILY_EARN_LIMIT:,}P)")
        return

    user['points'] -= 금액

    if random.random() < 승리확률:
        winnings = 금액 * 보상배수
        user['points'] += winnings
        user['daily_earnings'] += 금액
        await ctx.send(f"🎉 승리! +{금액}P 이득! (총 {winnings:,}P 반환)")
    else:
        await ctx.send(f"💥 패배... {금액}P 손실!")

    update_user_data(str(ctx.author.id), user)

# ===== 게임 명령어 =====
@bot.command()
async def 예시게임(ctx, 금액: int):
    await run_gamble_game(ctx, 금액, 승리확률=0.45, 보상배수=2)

@bot.command()
async def 홀짝(ctx, 선택, 금액: int):
    if 선택 not in ['홀', '짝']:
        await ctx.send("⚠️ 홀 또는 짝만 선택 가능!")
        return
    승리 = random.random() < 0.45
    결과 = 선택 if 승리 else ('짝' if 선택 == '홀' else '홀')
    await ctx.send(f"🎲 결과 : {결과}")
    if 선택 == 결과:
        await run_gamble_game(ctx, 금액, 승리확률=1.0, 보상배수=2)
    else:
        await run_gamble_game(ctx, 금액, 승리확률=0.0, 보상배수=2)

@bot.command()
async def 슬롯(ctx, 금액: int):
    symbols = ['🍎', '🍋', '🔔', '🐸', '💎']
    result = [random.choice(symbols) for _ in range(3)]
    await ctx.send(f"{' | '.join(result)}")
    if result[0] == result[1] == result[2] and random.random() < 0.9:
        await run_gamble_game(ctx, 금액, 승리확률=1.0, 보상배수=7)
    else:
        await run_gamble_game(ctx, 금액, 승리확률=0.0, 보상배수=7)

@bot.command()
async def 경마(ctx, 말번호: int, 금액: int):
    if 말번호 not in [1, 2, 3, 4]:
        await ctx.send("⚠️ 1~4번 말 중 선택하세요!")
        return
    win_chance = random.random()
    우승 = 말번호 if win_chance < 0.2375 else random.choice([i for i in [1, 2, 3, 4] if i != 말번호])
    await ctx.send(f"🐎 경주 결과: {우승}번 말 우승!")
    if 말번호 == 우승:
        await run_gamble_game(ctx, 금액, 승리확률=1.0, 보상배수=4)
    else:
        await run_gamble_game(ctx, 금액, 승리확률=0.0, 보상배수=4)

@bot.command()
async def 주사위(ctx, 선택: int, 금액: int):
    if 선택 < 1 or 선택 > 6:
        await ctx.send("⚠️ 1부터 6 사이 숫자 선택!")
        return
    결과 = 선택 if random.random() < (1 / 6) * 0.95 else random.choice([i for i in range(1, 7) if i != 선택])
    await ctx.send(f"🎲 결과: {결과}")
    if 선택 == 결과:
        await run_gamble_game(ctx, 금액, 승리확률=1.0, 보상배수=6)
    else:
        await run_gamble_game(ctx, 금액, 승리확률=0.0, 보상배수=6)

# ===== 쿠폰 =====
@bot.command()
async def 쿠폰(ctx, 쿠폰코드: str):
    user = get_user_data(ctx.author)
    if "used_coupons" not in user:
        user["used_coupons"] = []
    if 쿠폰코드 != "welcomeyachtbro":
        await ctx.send("❌ 존재하지 않는 쿠폰입니다.")
        return
    if "welcomeyachtbro" in user["used_coupons"]:
        await ctx.send("⚠️ 이미 사용한 쿠폰입니다!")
        return
    amount = random.choice(list(range(500, 1001, 100)))  # 500~1000, 100단위
    user["points"] = user.get("points", 0) + amount
    user["used_coupons"].append("welcomeyachtbro")
    update_user_data(str(ctx.author.id), user)
    await ctx.send(f"🎁 쿠폰 적용 완료! {amount:,}P 지급되었습니다.")

# ===== 상점 =====
shop_items = {
    "배민 3만원권": {"price": 30000, "description": "🍽 배민 3만원권 (운영진 수동 지급)"},
    "배민 5만원권": {"price": 50000, "description": "🍽 배민 5만원권 (운영진 수동 지급)"},
    "멤버십 1개월 구독권": {"price": 8000, "description": "🎫 멤버십 1개월 구독권 (운영진 수동 지급)"},
    "방송 시참 우선권": {"price": 25000, "description": "🎙 방송 시참 우선권 (운영진 수동 지급)"},
}

@bot.command()
async def 상점(ctx):
    await ctx.send(
        "🛒 요트형 리워드 상점\n\n"
        "🎁 교환 가능한 보상 목록\n\n"
        "💎 실물 보상\n"
        "- 배민 3만원권 — 30,000P\n"
        "- 배민 5만원권 — 50,000P\n\n"
        "🎙️ 방송 혜택\n"
        "- 멤버십 1개월 구독권 — 8,000P\n"
        "- 방송 시참 우선권 — 25,000P\n\n"
        "포인트 확인: !포인트\n"
        "구매 명령어: 예시) !구매 배민 3만원권"
    )

@bot.command()
async def 구매(ctx, *, 아이템명: str):
    item = shop_items.get(아이템명)
    if not item:
        await ctx.send("❌ 존재하지 않는 아이템입니다! (예: !구매 배민 3만원권)")
        return
    user = get_user_data(ctx.author)
    if user.get('points', 0) < item['price']:
        await ctx.send("💸 포인트가 부족합니다!")
        return
    user['points'] -= item['price']
    update_user_data(str(ctx.author.id), user)
    await ctx.send(
        f"🎉 {ctx.author.display_name}님이 '{아이템명}'을(를) 구매했습니다!\n"
        f"-{item['price']:,}P 차감되었습니다.\n\n"
        "📦 운영진이 확인 후 수동 지급 예정입니다."
    )

# ===== 실행 =====
bot.run(TOKEN)
