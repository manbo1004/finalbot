import discord
from discord.ext import commands, tasks
import os
import random
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

# 환경 변수 로딩
load_dotenv()
MONGO_URL = os.getenv("MONGO_URL")
TOKEN = os.getenv("TOKEN")

# MongoDB 연결
client = MongoClient(MONGO_URL)
db = client['discord_bot']
users_col = db['users']

# Discord 봇 설정
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 시간대 설정
KST = timezone(timedelta(hours=9))

# 도박 공통 설정
MAX_BET = 1000
MIN_BET = 100
BET_UNIT = 100
DAILY_EARN_LIMIT = 10000

# 사용자 데이터 관리 함수
def get_user_data(user):
    uid = str(user.id)
    data = users_col.find_one({"_id": uid})
    if not data:
        data = {"_id": uid, "points": 0, "attended": False, "used_coupons": []}
        users_col.insert_one(data)
    return data

def update_user_data(uid, data):
    users_col.update_one({"_id": uid}, {"$set": data}, upsert=True)

# 봇 시작 시 이벤트
@bot.event
async def on_ready():
    print(f'✅ 봇 실행됨: {bot.user.name}')
    reset_attendance.start()

# 자정 출석 초기화
@tasks.loop(minutes=1)
async def reset_attendance():
    now = datetime.utcnow() + timedelta(hours=9)
    if now.hour == 0 and now.minute == 0:
        users_col.update_many({}, {"$set": {"attended": False}})
        print("🕛 자정 출석 초기화 완료")

# 출석 명령어
@bot.command()
async def 출석(ctx):
    user = get_user_data(ctx.author)
    if user.get("attended", False):
        await ctx.send("이미 오늘 출석하셨습니다!")
        return
    user["points"] += 100
    user["attended"] = True
    update_user_data(str(ctx.author.id), user)
    await ctx.send(f"{ctx.author.display_name}님 출석 완료! ⭐ 100포인트 지급!")

# 포인트 확인
@bot.command()
async def 포인트(ctx):
    user = get_user_data(ctx.author)
    await ctx.send(f"{ctx.author.display_name}님의 포인트: 💰 {user['points']}P")

# 포인트 지급
@bot.command()
@commands.has_permissions(administrator=True)
async def 지급(ctx, member: discord.Member, amount: int):
    user = get_user_data(member)
    user['points'] += amount
    update_user_data(str(member.id), user)
    await ctx.send(f"{member.display_name}님께 💸 {amount}포인트를 지급했습니다!")

# 포인트 차감
@bot.command()
@commands.has_permissions(administrator=True)
async def 차감(ctx, member: discord.Member, amount: int):
    user = get_user_data(member)
    if amount <= 0:
        await ctx.send("❌ 차감할 금액은 1 이상이어야 합니다.")
        return
    if user['points'] < amount:
        await ctx.send("⚠️ 해당 유저의 포인트가 부족합니다.")
        return
    user['points'] -= amount
    update_user_data(str(member.id), user)
    await ctx.send(f"🚫 {member.display_name}님의 포인트에서 {amount}P 차감했습니다!")

# 포인트 랭킹
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
        result.append(f"{i}위 🏆 {name} - {user['points']}P")
        i += 1
    await ctx.send("🏅 포인트 랭킹\n" + "\n".join(result))

# 공통 도박 로직 템플릿
async def run_gamble_game(ctx, 금액: int, 승리확률: float, 보상배수: int):
    user = get_user_data(ctx.author)
    today_str = datetime.now(KST).strftime('%Y-%m-%d')
    if user.get('last_earn_date') != today_str:
        user['daily_earnings'] = 0
        user['last_earn_date'] = today_str

    if 금액 < MIN_BET or 금액 > MAX_BET or 금액 % BET_UNIT != 0:
        await ctx.send(f"⚠️ 베팅은 {BET_UNIT}P 단위이며, {MIN_BET}P 이상 {MAX_BET}P 이하만 가능합니다!")
        return

    if user['points'] < 금액:
        await ctx.send("❌ 보유한 포인트가 부족합니다!")
        return

    if user['daily_earnings'] + 금액 > DAILY_EARN_LIMIT:
        await ctx.send(f"⛔ 오늘은 더 이상 수익을 얻을 수 없습니다. (일일 제한 {DAILY_EARN_LIMIT:,}P)")
        return

    user['points'] -= 금액

    if random.random() < 승리확률:
        winnings = 금액 * 보상배수
        user['points'] += winnings
        user['daily_earnings'] += 금액
        await ctx.send(f"🎉 승리! +{금액}P 이득! (총 {winnings}P 반환)")
    else:
        await ctx.send(f"💥 패배... {금액}P 손실!")

    update_user_data(str(ctx.author.id), user)

# 게임 명령어들
@bot.command()
async def 에시게임(ctx, 금액: int):
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

# 쿠폰 기능
@bot.command()
async def 쿠폰(ctx, 쿠폰코드: str):
    user = get_user_data(ctx.author)
    if "used_coupons" not in user:
        user["used_coupons"] = []
    if 쿠폰코드 != "sorryhosu":
        await ctx.send("❌ 존재하지 않는 쿠폰입니다.")
        return
    if "sorryhosu" in user["used_coupons"]:
        await ctx.send("⚠️ 이미 사용한 쿠폰입니다!")
        return
    user["points"] += 500
    user["used_coupons"].append("sorryhosu")
    update_user_data(str(ctx.author.id), user)
    await ctx.send("🎁 쿠폰 적용 완료! 500P 지급되었습니다.")

# 상점 기능
shop_items = {
    "치킨": {"price": 30000, "description": "🍗 치킨 기프티콘"},
    "피자": {"price": 45000, "description": "🍕 피자 기프티콘"},
    "족발": {"price": 60000, "description": "🐷 족발 기프티콘"},
    "메소": {"price": 30000, "description": "💰 500만 메소"},
    "명찰": {"price": 10000, "description": "🏷️ 길드 명찰"},
}

@bot.command()
async def 상점(ctx):
    result = [f"{name} - {item['description']} ({item['price']}P)" for name, item in shop_items.items()]
    await ctx.send("🛒 상점 목록:\n" + "\n".join(result))

@bot.command()
async def 구매(ctx, 아이템명: str):
    아이템 = shop_items.get(아이템명)
    if not 아이템:
        await ctx.send("❌ 존재하지 않는 아이템입니다!")
        return
    user = get_user_data(ctx.author)
    if user['points'] < 아이템['price']:
        await ctx.send("💸 포인트가 부족합니다!")
        return
    user['points'] -= 아이템['price']
    update_user_data(str(ctx.author.id), user)
    await ctx.send(f"🎉 {아이템['description']} 구매 완료! -{아이템['price']}P")

bot.run(TOKEN)

