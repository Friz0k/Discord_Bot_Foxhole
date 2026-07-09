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

pending_data = {}

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

class RentModal(discord.ui.Modal, title="Пополнение отбития"):
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

        pending_data[interaction.user.id] = {
            "date": date,
            "amounts": amounts,
            "sum_earned": sum_earned,
            "total_before": total_before
        }

        embed = discord.Embed(
            title="📋 Ожидание скриншотов",
            description="Прикрепите 2–5 скриншотов к этому сообщению и нажмите кнопку 'Подтвердить'.",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="📅 Дата", value=date, inline=False)
        embed.add_field(name="💰 Суммы", value="\n".join(f"+ {a:,}" for a in amounts), inline=False)
        embed.add_field(name="📊 Остаток до вычета", value=f"{total_before:,} $", inline=True)
        embed.set_footer(text="Ожидание подтверждения")

        view = discord.ui.View()
        view.add_item(ConfirmButton(interaction.user.id))

        await interaction.response.send_message(embed=embed, view=view)

class ConfirmButton(discord.ui.Button):
    def __init__(self, user_id):
        super().__init__(label="✅ Подтвердить", style=discord.ButtonStyle.green)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Это не ваша заявка.", ephemeral=True)
            return

        data = pending_data.get(interaction.user.id)
        if not data:
            await interaction.response.send_message("❌ Данные не найдены. Попробуйте заново через `/пополнить`.", ephemeral=True)
            return

        attachments = interaction.message.attachments
        if len(attachments) < 2 or len(attachments) > 5:
            await interaction.response.send_message(
                f"❌ Прикрепите от 2 до 5 скриншотов. Сейчас приложено: {len(attachments)}.",
                ephemeral=True
            )
            return

        new_total = subtract(interaction.user.id, data["sum_earned"])

        embed = discord.Embed(
            title="📋 Пополнение отбития",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="📅 Дата", value=data["date"], inline=False)
        embed.add_field(name="💰 Заработано", value="\n".join(f"+ {a:,}" for a in data["amounts"]), inline=False)
        embed.add_field(name="📊 Остаток до вычета", value=f"{data['total_before']:,} $", inline=True)
        embed.add_field(name="💵 Новый остаток", value=f"**{new_total:,}** $", inline=True)
        embed.add_field(name="🖼 Скриншоты", value=f"Приложено файлов: {len(attachments)}", inline=False)
        embed.set_footer(text=f"Выдано: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")

        await interaction.response.edit_message(embed=embed, view=None, content="✅ Заявка подтверждена!")

        pending_data.pop(interaction.user.id, None)

@bot.tree.command(name="пополнить", description="Добавить заработанные суммы (откроется форма)")
async def пополнить(interaction: discord.Interaction):
    await interaction.response.send_modal(RentModal())

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
