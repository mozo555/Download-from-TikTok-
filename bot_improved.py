import datetime
import os
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import subprocess
import re

# دالة async لجلب المعلومات من API بسرعة وكفاءة (لم تعد تستخدم لجلب معلومات المستخدم)
# تم الاحتفاظ بها مؤقتًا في حال أردت العودة لوظيفة جلب المعلومات
async def fetch_user_info(username: str):
    API_URL = "https://www.tikwm.com/api/user/info?unique_id={username}"
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(API_URL.format(username=username))
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            return {"error": f"خطأ في الاتصال: {e}"}
        except httpx.HTTPStatusError as e:
            return {"error": f"رد HTTP غير صالح: {e}"}
        except Exception as e:
            return {"error": f"خطأ غير متوقع: {e}"}

# دالة لتحويل الطابع الزمني unix إلى نص مقروء (لم تعد تستخدم)
def format_timestamp(ts):
    try:
        if ts and ts > 0 and ts != 'N/A':
            return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    except:
        pass
    return None

# دالة لبناء نص المعلومات بشكل مرتب مع الهروب لـ MarkdownV2 (لم تعد تستخدم)
def build_info_text(user_info):
    def escape_md(text):
        escape_chars = r"\_*[]()~`>#+-=|{}.!"
        for ch in escape_chars:
            text = text.replace(ch, f"\\{ch}")
        return text

    unique_id = user_info.get('uniqueId')
    nickname = user_info.get('nickname')
    user_id = user_info.get('id')
    follower_count = user_info.get('followerCount', 0)
    following_count = user_info.get('followingCount', 0)
    heart_count = user_info.get('heartCount', 0)
    video_count = user_info.get('videoCount', 0)
    signature = user_info.get('signature')

    create_time = format_timestamp(user_info.get('createTime'))
    modify_unique_id_time = format_timestamp(user_info.get('modifyUniqueIdTime'))
    modify_nickname_time = format_timestamp(user_info.get('modifyNicknameTime'))
    country = user_info.get('country')

    text_parts = []
    if unique_id:
        text_parts.append(f"✅ *تم العثور على معلومات @{escape_md(unique_id)}*\n")
    else:
        text_parts.append(f"✅ *تم العثور على معلومات المستخدم*\n")

    text_parts.append(f"👤 *الاسم:* {escape_md(nickname) if nickname else 'N/A'}\n")
    text_parts.append(f"🆔 *المعرّف (ID):* `{escape_md(str(user_id)) if user_id else 'N/A'}`\n\n")

    text_parts.append(f"❤️ *المتابعون:* {follower_count:,}\n")
    text_parts.append(f"↗️ *يتابع:* {following_count:,}\n")
    text_parts.append(f"👍 *الإعجابات:* {heart_count:,}\n")
    text_parts.append(f"🎥 *الفيديوهات:* {video_count:,}\n\n")

    if create_time:
        text_parts.append(f"📅 *تاريخ إنشاء الحساب:* {create_time}\n")
    if modify_unique_id_time:
        text_parts.append(f"✏️ *تعديل اسم المستخدم:* {modify_unique_id_time}\n")
    if modify_nickname_time:
        text_parts.append(f"✏️ *تعديل الاسم:* {modify_nickname_time}\n")
    if country:
        text_parts.append(f"🌍 *الدولة:* {escape_md(country)}\n")

    text_parts.append(f"\n📝 *البايو:*\n{escape_md(signature) if signature else 'لا يوجد'}")

    return "".join(text_parts)

# أمر /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً بك! أرسل لي رابط فيديو تيك توك لتحميله بدون علامة مائية.")

# التعامل مع الرسائل النصية (رابط الفيديو)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video_url = update.message.text.strip()

    # التحقق من أن الرابط هو رابط تيك توك
    if not re.match(r"https?://(www\.)?(tiktok\.com|vm\.tiktok\.com)/.*", video_url):
        await update.message.reply_text("⚠️ الرجاء إرسال رابط فيديو تيك توك صالح.")
        return

    loading_msg = await update.message.reply_text("⏳ جاري تحميل الفيديو...")

    try:
        # إنشاء ملف مؤقت لتخزين الرابط
        links_file_path = "/tmp/links.txt"
        with open(links_file_path, "w") as f:
            f.write(video_url + "\n")

        # تحديد مسار مجلد التنزيلات
        download_dir = "/tmp/tiktok_downloads"
        os.makedirs(download_dir, exist_ok=True)

        # تشغيل سكريبت multitok.py
        command = [
            "python3",
            "/home/ubuntu/TikTok-Multi-Downloader/multitok.py",
            "--links", links_file_path,
            "--no-watermark",
            "--output-dir", download_dir
        ]
        
        process = subprocess.run(command, capture_output=True, text=True, check=False)
        
        if process.returncode != 0:
            error_output = process.stderr if process.stderr else process.stdout
            await loading_msg.edit_text(f"❌ حدث خطأ أثناء تحميل الفيديو:\n```\n{error_output[:500]}\n```\nالرجاء التأكد من صحة الرابط أو المحاولة لاحقًا.")
            print(f"Error running multitok.py: {error_output}")
            return

        # البحث عن الفيديو المحمل
        downloaded_files = []
        for root, _, files in os.walk(download_dir):
            for file in files:
                if file.endswith(('.mp4', '.jpeg')):
                    downloaded_files.append(os.path.join(root, file))
        
        if not downloaded_files:
            await loading_msg.edit_text("❌ لم يتم العثور على الفيديو المحمل. قد يكون الرابط غير صالح أو حدث خطأ.")
            return

        await loading_msg.edit_text("⬆️ جاري إرسال الفيديو...")

        # إرسال الفيديو (أو الصور) للمستخدم
        for file_path in downloaded_files:
            try:
                if file_path.endswith('.mp4'):
                    await update.message.reply_video(video=open(file_path, 'rb'))
                elif file_path.endswith('.jpeg'):
                    await update.message.reply_document(document=open(file_path, 'rb'), caption="صورة تيك توك بدون علامة مائية")
            except Exception as e:
                await update.message.reply_text(f"❌ حدث خطأ أثناء إرسال الملف: {os.path.basename(file_path)}\nالخطأ: {e}")
                print(f"Error sending file {file_path}: {e}")
            finally:
                # حذف الملف بعد الإرسال لتوفير المساحة
                os.remove(file_path)
        
        # لا نرسل رسالة نجاح هنا لأن رسالة الإرسال هي الأخيرة

    except Exception as e:
        await loading_msg.edit_text(f"❌ حدث خطأ غير متوقع: {e}")
        print(f"Unexpected error in handle_message: {e}")

def main():
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    if not BOT_TOKEN:
        print("خطأ: لم يتم العثور على توكن البوت. تأكد من ضبط متغير البيئة BOT_TOKEN")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 بدء تشغيل بوت تحميل فيديوهات تيك توك المتقدم...")
    application.run_polling()

if __name__ == "__main__":
    main()


