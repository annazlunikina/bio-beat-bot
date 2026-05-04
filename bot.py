import os
import asyncio
import logging
import subprocess
import static_ffmpeg
static_ffmpeg.add_paths()
from pathlib import Path
import numpy as np
import soundfile as sf
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден! Добавь переменную в Railway.")
BEAT_PATH = Path(__file__).parent / "beat.mp3"
VOICE_VOLUME = 1.0
BEAT_VOLUME = 0.3

def convert_to_wav(input_path, output_path):
    subprocess.run(["ffmpeg", "-y", "-i", input_path, "-ar", "44100", "-ac", "1", output_path], check=True, capture_output=True)

def mix_voice_with_beat(voice_path, output_path):
    voice_wav = voice_path + ".wav"
    beat_wav = str(BEAT_PATH) + ".wav"
    mixed_wav = output_path + ".wav"
    convert_to_wav(voice_path, voice_wav)
    convert_to_wav(str(BEAT_PATH), beat_wav)
    voice, sr = sf.read(voice_wav)
    beat, _ = sf.read(beat_wav)
    voice_len = len(voice)
    if len(beat) < voice_len:
        loops = (voice_len // len(beat)) + 1
        beat = np.tile(beat, loops)
    beat = beat[:voice_len]
    if voice.ndim > 1:
        voice = voice.mean(axis=1)
    if beat.ndim > 1:
        beat = beat.mean(axis=1)
    mixed = voice * VOICE_VOLUME + beat * BEAT_VOLUME
    max_val = np.max(np.abs(mixed))
    if max_val > 1.0:
        mixed = mixed / max_val
    sf.write(mixed_wav, mixed, sr)
    subprocess.run(["ffmpeg", "-y", "-i", mixed_wav, output_path], check=True, capture_output=True)
    for f in [voice_wav, beat_wav, mixed_wav]:
        if os.path.exists(f):
            os.remove(f)

async def handle_voice(update, context):
    user = update.effective_user
    if not BEAT_PATH.exists():
        await update.message.reply_text("❌ Бит не найден. Положи файл beat.mp3 рядом с bot.py")
        return
    await update.message.reply_text("🎤 Принял. Накладываю бит...")
    voice_path = f"/tmp/voice_{user.id}_{update.message.message_id}.ogg"
    output_path = f"/tmp/Биография.mp3"
    try:
        voice_file = await context.bot.get_file(update.message.voice.file_id)
        await voice_file.download_to_drive(voice_path)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, mix_voice_with_beat, voice_path, output_path)
        with open(output_path, "rb") as audio:
            await update.message.reply_audio(audio=audio, caption="Биография у всех разная, а бит один.")
    except Exception as e:
        logger.exception("Ошибка при обработке")
        await update.message.reply_text(f"❌ Ошибка: {e}")
    finally:
        for path in [voice_path, output_path]:
            if os.path.exists(path):
                os.remove(path)

async def handle_other(update, context):
    await update.message.reply_text("🎙 Отправь мне голосовое сообщение — я наложу под него бит Кровостока")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(~filters.VOICE, handle_other))
    logger.info("Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
