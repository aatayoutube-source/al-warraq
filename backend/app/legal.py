"""The pages every site needs before it shows ads (AdSense reviews them): about, privacy, terms, contact, and
the takedown form for rights holders.

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

from . import content, stats
from .pages import BRAND, LEGAL, T, UI_LANGS, esc, lang_q

# each page its own date: both changed with the second advertising network (the privacy policy also with the languages)
UPDATED = {"privacy": {"ar": "22 أكتوبر 2026", "en": "22 October 2026", "zh": "2026年10月22日", "fr": "22 octobre 2026",
                       "es": "22 de octubre de 2026", "pt": "22 de outubro de 2026", "ja": "2026年10月22日", "de": "22. Oktober 2026"},
           "terms": {"ar": "22 أكتوبر 2026", "en": "22 October 2026", "zh": "2026年10月22日", "fr": "22 octobre 2026",
                     "es": "22 de octubre de 2026", "pt": "22 de outubro de 2026", "ja": "2026年10月22日", "de": "22. Oktober 2026"}}
EMAIL_DEFAULT = "alwarraqibrary@gmail.com"  # the library's mailbox
PAGES = ("about", "privacy", "terms", "contact", "takedown")
THIN_PAGES = ("contact", "takedown")  # forms with a few lines around them: reachable from every page, not search results
KEEP_SECONDS = 365 * 86400  # contact messages are deleted after a year
PER_DAY = 5  # messages one visitor may send per day
MIN_AGE, MAX_AGE = 3, 2 * 86400  # seconds between showing the form and sending it
LIMITS = {"name": 80, "email": 120, "message": 3000, "url": 300}
EMAIL = re.compile(r"^[^@\s<>\"']{1,64}@[^@\s<>\"']+\.[^@\s<>\"']{2,}$")

TOPICS = {
    "ar": [("general", "سؤال عام"), ("suggest", "اقتراح كتاب أو تحسين"), ("error", "الإبلاغ عن خطأ أو رابط معطّل"),
           ("copyright", "حقوق النشر"), ("ads", "الإعلانات والتعاون")],
    "en": [("general", "General question"), ("suggest", "Suggest a book or an improvement"), ("error", "Report an error or a broken link"),
           ("copyright", "Copyright"), ("ads", "Advertising and partnerships")],
    "zh": [("general", "一般问题"), ("suggest", "推荐图书或改进建议"), ("error", "报告错误或失效链接"),
           ("copyright", "版权"), ("ads", "广告与合作")],
    "fr": [("general", "Question générale"), ("suggest", "Suggérer un livre ou une amélioration"),
           ("error", "Signaler une erreur ou un lien cassé"), ("copyright", "Droit d’auteur"), ("ads", "Publicité et partenariats")],
    "es": [("general", "Pregunta general"), ("suggest", "Sugerir un libro o una mejora"),
           ("error", "Informar de un error o un enlace roto"), ("copyright", "Derechos de autor"), ("ads", "Publicidad y colaboraciones")],
    "pt": [("general", "Dúvida geral"), ("suggest", "Sugerir um livro ou uma melhoria"),
           ("error", "Informar um erro ou link quebrado"), ("copyright", "Direitos autorais"), ("ads", "Publicidade e parcerias")],
    "ja": [("general", "一般的な質問"), ("suggest", "本や改善の提案"), ("error", "誤りやリンク切れの報告"),
           ("copyright", "著作権"), ("ads", "広告・提携")],
    "de": [("general", "Allgemeine Frage"), ("suggest", "Ein Buch oder eine Verbesserung vorschlagen"),
           ("error", "Einen Fehler oder defekten Link melden"), ("copyright", "Urheberrecht"), ("ads", "Werbung und Kooperationen")],
}
TOPIC_NAMES = dict(TOPICS["ar"], takedown="طلب إزالة محتوى")  # as the messages page shows them

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
        "takedown_d": "إن كنت صاحب حق في عمل تعرضه مكتبة الوراق، اطلب إزالته من هنا: اذكر الصفحة وسبب الطلب، ونراجعه ونرد عليك.",
        "t_lead": "إن كنت صاحب حق في عمل تعرضه مكتبة الوراق، أو تمثّل صاحب الحق، فاملأ هذا النموذج. نراجع كل طلب، ونزيل الرابط أو بيانات الكتاب إن ثبت أنها تخالف حقاً، ونرد عليك على بريدك.",
        "t_what": "تذكّر أن المكتبة لا تستضيف ملفات الكتب، بل تعرض بيانات الفهرسة ورابطاً إلى المصدر. فإن كان الملف نفسه منشوراً على موقع آخر، فراسل ذلك الموقع أيضاً.",
        "f_url": "رابط الصفحة في المكتبة", "f_reason": "سبب الطلب: ما حقك في العمل، ولماذا تطلب إزالته؟", "f_send_t": "إرسال طلب الإزالة",
        "sent_t": "وصل طلبك. سنراجعه ونرد عليك على بريدك في أقرب وقت.",
        "e_url": "اكتب رابط الصفحة المقصودة في المكتبة.", "e_reason": "اشرح سبب الطلب في 20 حرفاً على الأقل.",
        "c_lead": "يسعدنا أن نسمع منك: اقترح كتاباً لم تجده، أو أبلغ عن خطأ أو رابط معطّل، أو اسأل عن حقوق النشر والإعلانات.",
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
        "takedown_d": "If you hold rights in a work shown by Al-Warraq Library, ask for its removal here: name the page and the reason, and we will review it and reply.",
        "t_lead": "If you hold rights in a work shown by Al-Warraq Library, or act for the rights holder, fill in this form. We review every request, remove the link or the record if it infringes a right, and reply to your email.",
        "t_what": "Remember that the library hosts no book files: it shows catalogue records and a link to the source. If the file itself is published on another site, write to that site as well.",
        "f_url": "Address of the page in the library", "f_reason": "Reason: what right do you hold in the work, and why should it be removed?", "f_send_t": "Send the removal request",
        "sent_t": "Your request has arrived. We will review it and reply to your email soon.",
        "e_url": "Please give the address of the page in the library.", "e_reason": "Please explain the reason in at least 20 characters.",
        "c_lead": "We would love to hear from you: suggest a book you could not find, report an error or a broken link, or ask about copyright and advertising.",
    },
    "zh": {
        "updated": "最后更新：{d}",
        "about_d": "Al-Warraq 图书馆是一个开放的阿拉伯数字图书馆，为超过一百万本公有领域图书建立索引，并带你前往原始来源中的免费副本。",
        "privacy_d": "Al-Warraq 图书馆收集哪些信息、如何使用，以及 Cookie 和 Google AdSense 广告在本站如何运作。",
        "terms_d": "Al-Warraq 图书馆的使用条款：服务性质、公有领域与版权、可接受的使用方式以及责任限制。",
        "contact_d": "联系 Al-Warraq 图书馆：推荐图书、报告错误或失效链接，或咨询版权与广告事宜。",
        "f_name": "姓名", "f_email": "你的电子邮箱", "f_topic": "主题", "f_msg": "留言内容", "f_send": "发送留言",
        "f_hp": "请勿填写此栏",
        "f_note": "我们只会用你的姓名和邮箱回复你，详见{p}。",
        "mail": "或直接写信给我们：",
        "sent": "谢谢！我们已收到你的留言，会尽快通过邮件回复你。",
        "e_name": "请填写你的姓名。", "e_email": "电子邮箱地址似乎不正确。",
        "e_msg": "请填写 10 到 3,000 个字符的留言。",
        "e_form": "表单已过期，请重新发送留言。", "e_many": "你今天发送的留言太多了，请明天再试。",
        "takedown_d": "如果你对 Al-Warraq 图书馆展示的某部作品拥有权利，可以在这里申请移除：注明页面和理由，我们会审核并回复你。",
        "t_lead": "如果你对 Al-Warraq 图书馆展示的某部作品拥有权利，或代表权利人行事，请填写此表单。我们会审核每一项申请，如确认侵权，将移除相关链接或书目信息，并通过邮件回复你。",
        "t_what": "请注意，本图书馆不存放图书文件，只展示书目信息和指向来源的链接。如果文件本身发布在其他网站上，也请联系该网站。",
        "f_url": "图书馆中该页面的地址", "f_reason": "理由：你对这部作品拥有什么权利？为什么要求移除？", "f_send_t": "提交移除申请",
        "sent_t": "我们已收到你的申请，会尽快审核并通过邮件回复你。",
        "e_url": "请填写图书馆中相关页面的地址。", "e_reason": "请用至少 20 个字符说明理由。",
        "c_lead": "很高兴收到你的来信：推荐一本你没找到的书，报告错误或失效链接，或咨询版权与广告事宜。",
        "en_only": "本页面提供阿拉伯语和英语版本，以下显示英语版本。",
    },
    "fr": {
        "updated": "Dernière mise à jour : {d}",
        "about_d": "Al-Warraq est une bibliothèque numérique arabe ouverte qui indexe plus d’un million de livres du domaine public et vous mène à leurs copies gratuites aux sources d’origine.",
        "privacy_d": "Ce que la Bibliothèque Al-Warraq collecte, comment ces données sont utilisées, et comment fonctionnent les cookies et les annonces Google AdSense sur le site.",
        "terms_d": "Conditions d’utilisation de la Bibliothèque Al-Warraq : le service, le domaine public et le droit d’auteur, l’usage acceptable et la responsabilité.",
        "contact_d": "Contactez la Bibliothèque Al-Warraq : suggérez un livre, signalez une erreur ou un lien cassé, ou posez une question sur le droit d’auteur et la publicité.",
        "f_name": "Nom", "f_email": "Votre e-mail", "f_topic": "Objet", "f_msg": "Votre message", "f_send": "Envoyer le message",
        "f_hp": "Laissez ce champ vide",
        "f_note": "Nous utilisons votre nom et votre e-mail uniquement pour vous répondre, comme l’explique notre {p}.",
        "mail": "Ou écrivez-nous directement à :",
        "sent": "Merci ! Votre message est bien arrivé et nous vous répondrons bientôt par e-mail.",
        "e_name": "Veuillez indiquer votre nom.", "e_email": "Cette adresse e-mail ne semble pas valide.",
        "e_msg": "Veuillez écrire un message de 10 à 3 000 caractères.",
        "e_form": "Ce formulaire a expiré. Veuillez renvoyer votre message.", "e_many": "Vous avez envoyé beaucoup de messages aujourd’hui. Veuillez réessayer demain.",
        "takedown_d": "Si vous détenez des droits sur une œuvre présentée par la Bibliothèque Al-Warraq, demandez son retrait ici : indiquez la page et le motif, nous l’examinerons et vous répondrons.",
        "t_lead": "Si vous détenez des droits sur une œuvre présentée par la Bibliothèque Al-Warraq, ou agissez pour le compte de l’ayant droit, remplissez ce formulaire. Nous examinons chaque demande, retirons le lien ou la notice s’ils portent atteinte à un droit, et vous répondons par e-mail.",
        "t_what": "Rappelons que la bibliothèque n’héberge aucun fichier : elle affiche des notices et un lien vers la source. Si le fichier lui-même est publié sur un autre site, écrivez aussi à ce site.",
        "f_url": "Adresse de la page dans la bibliothèque", "f_reason": "Motif : quel droit détenez-vous sur l’œuvre, et pourquoi faut-il la retirer ?", "f_send_t": "Envoyer la demande de retrait",
        "sent_t": "Votre demande est bien arrivée. Nous l’examinerons et vous répondrons bientôt par e-mail.",
        "e_url": "Veuillez indiquer l’adresse de la page dans la bibliothèque.", "e_reason": "Veuillez expliquer le motif en au moins 20 caractères.",
        "c_lead": "Nous serions ravis d’avoir de vos nouvelles : suggérez un livre introuvable, signalez une erreur ou un lien cassé, ou posez une question sur le droit d’auteur et la publicité.",
        "en_only": "Cette page existe en arabe et en anglais ; la version anglaise est affichée ci-dessous.",
    },
    "es": {
        "updated": "Última actualización: {d}",
        "about_d": "Al-Warraq es una biblioteca digital árabe abierta que indexa más de un millón de libros de dominio público y te lleva a sus copias gratuitas en las fuentes originales.",
        "privacy_d": "Qué información recoge la Biblioteca Al-Warraq, cómo se usa y cómo funcionan las cookies y los anuncios de Google AdSense en el sitio.",
        "terms_d": "Términos de uso de la Biblioteca Al-Warraq: el servicio, el dominio público y los derechos de autor, el uso aceptable y la responsabilidad.",
        "contact_d": "Contacta con la Biblioteca Al-Warraq: sugiere un libro, informa de un error o un enlace roto, o pregunta sobre derechos de autor y publicidad.",
        "f_name": "Nombre", "f_email": "Tu correo electrónico", "f_topic": "Asunto", "f_msg": "Tu mensaje", "f_send": "Enviar mensaje",
        "f_hp": "Deja este campo vacío",
        "f_note": "Usamos tu nombre y tu correo solo para responderte, como explica nuestra {p}.",
        "mail": "O escríbenos directamente a:",
        "sent": "¡Gracias! Tu mensaje ha llegado y te responderemos pronto por correo.",
        "e_name": "Escribe tu nombre, por favor.", "e_email": "Esa dirección de correo no parece correcta.",
        "e_msg": "Escribe un mensaje de 10 a 3.000 caracteres, por favor.",
        "e_form": "Este formulario ha caducado. Vuelve a enviar tu mensaje, por favor.", "e_many": "Hoy has enviado muchos mensajes. Inténtalo de nuevo mañana.",
        "takedown_d": "Si tienes derechos sobre una obra que muestra la Biblioteca Al-Warraq, solicita aquí su retirada: indica la página y el motivo, y lo revisaremos y te responderemos.",
        "t_lead": "Si tienes derechos sobre una obra que muestra la Biblioteca Al-Warraq, o actúas en nombre del titular, rellena este formulario. Revisamos cada solicitud, retiramos el enlace o la ficha si vulnera un derecho y te respondemos por correo.",
        "t_what": "Recuerda que la biblioteca no aloja archivos de libros: muestra fichas de catálogo y un enlace a la fuente. Si el archivo está publicado en otro sitio, escribe también a ese sitio.",
        "f_url": "Dirección de la página en la biblioteca", "f_reason": "Motivo: ¿qué derecho tienes sobre la obra y por qué debe retirarse?", "f_send_t": "Enviar la solicitud de retirada",
        "sent_t": "Tu solicitud ha llegado. La revisaremos y te responderemos pronto por correo.",
        "e_url": "Indica la dirección de la página en la biblioteca, por favor.", "e_reason": "Explica el motivo en al menos 20 caracteres, por favor.",
        "c_lead": "Nos encantará saber de ti: sugiere un libro que no encontraste, informa de un error o un enlace roto, o pregunta sobre derechos de autor y publicidad.",
        "en_only": "Esta página está disponible en árabe y en inglés; a continuación se muestra la versión en inglés.",
    },
    "pt": {
        "updated": "Última atualização: {d}",
        "about_d": "A Al-Warraq é uma biblioteca digital árabe aberta que indexa mais de um milhão de livros em domínio público e leva você às cópias gratuitas nas fontes originais.",
        "privacy_d": "Quais informações a Biblioteca Al-Warraq coleta, como elas são usadas e como funcionam os cookies e os anúncios do Google AdSense no site.",
        "terms_d": "Termos de uso da Biblioteca Al-Warraq: o serviço, o domínio público e os direitos autorais, o uso aceitável e a responsabilidade.",
        "contact_d": "Fale com a Biblioteca Al-Warraq: sugira um livro, informe um erro ou link quebrado, ou tire dúvidas sobre direitos autorais e publicidade.",
        "f_name": "Nome", "f_email": "Seu e-mail", "f_topic": "Assunto", "f_msg": "Sua mensagem", "f_send": "Enviar mensagem",
        "f_hp": "Deixe este campo em branco",
        "f_note": "Usamos seu nome e e-mail apenas para responder a você, como explica nossa {p}.",
        "mail": "Ou escreva diretamente para:",
        "sent": "Obrigado! Sua mensagem chegou e responderemos no seu e-mail em breve.",
        "e_name": "Escreva seu nome, por favor.", "e_email": "Esse endereço de e-mail não parece correto.",
        "e_msg": "Escreva uma mensagem de 10 a 3.000 caracteres, por favor.",
        "e_form": "Este formulário expirou. Envie sua mensagem novamente, por favor.", "e_many": "Você enviou muitas mensagens hoje. Tente novamente amanhã.",
        "takedown_d": "Se você detém direitos sobre uma obra exibida pela Biblioteca Al-Warraq, peça a remoção aqui: informe a página e o motivo, e vamos analisar e responder.",
        "t_lead": "Se você detém direitos sobre uma obra exibida pela Biblioteca Al-Warraq, ou representa o detentor dos direitos, preencha este formulário. Analisamos cada pedido, removemos o link ou a ficha se houver violação de direitos e respondemos no seu e-mail.",
        "t_what": "Lembre-se de que a biblioteca não hospeda arquivos de livros: ela mostra fichas catalográficas e um link para a fonte. Se o próprio arquivo estiver publicado em outro site, escreva também para esse site.",
        "f_url": "Endereço da página na biblioteca", "f_reason": "Motivo: que direito você detém sobre a obra e por que ela deve ser removida?", "f_send_t": "Enviar o pedido de remoção",
        "sent_t": "Seu pedido chegou. Vamos analisá-lo e responder no seu e-mail em breve.",
        "e_url": "Informe o endereço da página na biblioteca, por favor.", "e_reason": "Explique o motivo em pelo menos 20 caracteres, por favor.",
        "c_lead": "Adoraríamos ouvir você: sugira um livro que não encontrou, informe um erro ou link quebrado, ou tire dúvidas sobre direitos autorais e publicidade.",
        "en_only": "Esta página está disponível em árabe e em inglês; a versão em inglês é exibida abaixo.",
    },
    "ja": {
        "updated": "最終更新日：{d}",
        "about_d": "アル・ワッラーク図書館は、100万冊以上のパブリックドメインの本を索引化し、元の情報源にある無料の本へ案内するオープンなアラビア語デジタル図書館です。",
        "privacy_d": "アル・ワッラーク図書館が収集する情報とその利用方法、そして当サイトでの Cookie と Google AdSense 広告の仕組みについて。",
        "terms_d": "アル・ワッラーク図書館の利用規約：サービスの内容、パブリックドメインと著作権、許容される利用、責任の制限。",
        "contact_d": "アル・ワッラーク図書館へのお問い合わせ：本の提案、誤りやリンク切れの報告、著作権や広告に関するご質問。",
        "f_name": "お名前", "f_email": "メールアドレス", "f_topic": "件名", "f_msg": "メッセージ", "f_send": "送信する",
        "f_hp": "この欄には何も入力しないでください",
        "f_note": "お名前とメールアドレスは返信のためだけに使用します。詳しくは{p}をご覧ください。",
        "mail": "またはこちらへ直接メールしてください：",
        "sent": "ありがとうございます。メッセージを受け付けました。追ってメールでご返信します。",
        "e_name": "お名前を入力してください。", "e_email": "メールアドレスが正しくないようです。",
        "e_msg": "10〜3,000文字でメッセージを入力してください。",
        "e_form": "フォームの有効期限が切れました。もう一度送信してください。", "e_many": "本日は多くのメッセージが送信されています。明日もう一度お試しください。",
        "takedown_d": "アル・ワッラーク図書館が掲載している作品の権利をお持ちの場合は、こちらから削除を依頼できます。ページと理由をお知らせいただければ、確認のうえご返信します。",
        "t_lead": "アル・ワッラーク図書館が掲載している作品の権利をお持ちの方、または権利者の代理人の方は、このフォームにご記入ください。すべての依頼を確認し、権利の侵害が認められた場合はリンクや書誌情報を削除して、メールでご返信します。",
        "t_what": "当図書館は本のファイルを掲載しておらず、書誌情報と情報源へのリンクのみを表示しています。ファイル自体が別のサイトで公開されている場合は、そのサイトにもご連絡ください。",
        "f_url": "図書館内のページのアドレス", "f_reason": "理由：この作品についてどのような権利をお持ちで、なぜ削除が必要ですか？", "f_send_t": "削除依頼を送信する",
        "sent_t": "依頼を受け付けました。確認のうえ、追ってメールでご返信します。",
        "e_url": "図書館内の該当ページのアドレスを入力してください。", "e_reason": "理由を20文字以上で説明してください。",
        "c_lead": "皆さまからのご連絡をお待ちしています。見つからなかった本の提案、誤りやリンク切れの報告、著作権や広告に関するご質問など、お気軽にどうぞ。",
        "en_only": "このページはアラビア語と英語で提供しています。以下は英語版です。",
    },
    "de": {
        "updated": "Zuletzt aktualisiert: {d}",
        "about_d": "Al-Warraq ist eine offene arabische digitale Bibliothek, die über eine Million gemeinfreie Bücher verzeichnet und Sie zu ihren kostenlosen Exemplaren an den Originalquellen führt.",
        "privacy_d": "Welche Daten die Bibliothek Al-Warraq erhebt, wie sie verwendet werden und wie Cookies und Google-AdSense-Anzeigen auf der Website funktionieren.",
        "terms_d": "Nutzungsbedingungen der Bibliothek Al-Warraq: der Dienst, Gemeinfreiheit und Urheberrecht, zulässige Nutzung und Haftung.",
        "contact_d": "Kontakt zur Bibliothek Al-Warraq: Schlagen Sie ein Buch vor, melden Sie einen Fehler oder defekten Link, oder fragen Sie zu Urheberrecht und Werbung.",
        "f_name": "Name", "f_email": "Ihre E-Mail-Adresse", "f_topic": "Betreff", "f_msg": "Ihre Nachricht", "f_send": "Nachricht senden",
        "f_hp": "Lassen Sie dieses Feld leer",
        "f_note": "Wir verwenden Ihren Namen und Ihre E-Mail-Adresse nur, um Ihnen zu antworten, wie unsere {p} erklärt.",
        "mail": "Oder schreiben Sie uns direkt an:",
        "sent": "Vielen Dank! Ihre Nachricht ist angekommen, und wir antworten Ihnen bald per E-Mail.",
        "e_name": "Bitte geben Sie Ihren Namen ein.", "e_email": "Diese E-Mail-Adresse scheint nicht korrekt zu sein.",
        "e_msg": "Bitte schreiben Sie eine Nachricht mit 10 bis 3.000 Zeichen.",
        "e_form": "Dieses Formular ist abgelaufen. Bitte senden Sie Ihre Nachricht erneut.", "e_many": "Sie haben heute viele Nachrichten gesendet. Bitte versuchen Sie es morgen wieder.",
        "takedown_d": "Wenn Sie Rechte an einem Werk haben, das die Bibliothek Al-Warraq zeigt, beantragen Sie hier seine Entfernung: Nennen Sie die Seite und den Grund, wir prüfen den Antrag und antworten Ihnen.",
        "t_lead": "Wenn Sie Rechte an einem Werk haben, das die Bibliothek Al-Warraq zeigt, oder im Auftrag des Rechteinhabers handeln, füllen Sie dieses Formular aus. Wir prüfen jeden Antrag, entfernen den Link oder die Katalogdaten, wenn sie ein Recht verletzen, und antworten Ihnen per E-Mail.",
        "t_what": "Bitte beachten Sie, dass die Bibliothek keine Buchdateien speichert: Sie zeigt Katalogdaten und einen Link zur Quelle. Ist die Datei selbst auf einer anderen Website veröffentlicht, schreiben Sie bitte auch dieser Website.",
        "f_url": "Adresse der Seite in der Bibliothek", "f_reason": "Grund: Welches Recht haben Sie an dem Werk, und warum soll es entfernt werden?", "f_send_t": "Antrag auf Entfernung senden",
        "sent_t": "Ihr Antrag ist angekommen. Wir prüfen ihn und antworten Ihnen bald per E-Mail.",
        "e_url": "Bitte geben Sie die Adresse der Seite in der Bibliothek an.", "e_reason": "Bitte erklären Sie den Grund in mindestens 20 Zeichen.",
        "c_lead": "Wir freuen uns, von Ihnen zu hören: Schlagen Sie ein Buch vor, das Sie nicht gefunden haben, melden Sie einen Fehler oder defekten Link, oder fragen Sie zu Urheberrecht und Werbung.",
        "en_only": "Diese Seite gibt es auf Arabisch und Englisch; unten sehen Sie die englische Fassung.",
    },
}


for _ui in UI_LANGS:  # a word a language lacks is shown in English; then the page titles
    L[_ui] = dict(L["en"], **L.get(_ui, {}))
    L[_ui].update(dict(LEGAL[_ui]))


def link(page: str, ui: str, extra: str = "") -> str:
    """/about, /about?lang=fr; extra is one more parameter (sent=1)."""
    q = lang_q(ui)
    return "/" + page + q + (("&" if q else "?") + extra if extra else "")


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
<li><b>لغة الموقع:</b> يفتح الموقع بلغة متصفحك إن كانت من لغاته (العربية والإنكليزية والصينية والفرنسية والإسبانية والبرتغالية واليابانية والألمانية)، وبالإنكليزية إن لم تكن. وإذا غيّرت اللغة بنفسك، نحفظ اختيارك في ملف كوكيز صغير اسمه warraq_lang لمدة سنة، يحمل رمز اللغة فقط (مثل ar أو en أو fr) ليعرض لك الموقع باللغة التي اخترتها، ولا نستخدمه لتتبعك.</li>
<li><b>التخزين المحلي في متصفحك:</b> نحفظ فيه اختيارك للمظهر (فاتح أو داكن) فقط، ولا يُرسل إلينا.</li>
</ul>
<h2>2. ملفات تعريف الارتباط (الكوكيز)</h2>
<p>الكوكيز ملفات نصية صغيرة تحفظها المواقع في متصفحك. يضع موقعنا كوكيز اللغة المذكور أعلاه، وتضع خدمة Google Analytics كوكيز إحصائية (مثل _ga) كما يوضح البند الرابع، وقد تستخدم أطراف ثالثة، منها Google، الكوكيز عند عرض الإعلانات كما يوضح البند التالي. يمكنك ضبط متصفحك لرفض الكوكيز أو حذفها في أي وقت، وقد يغيّر ذلك الإعلانات التي تراها.</p>
<h2>3. الإعلانات وGoogle AdSense</h2>
<p>نعرض إعلانات من خلال Google AdSense لتغطية تكاليف تشغيل المكتبة وإبقائها مجانية:</p>
<ul>
<li>يستخدم موردو الجهات الخارجية، ومنهم Google، ملفات تعريف الارتباط لعرض الإعلانات استناداً إلى زياراتك السابقة لهذا الموقع أو لمواقع أخرى على الإنترنت.</li>
<li>يتيح استخدام Google لملفات تعريف ارتباط الإعلانات لها ولشركائها عرض إعلانات لك استناداً إلى زيارتك لهذا الموقع و/أو لمواقع أخرى على الإنترنت.</li>
<li>يمكنك إيقاف الإعلانات المخصّصة من <a href="https://www.google.com/settings/ads" rel="noopener" target="_blank">إعدادات الإعلانات في Google</a>، كما يمكنك إيقاف استخدام موردين آخرين لملفات تعريف الارتباط للإعلانات المخصّصة عبر <a href="https://www.aboutads.info/choices/" rel="noopener" target="_blank">www.aboutads.info</a>.</li>
<li>لمعرفة المزيد عن طريقة استخدام Google للبيانات، راجع <a href="https://policies.google.com/technologies/partner-sites" rel="noopener" target="_blank">كيف تستخدم Google المعلومات من المواقع التي تستخدم خدماتها</a> و<a href="https://policies.google.com/technologies/ads" rel="noopener" target="_blank">طريقة استخدام Google للكوكيز في الإعلانات</a>.</li>
<li>للزوار من المنطقة الاقتصادية الأوروبية والمملكة المتحدة وسويسرا: نطلب موافقتك قبل أن تستخدم Google الكوكيز في الإعلانات المخصّصة وفي الإحصاءات، كما تفرض القوانين هناك.</li>
<li>نعرض أيضاً إعلانات أصلية (Native) من شبكة إعلانية تابعة لجهة خارجية تُحمَّل من النطاق bauval.org. قد تضع هذه الشبكة ملفات كوكيز، وتجمع معلومات عن جهازك ومتصفحك وعنوان IP الخاص بك، لعرض الإعلانات وقياسها ومنع الاحتيال، وفق سياسة الخصوصية الخاصة بها.</li>
</ul>
<h2>4. خدمات أطراف ثالثة أخرى</h2>
<p>يحمّل متصفحك بعض المحتوى من خدمات خارجية، وتتلقى هذه الخدمات عنوان IP الخاص بك كما يحدث في أي طلب على الإنترنت:</p>
<ul>
<li>الخطوط من Google Fonts.</li>
<li>أغلفة الكتب من Open Library ومشروع غوتنبرغ وHathiTrust ومؤسسة هنداوي، ونبذ المؤلفين من ويكيبيديا في صفحات الكتب.</li>
<li>روابط القراءة تنقلك إلى مواقع خارجية تحكمها سياسات الخصوصية الخاصة بها.</li>
<li>عبارات البحث في مكتب البحوث يرسلها خادمنا إلى OpenAlex للعثور على الأوراق العلمية.</li>
<li><b>Google Analytics:</b> لنعرف عدد الزوار والصفحات الأكثر زيارة وكيف يُستخدم الموقع، تجمع Google بيانات الاستخدام (الصفحات التي تزورها، ومدة الزيارة، ونوع الجهاز والمتصفح، والبلد أو المدينة على وجه التقريب) بكوكيز مثل _ga تبقى حتى سنتين. لا نرسل إليها اسمك ولا بريدك. يمكنك منعها بتثبيت <a href="https://tools.google.com/dlpage/gaoptout" rel="noopener" target="_blank">إضافة إيقاف Google Analytics</a>، ولمعرفة المزيد راجع <a href="https://policies.google.com/privacy" rel="noopener" target="_blank">سياسة خصوصية Google</a>.</li>
</ul>
<h2>5. كيف نستخدم المعلومات</h2>
<p>لتشغيل الموقع وتحسينه ومعرفة كيف يُستخدم، ولعرض الكتب الأكثر مشاهدة والعبارات الأكثر بحثاً، وللرد على رسائلك، ولحماية الموقع من الإساءة. لا نبيع بياناتك، ولا نشاركها إلا مع مزوّدي الخدمات المذكورين أعلاه، أو إذا ألزمنا القانون بذلك.</p>
<h2>6. الأطفال</h2>
<p>الموقع موجّه لعامة القرّاء، ولا نجمع عن قصد بيانات شخصية من أطفال دون 13 عاماً. إن علمت أن طفلاً أرسل إلينا بياناته فراسلنا لنحذفها.</p>
<h2>7. حقوقك</h2>
<p>يمكنك أن تطلب الاطلاع على رسالة أرسلتها إلينا أو حذفها عبر <a href="{link("contact", ui)}">صفحة الاتصال</a>. أما الإحصاءات فمجهولة الهوية ولا يمكن ربطها بشخصك.</p>
<h2>8. الأمان</h2>
<p>نستخدم اتصالاً مشفراً (HTTPS) وضوابط أمنية ونحدّ من الطلبات المتكررة، لكن لا توجد وسيلة نقل أو تخزين على الإنترنت آمنة تماماً.</p>
<h2>9. التعديلات</h2>
<p>قد نحدّث هذه السياسة من وقت لآخر، وننشر تاريخ آخر تحديث في أعلى الصفحة.</p>
<h2>10. اتصل بنا</h2>
<p>لأي سؤال عن الخصوصية، أو لطلب حذف رسالة أرسلتها إلينا، راسلنا على <a href="mailto:{contact_email()}">{contact_email()}</a> أو <a href="{link("contact", ui)}">من صفحة الاتصال</a>.</p>"""
    return f"""
<p class="lead">This policy explains what information Al-Warraq Library (“the site”, “we”) collects when you use the site, how we use it and the choices you have. By using the site you agree to this policy.</p>
<h2>1. Information we collect</h2>
<ul>
<li><b>No accounts:</b> you browse and read without signing up. We never ask for your name or email unless you type them into the contact form yourself.</li>
<li><b>Anonymous statistics:</b> to count visitors, views, likes and popular searches we compute an anonymous code from your IP address and browser type together with a secret value (a SHA-256 hash). We do not store the IP address or the browser type themselves. Daily visit codes are deleted after 3 days; monthly and yearly codes when the period ends. Search phrases are kept without any link to who searched, to show “most searched”.</li>
<li><b>Contact form:</b> the name, email address and message you send. We use them only to reply to you, and they are deleted automatically after 12 months.</li>
<li><b>Server logs:</b> our hosting provider may keep technical logs (such as IP address and time of request) for a short time, for security and abuse prevention.</li>
<li><b>Site language:</b> the site opens in your browser's language when it is one of the site's languages (Arabic, English, Chinese, French, Spanish, Portuguese, Japanese and German), and in English otherwise. If you change the language yourself, we keep your choice for a year in a small cookie named warraq_lang, holding only the language's code (such as ar, en or fr), so the site shows you the language you chose. It is not used to track you.</li>
<li><b>Local storage in your browser:</b> only your choice of theme (light or dark). It is never sent to us.</li>
</ul>
<h2>2. Cookies</h2>
<p>Cookies are small text files that websites store in your browser. Our site sets the language cookie above, Google Analytics sets statistics cookies (such as _ga) as section 4 explains, and third parties, including Google, may use cookies when showing ads, as described below. You can set your browser to refuse or delete cookies at any time; this may change the ads you see.</p>
<h2>3. Advertising and Google AdSense</h2>
<p>We show ads through Google AdSense to cover the costs of running the library and keep it free:</p>
<ul>
<li>Third-party vendors, including Google, use cookies to serve ads based on your prior visits to this website or other websites.</li>
<li>Google's use of advertising cookies enables it and its partners to serve ads to you based on your visit to this site and/or other sites on the Internet.</li>
<li>You may opt out of personalised advertising by visiting <a href="https://www.google.com/settings/ads" rel="noopener" target="_blank">Google Ads Settings</a>. You can also opt out of a third-party vendor's use of cookies for personalised advertising at <a href="https://www.aboutads.info/choices/" rel="noopener" target="_blank">www.aboutads.info</a>.</li>
<li>To learn more, see <a href="https://policies.google.com/technologies/partner-sites" rel="noopener" target="_blank">how Google uses information from sites that use its services</a> and <a href="https://policies.google.com/technologies/ads" rel="noopener" target="_blank">how Google uses cookies in advertising</a>.</li>
<li>Visitors from the European Economic Area, the United Kingdom and Switzerland are asked for consent before Google uses cookies for personalised ads and for statistics, as the law there requires.</li>
<li>We also show native ads from a third-party advertising network, loaded from the bauval.org domain. This network may set cookies and collect information about your device, browser and IP address to serve and measure ads and to prevent fraud, under its own privacy policy.</li>
</ul>
<h2>4. Other third-party services</h2>
<p>Your browser loads some content from outside services, which receive your IP address as with any request on the Internet:</p>
<ul>
<li>Fonts from Google Fonts.</li>
<li>Book covers from Open Library, Project Gutenberg, HathiTrust and the Hindawi Foundation; author summaries from Wikipedia on book pages.</li>
<li>Reading links take you to external sites governed by their own privacy policies.</li>
<li>Research-desk searches are sent by our server to OpenAlex to find papers.</li>
<li><b>Google Analytics:</b> to learn how many people visit, which pages they read and how the site is used, Google collects usage data (the pages you visit, visit length, device and browser type, approximate country or city) with cookies such as _ga that last up to two years. We never send it your name or email. You can block it with the <a href="https://tools.google.com/dlpage/gaoptout" rel="noopener" target="_blank">Google Analytics opt-out add-on</a>; see <a href="https://policies.google.com/privacy" rel="noopener" target="_blank">Google's privacy policy</a> for more.</li>
</ul>
<h2>5. How we use information</h2>
<p>To run and improve the site and learn how it is used, to show the most viewed books and most searched phrases, to reply to your messages and to protect the site from abuse. We do not sell your data, and we share it only with the service providers above, or when the law requires it.</p>
<h2>6. Children</h2>
<p>The site is meant for the general public, and we do not knowingly collect personal data from children under 13. If you learn that a child has sent us personal data, contact us and we will delete it.</p>
<h2>7. Your rights</h2>
<p>You can ask to see or delete a message you sent us through the <a href="{link("contact", ui)}">contact page</a>. Statistics are anonymous and cannot be linked to you.</p>
<h2>8. Security</h2>
<p>We use encrypted connections (HTTPS), security controls and rate limits, but no method of transmission or storage on the Internet is completely secure.</p>
<h2>9. Changes</h2>
<p>We may update this policy from time to time and will show the date of the latest update at the top of this page.</p>
<h2>10. Contact</h2>
<p>For any privacy question, or to have a message you sent us deleted, email <a href="mailto:{contact_email()}">{contact_email()}</a> or <a href="{link("contact", ui)}">use the contact page</a>.</p>"""


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
<p>تصميم الموقع وشعاره وشيفرته البرمجية ونصوصه التعريفية ملك لمكتبة الوراق. أما الكتب فهي ملك لأصحاب حقوقها أو في الملك العام، بحسب كل عمل وقانون كل بلد، وأسماء المصادر وعلاماتها التجارية ملك أصحابها.</p>
<h2>7. بلاغات حقوق النشر</h2>
<p>إن رأيت أن رابطاً في المكتبة يخالف حقوقك، <a href="{link("takedown", ui)}">املأ نموذج طلب الإزالة</a> واذكر اسم العمل ورابطه وصفتك، وسنراجع البلاغ ونزيل الرابط إن ثبتت المخالفة.</p>
<h2>8. الإعلانات</h2>
<p>يعرض الموقع إعلانات من Google وشركائها ومن شبكات إعلانية أخرى. ظهور إعلان لا يعني أننا نؤيد المعلن أو منتجه، وأي تعامل بينك وبين المعلن شأن بينكما وحدكما.</p>
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
<p>The site's design, logo, code and descriptive texts belong to Al-Warraq Library. The books belong to their rights holders or are in the public domain, depending on each work and the law of each country; the names and trademarks of the sources belong to their owners.</p>
<h2>7. Copyright reports</h2>
<p>If you believe a link in the library infringes your rights, <a href="{link("takedown", ui)}">send a removal request</a> with the title of the work, its link and your capacity, and we will review the report and remove the link if it infringes.</p>
<h2>8. Advertising</h2>
<p>The site shows ads from Google and its partners and from other advertising networks. An ad does not mean that we endorse the advertiser or the product, and any dealings between you and an advertiser are between you and the advertiser alone.</p>
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
        return '<p class="notice ok" role="status">%s</p><p><a href="%s">%s</a></p>' % (esc(l["sent"]), "/" + lang_q(ui), esc(T[ui]["home"]))
    intro = '<p class="lead">%s</p>' % esc(l["c_lead"])
    mail = contact_email()
    if mail:
        intro += '<p class="mail">%s <a href="mailto:%s">%s</a></p>' % (esc(l["mail"]), esc(mail), esc(mail))
    topics = "".join('<option value="%s"%s>%s</option>' % (k, " selected" if v.get("topic") == k else "", esc(n))
                     for k, n in TOPICS.get(ui, TOPICS["en"]))
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


def _takedown(conn, ui, values=None, error="", sent=False):
    l, v = L[ui], values or {}
    if sent:
        return '<p class="notice ok" role="status">%s</p><p><a href="%s">%s</a></p>' % (esc(l["sent_t"]), "/" + lang_q(ui), esc(T[ui]["home"]))
    err = '<p class="notice err" role="alert">%s</p>' % esc(error) if error else ""
    note = l["f_note"].format(p='<a href="%s">%s</a>' % (link("privacy", ui), esc(L[ui]["privacy"])))
    mail = contact_email()
    mail_html = '<p class="mail">%s <a href="mailto:%s">%s</a></p>' % (esc(l["mail"]), esc(mail), esc(mail)) if mail else ""
    return """<p class="lead">%s</p><p>%s</p>%s%s
<form class="contact" method="post" action="%s">
<label>%s<input name="name" maxlength="%d" required autocomplete="name" value="%s"></label>
<label>%s<input type="email" name="email" maxlength="%d" required autocomplete="email" dir="ltr" value="%s"></label>
<label>%s<input name="url" maxlength="%d" required dir="ltr" value="%s"></label>
<label>%s<textarea name="reason" rows="7" minlength="20" maxlength="%d" required>%s</textarea></label>
<label class="hp" aria-hidden="true">%s<input name="website" tabindex="-1" autocomplete="off"></label>
<input type="hidden" name="t" value="%s">
<button type="submit">%s</button>
<p class="fine">%s</p>
</form>""" % (esc(l["t_lead"]), esc(l["t_what"]), mail_html, err, link("takedown", ui),
              esc(l["f_name"]), LIMITS["name"], esc(v.get("name", "")), esc(l["f_email"]), LIMITS["email"], esc(v.get("email", "")),
              esc(l["f_url"]), LIMITS["url"], esc(v.get("url", "")), esc(l["f_reason"]), LIMITS["message"], esc(v.get("reason", "")),
              esc(l["f_hp"]), form_token(conn), esc(l["f_send_t"]), note)


def parse_form(body: bytes) -> dict:
    data = parse_qs(body[:20000].decode("utf-8", "replace"), keep_blank_values=True)
    return {k: (data.get(k) or [""])[0] for k in ("name", "email", "topic", "message", "url", "reason", "website", "t")}


def submit(conn, request, form: dict, ui: str, kind: str = "contact"):
    """Returns (ok, error message, cleaned values). A filled honeypot is accepted silently and dropped.
    kind "takedown": a removal request (the page's address and the reason), kept with the messages."""
    l = L[ui]
    v = {
        "name": " ".join(form.get("name", "").split())[:LIMITS["name"]],
        "email": form.get("email", "").strip()[:LIMITS["email"]],
        "topic": form.get("topic", "") if form.get("topic", "") in dict(TOPICS["en"]) else "general",
        "message": form.get("message", "").replace("\r\n", "\n").strip()[:LIMITS["message"]],
        "url": " ".join(form.get("url", "").split())[:LIMITS["url"]],
        "reason": form.get("reason", "").replace("\r\n", "\n").strip()[:LIMITS["message"]],
    }
    if form.get("website"):  # only bots fill a field nobody can see
        return True, "", v
    if not token_ok(conn, form.get("t", "")):
        return False, l["e_form"], v
    if not v["name"]:
        return False, l["e_name"], v
    if not EMAIL.match(v["email"]):
        return False, l["e_email"], v
    if kind == "takedown":
        if not v["url"]:
            return False, l["e_url"], v
        if len(v["reason"]) < 20:
            return False, l["e_reason"], v
        topic, message = "takedown", ("رابط الصفحة: %s\n\n%s" % (v["url"], v["reason"]))[:LIMITS["message"] + LIMITS["url"]]
    else:
        if not 10 <= len(v["message"]) <= LIMITS["message"]:
            return False, l["e_msg"], v
        topic, message = v["topic"], v["message"]
    who = stats.visitor_id(conn, request)
    now = int(time.time())
    if conn.execute("SELECT COUNT(*) FROM contact_messages WHERE visitor=? AND ts>?", (who, now - 86400)).fetchone()[0] >= PER_DAY:
        return False, l["e_many"], v
    conn.execute("INSERT INTO contact_messages(ts, name, email, topic, message, lang, visitor) VALUES(?,?,?,?,?,?,?)",
                 (now, v["name"], v["email"], topic, message, ui, who))
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
.notice.lang{background:var(--card);border:1px solid var(--line);color:var(--muted)}
.mail a{font-weight:600;direction:ltr;unicode-bidi:isolate}
"""


def page_html(kind: str, base: str, ui: str, conn=None, numbers=None, values=None, error="", sent=False) -> str:
    from .seo import _ld, _shell
    l = L[ui]
    body_html = {"about": lambda: _about(ui, numbers or {}), "privacy": lambda: _privacy(ui), "terms": lambda: _terms(ui),
                 "contact": lambda: _contact(conn, ui, values, error, sent),
                 "takedown": lambda: _takedown(conn, ui, values, error, sent)}[kind]()
    if kind in ("about", "privacy", "terms") and content.text_ui(ui) != ui:  # these texts are written in Arabic and English
        body_html = '<p class="notice lang">%s</p><div lang="en">%s</div>' % (esc(l["en_only"]), body_html)
    updated = '<p class="updated">%s</p>' % esc(l["updated"].format(d=UPDATED[kind][ui])) if kind in ("privacy", "terms") else ""
    body = '<article class="page"><p class="crumbs"><a href="/%s">%s</a> / %s</p><h1>%s</h1>%s%s</article>' % (
        lang_q(ui), esc(T[ui]["home"]), esc(l[kind]), esc(l[kind]), updated, body_html)
    types = {"about": "AboutPage", "contact": "ContactPage"}
    ld = _ld({"@context": "https://schema.org", "@type": types.get(kind, "WebPage"), "name": l[kind] + " | " + BRAND[ui],
              "url": base + "/" + kind, "inLanguage": ui, "isPartOf": {"@id": base + "/#site"}})
    return _shell(ui, base, "/" + kind, l[kind] + " | " + BRAND[ui], l[kind + "_d"], body, ld, extra_css=EXTRA_CSS,
                  robots="noindex,follow" if kind in THIN_PAGES else "")


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
    topics = TOPIC_NAMES
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
