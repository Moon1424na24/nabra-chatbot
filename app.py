from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
from difflib import get_close_matches
import os
import re
from google import genai
from google.genai.errors import APIError

# ----------------------------------------------------
# ثوابت إدارة حالة المستخدم
# ----------------------------------------------------
STATE_AWAITING_GREETING = "awaiting_greeting"
STATE_AWAITING_WORD = "awaiting_word"
STATE_AWAITING_DIALECT = "awaiting_dialect_choice"
STATE_AWAITING_CONFIRMATION = "awaiting_confirmation_yes_no" # لحالة تصحيح الكلمة
STATE_AWAITING_AI_CONFIRMATION = "awaiting_ai_confirmation_yes_no" # 📌 حالة جديدة: تأكيد المساعد الخارجي
STATE_AWAITING_FULL_DETAILS = "awaiting_full_details_yes_no"

# ----------------------------------------------------
# قوائم الإجابات الموسعة لـ 'نعم' و 'لا' (باللهجات والأخطاء الإملائية)
# ----------------------------------------------------
EXPLICIT_YES = [
    "نعم", "ايه", "أيوه", "إيه", "اي", "يس", "yes", "أكيد", "صحيح", "نعم صحيح",
    "تمام", "تكفى", "ي", "يي", "اوافق", "حسنا"
]
EXPLICIT_NO = [
    "لا", "لأ", "no", "نو", "ما ابغى", "خلاص", "كفاية", "لا مش لازم",
    "لالا", "كاني", "شكرا"
]

# ----------------------------------------------------
# إعدادات Flask والقواميس
# ----------------------------------------------------
app = Flask(__name__)
CORS(app)


# تحميل القاموس
try:
    with open("dictionary.json", "r", encoding="utf-8") as f:
        dictionary = json.load(f)
except FileNotFoundError:
    print("❌ خطأ: ملف dictionary.json غير موجود.")
    dictionary = {}

# حالة المستخدم (للتتبع الحواري)
user_state = {}

# دمج اللهجات في قاموس للربط بالرقم (تم تحديث الأسماء لتطابق القاموس)
DIALECT_OPTIONS = {
    1: "وسطى",
    2: "جنوبية",
    3: "بيضا",
    4: "غربية",
    5: "شمالية",
    6: "اللغة الإنجليزية"
}
# بناء قائمة الخيارات للعرض في المحادثة
DIALECT_CHOICES_TEXT = "\n".join([f"{num}- {dialect}" for num, dialect in DIALECT_OPTIONS.items()])

#    تبحث عن الكلمة في المفاتيح والمرادفات.
def find_word_in_dictionary(word_input):
    cleaned_input = clean_text(word_input)
    
    # 1. قائمة بجميع الكلمات القابلة للبحث (المفاتيح والمرادفات)
    all_searchable_words = []
    
    # 2. البحث عن تطابق كامل أولاً
    for key, translations in dictionary.items():
        cleaned_key = clean_text(key)
        all_searchable_words.append(cleaned_key)
        
        # تطابق مع المفتاح (الكلمة الأصلية)
        if cleaned_input == cleaned_key:
            return key, translations, "exact_match"

        # البحث في الترجمات
        for translation_word in translations.values():
            cleaned_translation = clean_text(translation_word)
            all_searchable_words.append(cleaned_translation)
            
            if cleaned_input == cleaned_translation:
                return key, translations, "exact_match"
                
    # 3. إذا لم يوجد تطابق كامل، البحث عن الكلمة الأقرب (التصحيح الإملائي)
    close_matches = get_close_matches(cleaned_input, list(set(all_searchable_words)), n=1, cutoff=0.8)
    
    if close_matches:
        # البحث عن الكلمة الأصلية المطابقة لأقرب كلمة معقمة
        for key, translations in dictionary.items():
            if clean_text(key) == close_matches[0]:
                return key, translations, "close_match"
            for translation_word in translations.values():
                if clean_text(translation_word) == close_matches[0]:
                    return key, translations, "close_match"
    
    return None, None, "no_match"

# ----------------------------------------------------
# قسم تهيئة البوت الذكي (Generative AI)
# ----------------------------------------------------
client = None
try: 
    # **مفتاحك الخاص:** (تم ترك المفتاح المقدم من المستخدم هنا)
    client = genai.Client(api_key="AIzaSyB6oau5t-2roPzurNzULa8PwstHJgWwKF4")
    print("🤖 The ai chatbot has been successfully")
except Exception as e:
    # ⚠️ ملاحظة: يجب أن يظل `client` هو `None` إذا فشل التهيئة
    print(f"❌ فشل تهيئة البوت الذكي: {e}")
    client = None
    
# ----------------------------------------------------
# دالة تنظيف النص وتوحيد الأحرف (لتصحيح أخطاء المستخدم)
# ----------------------------------------------------
def clean_text(text):
    if not text:
        return ""
    
    # 1. إزالة التشكيل (الحركات)
    text = re.sub(r'[\u064b-\u0652]', '', text)
    
    # 2. توحيد الألف (أ, إ, آ, ٱ) إلى ا
    text = re.sub(r'[أإآٱ]', 'ا', text)
    
    # 3. توحيد الياء والألف المقصورة (ي, ى) والياء المهموزة (ئ) إلى ي
    text = re.sub(r'[يىئ]', 'ي', text)
    
    # 4. توحيد التاء المربوطة (ة) إلى ه
    text = re.sub(r'ة', 'ه', text)

    # 5. إزالة علامات الترقيم
    text = re.sub(r'[؟\?\.,:;!\'"]', '', text).strip()
    
    return text.strip()


# ----------------------------------------------------
# 🧠 دوال الـ AI (Generative AI Functions)
# ----------------------------------------------------

def deduce_user_dialect(user_text):
    """استنباط لهجة المستخدم (المساعد الخارجي)."""
    if not client: return 'فصحى'
    
    prompt = ( 
        f"قم بتحليل النص التالي: '{user_text}'. "
        f"حدد اللهجة السعودية الأقرب للنص (جنوبية، وسطى، غربية، شمالية، بيضا) أو 'فصحى' إن كان باللغة العربية الفصحى. "
        f"أجب بكلمة واحدة فقط من هذه الخيارات: 'جنوبية', 'وسطى', 'غربية', 'شمالية', 'بيضا', 'فصحى'. "
        f"لا تضف أي شرح."
    )
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        # توحيد الرد لحالة اللهجة 'عامة' (لتجنب ردود غريبة من AI)
        deduced = response.text.strip().lower()
        if 'جنوبية' in deduced: return 'جنوبية'
        if 'وسطى' in deduced: return 'وسطى'
        if 'غربية' in deduced: return 'غربية'
        if 'شمالية' in deduced: return 'شمالية'
        if 'بيضا' in deduced: return 'بيضا'
        return 'فصحى'

    except Exception as e:
        print(f"❌ خطأ في استنباط اللهجة: {e}")
        return 'فصحى' 

def generate_conversational_reply(user_input, deduced_dialect):
    """الرد الحواري (للترحيب) - المساعد الخارجي يولد الرد."""
    if not client: return "تمام الحمد لله، وأنت؟"

    prompt = (
        f"رد على الرسالة التالية بأسلوب محادثة لطيف ومختصر جداً (في سطر واحد) وبلهجة '{deduced_dialect}' قدر الإمكان. "
        f"النص: '{user_input}'"
    )
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"❌ خطأ في الرد الحواري: {e}")
        return "تمام الحمد لله، وأنت؟"

def get_ai_persona_prompt(user_question, chosen_dialect):
    """تحديد الشخصية والرد المختصر (للأسئلة المعرفية)."""
    brief_instruction = "**أجب في سطر واحد أو سطرين على الأكثر، وكن مختصراً ومباشراً.**"
    
    if "اللغة الإنجليزية" in chosen_dialect:
        instruction_prefix = f"أنت مترجم متخصص، أجب بالإنجليزية."
        dialect_for_persona = "English" # نستخدمها داخليًا لتوجيه AI
    elif chosen_dialect == "فصحى":
        instruction_prefix = f"أنت خبير لغوي، أجب مرادف الكلمة في اللغة الفصحى."
        dialect_for_persona = chosen_dialect
    else:
        instruction_prefix = f"أنت خبير لهجات، أجب مرادف الكلمة بلهجة '{chosen_dialect}'."
        dialect_for_persona = chosen_dialect
    
    # 📌 التعديل: إزالة منطق الشخصيات المعقد لضمان التركيز على الترجمة
    # food_keywords = ["أكل", "مطعم", "طبق", "غداء", "عشاء", "وجبة", "طعام"]
    # travel_keywords = ["سفر", "سياحة", "مكان", "وجهة", "منطقة", "جدة", "رياض"]
    
    # الشخصية الافتراضية
    persona = (
        f"{instruction_prefix} {brief_instruction}"
    )
    return persona

def ask_ai_with_persona(word_input, chosen_dialect):
    """استدعاء المساعد الخارجي للرد على كلمة غير موجودة أو سؤال."""
    if not client:
        return "⚠️ لا يمكن الاتصال بالبوت الذكي حالياً (المفتاح مفقود)."

    persona_prompt = get_ai_persona_prompt(word_input, chosen_dialect)
    prompt = (
        f"القواعد: {persona_prompt} "
        f"السؤال: '{word_input}'"
    )
    
    try:
        final_dialect = "English" if "اللغة الإنجليزية" in chosen_dialect else chosen_dialect

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text.strip()
    except APIError as e:
        print(f"❌ خطأ API عند استدعاء Gemini: {e}")
        return f"⚠️ خطأ في الاستعلام من API: {e}"
    except Exception as e:
        print(f"❌ خطأ غير متوقع: {e}")
        return f"⚠️ حدث خطأ غير متوقع: {e}"
        
def classify_user_intent_with_ai(user_answer, context):
    """تصنيف نية المستخدم بواسطة الذكاء الاصطناعي (فهم النوايا نعم/لا)."""
    if not client: return 'unknown'
    context_questions = {
        STATE_AWAITING_CONFIRMATION: "هل توافق على الكلمة المقترحة؟",
        STATE_AWAITING_AI_CONFIRMATION: "هل توافق على سؤال المساعد الخارجي؟", 
        STATE_AWAITING_FULL_DETAILS: "هل تريد رؤية الكلمة في كل اللهجات؟",
    }
    question_to_classify = context_questions.get(context, "هل يقصد المستخدم نعم أو لا؟")
    prompt = (
        f"لقد طُرح على المستخدم هذا السؤال: '{question_to_classify}' "
        f"وكانت إجابته هي: '{user_answer}'. "
        f"صنّف إجابته بكلمة واحدة فقط: 'yes' أو 'no' أو 'unknown'. "
        f"لا تضف أي نص آخر أو شرح أو علامات ترقيم."
    )
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        classification = response.text.strip().lower()
        if classification in ['yes', 'no']: return classification
        else: return 'unknown'
    except Exception as e:
        print(f"❌ خطأ في تصنيف الذكاء الاصطناعي: {e}")
        return 'unknown'
        
# ----------------------------------------------------
# 🔄 دوال معالجة الطلبات (Route Handlers)
# ----------------------------------------------------

def ask_ai_only(word_input, chosen_dialect):
    """مسار ask_ai_only للرد المباشر من الذكاء الاصطناعي (المساعد الخارجي)."""
    
    ai_reply = ask_ai_with_persona(word_input, chosen_dialect)
    chosen_dialect_display = chosen_dialect
    
    # ⚠️ رسالة الرد بشخصية المساعد الخارجي
    final_reply = f"🤖: أنا Gemini المساعد الخارجي لنَبْرة، يسعدني أرد عليك بخصوص سؤالك عن **{word_input}** في لهجة {chosen_dialect_display}:\n\n{ai_reply}\n\n"
    final_reply += "انا مُولًد آليًا، قد يحتوي أجوبتي على أخطاء طفيفة،،إذا تحب تشوف كلمة أخرى اكتبها."
    
    # نستخدم حالة 'ai_only_success' لتنبيه الـ Front-end (script.js)
    return jsonify({"status": "ai_only_success", "reply": final_reply})

def handle_dialect_selection(user_id, selection_input):
    """دالة معالجة اختيار اللهجة (بعد الإدخال الأولي)."""
    state = user_state.get(user_id)
    # التحقق الأولي من الحالة
    if not state or state.get("state") != STATE_AWAITING_DIALECT:
        user_state[user_id] = {"state": STATE_AWAITING_WORD} 
        return jsonify({"status": "awaiting_word", "reply": "⚠️ حدث خطأ في النظام. يرجى البدء من جديد وكتابة كلمة جديدة للترجمة."})

    # التحقق من أن المدخل رقم صحيح ويقع ضمن الخيارات
    try:
        choice_num = int(selection_input.strip())
        chosen_dialect = DIALECT_OPTIONS.get(choice_num)
    except ValueError:
        chosen_dialect = None
    
    if chosen_dialect:
        word_to_process = state["pending_word"]
        
        # 1. البحث في القاموس مرة أخرى (هنا نعتمد على الكلمة المصححة إذا وجدت)
        found_word, translations, match_type = find_word_in_dictionary(word_to_process)
        
        # في هذه المرحلة، المفروض تكون الكلمة صحيحة أو تم تأكيدها
        # ولكن نكرر منطق الـ AI في حالة لم يتم إيجادها بالرغم من كل شيء
        if translations:
            # الكلمة موجودة في القاموس (شخصية نبرة) - المسار القديم
            reply = f'📖 أنا نَبْرة، مرادف **{found_word}** بلهجة {chosen_dialect}: {translations.get(chosen_dialect,"غير موجود")}\n'
            reply += "\nهل تحب تشوفها بكل اللهجات؟ (نعم/لا)"
            user_state[user_id] = {
                "word": found_word,
                "translations": translations,
                "state": STATE_AWAITING_FULL_DETAILS,
                "initial_dialect": chosen_dialect
            }
            return jsonify({"status": "success", "reply": reply})

        # 2. الكلمة غير موجودة بعد محاولة البحث
        else:
            user_state[user_id] = {
                "word": word_to_process,
                "translations": None,
                "state": STATE_AWAITING_AI_CONFIRMATION, # حالة جديدة
                "initial_dialect": chosen_dialect
            }
            # الرد بشخصية نبرة، لأن القرار يخص قدرات القاموس الداخلي
            reply = f"📖 أنا نَبْرة. آسف، كلمة **{word_to_process}** غير موجودة في قاموس اللهجات الخاص بي."
            reply += f"\n\nهل تحب أن أسأل Gemini المساعد الخارجي لنَبْرة عن معناها في لهجة **{chosen_dialect}**؟ (نعم/لا)"
            return jsonify({"status": "success", "reply": reply})

    else:
        # إذا كان الاختيار غير صحيح
        reply = "⚠️ يرجى تحديد رقم اللهجة من 1 إلى 7 بشكل صحيح.\n"
        reply += "حدد رقم اللهجة الي تبيها:\n" + DIALECT_CHOICES_TEXT
        return jsonify({"status": "success", "reply": reply})


@app.route("/ask", methods=["POST"])
def ask():
    """مسار ask (للبحث الأولي عن الكلمة - المسار الحواري الرئيسي)."""
    data = request.get_json()
    user_id = data.get("user_id", "default")
    word_input = data.get("text", "").strip()
    
    # 0. تهيئة الحالة للمستخدم الجديد
    if user_id not in user_state or user_state[user_id].get("state") not in [
        STATE_AWAITING_WORD, STATE_AWAITING_DIALECT, STATE_AWAITING_CONFIRMATION, 
        STATE_AWAITING_AI_CONFIRMATION, STATE_AWAITING_FULL_DETAILS
    ]:
        user_state[user_id] = {"state": STATE_AWAITING_GREETING}

    current_state = user_state[user_id].get("state")

    # 1. حالة انتظار التحية (أول رسالة)
    if current_state == STATE_AWAITING_GREETING: 
        
        # المنطق الجديد: استنباط اللهجة والرد بها
        deduced_dialect = deduce_user_dialect(word_input)
        conversational_response = generate_conversational_reply(word_input, deduced_dialect)
        
        # بناء الرد النهائي
        reply = f"📖 أنا نَبْرة. {conversational_response}\n"
        reply += f"لاحظت أن لهجتك تميل إلى {deduced_dialect}" # لغرض الاختبار
        reply += "\n\nتفضل، وش الكلمة اللي تبغاني أترجمها لك اليوم؟"
        
        user_state[user_id] = {"state": STATE_AWAITING_WORD}
        return jsonify({"status": "awaiting_word", "reply": reply})

    # 2. حالة انتظار الكلمة الفعلية (بعد التحية)
    elif current_state == STATE_AWAITING_WORD:
        
        # 2.1 البحث في القاموس مع محاولة التصحيح
        found_word, translations, match_type = find_word_in_dictionary(word_input)
        
        if match_type == "exact_match":
            # الكلمة موجودة بالتحديد، نطلب اللهجة مباشرة
            user_state[user_id].update({
                "state": STATE_AWAITING_DIALECT,
                "pending_word": word_input # الكلمة الفعلية للبحث
            })
            
            reply = f"📖:انا نَبْرة، تمام! حدد اللهجة اللي تبغاني أجاوبك فيها:\n\n"
            reply += DIALECT_CHOICES_TEXT + "\n\n"
            reply += "حدد رقم اللهجة الي تبيها:"
            return jsonify({"status": STATE_AWAITING_DIALECT, "reply": reply})

        elif match_type == "close_match":
            # 📌 الكلمة غير موجودة، لكن وجدنا كلمة قريبة جداً (تصحيح إملائي)
            # ننتقل إلى حالة التأكيد (CONFIRMATION)
            user_state[user_id].update({
                "state": STATE_AWAITING_CONFIRMATION,
                "word": found_word,          # الكلمة المصححة المقترحة
                "translations": translations, # ترجمات الكلمة المصححة
                "pending_word": word_input    # الكلمة التي أدخلها المستخدم
            })
            
            # 📖 الرد بشخصية نبرة، لأن القرار يخص القاموس
            reply = f"📖 أنا نَبْرة. لم أجد كلمة **{word_input}** بالضبط."
            reply += f"\n\nهل تقصد **{found_word}**؟ (نعم/لا)"
            return jsonify({"status": "success", "reply": reply})

        else: # no_match
            # الكلمة غير موجودة في القاموس، نقترح الاستعانة بالـ AI
            
            # 📌 ننتقل إلى حالة انتظار اختيار اللهجة أولاً لتحديد السياق للـ AI
            user_state[user_id].update({
                "state": STATE_AWAITING_DIALECT,
                "pending_word": word_input # الكلمة الفعلية للبحث
            })
            
            reply = f"📖:انا نَبْرة، تمام! حدد اللهجة اللي تبغاني أجاوبك فيها :\n\n"
            reply += DIALECT_CHOICES_TEXT + "\n\n"
            reply += "حدد رقم اللهجة الي تبيها:"
            
            return jsonify({"status": STATE_AWAITING_DIALECT, "reply": reply})
            
    # 3. حالة انتظار اختيار رقم اللهجة (تنفيذها في handle_dialect_selection)
    elif current_state == STATE_AWAITING_DIALECT:
        return handle_dialect_selection(user_id, word_input)

    # 4. إذا كانت الإجابة غير متوقعة في حالة انتظار "نعم/لا" (خطأ)
    elif current_state in [STATE_AWAITING_CONFIRMATION, STATE_AWAITING_AI_CONFIRMATION, STATE_AWAITING_FULL_DETAILS]:
        # نرسل رسالة تذكير حسب الحالة الحالية
        if current_state == STATE_AWAITING_AI_CONFIRMATION:
            return jsonify({"status": "success", "reply": "يرجى الإجابة بـ 'نعم' للمساعدة الخارجية أو 'لا' لإلغاء البحث."})
        elif current_state == STATE_AWAITING_FULL_DETAILS:
            return jsonify({"status": "success", "reply": "يرجى الإجابة بـ 'نعم' أو 'لا' لعرض كل اللهجات."})
        elif current_state == STATE_AWAITING_CONFIRMATION:
            return jsonify({"status": "success", "reply": "يرجى الإجابة بـ 'نعم' أو 'لا' لتأكيد الكلمة المقترحة."})
            
    # إذا كانت الحالة غير معرفة أو غير تابعة للمحادثة الحوارية
    return jsonify({"status": "error", "message": "حدث خطأ غير متوقع. يرجى البدء من جديد."})


@app.route("/ask_full", methods=["POST"])
def ask_full():
    """مسار ask_full (لمعالجة نعم/لا - مع منطق الفحص الموسع)."""
    data = request.get_json()
    user_id = data.get("user_id", "default")
    answer = data.get("answer", "").strip()

    state = user_state.get(user_id)
    if not state:
        return jsonify({"status": "error", "reply": "لا توجد كلمات محفوظة حالياً للبحث. يرجى كتابة كلمة جديدة."})

    cleaned_answer = clean_text(answer).lower()
    
    # 1. الفحص الموسع للإجابات الصريحة (بما في ذلك الأخطاء الإملائية والبدائل)
    classification = None
    if any(keyword in cleaned_answer for keyword in EXPLICIT_YES):
        classification = 'yes'
    elif any(keyword in cleaned_answer for keyword in EXPLICIT_NO):
        classification = 'no'
    else:
        # 2. إذا كانت الإجابة غير صريحة، نستخدم الذكاء الاصطناعي لفهم النية (كـ fallback)
        context_type = state.get("state")
        
        if context_type and client:
            classification = classify_user_intent_with_ai(answer, context_type)
        else:
            classification = 'unknown'

    # ----------------------------------------------------
    # تطبيق المنطق بناءً على تصنيف (نعم/لا)
    # ----------------------------------------------------
    
    # 📌 حالة التأكيد (هل تسأل المساعد الخارجي؟) - المنطق الجديد
    if state.get("state") == STATE_AWAITING_AI_CONFIRMATION:
        word = state["word"]
        chosen_dialect = state["initial_dialect"]

        if classification == 'yes':
            user_state.pop(user_id) # مسح الحالة مؤقتاً
            # 🤖 استدعاء المساعد الخارجي مباشرةً
            return ask_ai_only(word, chosen_dialect)
            
        elif classification == 'no':
            # العودة لحالة انتظار كلمة جديدة
            user_state[user_id] = {"state": STATE_AWAITING_WORD}
            return jsonify({"status": "success", "reply": "حسناً، لن أسأل المساعد الخارجي. يمكنك كتابة كلمة أخرى للترجمة."})
        else:
            return jsonify({"status": "success", "reply": "لم أفهم إجابتك. يرجى الإجابة بـ 'نعم' للمساعدة الخارجية أو 'لا' لإلغاء البحث."})

    # حالة التصحيح (هل قصدت الكلمة كذا؟) - بشخصية نبرة
    if state.get("state") == STATE_AWAITING_CONFIRMATION:
        if classification == 'yes':
            word = state["word"]
            translations = state["translations"]
            chosen_dialect = state.get("initial_dialect", "فصحى") # قد لا تكون موجودة، نستخدم فصحى كافتراضي
            
            # نعود لطلب اللهجة لاكمال المسار
            user_state[user_id].update({
                "state": STATE_AWAITING_DIALECT,
                "pending_word": word # الكلمة المصححة هي الكلمة التي سنبحث عنها الآن
            })

            reply = f"📖 أنا نَبْرة. حسناً، سأبحث عن كلمة **{word}**. حدد اللهجة التي تريد أن أترجم إليها:\n\n"
            reply += DIALECT_CHOICES_TEXT + "\n\n"
            reply += "حدد رقم اللهجة الي تبيها:"
            
            return jsonify({"status": "success", "reply": reply})
            
        elif classification == 'no':
            # العودة لحالة انتظار كلمة جديدة
            user_state[user_id] = {"state": STATE_AWAITING_WORD}
            return jsonify({"status": "success", "reply": "حسناً، لم يتم تأكيد الكلمة المقترحة. تفضل بكتابة الكلمة الصحيحة الآن."})
        else:
            return jsonify({"status": "success", "reply": "لم أفهم إجابتك. يرجى الإجابة بـ 'نعم' أو 'لا' للتأكيد."})

    # حالة عرض كل اللهجات (هل تحب تشوفها بكل اللهجات؟)
    if state.get("state") == STATE_AWAITING_FULL_DETAILS:
        if classification == 'yes':
            translations = state["translations"]
            reply = f"🌐 الكلمة بكل مرادفاتها:\n"
            for d, val in translations.items():
                reply += f"- {d}: {val}\n"
            reply += "\nإذا تحب تشوف كلمة أخرى، اكتبها."
            # العودة لحالة انتظار كلمة جديدة
            user_state[user_id] = {"state": STATE_AWAITING_WORD}
            return jsonify({"status": "success", "reply": reply})
        
        elif classification == 'no':
            # العودة لحالة انتظار كلمة جديدة
            user_state[user_id] = {"state": STATE_AWAITING_WORD}
            return jsonify({"status": "success", "reply": "حسناً 👍. إذا تحب تشوف كلمة أخرى، اكتبها."})
        
        else:
            return jsonify({"status": "success", "reply": "لم أفهم إجابتك. يرجى الإجابة بـ 'نعم' أو 'لا' لعرض كل اللهجات."})

    return jsonify({"status": "error", "message": "لا توجد حالة معرفة حالياً."})

# ----------------------------------------------------
# المسارات الثابتة
# ----------------------------------------------------
@app.route("/")
def index():
    return send_from_directory('.', 'index.html')

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory('.', path)

# تشغيل السيرفر
if __name__ == "__main__":
    app.run()