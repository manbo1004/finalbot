import discord
from discord.ext import commands, tasks
import json
import os
from datetime import datetime, timedelta
import pytz
import random

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

DATA_FILE = 'user_data.json'
KST = pytz.timezone('Asia/Seoul')

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        json.dump({}, f)

def load_data():
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_display_name(ctx, user_id):
    member = ctx.guild.get_member(int(user_id))
    return member.display_name if member else "Unknown"

def get_user_data(user_id):
    data = load_data()
    if str(user_id) not in data:
        data[str(user_id)] = {"points": 0, "last_daily": "1970-01-01"}
        save_data(data)
    return data[str(user_id)]

def update_user_data(user_id, key, value):
    data = load_data()
    if str(user_id) not in data:
        data[str(user_id)] = {"points": 0, "last_daily": "1970-01-01"}
    data[str(user_id)][key] = value
    save_data(data)

@bot.event
async def on_ready():
    print(f'봇 실행됨: {bot.user}')

@bot.command()
async def 출석(ctx):
    user_id = str(ctx.author.id)
    data = load_data()
    now = datetime.now(KST)
    today_str = now.strftime('%Y-%m-%d')
    last_daily_str = data.get(user_id, {}).get("last_daily", "1970-01-01")
    last_daily = datetime.strptime(last_daily_str, '%Y-%m-%d')

    if last_daily.date() == now.date():
        await ctx.send(f"{ctx.author.mention} 이미 출석했습니다!")
    else:
        user_data = get_user_data(user_id)
        user_data["points"] += 1000
        update_user_data(user_id, "points", user_data["points"])
        update_user_data(user_id, "last_daily", today_str)
        await ctx.send(f"{ctx.author.mention} 출석 완료! 1,000포인트 지급되었습니다.")

@bot.command()
async def 포인트(ctx):
    user_data = get_user_data(ctx.author.id)
    await ctx.send(f"{ctx.author.mention} 현재 포인트: {user_data['points']}P")

@bot.command()
async def 지급(ctx, member: discord.Member, amount: int):
    if ctx.author.guild_permissions.administrator:
        user_data = get_user_data(member.id)
        user_data['points'] += amount
        update_user_data(member.id, 'points', user_data['points'])
        await ctx.send(f"{member.mention}에게 {amount}포인트를 지급했습니다.")
    else:
        await ctx.send("관리자만 사용할 수 있는 명령어입니다.")

@bot.command()
async def 랭킹(ctx):
    data = load_data()
    sorted_users = sorted(data.items(), key=lambda x: x[1].get('points', 0), reverse=True)[:10]
    rank_msg = "\n".join([f"{i+1}. {get_display_name(ctx, uid)}: {info['points']}P" for i, (uid, info) in enumerate(sorted_users)])
    await ctx.send(f"🏆 포인트 랭킹 🏆\n{rank_msg}")

@bot.command()
async def 상점(ctx):
    shop_items = {
        "치킨": 30000,
        "500만 메소": 30000,
        "피자": 45000,
        "족발": 60000,
        "길드 명찰": 10000
    }
    msg = "\n".join([f"{item}: {price}P" for item, price in shop_items.items()])
    await ctx.send(f"🛍️ 상점 목록\n{msg}")

@bot.command()
async def 구매(ctx, *, item):
    shop_items = {
        "치킨": 30000,
        "500만 메소": 30000,
        "피자": 45000,
        "족발": 60000,
        "길드 명찰": 10000
    }
    user_data = get_user_data(ctx.author.id)
    if item in shop_items:
        cost = shop_items[item]
        if user_data['points'] >= cost:
            user_data['points'] -= cost
            update_user_data(ctx.author.id, 'points', user_data['points'])
            await ctx.send(f"{ctx.author.mention} {item} 구매 완료! ({cost}P 차감)")
        else:
            await ctx.send(f"{ctx.author.mention} 포인트가 부족합니다. ({user_data['points']}P 보유)")
    else:
        await ctx.send("해당 상품이 없습니다.")

@bot.command()
async def 슬롯(ctx, amount: int):
    symbols = ['🍒', '🍋', '🔔']
    user_data = get_user_data(ctx.author.id)
    if user_data['points'] < amount:
        await ctx.send("포인트가 부족합니다.")
        return
    result = [random.choice(symbols) for _ in range(3)]
    if result.count(result[0]) == 3:
        winnings = amount * 5
        msg = "🎉 잭팟! 5배 당첨!"
    elif len(set(result)) == 2:
        winnings = amount * 2
        msg = "✨ 2배 당첨!"
    else:
        winnings = 0
        msg = "꽝! 다음 기회에..."
    net_change = winnings - amount
    user_data['points'] += net_change
    update_user_data(ctx.author.id, 'points', user_data['points'])
    await ctx.send(f"{' | '.join(result)}\n{msg} 현재 포인트: {user_data['points']}P")

@bot.command()
async def 홀짝(ctx, guess: str, amount: int):
    user_data = get_user_data(ctx.author.id)
    if user_data['points'] < amount:
        await ctx.send("포인트가 부족합니다.")
        return
    result = random.choice(['홀', '짝'])
    if guess == result:
        winnings = amount * 2
        msg = f"정답! {winnings}P 획득"
    else:
        winnings = 0
        msg = f"틀렸습니다! 정답은 {result}"
    net_change = winnings - amount
    user_data['points'] += net_change
    update_user_data(ctx.author.id, 'points', user_data['points'])
    await ctx.send(f"{msg} 현재 포인트: {user_data['points']}P")

@bot.command()
async def 주사위(ctx, guess: int, amount: int):
    if not (1 <= guess <= 6):
        await ctx.send("1~6 사이의 숫자를 입력해주세요.")
        return
    user_data = get_user_data(ctx.author.id)
    if user_data['points'] < amount:
        await ctx.send("포인트가 부족합니다.")
        return
    roll = random.randint(1, 6)
    if guess == roll:
        winnings = amount * 6
        msg = f"🎲 정답! 주사위: {roll}, {winnings}P 획득!"
    else:
        winnings = 0
        msg = f"주사위: {roll}, 꽝!"
    net_change = winnings - amount
    user_data['points'] += net_change
    update_user_data(ctx.author.id, 'points', user_data['points'])
    await ctx.send(f"{msg} 현재 포인트: {user_data['points']}P")

@bot.command()
async def 경마(ctx, horse: int, amount: int):
    if not (1 <= horse <= 4):
        await ctx.send("1~4번 말 중에서 선택해주세요.")
        return
    user_data = get_user_data(ctx.author.id)
    if user_data['points'] < amount:
        await ctx.send("포인트가 부족합니다.")
        return
    winner = random.randint(1, 4)
    if horse == winner:
        winnings = amount * 4
        msg = f"🏇 {winner}번 말 우승! {winnings}P 획득!"
    else:
        winnings = 0
        msg = f"{winner}번 말이 우승했습니다. 꽝!"
    net_change = winnings - amount
    user_data['points'] += net_change
    update_user_data(ctx.author.id, 'points', user_data['points'])
    await ctx.send(f"{msg} 현재 포인트: {user_data['points']}P")

# 환경변수 TOKEN을 이용한 실행
bot.run(os.getenv("TOKEN"))
