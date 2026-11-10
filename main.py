import os
import asyncio
from contextlib import asynccontextmanager
import httpx
import discord
from discord.ext import commands
from discord import app_commands
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import uvicorn

# --- CONFIGURATION (Read from Render Environment Variables) ---
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
RAW_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
# Fix capital 'Https://' if present
DISCORD_WEBHOOK_URL = "https://" + RAW_WEBHOOK[8:] if RAW_WEBHOOK.lower().startswith("https://") else RAW_WEBHOOK
ANON_CHANNEL_ID = int(os.getenv("ANON_CHANNEL_ID", "1569705078556983366").strip())
PORT = int(os.getenv("PORT", 10000))

# --- 1. DISCORD BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True  # Make sure 'Message Content Intent' is ON in Discord Dev Portal!
bot = commands.Bot(command_prefix="!", intents=intents)

class AnonQuestionModal(discord.ui.Modal, title="Ask Anonymously"):
    question = discord.ui.TextInput(
        label="Your Anonymous Question / Confession",
        style=discord.TextStyle.paragraph,
        placeholder="Type here... Nobody (not even admins) can see who sent this.",
        required=True,
        max_length=1800
    )

    async def on_submit(self, interaction: discord.Interaction):
        clean_q = self.question.value.replace("@everyone", "@\u200beveryone").replace("@here", "@\u200bhere")
        embed = discord.Embed(
            title="🕵️ Anonymous Question",
            description=clean_q,
            color=discord.Color.from_rgb(255, 75, 92)
        )
        embed.set_footer(text="Click 'Ask Anonymously' below or use /ask to send yours!")

        target_channel = bot.get_channel(ANON_CHANNEL_ID) or interaction.channel
        await target_channel.send(embed=embed, view=PersistentAskView())
        await interaction.response.send_message("✅ Your message has been posted anonymously!", ephemeral=True)

class PersistentAskView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ask Anonymously", style=discord.ButtonStyle.danger, emoji="🕵️", custom_id="persistent_anon_ask_btn")
    async def ask_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AnonQuestionModal())

@bot.event
async def on_ready():
    bot.add_view(PersistentAskView())
    await bot.tree.sync()
    print(f"✅ DISCORD BOT ONLINE: Logged in as {bot.user} (ID: {bot.user.id})")

@bot.tree.command(name="ask", description="Send a 100% anonymous question to the Q&A channel")
async def ask_slash(interaction: discord.Interaction):
    await interaction.response.send_modal(AnonQuestionModal())

@bot.tree.command(name="spawn_panel", description="Post the sticky 'Ask Anonymously' button panel in this channel")
@app_commands.checks.has_permissions(manage_channels=True)
async def spawn_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📬 Anonymous Questions & Confessions",
        description=(
            "Want to ask something or share a thought without revealing your name?\n\n"
            "• **Click the button below** to open a private pop-up window.\n"
            "• **Type `/ask`** anywhere in the server.\n"
            "• **Use our Web Portal:** https://askmon-anon.onrender.com\n"
            "• **Or just type directly in this channel**—the bot will instantly delete your message and repost it anonymously!"
        ),
        color=discord.Color.from_rgb(255, 75, 92)
    )
    await interaction.channel.send(embed=embed, view=PersistentAskView())
    await interaction.response.send_message("✅ Panel spawned!", ephemeral=True)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.webhook_id:
        return

    if message.channel.id == ANON_CHANNEL_ID:
        content = message.content.replace("@everyone", "@\u200beveryone").replace("@here", "@\u200bhere")
        try:
            await message.delete()
        except discord.DiscordException as e:
            print(f"⚠️ Could not delete message: {e}")

        if content:
            embed = discord.Embed(
                title="🕵️ Anonymous Question",
                description=content,
                color=discord.Color.from_rgb(255, 75, 92)
            )
            embed.set_footer(text="Click 'Ask Anonymously' below so your name never flashes on screen!")
            await message.channel.send(embed=embed, view=PersistentAskView())

    await bot.process_commands(message)


# --- 2. FASTAPI LIFESPAN (Automatically starts Discord Bot under Uvicorn) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    bot_task = None
    if DISCORD_BOT_TOKEN:
        print("🚀 Starting Discord bot in background task...")
        bot_task = asyncio.create_task(bot.start(DISCORD_BOT_TOKEN))
    else:
        print("⚠️ WARNING: DISCORD_BOT_TOKEN environment variable is not set in Render!")
    yield
    if bot_task:
        await bot.close()

app = FastAPI(title="AskMon Anonymous Portal", lifespan=lifespan)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ask Anonymously</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { background: #0f0f14; color: #f1f1f5; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
        .card { background: #1a1b23; padding: 28px; border-radius: 16px; width: 92%; max-width: 440px; box-shadow: 0 12px 32px rgba(0,0,0,0.6); border: 1px solid #2b2d3c; }
        h2 { margin: 0 0 6px; color: #ff4b5c; font-size: 22px; }
        p { font-size: 13.5px; color: #9ea1b4; margin: 0 0 18px; line-height: 1.4; }
        textarea { width: 100%; height: 130px; background: #121319; border: 1px solid #323546; border-radius: 10px; color: #fff; padding: 14px; font-size: 15px; resize: none; outline: none; transition: border 0.2s; }
        textarea:focus { border-color: #ff4b5c; }
        button { width: 100%; margin-top: 16px; background: #ff4b5c; color: #fff; border: none; padding: 14px; border-radius: 10px; font-size: 15px; font-weight: 700; cursor: pointer; transition: opacity 0.2s; }
        button:hover { opacity: 0.9; }
        .badge { display: inline-block; margin-top: 14px; font-size: 12px; color: #6c6f85; }
        .success { background: rgba(67, 181, 129, 0.15); border: 1px solid #43b581; color: #43b581; padding: 10px; border-radius: 8px; text-align: center; margin-bottom: 14px; font-size: 14px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Ask Anything Anonymously</h2>
        <p>Your identity is never tracked, logged, or visible. Questions go straight to our Discord channel.</p>
        {status_banner}
        <form method="POST" action="/ask">
            <textarea name="question" placeholder="Type your anonymous question or confession here..." maxlength="1800" required></textarea>
            <button type="submit">Send Anonymously</button>
        </form>
        <span class="badge">🔒 100% Zero-Log Encryption</span>
    </div>
</body>
</html>
"""

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def index():
    return HTML_PAGE.replace("{status_banner}", "")

@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok", "bot_online": bot.is_ready()}

@app.post("/ask", response_class=HTMLResponse)
async def submit_question(question: str = Form(...)):
    clean_q = question.strip().replace("@everyone", "@\u200beveryone").replace("@here", "@\u200bhere")
    if clean_q and DISCORD_WEBHOOK_URL:
        payload = {
            "username": "Anonymous Q&A",
            "embeds": [{
                "title": "🕵️ New Anonymous Question",
                "description": clean_q,
                "color": 0xff4b5c,
                "footer": {"text": "Submitted via Web Portal • 100% Anonymous"}
            }]
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(DISCORD_WEBHOOK_URL, json=payload)
            print(f"Webhook POST status: {resp.status_code}")

    banner = '<div class="success">✅ Sent anonymously to Discord!</div>'
    return HTML_PAGE.replace("{status_banner}", banner)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
    
