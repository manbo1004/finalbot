import discord
from discord.ext import commands, tasks
import json
import os
from datetime import datetime, timedelta
import random

# 현재 파일의 디렉토리 경로를 기준으로 data.json 경로 지정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data.json')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

user_data = load_data()

@bot.event
async def on_ready():
    print(f'✅ 봇 실행됨: {bot.user.name}')
    reset_attendance.start()

@tasks.loop(minutes=1)
async def reset_attendance():
    now = datetime.utcnow() + timedelta(hours=9)  # 한국시간
    if now.hour == 0 and now.minute == 0:
        for uid in user_data:
            user_data[uid]["attended"] = False
        save_data(user_data)
        print("🕛 자정 출석 초기화 완료")

def get_user_data(user):
    uid = str(user.id)
    if uid not in user_data:
        user_data[uid] = {"points": 0, "attended": False}
    return user_data[uid]

@bot.command()
async def 출석(ctx):
    user = get_user_data(ctx.author)
    if user.get("attended", False):
        await ctx.send("이미 오늘 출석하셨습니다!")
        return
    user["points"] += 100
    user["attended"] = True
    save_data(user_data)
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
    save_data(user_data)
    await ctx.send(f"{member.display_name}님께 💸 {amount}포인트를 지급했습니다!")

@bot.command()
async def 랭킹(ctx):
    sorted_users = sorted(user_data.items(), key=lambda x: x[1]["points"], reverse=True)
    result = []
    for i, (uid, data) in enumerate(sorted_users[:10], start=1):
        member = ctx.guild.get_member(int(uid))
        name = member.display_name if member else f"탈퇴자({uid})"
        result.append(f"{i}위 🏆 {name} - {data['points']}P")
    await ctx.send("🏅 포인트 랭킹\n" + "\n".join(result))

@bot.command()
async def 상점(ctx):
    await ctx.send(
        "**🎁 포인트 상점**\n"
        "🍗 치킨 기프티콘 - 30,000P (!구매 치킨)\n"
        "💰 500만 메소 - 30,000P (!구매 메소)\n"
        "🍕 피자 - 45,000P (!구매 피자)\n"
        "🐷 족발 - 60,000P (!구매 족발)\n"
        "📛 길드 명찰 - 10,000P (!구매 명찰)"
    )

@bot.command()
async def 구매(ctx, 항목):
    가격표 = {
        "치킨": 30000, "메소": 30000,
        "피자": 45000, "족발": 60000,
        "명찰": 10000
    }
    항목 = 항목.strip()
    if 항목 not in 가격표:
        await ctx.send("존재하지 않는 상품입니다!")
        return
    user = get_user_data(ctx.author)
    가격 = 가격표[항목]
    if user['points'] < 가격:
        await ctx.send("포인트가 부족합니다!")
        return
    user['points'] -= 가격
    save_data(user_data)
    await ctx.send(f"{ctx.author.display_name}님이 {항목}을(를) 구매했습니다! 🎉")

@bot.command()
async def 슬롯(ctx, 금액: int):
    user = get_user_data(ctx.author)
    if 금액 <= 0 or user["points"] < 금액:
        await ctx.send("❌ 잘못된 금액이거나 포인트가 부족합니다.")
        return
    symbols = ['🍒', '🍋', '🔔', '🍀', '💎']
    result = [random.choice(symbols) for _ in range(3)]
    await ctx.send(f"{' | '.join(result)}")
    if result.count(result[0]) == 3:
        배수 = 7
        winnings = 금액 * 배수
        user["points"] += winnings
        await ctx.send(f"🎰 JACKPOT! {배수}배 당첨! +{winnings}P")
    else:
        user["points"] -= 금액
        await ctx.send(f"😭 꽝! -{금액}P")
    save_data(user_data)

@bot.command()
async def 홀짝(ctx, 선택, 금액: int):
    if 선택 not in ['홀', '짝']:
        await ctx.send("홀 또는 짝만 선택 가능!")
        return
    user = get_user_data(ctx.author)
    if 금액 <= 0 or user['points'] < 금액:
        await ctx.send("포인트가 부족하거나 잘못된 금액입니다!")
        return
    결과 = random.choice(['홀', '짝'])
    await ctx.send(f"🎯 결과: {결과}")
    if 선택 == 결과:
        user['points'] += int(금액 * 1.9)
        await ctx.send(f"🎉 정답! +{int(금액 * 1.9)}P")
    else:
        user['points'] -= 금액
        await ctx.send(f"❌ 실패! -{금액}P")
    save_data(user_data)

@bot.command()
async def 주사위(ctx, 선택: int):
    if 선택 < 1 or 선택 > 6:
        await ctx.send("1부터 6 사이의 숫자를 선택하세요!")
        return
    user = get_user_data(ctx.author)
    금액 = 1000
    if user['points'] < 금액:
        await ctx.send("포인트가 부족합니다!")
        return
    결과 = random.randint(1, 6)
    await ctx.send(f"🎲 결과: {결과}")
    if 선택 == 결과:
        user['points'] += 금액 * 5
        await ctx.send(f"🎯 정답! +{금액 * 5}P")
    else:
        user['points'] -= 금액
        await ctx.send(f"❌ 실패! -{금액}P")
    save_data(user_data)

@bot.command()
async def 경마(ctx, 말번호: int, 금액: int):
    if 말번호 not in [1, 2, 3, 4]:
        await ctx.send("1~4번 말 중 선택하세요!")
        return
    user = get_user_data(ctx.author)
    if 금액 <= 0 or user['points'] < 금액:
        await ctx.send("포인트가 부족하거나 잘못된 금액입니다!")
        return
    우승 = random.randint(1, 4)
    await ctx.send(f"🏇 경주 시작! 결과: {우승}번 말 우승!")
    if 말번호 == 우승:
        user['points'] += 금액 * 3
        await ctx.send(f"🎉 승리! +{금액 * 3}P")
    else:
        user['points'] -= 금액
        await ctx.send(f"😭 패배! -{금액}P")
    save_data(user_data)

bot.run(os.getenv("TOKEN"))

