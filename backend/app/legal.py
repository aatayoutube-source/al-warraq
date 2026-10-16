"""The pages every site needs before it shows ads (AdSense reviews them): about, privacy, terms, contact.

Contact messages go to the statistics database (table contact_messages, deleted after a year) and are
read at /admin/messages, behind HTTP Basic auth with the password in ADMIN_PASSWORD; without that
setting the page does not exist. Spam protection: a hidden field people never fill, a signed timestamp
(the form must be at least a few seconds old), a per-visitor daily cap and the per-IP rate limit.

Settings (environment): CONTACT_EMAIL (shown on the contact page; defaults to the library's address), ADMIN_PASSWORD.
"""
import hashlib
import hmac
import os
import re
import secrets
import time
from urllib.parse import parse_qs

from . import stats
from .pages import BRAND, LEGAL, T, esc

UPDATED = {"ar": "16 أكتوبر 2026", "en": "16 October 2026"}
EMAIL_DEFAULT = "alwarraqibrary@gmail.com"  # the library's mailbox
PAGES = ("about", "privacy", "terms", "contact")
KEEP_SECONDS = 365 * 86400  # contact messages are deleted after a year
PER_DAY = 5  # messages one visitor may send per day
MIN_AGE, MAX_AGE = 3, 2 * 86400  # seconds between showing the form and sending it
LIMITS = {"name": 80, "email": 120, "message": 3000}
EMAIL = re.compile(r"^[^@\s<>\"']{1,64}@[^@\s<>\"']+\.[^@\s<>\"']{2,}$")

TOPICS = {
    "ar": [("general", "سؤال عام"), ("suggest", "اقتراح كتاب أو تحسين"), ("error", "الإبلاغ عن خطأ أو رابط معطّل"),
           ("copyright", "حقوق النشر"), ("ads", "الإعلانات والتعاون")],
    "en": [("general", "General question"), ("suggest", "Suggest a book or an improvement"), ("error", "Report an error or a broken link"),
           ("copyright", "Copyright"), ("ads", "Advertising and partnerships")],
}

L = {
    "ar": {
        "updated": "آخر تحديث: {d}",
        "about_d": "مكتبة الوراق مكتبة رقمية عربية مفتوحة تفهرس أكثر من مليون كتاب سقط عنها حق النشر، وتوصلك إلى نسخها المجانية في مصادرها الأصلية.",
        "privacy_d": "ما الذي تجمعه مكتبة الوراق من معلومات، وكيف تستخدمها، وكيف تعمل ملفات الكوكيز وإعلانات Google AdSense على الموقع.",
        "terms_d": "شروط استخدام مكتبة الوراق: طبيعة الخدمة، والملك العام وحقوق النشر، والاستخدام المقبول، وحدود المسؤولية.",
        "contact_d": "تواصل مع مكتبة الوراق: اقترح كتاباً، أو أبلغ عن خطأ أو رابط معطّل، أو اسأل عن حقوق النشر والإعلانات.",
        "f_name": "الاسم", "f_email": "بريدك الإلكتروني", "f_topic": "الموضوع", "f_msg": "رسالتك", "f_send": "إرسال الرسالة",
        "f_hp": "اترك هذا الحقل فارغاً",
        "f_note": "نستخدم اسمك وبريدك للرد عليك فقط، كما توضح {p}.",
        "mail": "أو راسلنا مباشرة على:",
        "sent": "شكراً لك! وصلت رسالتك، وسنرد عليك على بريدك في أقرب وقت.",
        "e_name": "اكتب اسمك من فضلك.", "e_email": "عنوان البريد الإلكتروني غير صحيح.",
        "e_msg": "اكتب رسالة من 10 أحرف على الأقل و3000 حرف على الأكثر.",
        "e_form": "انتهت صلاحية النموذج. أعد إرسال الرسالة من فضلك.", "e_many": "أرسلت رسائل كثيرة اليوم. حاول مرة أخرى غداً.",
    },
    "en": {
        "updated": "Last updated: {d}",
        "about_d": "Al-Warraq is an open Arabic digital library that indexes over a million public-domain books and leads you to their free copies at the original sources.",
        "privacy_d": "What Al-Warraq Library collects, how it is used, and how cookies and Google AdSense ads work on the site.",
        "terms_d": "Terms of use of Al-Warraq Library: the service, the public domain and copyright, acceptable use and liability.",
        "contact_d": "Contact Al-Warraq Library: suggest a book, report an error or a broken link, or ask about copyright and advertising.",
        "f_name": "Name", "f_email": "Your email", "f_topic": "Subject", "f_msg": "Your message", "f_send": "Send message",
        "f_hp": "Leave this field empty",
        "f_note": "We use your name and email only to reply to you, as our {p} explains.",
        "mail": "Or write to us directly at:",
        "sent": "Thank you! Your message has arrived and we will reply to your email soon.",
        "e_name": "Please write your name.", "e_email": "That email address does not look right.",
        "e_msg": "Please write a message of 10 to 3,000 characters.",
        "e_form": "This form has expired. Please send your message again.", "e_many": "You have sent many messages today. Please try again tomorrow.",
    },
}


for _ui in L:
    L[_ui].update(dict(LEGAL[_ui]))  # the page titles


def link(page: str, ui: str) -> str:
    return "/" + page + ("?lang=en" if ui == "en" else "")


def contact_email() -> str:
    e = os.environ.get("CONTACT_EMAIL", "").strip() or EMAIL_DEFAULT
    return e if EMAIL.match(e) else ""


# ---------- the texts ----------

def _about(ui, n):
    num = lambda k: "{:,}".format(n.get(k, 0))  # noqa: E731
    if ui == "ar":
        return f"""
<p class="lead">مكتبة الوراق مكتبة رقمية عربية مفتوحة، تفهرس الكتب التي سقط عنها حق النشر وتوصل القارئ إلى نسخها المجانية القانونية في مصادرها الأصلية.</p>
<h2>من نحن</h2>
<p>سمّينا المكتبة باسم «الورّاقين»، نسّاخ الكتب وباعتها في بغداد العباسية، الذين جعلوا سوق الورّاقين ملتقى للعلماء والقرّاء. وعلى خطاهم نريد أن يصل كل قارئ عربي إلى الكتاب المجاني بسهولة، من هاتفه أو حاسوبه، بلا اشتراك ولا تسجيل.</p>
<h2>رسالتنا</h2>
<p>أن نجمع تراث الإنسانية المتاح للجميع في مكان واحد وبلغة عربية سهلة: كتاب تبحث عنه بالعنوان أو باسم المؤلف، مصنّف في أبواب واضحة، بغلافه ونبذة عنه، ومعه رابط مباشر لقراءته كاملاً.</p>
<h2>ماذا تجد في المكتبة</h2>
<ul>
<li><b>{num("books")} كتاب</b> في الملك العام بـ{num("langs")} لغة، من مشروع غوتنبرغ وHathiTrust وOpen Library وأرشيف الإنترنت.</li>
<li><b>ديوان العرب:</b> {num("poems")} قصيدة لكبار الشعراء من الجاهلية إلى العصر الحديث، من ويكي مصدر.</li>
<li><b>{num("authors")} مؤلف</b> و{num("cats")} تصنيفاً، من الرواية والشعر إلى التاريخ والفلسفة والطب.</li>
<li><b>{num("modern")} كتاب عربي حديث</b> (روايات وتنمية بشرية وغيرها): ما نشرته «صفحات» (مؤسسة هنداوي) مجاناً بإذن أصحابه تقرؤه هناك كاملاً، وما حقوقه محفوظة نعرض بيانات فهرسته ونوصلك إلى صفحته في Open Library.</li>
<li><b>مكتب البحوث:</b> أوراق علمية طبية وهندسية مجانية الوصول، نبحث عنها في OpenAlex.</li>
</ul>
<h2>كيف نعمل</h2>
<p>لا نستضيف ملفات الكتب ولا نبيعها. نجمع بيانات الفهرسة من مصادر مفتوحة، ونرتّبها ونصنّفها ونعرّب عناوين الكتب المشهورة وأسماء مؤلفيها، ثم نوصلك إلى صفحة القراءة في المصدر الأصلي. القراءة مجانية تماماً.</p>
<h2>مبادئنا</h2>
<ul>
<li><b>مجانية دائماً</b> للقارئ، بلا حسابات ولا اشتراكات.</li>
<li><b>احترام الخصوصية:</b> إحصاءاتنا مجهولة الهوية، كما توضح <a href="{link("privacy", ui)}">سياسة الخصوصية</a>.</li>
<li><b>احترام حقوق النشر:</b> لا نعرض نص أي كتاب محفوظ الحقوق، بل بيانات فهرسته ورابطاً إلى مصدر قانوني يعرضه، ونراجع أي بلاغ ونزيل الرابط إن ثبت أنه يخالف حقاً.</li>
</ul>
<h2>تواصل معنا</h2>
<p>اقتراحاتك تصنع المكتبة: إن أردت كتاباً لم تجده، أو لاحظت خطأً، فـ<a href="{link("contact", ui)}">راسلنا</a>.</p>"""
    return f"""
<p class="lead">Al-Warraq is an open Arabic digital library. It indexes books that have left copyright and leads readers to their free, legal copies at the original sources.</p>
<h2>Who we are</h2>
<p>The library is named after the <i>warraqin</i>, the copyists and booksellers of Abbasid Baghdad whose market was a meeting place for scholars and readers. In their footsteps, we want every reader to reach free books easily, from a phone or a computer, with no subscription and no sign-up.</p>
<h2>Our mission</h2>
<p>To gather humanity's free heritage in one place, in plain Arabic and English: books you can search by title or author, sorted into clear categories, with covers and short descriptions, and a direct link to read them in full.</p>
<h2>What you will find</h2>
<ul>
<li><b>{num("books")} public-domain books</b> in {num("langs")} languages, from Project Gutenberg, HathiTrust, Open Library and the Internet Archive.</li>
<li><b>Diwan of the Arabs:</b> {num("poems")} poems by the great Arab poets, from pre-Islamic times to the modern era, from Arabic Wikisource.</li>
<li><b>{num("authors")} authors</b> and {num("cats")} categories, from novels and poetry to history, philosophy and medicine.</li>
<li><b>{num("modern")} modern Arabic books</b> (novels, self-development and more): those Safahat (Hindawi Foundation) publishes free with their owners' permission are read in full there; for books under copyright we show the catalogue record and link to their Open Library page.</li>
<li><b>The research desk:</b> free-to-read medical and engineering papers, found through OpenAlex.</li>
</ul>
<h2>How it works</h2>
<p>We do not host or sell book files. We gather catalogue data from open sources, sort and categorise it, translate the titles of famous books and the names of their authors, and send you to the reading page at the original source. Reading is completely free.</p>
<h2>Our principles</h2>
<ul>
<li><b>Always free</b> for readers: no accounts, no subscriptions.</li>
<li><b>Privacy first:</b> our statistics are anonymous, as the <a href="{link("privacy", ui)}">privacy policy</a> explains.</li>
<li><b>Respect for copyright:</b> we never show the text of a book under copyright, only its catalogue record and a link to a legal source that shows it; we review every report and remove a link if it infringes.</li>
</ul>
<h2>Get in touch</h2>
<p>Your suggestions shape the library. If a book is missing or something is wrong, <a href="{link("contact", ui)}">write to us</a>.</p>"""


def _privacy(ui):
    if ui == "ar":
        return f"""
<p class="lead">توضح هذه السياسة ما تجمعه مكتبة الوراق («الموقع» أو «نحن») من معلومات عند استخدامك للموقع، وكيف نستخدمها، وما خياراتك. باستخدامك للموقع فأنت توافق على هذه السياسة.</p>
<h2>1. المعلومات التي نجمعها</h2>
<ul>
<li><b>لا حسابات:</b> تتصفح المكتبة وتقرأ بلا تسجيل، ولا نطلب اسمك أو بريدك إلا إذا كتبتهما بنفسك في نموذج الاتصال.</li>
<li><b>إحصاءات مجهولة الهوية:</b> لنعدّ الزوار والمشاهدات والإعجابات والعبارات الأكثر بحثاً، نحسب رمزاً مجهولاً من عنوان IP ونوع المتصفح مع قيمة سرية (تجزئة SHA-256). لا نحفظ عنوان IP ولا نوع المتصفح نفسيهما. تُحذف رموز الزيارات اليومية بعد 3 أيام، ورموز الشهر والسنة بانتهاء الفترة. ونحفظ عبارات البحث بلا اسم أصحابها لنعرض «الأكثر بحثاً».</li>
<li><b>نموذج الاتصال:</b> الاسم والبريد الإلكتروني والرسالة التي ترسلها، نستخدمها للرد عليك فقط، وتُحذف تلقائياً بعد 12 شهراً.</li>
<li><b>سجلات الخادم:</b> قد يحتفظ مزوّد الاستضافة مؤقتاً بسجلات تقنية (مثل عنوان IP ووقت الطلب) لأغراض الأمان ومنع الإساءة.</li>
<li><b>التخزين المحلي في متصفحك:</b> نحفظ فيه اختيارك للغة والمظهر (فاتح أو داكن) فقط، ولا يُرسل إلينا.</li>
</ul>
<h2>2. ملفات تعريف الارتباط (الكوكيز)</h2>
<p>الكوكيز ملفات نصية صغيرة تحفظها المواقع في متصفحك. لا يضع موقعنا كوكيز لتتبعك، لكن أطرافاً ثالثة، منها Google، قد تستخدمها عند عرض الإعلانات كما يوضح البند التالي. يمكنك ضبط متصفحك لرفض الكوكيز أو حذفها في أي وقت، وقد يغيّر ذلك الإعلانات التي تراها.</p>
<h2>3. الإعلانات وGoogle AdSense</h2>
<p>قد نعرض إعلانات من خلال Google AdSense لتغطية تكاليف تشغيل المكتبة وإبقائها مجانية:</p>
<ul>
<li>يستخدم موردو الجهات الخارجية، ومنهم Google، ملفات تعريف الارتباط لعرض الإعلانات استناداً إلى زياراتك السابقة لهذا الموقع أو لمواقع أخرى على الإنترنت.</li>
<li>يتيح استخدام Google لملفات تعريف ارتباط الإعلانات لها ولشركائها عرض إعلانات لك استناداً إلى زيارتك لهذا الموقع و/أو لمواقع أخرى على الإنترنت.</li>
<li>يمكنك إيقاف الإعلانات المخصّصة من <a href="https://adssettings.google.com" rel="noopener" target="_blank">إعدادات الإعلانات في Google</a>، كما يمكنك إيقاف استخدام موردين آخرين لملفات تعريف الارتباط للإعلانات المخصّصة عبر <a href="https://www.aboutads.info/choices/" rel="noopener" target="_blank">www.aboutads.info</a>.</li>
<li>لمعرفة المزيد عن طريقة استخدام Google للبيانات، راجع <a href="https://policies.google.com/technologies/partner-sites" rel="noopener" target="_blank">كيف تستخدم Google المعلومات من المواقع التي تستخدم خدماتها</a> و<a href="https://policies.google.com/technologies/ads" rel="noopener" target="_blank">طريقة استخدام Google للكوكيز في الإعلانات</a>.</li>
<li>للزوار من المنطقة الاقتصادية الأوروبية والمملكة المتحدة وسويسرا: نطلب موافقتك قبل استخدام الكوكيز في الإعلانات المخصّصة، كما تفرض القوانين هناك.</li>
</ul>
<h2>4. خدمات أطراف ثالثة أخرى</h2>
<p>يحمّل متصفحك بعض المحتوى من خدمات خارجية، وتتلقى هذه الخدمات عنوان IP الخاص بك كما يحدث في أي طلب على الإنترنت:</p>
<ul>
<li>الخطوط من Google Fonts.</li>
<li>أغلفة الكتب من Open Library ومشروع غوتنبرغ وHathiTrust ومؤسسة هنداوي، ونبذ المؤلفين من ويكيبيديا في صفحات الكتب.</li>
<li>روابط القراءة تنقلك إلى مواقع خارجية تحكمها سياسات الخصوصية الخاصة بها.</li>
<li>عبارات البحث في مكتب البحوث يرسلها خادمنا إلى OpenAlex للعثور على الأوراق العلمية.</li>
</ul>
<h2>5. كيف نستخدم المعلومات</h2>
<p>لتشغيل الموقع وتحسينه، ولعرض الكتب الأكثر مشاهدة والعبارات الأكثر بحثاً، وللرد على رسائلك، ولحماية الموقع من الإساءة. لا نبيع بياناتك، ولا نشاركها إلا مع مزوّدي الخدمات المذكورين أعلاه، أو إذا ألزمنا القانون بذلك.</p>
<h2>6. الأطفال</h2>
<p>الموقع موجّه لعامة القرّاء، ولا نجمع عن قصد بيانات شخصية من أطفال دون 13 عاماً. إن علمت أن طفلاً أرسل إلينا بياناته فراسلنا لنحذفها.</p>
<h2>7. حقوقك</h2>
<p>يمكنك أن تطلب الاطلاع على رسالة أرسلتها إلينا أو حذفها عبر <a href="{link("contact", ui)}">صفحة الاتصال</a>. أما الإحصاءات فمجهولة الهوية ولا يمكن ربطها بشخصك.</p>
<h2>8. الأمان</h2>
<p>نستخدم اتصالاً مشفراً (HTTPS) وضوابط أمنية ونحدّ من الطلبات المتكررة، لكن لا توجد وسيلة نقل أو تخزين على الإنترنت آمنة تماماً.</p>
<h2>9. التعديلات</h2>
<p>قد نحدّث هذه السياسة من وقت لآخر، وننشر تاريخ آخر تحديث في أعلى الصفحة.</p>
<h2>10. اتصل بنا</h2>
<p>لأي سؤال عن الخصوصية، <a href="{link("contact", ui)}">راسلنا من هنا</a>.</p>"""
    return f"""
<p class="lead">This policy explains what information Al-Warraq Library (“the site”, “we”) collects when you use the site, how we use it and the choices you have. By using the site you agree to this policy.</p>
<h2>1. Information we collect</h2>
<ul>
<li><b>No accounts:</b> you browse and read without signing up. We never ask for your name or email unless you type them into the contact form yourself.</li>
<li><b>Anonymous statistics:</b> to count visitors, views, likes and popular searches we compute an anonymous code from your IP address and browser type together with a secret value (a SHA-256 hash). We do not store the IP address or the browser type themselves. Daily visit codes are deleted after 3 days; monthly and yearly codes when the period ends. Search phrases are kept without any link to who searched, to show “most searched”.</li>
<li><b>Contact form:</b> the name, email address and message you send. We use them only to reply to you, and they are deleted automatically after 12 months.</li>
<li><b>Server logs:</b> our hosting provider may keep technical logs (such as IP address and time of request) for a short time, for security and abuse prevention.</li>
<li><b>Local storage in your browser:</b> only your choice of language and theme (light or dark). It is never sent to us.</li>
</ul>
<h2>2. Cookies</h2>
<p>Cookies are small text files that websites store in your browser. Our site does not set cookies to track you, but third parties, including Google, may use cookies when showing ads, as described below. You can set your browser to refuse or delete cookies at any time; this may change the ads you see.</p>
<h2>3. Advertising and Google AdSense</h2>
<p>We may show ads through Google AdSense to cover the costs of running the library and keep it free:</p>
<ul>
<li>Third-party vendors, including Google, use cookies to serve ads based on your prior visits to this website or other websites.</li>
<li>Google's use of advertising cookies enables it and its partners to serve ads to you based on your visit to this site and/or other sites on the Internet.</li>
<li>You may opt out of personalised advertising by visiting <a href="https://adssettings.google.com" rel="noopener" target="_blank">Google Ads Settings</a>. You can also opt out of a third-party vendor's use of cookies for personalised advertising at <a href="https://www.aboutads.info/choices/" rel="noopener" target="_blank">www.aboutads.info</a>.</li>
<li>To learn more, see <a href="https://policies.google.com/technologies/partner-sites" rel="noopener" target="_blank">how Google uses information from sites that use its services</a> and <a href="https://policies.google.com/technologies/ads" rel="noopener" target="_blank">how Google uses cookies in advertising</a>.</li>
<li>Visitors from the European Economic Area, the United Kingdom and Switzerland are asked for consent before cookies are used for personalised ads, as the law there requires.</li>
</ul>
<h2>4. Other third-party services</h2>
<p>Your browser loads some content from outside services, which receive your IP address as with any request on the Internet:</p>
<ul>
<li>Fonts from Google Fonts.</li>
<li>Book covers from Open Library, Project Gutenberg, HathiTrust and the Hindawi Foundation; author summaries from Wikipedia on book pages.</li>
<li>Reading links take you to external sites governed by their own privacy policies.</li>
<li>Research-desk searches are sent by our server to OpenAlex to find papers.</li>
</ul>
<h2>5. How we use information</h2>
<p>To run and improve the site, to show the most viewed books and most searched phrases, to reply to your messages and to protect the site from abuse. We do not sell your data, and we share it only with the service providers above, or when the law requires it.</p>
<h2>6. Children</h2>
<p>The site is meant for the general public, and we do not knowingly collect personal data from children under 13. If you learn that a child has sent us personal data, contact us and we will delete it.</p>
<h2>7. Your rights</h2>
<p>You can ask to see or delete a message you sent us through the <a href="{link("contact", ui)}">contact page</a>. Statistics are anonymous and cannot be linked to you.</p>
<h2>8. Security</h2>
<p>We use encrypted connections (HTTPS), security controls and rate limits, but no method of transmission or storage on the Internet is completely secure.</p>
<h2>9. Changes</h2>
<p>We may update this policy from time to time and will show the date of the latest update at the top of this page.</p>
<h2>10. Contact</h2>
<p>For any privacy question, <a href="{link("contact", ui)}">write to us here</a>.</p>"""


def _terms(ui):
    if ui == "ar":
        return f"""
<p class="lead">مرحباً بك في مكتبة الوراق. باستخدامك للموقع فأنت توافق على الشروط التالية؛ وإن لم توافق عليها فنرجو ألا تستخدم الموقع.</p>
<h2>1. طبيعة الخدمة</h2>
<p>مكتبة الوراق فهرس مجاني يدلّك على كتب في الملك العام وبحوث علمية مجانية الوصول في مواقع خارجية. لا نستضيف ملفات الكتب ولا نملكها، ولا نبيع أي محتوى.</p>
<h2>2. الملك العام وحقوق النشر</h2>
<p>نصنّف الكتب بحسب بيانات مصادرها، ومعظمها في الملك العام في الولايات المتحدة. قد يختلف وضع العمل نفسه في بلدك، وأنت المسؤول عن التحقق من قانون بلدك قبل تنزيل أي عمل أو إعادة نشره.</p>
<p>ونعرض أيضاً كتباً عربية حديثة محفوظة الحقوق، تحمل صفحاتها شارة توضح ذلك: لا ننشر نصها، بل بيانات فهرستها (العنوان والمؤلف والناشر والسنة) ورابطاً إلى صفحتها لدى مصدر قانوني، مثل «صفحات» (مؤسسة هنداوي) التي تتيحها بإذن أصحابها، أو Open Library.</p>
<h2>3. المواقع الخارجية</h2>
<p>روابط القراءة والتنزيل تقود إلى مواقع خارجية لا نتحكم في محتواها أو سياساتها أو توافرها، ولا نتحمل مسؤوليتها.</p>
<h2>4. دقة المعلومات</h2>
<p>نجمع بيانات الفهرسة (العناوين وأسماء المؤلفين وترجماتها والأغلفة والتصنيفات) من مصادر مفتوحة، وقد تقع فيها أخطاء. تُقدَّم الخدمة «كما هي» و«حسب توافرها» بلا أي ضمانات صريحة أو ضمنية.</p>
<h2>5. الاستخدام المقبول</h2>
<p>يُمنع عليك:</p>
<ul>
<li>إرهاق الخادم بالطلبات الآلية أو الزحف المكثف أو تجاوز حدود الطلبات.</li>
<li>محاولة اختراق الموقع أو تعطيله أو الوصول إلى أجزاء غير مخصصة للعامة.</li>
<li>استخدام نموذج الاتصال للإزعاج أو للرسائل غير المرغوب فيها.</li>
<li>أي استخدام يخالف القانون أو يضر بالآخرين.</li>
</ul>
<h2>6. الملكية الفكرية</h2>
<p>تصميم الموقع وشعاره وشيفرته البرمجية ونصوصه التعريفية ملك لمكتبة الوراق. أما نصوص الكتب فهي في الملك العام، وأسماء المصادر وعلاماتها التجارية ملك أصحابها.</p>
<h2>7. بلاغات حقوق النشر</h2>
<p>إن رأيت أن رابطاً في المكتبة يخالف حقوقك، <a href="{link("contact", ui)}">راسلنا</a> واذكر اسم العمل ورابطه وصفتك، وسنراجع البلاغ ونزيل الرابط إن ثبتت المخالفة.</p>
<h2>8. الإعلانات</h2>
<p>قد يعرض الموقع إعلانات من Google وشركائها. ظهور إعلان لا يعني أننا نؤيد المعلن أو منتجه، وأي تعامل بينك وبين المعلن شأن بينكما وحدكما.</p>
<h2>9. حدود المسؤولية</h2>
<p>في أقصى حدّ يسمح به القانون، لا تتحمل مكتبة الوراق مسؤولية أي ضرر مباشر أو غير مباشر ينتج عن استخدامك للموقع أو للمواقع الخارجية التي يدلّك عليها.</p>
<h2>10. التعديلات</h2>
<p>قد نعدّل هذه الشروط أو الخدمة في أي وقت، وننشر تاريخ آخر تحديث في أعلى الصفحة. استمرارك في استخدام الموقع بعد التعديل يعني قبولك للشروط الجديدة.</p>
<h2>11. التواصل</h2>
<p>لأي سؤال عن هذه الشروط، <a href="{link("contact", ui)}">راسلنا من هنا</a>. وتجد طريقة تعاملنا مع بياناتك في <a href="{link("privacy", ui)}">سياسة الخصوصية</a>.</p>"""
    return f"""
<p class="lead">Welcome to Al-Warraq Library. By using the site you agree to the following terms; if you do not agree, please do not use the site.</p>
<h2>1. The service</h2>
<p>Al-Warraq Library is a free index that points to public-domain books and free-to-read research on external websites. We do not host or own book files, and we do not sell any content.</p>
<h2>2. Public domain and copyright</h2>
<p>Books are classified according to the data of their sources, and most are in the public domain in the United States. The status of a work may differ in your country; you are responsible for checking your local law before downloading or republishing any work.</p>
<p>We also list modern Arabic books that are under copyright; their pages say so. We never publish their text, only their catalogue record (title, author, publisher, year) and a link to their page at a legal source, such as Safahat (Hindawi Foundation), which offers them with their owners' permission, or Open Library.</p>
<h2>3. External websites</h2>
<p>Reading and download links lead to external websites. We do not control their content, policies or availability, and we are not responsible for them.</p>
<h2>4. Accuracy</h2>
<p>We gather catalogue data (titles, author names and their translations, covers and categories) from open sources, and it may contain errors. The service is provided “as is” and “as available”, without warranties of any kind, express or implied.</p>
<h2>5. Acceptable use</h2>
<p>You must not:</p>
<ul>
<li>overload the server with automated requests, heavy crawling or by working around rate limits;</li>
<li>attempt to break into, disrupt or reach non-public parts of the site;</li>
<li>use the contact form to harass anyone or to send spam;</li>
<li>use the site in any way that breaks the law or harms others.</li>
</ul>
<h2>6. Intellectual property</h2>
<p>The site's design, logo, code and descriptive texts belong to Al-Warraq Library. Book texts are in the public domain; the names and trademarks of the sources belong to their owners.</p>
<h2>7. Copyright reports</h2>
<p>If you believe a link in the library infringes your rights, <a href="{link("contact", ui)}">contact us</a> with the title of the work, its link and your capacity, and we will review the report and remove the link if it infringes.</p>
<h2>8. Advertising</h2>
<p>The site may show ads from Google and its partners. An ad does not mean that we endorse the advertiser or the product, and any dealings between you and an advertiser are between you and the advertiser alone.</p>
<h2>9. Limitation of liability</h2>
<p>To the fullest extent permitted by law, Al-Warraq Library is not liable for any direct or indirect damage arising from your use of the site or of the external sites it points to.</p>
<h2>10. Changes</h2>
<p>We may change these terms or the service at any time and will show the date of the latest update at the top of this page. Using the site after a change means you accept the new terms.</p>
<h2>11. Contact</h2>
<p>For any question about these terms, <a href="{link("contact", ui)}">write to us here</a>. How we handle your data is described in the <a href="{link("privacy", ui)}">privacy policy</a>.</p>"""


# ---------- the contact form ----------

def _secret(conn) -> bytes:
    return stats._salt(conn).encode()


def form_token(conn, now=None) -> str:
    ts = str(int(now if now is not None else time.time()))
    return ts + "." + hmac.new(_secret(conn), ts.encode(), hashlib.sha256).hexdigest()[:20]


def token_ok(conn, token: str, now=None) -> bool:
    ts, _, sig = (token or "").partition(".")
    if not ts.isdigit() or not hmac.compare_digest(sig, form_token(conn, int(ts)).partition(".")[2]):
        return False
    age = (now if now is not None else time.time()) - int(ts)
    return MIN_AGE <= age <= MAX_AGE


def _contact(conn, ui, values=None, error="", sent=False):
    l, v = L[ui], values or {}
    if sent:
        return '<p class="notice ok" role="status">%s</p><p><a href="%s">%s</a></p>' % (esc(l["sent"]), "/" + ("?lang=en" if ui == "en" else ""), esc(T[ui]["home"]))
    intro = ("<p class=\"lead\">يسعدنا أن نسمع منك: اقترح كتاباً لم تجده، أو أبلغ عن خطأ أو رابط معطّل، أو اسأل عن حقوق النشر والإعلانات.</p>"
             if ui == "ar" else
             "<p class=\"lead\">We would love to hear from you: suggest a book you could not find, report an error or a broken link, or ask about copyright and advertising.</p>")
    mail = contact_email()
    if mail:
        intro += '<p class="mail">%s <a href="mailto:%s">%s</a></p>' % (esc(l["mail"]), esc(mail), esc(mail))
    topics = "".join('<option value="%s"%s>%s</option>' % (k, " selected" if v.get("topic") == k else "", esc(n)) for k, n in TOPICS[ui])
    err = '<p class="notice err" role="alert">%s</p>' % esc(error) if error else ""
    note = l["f_note"].format(p='<a href="%s">%s</a>' % (link("privacy", ui), esc(L[ui]["privacy"])))
    return """%s%s
<form class="contact" method="post" action="%s">
<label>%s<input name="name" maxlength="%d" required autocomplete="name" value="%s"></label>
<label>%s<input type="email" name="email" maxlength="%d" required autocomplete="email" dir="ltr" value="%s"></label>
<label>%s<select name="topic">%s</select></label>
<label>%s<textarea name="message" rows="7" minlength="10" maxlength="%d" required>%s</textarea></label>
<label class="hp" aria-hidden="true">%s<input name="website" tabindex="-1" autocomplete="off"></label>
<input type="hidden" name="t" value="%s">
<button type="submit">%s</button>
<p class="fine">%s</p>
</form>""" % (intro, err, link("contact", ui), esc(l["f_name"]), LIMITS["name"], esc(v.get("name", "")),
              esc(l["f_email"]), LIMITS["email"], esc(v.get("email", "")), esc(l["f_topic"]), topics,
              esc(l["f_msg"]), LIMITS["message"], esc(v.get("message", "")), esc(l["f_hp"]), form_token(conn), esc(l["f_send"]), note)


def parse_form(body: bytes) -> dict:
    data = parse_qs(body[:20000].decode("utf-8", "replace"), keep_blank_values=True)
    return {k: (data.get(k) or [""])[0] for k in ("name", "email", "topic", "message", "website", "t")}


def submit(conn, request, form: dict, ui: str):
    """Returns (ok, error message, cleaned values). A filled honeypot is accepted silently and dropped."""
    l = L[ui]
    v = {
        "name": " ".join(form.get("name", "").split())[:LIMITS["name"]],
        "email": form.get("email", "").strip()[:LIMITS["email"]],
        "topic": form.get("topic", "") if form.get("topic", "") in dict(TOPICS["en"]) else "general",
        "message": form.get("message", "").replace("\r\n", "\n").strip()[:LIMITS["message"]],
    }
    if form.get("website"):  # only bots fill a field nobody can see
        return True, "", v
    if not token_ok(conn, form.get("t", "")):
        return False, l["e_form"], v
    if not v["name"]:
        return False, l["e_name"], v
    if not EMAIL.match(v["email"]):
        return False, l["e_email"], v
    if not 10 <= len(v["message"]) <= LIMITS["message"]:
        return False, l["e_msg"], v
    who = stats.visitor_id(conn, request)
    now = int(time.time())
    if conn.execute("SELECT COUNT(*) FROM contact_messages WHERE visitor=? AND ts>?", (who, now - 86400)).fetchone()[0] >= PER_DAY:
        return False, l["e_many"], v
    conn.execute("INSERT INTO contact_messages(ts, name, email, topic, message, lang, visitor) VALUES(?,?,?,?,?,?,?)",
                 (now, v["name"], v["email"], v["topic"], v["message"], ui, who))
    conn.execute("DELETE FROM contact_messages WHERE ts<?", (now - KEEP_SECONDS,))
    conn.commit()
    return True, "", v


# ---------- page assembly ----------

EXTRA_CSS = """
.page{max-width:760px}
.page h1{margin:22px 0 4px}
.page .updated{margin:0 0 14px;color:var(--muted);font-size:.88rem}
.page .lead{font-size:1.08rem;color:var(--ink);margin:6px 0 10px}
.page h2{margin:26px 0 8px}
.page p,.page li{line-height:1.9}
.page ul{padding-inline-start:22px;margin:6px 0}
.page li{margin:4px 0}
.page li::marker{color:var(--brand)}
.contact{display:grid;gap:14px;margin:18px 0 8px;padding:20px;background:var(--card);border:1px solid var(--line);border-radius:20px;box-shadow:var(--shadow)}
.contact label{display:grid;gap:6px;font-weight:600;font-size:.94rem}
.contact input,.contact select,.contact textarea{font:inherit;font-weight:400;color:var(--ink);background:var(--bg);border:1.5px solid var(--line);border-radius:12px;padding:10px 12px;width:100%}
.contact textarea{resize:vertical;min-height:150px}
.contact input:focus,.contact select:focus,.contact textarea:focus{outline:0;border-color:var(--brand-2);box-shadow:0 0 0 4px color-mix(in srgb,var(--brand-2) 22%,transparent)}
.contact button{justify-self:start;border:0;border-radius:14px;padding:11px 26px;background:var(--btn);color:var(--brand-ink);font:600 1rem "IBM Plex Sans Arabic",sans-serif;cursor:pointer}
.contact{position:relative}
.contact .hp{position:absolute;inset-inline-start:0;top:0;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
.contact .fine{margin:0;color:var(--muted);font-size:.86rem}
.notice{padding:12px 16px;border-radius:14px;margin:16px 0}
.notice.ok{background:var(--soft);color:var(--brand);font-weight:600}
.notice.err{background:var(--rose-soft);color:var(--rose)}
.mail a{font-weight:600;direction:ltr;unicode-bidi:isolate}
"""


def page_html(kind: str, base: str, ui: str, conn=None, numbers=None, values=None, error="", sent=False) -> str:
    from .seo import _ld, _shell
    l = L[ui]
    body_html = {"about": lambda: _about(ui, numbers or {}), "privacy": lambda: _privacy(ui), "terms": lambda: _terms(ui),
                 "contact": lambda: _contact(conn, ui, values, error, sent)}[kind]()
    updated = '<p class="updated">%s</p>' % esc(l["updated"].format(d=UPDATED[ui])) if kind in ("privacy", "terms") else ""
    body = '<article class="page"><p class="crumbs"><a href="/%s">%s</a> / %s</p><h1>%s</h1>%s%s</article>' % (
        "?lang=en" if ui == "en" else "", esc(T[ui]["home"]), esc(l[kind]), esc(l[kind]), updated, body_html)
    types = {"about": "AboutPage", "contact": "ContactPage"}
    ld = _ld({"@context": "https://schema.org", "@type": types.get(kind, "WebPage"), "name": l[kind] + " | " + BRAND[ui],
              "url": base + "/" + kind, "inLanguage": ui, "isPartOf": {"@id": base + "/#site"}})
    return _shell(ui, base, "/" + kind, l[kind] + " | " + BRAND[ui], l[kind + "_d"], body, ld, extra_css=EXTRA_CSS)


# ---------- reading the messages ----------

def admin_password() -> str:
    return os.environ.get("ADMIN_PASSWORD", "")


def admin_ok(request) -> bool:
    import base64
    pw = admin_password()
    auth = request.headers.get("authorization", "")
    if not pw or not auth.lower().startswith("basic "):
        return False
    try:
        given = base64.b64decode(auth[6:].strip()).decode("utf-8", "replace").partition(":")[2]
    except ValueError:
        return False
    return secrets.compare_digest(given.encode(), pw.encode())


def admin_html(conn) -> str:
    rows = conn.execute("SELECT * FROM contact_messages ORDER BY id DESC LIMIT 300").fetchall()
    topics = dict(TOPICS["ar"])
    items = "".join(
        '<article><header><b>%s</b> &lt;<a href="mailto:%s">%s</a>&gt; · %s · %s</header><pre>%s</pre></article>'
        % (esc(r["name"]), esc(r["email"]), esc(r["email"]), esc(topics.get(r["topic"], r["topic"])),
           time.strftime("%Y-%m-%d %H:%M", time.gmtime(r["ts"])) + " UTC", esc(r["message"])) for r in rows)
    return ('<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="robots" content="noindex">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>رسائل الزوار</title><style>'
            'body{font:15px/1.7 system-ui,sans-serif;max-width:860px;margin:20px auto;padding:0 16px;background:#F2F0EA;color:#13201C}'
            'article{background:#fff;border:1px solid #E1DCD0;border-radius:14px;padding:12px 16px;margin:10px 0}'
            'pre{white-space:pre-wrap;font:inherit;margin:8px 0 0}header{color:#5A6762;font-size:.9rem}</style></head>'
            '<body><h1>رسائل الزوار (%d)</h1>%s</body></html>' % (len(rows), items or "<p>لا توجد رسائل بعد.</p>"))
