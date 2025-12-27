import os
import asyncio
import subprocess
import uuid
import shutil
from pathlib import Path

from telethon import TelegramClient, events, Button

BOT_TOKEN = os.environ["BOT_TOKEN"].strip()
API_ID = int(os.environ["TELEGRAM_API_ID"].strip())
API_HASH = os.environ["TELEGRAM_API_HASH"].strip()
FFMPEG_CONCURRENCY = int(os.environ.get("FFMPEG_CONCURRENCY", "1"))

WORKDIR = Path("/app/work")
WORKDIR.mkdir(parents=True, exist_ok=True)

SESSION_DIR = Path("/app/session")
SESSION_DIR.mkdir(parents=True, exist_ok=True)
SESSION_PATH = str(SESSION_DIR / "bot")

PRESETS = {"144p": 144, "240p": 240, "360p": 360, "480p": 480}
sem = asyncio.Semaphore(FFMPEG_CONCURRENCY)
LAST_MEDIA = {}  # chat_id -> message_id


def ffmpeg_resize(inp: Path, outp: Path, height: int):
    cmd = [
        "ffmpeg", "-y", "-nostdin",
        "-i", str(inp),
        "-vf", f"scale=-2:{height}",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "28",
        "-c:a", "aac",
        "-movflags", "+faststart",
        str(outp),
    ]
    subprocess.check_call(cmd)


async def main():
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)

    @client.on(events.NewMessage(pattern=r"^/start$"))
    async def on_start(event):
        await event.reply(
            "✅ جاهز (MTProto)\n"
            "أرسل فيديو ثم اضغط زر التحويل\n"
            "🚀 هذه النسخة لا تستخدم getFile نهائيًا"
        )

    @client.on(events.NewMessage)
    async def on_media(event):
        if not event.message.media:
            return

        is_video = False
        if getattr(event.message, "video", None):
            is_video = True
        elif getattr(event.message, "document", None):
            mime = getattr(event.message.document, "mime_type", "") or ""
            if "video" in mime:
                is_video = True

        if not is_video:
            return

        LAST_MEDIA[event.chat_id] = event.message.id
        await event.reply(
            "اختر العملية:",
            buttons=[[Button.inline("🔧 تحويل 144/240/360/480", data=b"resize_all")]],
        )

    @client.on(events.CallbackQuery(data=b"resize_all"))
    async def on_resize_all(event):
        chat_id = event.chat_id
        msg_id = LAST_MEDIA.get(chat_id)
        if not msg_id:
            await event.answer("أرسل الفيديو من جديد.", alert=True)
            return

        await event.answer("جاري التحضير...", alert=False)
        await client.send_message(chat_id, "⬇️ جاري تنزيل الملف عبر MTProto...")

        src_msg = await client.get_messages(chat_id, ids=msg_id)
        if not src_msg or not src_msg.media:
            await client.send_message(chat_id, "❌ لم أجد ميديا في الرسالة.")
            return

        job_dir = WORKDIR / uuid.uuid4().hex
        job_dir.mkdir(parents=True, exist_ok=True)

        try:
            input_path = job_dir / "input"
            downloaded = await client.download_media(src_msg, file=str(input_path))
            if not downloaded:
                await client.send_message(chat_id, "❌ فشل تنزيل الملف.")
                return

            input_file = Path(downloaded)
            loop = asyncio.get_running_loop()

            async with sem:
                for label, height in PRESETS.items():
                    outp = job_dir / f"{label}.mp4"
                    await client.send_message(chat_id, f"🔧 تحويل {label}...")

                    try:
                        await loop.run_in_executor(None, ffmpeg_resize, input_file, outp, height)
                        await client.send_file(chat_id, str(outp), caption=f"✅ {label}")
                    except Exception as e:
                        await client.send_message(chat_id, f"❌ فشل {label}: {e}")

            await client.send_message(chat_id, "✅ انتهى التحويل")

        finally:
            shutil.rmtree(job_dir, ignore_errors=True)

    print("✅ MTProto bot is running...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
