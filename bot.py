import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os
import threading
import http.server
import socketserver
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("Токен не найден")

conn = sqlite3.connect("data.db")
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, total INTEGER DEFAULT 0)")
conn.commit()

def get_total(user_id):
    c.execute("SELECT total FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    return row[0] if row else 0

def set_total(user_id, amount):
    c.execute("INSERT OR REPLACE INTO users (user_id, total) VALUES (?, ?)", (user_id, amount))
    conn.commit()

def subtract(user_id, amount_sum):
    total = get_total(user_id)
    new_total = total - amount_sum
    set_total(user_id, new_total)
    return new_total

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Бот {bot.user} запущен!")

@bot.tree.command(name="суммаотбить", description="Установить сумму, которую нужно отбить (ваш личный капитал)")
@app_commands.describe(сумма="Общая сумма для отбития (только цифры)")
async def суммаотбить(interaction: discord.Interaction, сумма: str):
    try:
        val = int(сумма.replace(" ", "").replace(",", "").replace(".", ""))
    except:
        await interaction.response.send_message("❌ Неверный формат. Введите число, например 117108658.", ephemeral=True)
        return
    set_total(interaction.user.id, val)
    await interaction.response.send_message(f"✅ Ваша сумма для отбития установлена: **{val:,}** $")

class TopUpModal(discord.ui.Modal, title="Пополнение отбития"):
    date = discord.ui.TextInput(
        label="📅 Дата",
        placeholder="Например: 05.07",
        required=True,
        max_length=50
    )
    sums = discord.ui.TextInput(
        label="💰 Суммы (через пробел)",
        placeholder="Например: 75000 85500",
        required=True,
        max_length=200
    )

    def __init__(self, proof_url: str):
        super().__init__()
        self.proof_url = proof_url

    async def on_submit(self, interaction: discord.Interaction):
        date = self.date.value
        sums_str = self.sums.value

        parts = sums_str.split()
        amounts = []
        for p in parts:
            try:
                val = int(p.replace(" ", "").replace(",", "").replace(".", ""))
                amounts.append(val)
            except:
                await interaction.response.send_message(
                    f"❌ Некорректное число: `{p}`. Используйте только цифры, разделяйте пробелами.",
                    ephemeral=True
                )
                return

        if not amounts:
            await interaction.response.send_message("❌ Вы не ввели ни одной суммы.", ephemeral=True)
            return

        sum_earned = sum(amounts)
        if sum_earned == 0:
            await interaction.response.send_message("❌ Сумма не может быть равна 0.", ephemeral=True)
            return

        total_before = get_total(interaction.user.id)
        if total_before == 0:
            await interaction.response.send_message("❌ Сначала установите свою сумму для отбития командой `/суммаотбить`.", ephemeral=True)
            return

        new_total = subtract(interaction.user.id, sum_earned)

        embed = discord.Embed(
            title="📋 Пополнение отбития",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="📅 Дата", value=date, inline=False)
        embed.add_field(name="💰 Заработано", value="\n".join(f"+ {a:,}" for a in amounts), inline=False)
        embed.add_field(name="📊 Остаток до вычета", value=f"{total_before:,} $", inline=True)
        embed.add_field(name="💵 Новый остаток", value=f"**{new_total:,}** $", inline=True)
        embed.set_image(url=self.proof_url)
        embed.set_footer(text=f"Выдано: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")

        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="пополнить", description="Пополнить отбитие (обязателен скриншот)")
@app_commands.describe(скриншот="Прикрепите основной скриншот")
async def пополнить(interaction: discord.Interaction, скриншот: discord.Attachment):
    if not скриншот:
        await interaction.response.send_message("❌ Прикрепите скриншот в поле 'Вложение'.", ephemeral=True)
        return
    await interaction.response.send_modal(TopUpModal(скриншот.url))

@bot.tree.command(name="остаток", description="Показать ваш текущий остаток для отбития")
async def остаток(interaction: discord.Interaction):
    total = get_total(interaction.user.id)
    embed = discord.Embed(title="📊 Ваш текущий остаток", description=f"**{total:,}** $", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed)

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("0.0.0.0", port), handler) as httpd:
        print(f"🌐 Веб-сервер запущен на порту {port}")
        httpd.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    bot.run(TOKEN)
