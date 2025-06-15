import discord
from discord.ext import commands, tasks
import os
import random
from datetime import datetime, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
MONGO_URL = os.getenv("MONGO_URL")
TOKEN = os.getenv("TOKEN")

client = MongoClient(MONGO_URL)
db = client['discord_bot']
users_col = db['users']

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 사용자 데이터 로드 및 저장

def get_user_data(user):
    uid = str(user.id)
    data = users_col.find_one({"_id": uid})
    if not data:
        data = {"_id": uid, "points": 0, "attended": False, "used_coupons": []}
        users_col.insert_one(data)
    return data

def update_user_data(uid, data):
    users_col.update_one({"_id": uid}, {"$set": data}, upsert=True)

@bot.event
async def on_ready():
    print(f'✅ 봇 실행됨: {bot.user.name}')
    reset_attendance.start()

@tasks.loop(minutes=1)
async def reset_attendance():
    now = datetime.utcnow() + timedelta(hours=9)
    if now.hour == 0 and now.minute == 0:
        users_col.update_many({}, {"$set": {"attended": False}})
        print("🕛 자정 출석 초기화 완료")

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

@bot.command()
async def 포인트(ctx):
    user = get_user_data(ctx.author)
    await ctx.send(f"{ctx.author.display_name}님의 포인트: 💰 {user['points']}P")

@bot.command()
@commands.has_permissions(administrator=True)
async def 지급(ctx, member: discord.Member, amount: int):
    user = get_user_data(member)
    user['points'] += amount
    update_user_data(str(member.id), user)
    await ctx.send(f"{member.display_name}님께 💸 {amount}포인트를 지급했습니다!")

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


@bot.command()
async def 랭킹(ctx):
    top_users = users_col.find().sort("points", -1).limit(10)
    result = []
    i = 1  # 순위용 수동 인덱스
    for user in top_users:
        try:
            member_id = int(user['_id'])
            member = await ctx.guild.fetch_member(member_id)
            name = member.display_name
        except:
            continue  # 탈퇴자 또는 조회 실패한 유저는 건너뜀
        result.append(f"{i}위 🏆 {name} - {user['points']}P")
        i += 1
    await ctx.send("🏅 포인트 랭킹\n" + "\n".join(result))

from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
today_str = datetime.now(KST).strftime('%Y-%m-%d')

# 일일 수익 초기화
if user.get('last_earn_date') != today_str:
    user['daily_earnings'] = 0
    user['last_earn_date'] = today_str

# 금액 유효성 검사
if 금액 < 100 or 금액 > 1000 or 금액 % 100 != 0:
    await ctx.send("⚠️ 베팅은 100P 단위이며, 100P 이상 1000P 이하만 가능합니다!")
    return

# 수익 제한 확인 (이겼을 경우 수익만큼 제한)
예상_수익 = 금액  # 예: 2배 게임이면 수익만큼
if user['daily_earnings'] + 예상_수익 > 10000:
    await ctx.send("🚫 오늘은 더 이상 수익을 얻을 수 없습니다. (일일 제한 10,000P)")
    return

@bot.command()
async def 홀짝(ctx, 선택, 금액: int):
    if 선택 not in ['홀', '짝']:
        await ctx.send("⚠️ 홀 또는 짝만 선택 가능!")
        return

    if 금액 <= 0 or 금액 > MAX_BET:
        await ctx.send(f"❌ 베팅 금액은 1P 이상 {MAX_BET}P 이하이어야 합니다!")
        return

    user = get_user_data(ctx.author)
    if user['points'] < 금액:
        await ctx.send("⚠️ 포인트가 부족합니다!")
        return

    승리 = random.random() < 0.47
    결과 = '짝' if 선택 == '홀' else '홀' if not 승리 else 선택

    await ctx.send(f"🎯 결과 : {결과}")

    if 선택 == 결과:
        user['points'] += 금액  # 수익만큼만 추가
        await ctx.send(f"✅ 정답! +{금액}P")
    else:
        user['points'] -= 금액
        await ctx.send(f"❌ 실패! (-{금액}P)")

    update_user_data(str(ctx.author.id), user)

@bot.command()
async def 슬롯(ctx, 금액: int):
    if 금액 <= 0 or 금액 > MAX_BET:
        await ctx.send(f"❌ 베팅 금액은 1P 이상 {MAX_BET}P 이하이어야 합니다!")
        return

    user = get_user_data(ctx.author)
    if user["points"] < 금액:
        await ctx.send("⚠️ 포인트가 부족합니다.")
        return

    # 먼저 금액 차감 (이기면 나중에 수익 지급)
    user["points"] -= 금액

    symbols = ['🍎', '🍋', '🔔', '🐸', '💎']
    result = [random.choice(symbols) for _ in range(3)]
    await ctx.send(f"{' | '.join(result)}")

    if result[0] == result[1] == result[2]:
        if random.random() < 0.9:
            배수 = 7
            winnings = 금액 * 배수
            user["points"] += winnings  # 수익만 지급
            await ctx.send(f"🎰 JACKPOT! {배수}배 당첨! +{winnings}P")
        else:
            await ctx.send(f"🥲 아쉽게도 보정 실패! (-{금액}P)")
    else:
        await ctx.send(f"😭 꽝! (-{금액}P)")

    update_user_data(str(ctx.author.id), user)

@bot.command()
async def 경마(ctx, 말번호: int, 금액: int):
    if 말번호 not in [1, 2, 3, 4]:
        await ctx.send("⚠️ 1~4번 말 중 선택하세요!")
        return

    if 금액 <= 0 or 금액 > MAX_BET:
        await ctx.send(f"❌ 베팅 금액은 1P 이상 {MAX_BET}P 이하이어야 합니다!")
        return

    user = get_user_data(ctx.author)
    if user['points'] < 금액:
        await ctx.send("⚠️ 포인트가 부족합니다!")
        return

    # 포인트 먼저 차감
    user['points'] -= 금액

    win_chance = random.random()
    if win_chance < 0.25 * 0.95:
        우승 = 말번호
    else:
        말후보 = [i for i in [1, 2, 3, 4] if i != 말번호]
        우승 = random.choice(말후보)

    await ctx.send(f"🐎 경주 시작! 결과: {우승}번 말 우승!")

    if 말번호 == 우승:
        winnings = 금액 * 4
        user['points'] += winnings
        await ctx.send(f"🏆 승리! +{winnings}P")
    else:
        await ctx.send(f"😭 패배! (-{금액}P)")

    update_user_data(str(ctx.author.id), user)

@bot.command()
async def 주사위(ctx, 선택: int, 금액: int):
    if 선택 < 1 or 선택 > 6:
        await ctx.send("⚠️ 1부터 6 사이의 숫자를 선택하세요!")
        return

    if 금액 <= 0 or 금액 > MAX_BET:
        await ctx.send(f"❌ 베팅 금액은 1P 이상 {MAX_BET}P 이하이어야 합니다!")
        return

    user = get_user_data(ctx.author)
    if user['points'] < 금액:
        await ctx.send("❌ 포인트가 부족합니다!")
        return

    # 포인트 먼저 차감
    user['points'] -= 금액

    win_chance = random.random()
    if win_chance < (1 / 6) * 0.95:
        결과 = 선택
    else:
        후보 = [i for i in range(1, 7) if i != 선택]
        결과 = random.choice(후보)

    await ctx.send(f"🎲 결과: {결과}")

    if 선택 == 결과:
        winnings = 금액 * 6
        user['points'] += winnings
        await ctx.send(f"🎯 정답! +{winnings}P")
    else:
        await ctx.send(f"❌ 실패! -{금액}P")

    update_user_data(str(ctx.author.id), user)

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

# ✅ 상점 기능
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
