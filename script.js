// ------------------------------
// صندوق عرض الرسائل
// ------------------------------
const chatBox = document.getElementById("chat-box");


// معرف المستخدم لتتبع الحالة
let userId = "user1";


// ------------------------------
// 💡 دالة تحديث تذييل الصفحة (Footer) بالتاريخ [جديد]
// ------------------------------
function updateFooter() {
    const footerElement = document.getElementById('app-footer');
    if (footerElement) {
        const date = new Date();
        // تنسيق التاريخ واليوم باللغة العربية
        const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        const formattedDate = date.toLocaleDateString('ar-SA', options); 
        
        // تحديث المحتوى بالصيغة المطلوبة (التاريخ)
        footerElement.innerHTML = `
            <span>${formattedDate}</span>
        `;
    }
}

// ------------------------------
// دالة عرض الرسائل في الصندوق (تم تعديلها لعرض الأسطر الجديدة)
// ------------------------------
function addMessage(text, sender) {
  const msg = document.createElement("div");
  msg.classList.add("message", sender);
  // استخدام innerHTML لإدخال روابط HTML قابلة للضغط
  msg.innerHTML = text.replace(/\n/g, '<br>'); 
  chatBox.appendChild(msg);
  chatBox.scrollTop = chatBox.scrollHeight;
  return msg; 
}


// ------------------------------
// دالة مساعدة لتنسيق رسالة البوت مع الأيقونة الجديدة (الصورة بالشماغ)
// ------------------------------
function formatBotMessage(text) {
    // نستخدم وسوم <img> مباشرة ونضبط حجمها ليتناسب مع الرسالة
    const icon = '<img src="zz.png" alt="نبرة" style="height: 20px; vertical-align: middle; margin-left: 5px;">';
    return icon + text;
}


// ------------------------------
// دالة بدء المحادثة الترحيبية
// ------------------------------
function startGreetingConversation() {
  // الرسالة الأولى: تعريف البوت (باستخدام دالة التنسيق الجديدة)
  addMessage(formatBotMessage(": أهلاً بك! أنا نَبْرة، البوت اللي يحوّل لك الكلمة بمرادفاتها من لهجات السعودية."), "bot"); 
  
  // الرسالة الثانية: طلب الإدخال من المستخدم (باستخدام دالة التنسيق الجديدة)
  setTimeout(() => {
    addMessage(formatBotMessage(": تفضل، اكتب أي شيء عشان نبدأ سوالف!"), "bot");
  }, 1000); 
}


// ------------------------------
// دالة إرسال الرسالة
// ------------------------------
async function sendMessage() {
  const input = document.getElementById("user-input");
  const text = input.value.trim();

  if (!text) return;

  addMessage(text, "user"); 
  input.value = "";         

  let loadingMsg = null; 

  // ------------------------------
  // التحقق من نعم/لا (لمعالجة الحالات المعلقة)
  // ------------------------------
  if (["نعم", "لا", "ايه"].includes(text.toLowerCase())) { 
    
    try {
      const res = await fetch("http://localhost:5000/ask_full", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer: text, user_id: userId })
      });
      const data = await res.json();
      
      addMessage(data.reply, "bot");
      return; 
    } catch (err) {
      addMessage("⚠️ خطأ في الاتصال بالسيرفر. تأكد من أن السيرفر يعمل.", "bot");
      return;
    }
  }

  // ------------------------------
  // إرسال الكلمة / الاختيار للبحث الأولي
  // ------------------------------
  // إضافة رسالة التحميل
  loadingMsg = addMessage(formatBotMessage("ثواني..."), "bot"); 

  try {
    const res = await fetch("http://localhost:5000/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, user_id: userId })
    });

    const data = await res.json();
    
    // **حذف رسالة التحميل عند وصول الرد**
    if (loadingMsg) {
       chatBox.removeChild(loadingMsg);
    }
    
    // معالجة حالات المحادثة الجديدة وحالات النجاح الأخرى
    if (data.status === "awaiting_word" || data.status === "awaiting_dialect_choice" || data.status === "ai_only_success" || data.status === "success") {
        addMessage(data.reply, "bot");
    } else {
        // حالة الخطأ
        addMessage(data.message, "bot");
    }

  } catch (err) {
    // حذف رسالة التحميل حتى في حالة الخطأ
    if (loadingMsg) {
       chatBox.removeChild(loadingMsg);
    }
    addMessage("⚠️ خطأ في الاتصال بالسيرفر. تأكد من أن السيرفر يعمل.", "bot");
  }
}

// ------------------------------
// دعم إرسال الرسالة بالضغط على Enter
// ------------------------------
document.getElementById("user-input").addEventListener("keypress", function(e) {
  if (e.key === "Enter") sendMessage();
});


// ------------------------------
// دالة التواصل مع خدمة العملاء (الضغط)
// ------------------------------
function contactSupport() {
  const email = "smrkknr63@gmail.com";
  const phone = "0532123789";
  
  // بناء الرسالة مع الروابط القابلة للضغط
  const messageText = `📩 للتواصل مع خدمة العملاء:\n\n` +
                      `البريد الإلكتروني: <a href="mailto:${email}" style="color: #f7a61a; text-decoration: none;">${email}</a>\n` +
                      `رقم الهاتف: <a href="tel:${phone}" style="color: #f7a61a; text-decoration: none; direction: ltr; display: inline-block;">${phone}</a>`;
                      
  // إرسال الرسالة إلى صندوق الشات
  addMessage(messageText, "bot");
}

// ------------------------------
//جزء الخريطة التفاعلية
// ------------------------------

const map = document.getElementById('ksa-map');
const regions = document.querySelectorAll('.region');
const tooltip = document.getElementById('region-tooltip'); 

// وظيفة إخفاء الفقاعة فقط

function hideTooltip() {
    tooltip.style.display = 'none';
}

// 2. إضافة مستمعي الأحداث
regions.forEach(region => {
    
    // 🔴 عند التمرير بالماوس: إظهار الفقاعة وتحديد موقعها
    region.addEventListener('mousemove', function(e) {
        tooltip.textContent = this.dataset.name;
        tooltip.style.display = 'block';
        
        // تحديد موقع الفقاعة بالقرب من مؤشر الماوس
        tooltip.style.left = `${e.clientX + 10}px`;
        tooltip.style.top = `${e.clientY - 30}px`; // دفعها للأعلى فوق السهم
    });
    
    // 🔴 عند إزالة التمرير: إخفاء الفقاعة
    region.addEventListener('mouseout', function() {
        hideTooltip();
    });
});

// عند النقر على مساحة فارغة أو أي مكان، لا يحدث شيء
map.addEventListener('click', function(event) {
    // ترك هذا فارغاً لضمان عدم حدوث أي حركة أو إعادة تعيين
});

// إخفاء الفقاعة عند تحميل الصفحة
hideTooltip();

// ------------------------------
//اخر جزء الخريطة التفاعلية
// ------------------------------


// ========================================================
// === [كود الروبوت التفاعلي: تتبع العينين للفأرة] ===
// ========================================================

document.addEventListener('mousemove', (event) => {
    // 1. تعريف العناصر
    const leftPupil = document.getElementById('left-pupil');
    const rightPupil = document.getElementById('right-pupil');
    const robotContainer = document.getElementById('robot-container');

    // التأكد من وجود العناصر قبل البدء
    if (!leftPupil || !rightPupil || !robotContainer) return; 

    const containerRect = robotContainer.getBoundingClientRect();
    const mouseX = event.clientX; 
    const mouseY = event.clientY;

    // 2. ثوابت وحسابات العينين
    // تم ضبط هذه القيم لتتناسب مع حجم الروبوت الجديد (120x120px) 
    // وبناءً على viewBox="0 0 250 250"
    const LEFT_EYE_CX_SVG = 165; 
    const LEFT_EYE_CY_SVG = 140; 
    const RIGHT_EYE_CX_SVG = 235;
    const RIGHT_EYE_CY_SVG = 140;
    const maxMove = 8; // أقصى إزاحة لحدة العين

   // 3. حساب موضع مركز العين الفعلي على الشاشة
    // ⚠️ التعديل هنا ليعكس أبعاد viewBox="0 0 400 500" ⚠️
    const ratioX = containerRect.width / 400; // نسبة العرض (مقسومة على 400)
    const ratioY = containerRect.height / 500; // نسبة الارتفاع (مقسومة على 500)
    
    const leftEyeCenter = {
        x: containerRect.left + LEFT_EYE_CX_SVG * ratioX, 
        y: containerRect.top + LEFT_EYE_CY_SVG * ratioY
    };

    const rightEyeCenter = {
        x: containerRect.left + RIGHT_EYE_CX_SVG * ratioX,
        y: containerRect.top + RIGHT_EYE_CY_SVG * ratioY
    };
    
    // دالة لحساب الإزاحة (النظرة)
    function getPupilPosition(eyeCenter) {
        const deltaX = mouseX - eyeCenter.x;
        const deltaY = mouseY - eyeCenter.y;
        const angle = Math.atan2(deltaY, deltaX);
        const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
        
        const limitedDistance = Math.min(distance, maxMove); 
        
        const moveX = Math.cos(angle) * limitedDistance;
        const moveY = Math.sin(angle) * limitedDistance;
        
        return { moveX, moveY };
    }

    // 3. تطبيق الحركة
    const leftMove = getPupilPosition(leftEyeCenter);
    leftPupil.setAttribute('transform', `translate(${leftMove.moveX}, ${leftMove.moveY})`);

    const rightMove = getPupilPosition(rightEyeCenter);
    rightPupil.setAttribute('transform', `translate(${rightMove.moveX}, ${rightMove.moveY})`);
});



// دوال المساعدة: إظهار الرسائل في واجهة المستخدم

/**
 * دالة لإظهار رسالة جديدة في صندوق الدردشة.
 * @param {string} text - نص الرسالة.
 * @param {string} sender - مرسل الرسالة ('user' أو 'bot').
 */
function displayMessage(text, sender) {
    const chatBox = document.getElementById('chat-box');
    
    // إنشاء عنصر الرسالة (فقاعة)
    const messageElement = document.createElement('div');
    messageElement.classList.add('chat-message', sender);
    
    // إدخال النص في الفقاعة
    const textNode = document.createElement('span');
    textNode.textContent = text;
    messageElement.appendChild(textNode);
    
    // إضافة الرسالة إلى صندوق الدردشة
    chatBox.appendChild(messageElement);
    
    // التمرير إلى أسفل صندوق الدردشة لرؤية الرسالة الجديدة
    chatBox.scrollTop = chatBox.scrollHeight;
}


// دوال معالجة الإدخال والرد

/**
 * دالة لمعالجة إدخال المستخدم وإظهار الرد المناسب.
 * @param {string} message - رسالة المستخدم.
 */
function processMessage(message) {
    let botResponse = '';
    
    // نظام الردود القاعدي (Rule-Based Responses)
    switch (message.trim()) {
        
        // ------------------------------------
        // 1. التحية والسلام
        // ------------------------------------
        case 'السلام عليكم':
            botResponse = 'وعليكم السلام ورحمة الله وبركاته! أسعدني سلامك. تفضل، كيف يمكنني خدمتك؟';
            break;
        case 'كيف حالك':
            botResponse = 'أنا بوت يعمل بكامل طاقته بفضل الله، وأتمنى لك يوماً سعيداً. ما هي الكلمة التي تريد تحويلها؟';
            break;
            
        // ------------------------------------
        // 2. الشكر والامتنان (جديد)
        // ------------------------------------
        case 'شكراً':
        case 'شكرا':
            botResponse = 'العفو، هذا واجبي. لا تتردد في طلب المساعدة مرة أخرى!';
            break;
        case 'يعطيك العافية':
            botResponse = 'الله يعافيك ويبارك فيك. أنا جاهز لخدمتك في أي وقت.';
            break;
            
        // ------------------------------------
        // 3. التمنيات الصباحية والمسائية (جديد)
        // ------------------------------------
        case 'صباح الخير':
            botResponse = 'صباح النور والسرور! أتمنى لك بداية يوم موفقة. 👋';
            break;
        case 'مساء الخير':
            botResponse = 'مساء الخيرات! أتمنى لك أمسية هادئة. هل نبدأ المحادثة؟';
            break;

        // ------------------------------------
        // 4. الوداع (جديد)
        // ------------------------------------
        case 'إلى اللقاء':
            botResponse = 'في أمان الله وحفظه، سعيد جداً بالحديث معك! أتمنى أن أراك قريباً. 👋';
            break;
            
        // ------------------------------------
        // 5. استفسارات البوت الأساسية
        // ------------------------------------
        case 'من انت':
            botResponse = 'أنا نبرة، البوت المصمم لمساعدتك في فهم مرادفات الكلمات باللهجات السعودية المختلفة.';
            break;
        case 'كتابة الكلمة':
            botResponse = 'تفضل، اكتب الكلمة التي تريد تحويلها الآن في صندوق الإدخال.';
            break;
            
        // ------------------------------------
        // 6. الرد الافتراضي
        // ------------------------------------
        default:
            botResponse = 'أعتذر، لا أستطيع فهم هذه العبارة حالياً. هل يمكن أن تختار أحد الخيارات المتاحة؟';
    }
    
    // إظهار رد البوت
    setTimeout(() => {
        displayMessage(botResponse, 'bot');
    }, 500);
}
/**
 * دالة يتم استدعاؤها عند الضغط على أزرار الخيارات.
 * @param {string} option - الخيار الذي اختاره المستخدم.
 */
function handleOption(option) {
    // 1. إظهار رسالة المستخدم (نص الزر المضغوط)
    displayMessage(option, 'user');

    // 2. إرسال النص لمعالجته والحصول على رد البوت
    processMessage(option);
    
    // (اختياري) إخفاء الأزرار بعد اختيار أحدها 
    // const mainButtons = document.getElementById('main-buttons');
    // if (mainButtons) {
    //     mainButtons.style.display = 'none';
    // }
}

// ------------------------------
// استدعاء الدوال عند تحميل الصفحة
// ------------------------------
window.onload = function() {
  startGreetingConversation();
  updateFooter(); // 💡 تحديث التاريخ والتعليق
};