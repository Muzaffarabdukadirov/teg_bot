import logging
import os
import csv
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.enums import ParseMode, ContentType
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.filters import Command

# Bot konfiguratsiyasi
BOT_TOKEN = "7383119117:AAFnL4h4B6eF0tzJRLRkWDUVkRf7rdrg1QM"
ADMIN_GROUP_ID = -1002459383963
CSV_FILE = "savollar.csv"
HISOBOT_PAROLI = "menga_savol_ber"  # Hisobot uchun parol

# Log yozish
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Botni ishga tushirish
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# Xotira saqlash
kutilayotgan_savollar = {}  # {gruppa_xabari_id: {foydalanuvchi_id, chat_id, modul, content_type}}
javob_kutayotganlar = {}    # {admin_id: {foydalanuvchi_id, user_chat_id, group_msg_id}}
foydalanuvchi_holati = {}   # {foydalanuvchi_id: {'modul': tanlangan_modul}}

# Modullar
MODULLAR = ["HTML", "CSS", "Bootstrap", "WIX", "JavaScript", "Scratch"]

def csvga_yozish(foydalanuvchi_id, modul, savol, content_type="text"):
    """Savollarni CSV fayliga yozish"""
    sana_vaqt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        # Agar fayl yo'q bo'lsa, yaratib olish
        if not os.path.exists(CSV_FILE):
            with open(CSV_FILE, 'w', newline='', encoding='utf-8') as fayl:
                yozuvchi = csv.writer(fayl)
                yozuvchi.writerow(["foydalanuvchi_id", "modul", "savol", "content_type", "sana_vaqt"])
        
        # Ma'lumotlarni qo'shish
        with open(CSV_FILE, 'a', newline='', encoding='utf-8') as fayl:
            yozuvchi = csv.writer(fayl)
            yozuvchi.writerow([foydalanuvchi_id, modul, savol, content_type, sana_vaqt])
    except Exception as e:
        logger.error(f"CSVga yozishda xato: {e}")

async def forward_to_admin_group(content, modul, foydalanuvchi_id, username):
    """Foydalanuvchi kontentini adminlar guruhiga yuborish"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✉️ Javob berish",
        callback_data=f"javob_{foydalanuvchi_id}_{content.chat.id}"
    )
    builder.adjust(1)
    
    caption = f"❓ Savol ({modul}) @{username or 'foydalanuvchi'} (ID: {foydalanuvchi_id})"
    
    if content.content_type == ContentType.TEXT:
        sent = await bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=f"{caption}:\n\n{content.text}",
            reply_markup=builder.as_markup()
        )
    elif content.content_type == ContentType.PHOTO:
        sent = await bot.send_photo(
            chat_id=ADMIN_GROUP_ID,
            photo=content.photo[-1].file_id,
            caption=f"{caption}:\n\n{content.caption or ''}",
            reply_markup=builder.as_markup()
        )
    elif content.content_type == ContentType.VIDEO:
        sent = await bot.send_video(
            chat_id=ADMIN_GROUP_ID,
            video=content.video.file_id,
            caption=f"{caption}:\n\n{content.caption or ''}",
            reply_markup=builder.as_markup()
        )
    elif content.content_type == ContentType.VOICE:
        sent = await bot.send_voice(
            chat_id=ADMIN_GROUP_ID,
            voice=content.voice.file_id,
            caption=caption,
            reply_markup=builder.as_markup()
        )
    else:
        return None
        
    return sent

@router.message(Command("start"))
async def boshlash(message: types.Message):
    """Boshlash xabari va modul tanlash tugmalari"""
    builder = ReplyKeyboardBuilder()
    for modul in MODULLAR:
        builder.add(types.KeyboardButton(text=modul))
    builder.adjust(2)  # Har qatorda 2 ta tugma
    
    await message.answer(
        "👋 Qo'llab-quvvatlash botiga xush kelibsiz!\n\n"
        "Iltimos, yordam kerak bo'lgan modulni tanlang:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@router.message(F.text.in_(MODULLAR))
async def modul_tanlash(message: types.Message):
    """Modul tanlashni qayta ishlash"""
    foydalanuvchi_id = message.from_user.id
    modul = message.text
    
    foydalanuvchi_holati[foydalanuvchi_id] = {'modul': modul}
    
    await message.answer(
        f"📝 Siz <b>{modul}</b> modulini tanladingiz. Iltimos, savolingizni yuboring (matn, rasm, video yoki ovozli xabar):",
        reply_markup=types.ReplyKeyboardRemove()
    )

@router.message(F.content_type.in_({ContentType.TEXT, ContentType.PHOTO, ContentType.VIDEO, ContentType.VOICE}))
async def foydalanuvchi_savoli(message: types.Message):
    """Foydalanuvchi savolini qabul qilish"""
    if message.chat.type != 'private' or message.from_user.is_bot:
        return
        
    foydalanuvchi_id = message.from_user.id
    foydalanuvchi_holati_ = foydalanuvchi_holati.get(foydalanuvchi_id)
    
    if not foydalanuvchi_holati_ or 'modul' not in foydalanuvchi_holati_:
        await message.answer("Iltimos, avval /start buyrug'i orqali modulni tanlang")
        return
        
    modul = foydalanuvchi_holati_['modul']
    username = message.from_user.username

    try:
        # Adminlarga yuborish
        sent = await forward_to_admin_group(message, modul, foydalanuvchi_id, username)
        
        if not sent:
            await message.answer("❌ Faqat matn, rasm, video yoki ovozli xabarlar qabul qilinadi")
            return

        # Ma'lumotlarni saqlash
        content_text = ""
        if message.content_type == ContentType.TEXT:
            content_text = message.text
        elif message.caption:
            content_text = message.caption
            
        kutilayotgan_savollar[sent.message_id] = {
            "foydalanuvchi_id": foydalanuvchi_id,
            "foydalanuvchi_chat_id": message.chat.id,
            "modul": modul,
            "content_type": message.content_type
        }
        
        csvga_yozish(foydalanuvchi_id, modul, content_text, message.content_type)
        
        await message.answer("✅ Savolingiz support jamoasiga yuborildi!")
        foydalanuvchi_holati.pop(foydalanuvchi_id, None)

    except Exception as e:
        logger.error(f"Savol yuborishda xato: {e}")
        await message.answer("❌ Savolingizni yuborishda xato yuz berdi. Iltimos, qayta urinib ko'ring.")

@router.callback_query(F.data.startswith("javob_"))
async def javob_berish_tugmasi(callback_query: types.CallbackQuery):
    try:
        admin_id = callback_query.from_user.id
        foydalanuvchi_id, foydalanuvchi_chat_id = map(int, callback_query.data.split("_")[1:])

        # Adminlikni tekshirish
        a_zo = await bot.get_chat_member(callback_query.message.chat.id, admin_id)
        if a_zo.status not in ['administrator', 'creator']:
            await callback_query.answer("Faqat adminlar javob berishi mumkin.")
            return

        javob_kutayotganlar[admin_id] = {
            "foydalanuvchi_id": foydalanuvchi_id,
            "foydalanuvchi_chat_id": foydalanuvchi_chat_id,
            "gruppa_xabari_id": callback_query.message.message_id,
            "content_type": kutilayotgan_savollar.get(callback_query.message.message_id, {}).get("content_type", "text")
        }

        # Admin ismini olish
        admin = await bot.get_chat(admin_id)
        admin_ismi = admin.first_name
        if admin.last_name:
            admin_ismi += " " + admin.last_name

        # Original xabarni tahrirlash (admin ismi bilan)
        await callback_query.message.edit_reply_markup(
            reply_markup=InlineKeyboardBuilder()
            .button(text=f"✓ Javob berildi || {admin_ismi}", callback_data="javob_berildi")
            .adjust(1)
            .as_markup()
        )

        await bot.send_message(admin_id, "💬 Iltimos, foydalanuvchiga javobingizni shu xabar orqali yuboring (matn, rasm, video yoki ovozli xabar):")
        await callback_query.answer("Endi foydalanuvchiga javob yozishingiz mumkin")

    except Exception as e:
        logger.error(f"Javob tugmasida xato: {e}")
        await callback_query.answer("Xato yuz berdi.")

@router.message(F.content_type.in_({ContentType.TEXT, ContentType.PHOTO, ContentType.VIDEO, ContentType.VOICE}))
async def admin_javobi(message: types.Message):
    """Admin javobini qayta ishlash"""
    if message.chat.type != 'private' or message.from_user.is_bot:
        return
        
    admin_id = message.from_user.id
    context = javob_kutayotganlar.get(admin_id)
    
    if not context:
        return
        
    try:
        # Foydalanuvchiga javobni yuborish
        if message.content_type == ContentType.TEXT:
            await bot.send_message(
                chat_id=context["foydalanuvchi_chat_id"],
                text=f"📬 Supportdan javob:\n\n{message.text}"
            )
        elif message.content_type == ContentType.PHOTO:
            await bot.send_photo(
                chat_id=context["foydalanuvchi_chat_id"],
                photo=message.photo[-1].file_id,
                caption=f"📬 Supportdan javob:\n\n{message.caption or ''}"
            )
        elif message.content_type == ContentType.VIDEO:
            await bot.send_video(
                chat_id=context["foydalanuvchi_chat_id"],
                video=message.video.file_id,
                caption=f"📬 Supportdan javob:\n\n{message.caption or ''}"
            )
        elif message.content_type == ContentType.VOICE:
            await bot.send_voice(
                chat_id=context["foydalanuvchi_chat_id"],
                voice=message.voice.file_id,
                caption="📬 Supportdan javob"
            )
            
        # Original xabarni tahrirlash
        try:
            await bot.edit_message_reply_markup(
                chat_id=ADMIN_GROUP_ID,
                message_id=context["gruppa_xabari_id"],
                reply_markup=None
            )
        except Exception as e:
            logger.error(f"Original xabarni tahrirlashda xato: {e}")

        await message.answer("✅ Javob foydalanuvchiga yuborildi!")
        
        # Tozalash
        javob_kutayotganlar.pop(admin_id, None)
        kutilayotgan_savollar.pop(context["gruppa_xabari_id"], None)
        
    except Exception as e:
        logger.error(f"Javob yuborishda xato: {e}")
        await message.answer(f"❌ Javob yuborishda xato: {e}")

# Asosiy funksiya
async def asosiy():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(asosiy())
