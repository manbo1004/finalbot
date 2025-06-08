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
async def reset_attendance():  # <-- 반드시 async def 이어야 함
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

def biased_outcome():
    return random.random() > 0.51  # True면 유저 승리, False면 봇 승리

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
async def 슬롯(ctx, 금액: int):
    user = get_user_data(ctx.author)
    if 금액 <= 0 or user["points"] < 금액:
        await ctx.send("❌ 잘못된 금액이거나 포인트가 부족합니다.")
        return

    # 봇이 이길 확률 설정: 55% 확률로 꽝
    if random.random() < 0.55:
        user["points"] -= 금액
        save_data(user_data)
        await ctx.send(f"🍒 | 🍋 | 🔔\n😭 꽝! -{금액}P")
        return

    # 당첨 시 랜덤 3개 심볼 생성 (무조건 일치로 7배 지급)
    symbols = ['🍒', '🍋', '🔔', '🍀', '💎']
    selected = random.choice(symbols)
    result = [selected] * 3
    winnings = 금액 * 7
    user["points"] += winnings
    save_data(user_data)
    await ctx.send(f"{' | '.join(result)}\n🎰 JACKPOT! 7배 당첨! +{winnings}P")


import random

# 유저가 이길 확률: 45% (봇이 이길 확률: 55%)
def biased_outcome():
    return random.random() >= 0.55

@bot.command()
async def 홀짝(ctx, 선택, 금액: int):
    if 선택 not in ['홀', '짝']:
        await ctx.send("홀 또는 짝만 선택 가능!")
        return

    user = get_user_data(ctx.author)
    if 금액 <= 0 or user['points'] < 금액:
        await ctx.send("포인트가 부족하거나 잘못된 금액입니다!")
        return

    승리 = biased_outcome()
    결과 = '짝' if 선택 == '홀' else '홀' if not 승리 else 선택  # 봇이 이길 때 반대값 줌

    await ctx.send(f"🎯 결과: {결과}")

    if 선택 == 결과:
        user['points'] += 금액 * 2
        await ctx.send(f"🎉 정답! +{금액 * 2}P")
    else:
        user['points'] -= 금액
        await ctx.send(f"❌ 실패! -{금액}P")

    save_data(user_data)


import random

# 유저가 이길 확률: 45%, 봇이 이길 확률: 55%
def biased_dice_result(user_choice):
    if random.random() < 0.55:
        # 봇이 이김 → 다른 숫자 반환
        options = [i for i in range(1, 7) if i != user_choice]
        return random.choice(options)
    else:
        # 유저가 이김 → 선택한 숫자 그대로 반환
        return user_choice

@bot.command()
async def 주사위(ctx, 선택: int, 금액: int):
    if 선택 < 1 or 선택 > 6:
        await ctx.send("1부터 6 사이의 숫자를 선택하세요!")
        return

    user = get_user_data(ctx.author)
    if 금액 <= 0 or user['points'] < 금액:
        await ctx.send("포인트가 부족하거나 잘못된 금액입니다!")
        return

    결과 = biased_dice_result(선택)
    await ctx.send(f"🎲 결과: {결과}")

    if 선택 == 결과:
        user['points'] += 금액 * 6
        await ctx.send(f"🎯 정답! +{금액 * 6}P")
    else:
        user['points'] -= 금액
        await ctx.send(f"❌ 실패! -{금액}P")

    save_data(user_data)



import random

# 유저가 이길 확률 45%, 봇이 이길 확률 55%
def biased_horse_result(user_choice):
    if random.random() < 0.55:
        # 봇 승리 → 유저가 선택한 번호를 제외한 말 중에서 무작위 선택
        options = [i for i in range(1, 5) if i != user_choice]
        return random.choice(options)
    else:
        # 유저 승리 → 유저가 선택한 말 우승
        return user_choice

@bot.command()
async def 경마(ctx, 말번호: int, 금액: int):
    if 말번호 not in [1, 2, 3, 4]:
        await ctx.send("1~4번 말 중 하나를 선택하세요!")
        return

    user = get_user_data(ctx.author)
    if 금액 <= 0 or user['points'] < 금액:
        await ctx.send("포인트가 부족하거나 잘못된 금액입니다!")
        return

    우승 = biased_horse_result(말번호)
    await ctx.send(f"🏇 경주 시작! 결과: {우승}번 말이 우승했습니다!")

    if 말번호 == 우승:
        user['points'] += 금액 * 4
        await ctx.send(f"🎉 승리! +{금액 * 4}P")
    else:
        user['points'] -= 금액
        await ctx.send(f"😭 패배! -{금액}P")

    save_data(user_data)


# 디스코드 토큰 실행 (환경변수 TOKEN에서 불러오기)
bot.run(os.getenv("TOKEN"))

