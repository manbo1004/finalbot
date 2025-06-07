import discord
from discord.ext import commands
import json
import os
import random
from datetime import datetime, timedelta

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

DATA_FILE = "data.json"

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_user_data(user_id):
    if str(user_id) not in data:
        data[str(user_id)] = {"points": 0, "last_checkin": ""}
    return data[str(user_id)]

@bot.event
async def on_ready():
    print("✅ 요트봇 봇이 정상 작동 중입니다.")

@bot.command()
async def 출석(ctx):
    user_id = str(ctx.author.id)
    now_kst = datetime.utcnow() + timedelta(hours=9)
    today_str = now_kst.strftime("%Y-%m-%d")
    user_data = get_user_data(user_id)

    if user_data["last_checkin"] != today_str:
        user_data["last_checkin"] = today_str
        user_data["points"] += 100
        await ctx.send(f"{ctx.author.display_name}님 출석 완료! +100P")
        save_data()
    else:
        await ctx.send(f"{ctx.author.display_name}님은 이미 출석하셨습니다!")

@bot.command()
async def 포인트(ctx):
    user_data = get_user_data(ctx.author.id)
    await ctx.send(f"{ctx.author.mention}님의 포인트: {user_data['points']}P")

@bot.command()
async def 지급(ctx, member: discord.Member, amount: int):
    if ctx.author.guild_permissions.administrator:
        user_data = get_user_data(member.id)
        user_data["points"] += amount
        save_data()
        await ctx.send(f"{member.display_name}님에게 {amount}P를 지급했습니다.")
    else:
        await ctx.send("이 명령어는 관리자만 사용할 수 있습니다.")

@bot.command()
async def 홀짝(ctx, guess: str, amount: int):
    if guess not in ["홀", "짝"]:
        await ctx.send("홀 또는 짝을 입력하세요.")
        return
    user_data = get_user_data(ctx.author.id)
    if user_data["points"] < amount:
        await ctx.send("포인트가 부족합니다.")
        return
    result = random.choice(["홀", "짝"])
    if guess == result:
        winnings = amount * 2
        user_data["points"] += amount
        await ctx.send(f"결과: {result}! 축하합니다! {amount}P → {winnings}P")
    else:
        user_data["points"] -= amount
        await ctx.send(f"결과: {result}. 아쉽습니다. {amount}P 차감됩니다.")
    save_data()

@bot.command()
async def 경마(ctx, num: int, amount: int):
    if num not in [1, 2, 3, 4]:
        await ctx.send("1~4번 말 중 선택하세요.")
        return
    user_data = get_user_data(ctx.author.id)
    if user_data["points"] < amount:
        await ctx.send("포인트가 부족합니다.")
        return
    winner = random.randint(1, 4)
    if num == winner:
        winnings = amount * 4
        user_data["points"] += winnings - amount
        await ctx.send(f"🏇 {winner}번 말이 우승! +{winnings - amount}P")
    else:
        user_data["points"] -= amount
        await ctx.send(f"🏇 {winner}번 말이 우승. {amount}P 차감됩니다.")
    save_data()

import os
bot.run(os.getenv("TOKEN"))
