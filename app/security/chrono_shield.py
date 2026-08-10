import asyncio
import logging
import os
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

from app.security.client_identity import client_ip_or_unknown
from app.security.passwords import pwd_context

# Use standard logging as per project convention in security module
logger = logging.getLogger(__name__)

# A pre-computed hash for dummy verification to ensure CPU work is done
# Optimization: Skip heavy computation in test environments
if os.getenv("TESTING", "False").lower() == "true":
    DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$QaH8hQ"  # Mock hash
else:
    try:
        DUMMY_HASH = pwd_context.hash("phantom_verification_string_for_timing_protection")
    except Exception as e:
        logger.warning(f"ChronoShield: Could not pre-compute DUMMY_HASH ({e}). Using fallback.")
        DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$QaH8hQ"


def _target_key(identifier: str) -> str:
    """مفتاح متّجه الهوية — **مُطبَّعاً** كما تُطبِّعه `AuthService.authenticate`.

    ⛔ رصدت مراجعة CodeRabbit تفاوتاً حقيقياً: المصادقة تُطبِّع البريد
    (``email.lower().strip()``) بينما الدرع كان يُفهرس النصّ الخام. فكان
    ``Victim@x.com`` و``victim@x.com`` و`` victim@x.com `` **ثلاثة عدّادات**
    لحسابٍ واحد — وكلٌّ منها يبدأ من الصفر. أي أنّ القفل الذي نُقل إلى الهوية
    عمداً (لئلّا يُعاقَب الجار) كان يُتجاوَز **بحرف كبير**، والحساب المستهدَف
    يُهاجَم بلا حدٍّ فعلي.

    والتطبيع هنا ليس تجميلاً بل **شرط أن يكون العدّاد عن الشيء الذي يحميه**:
    مفتاحٌ لا يطابق ما تراه المصادقة يَعُدّ كياناً آخر.
    """
    return identifier.strip().lower()


class ChronoShield:
    """
    The Chrono-Kinetic Defense Shield (Advanced Authentication Protection).

    This system implements a "Neuronal Defense Matrix" to protect authentication endpoints.
    It uses:
    1. **Adaptive Exponential Backoff (Temporal Dilation):** Increasing delays for repeated failures.
    2. **Dual-Vector Tracking:** Tracks threats by both Source IP and Target Identity (Email).
    3. **Phantom Verification:** Performs real cryptographic work on invalid users to mask timing oracles.
    4. **Hard Lockout (Event Horizon):** Completely blocks traffic after a threshold.
    5. **Self-Cleaning (Entropy Management):** Automatically purges stale threat records to prevent memory exhaustion.
    """

    def __init__(self):
        # Stores failure timestamps: failures[key] = [timestamp1, timestamp2, ...]
        self._failures: defaultdict[str, list[float]] = defaultdict(list)

        # Configuration - "The Physics Constants of the Shield"
        self.WINDOW = 300.0  # 5 minutes memory horizon
        self.MAX_FREE_ATTEMPTS = 5  # Attempts before Temporal Dilation begins
        self.LOCKOUT_THRESHOLD = 20  # Attempts (per IDENTITY) before Event Horizon
        # D-236 · ISS-152: سقف العنوان منفصل وأعلى بكثير. الشبكات الجزائرية خلف
        # carrier-NAT تجعل آلاف الطلاب يتقاسمون عنواناً واحداً، ومقهى إنترنت أو
        # مدرسة تُخرج عشرات الطلاب من عنوان واحد. سقفٌ مشترك بقيمة ٢٠ حوّل الدرع
        # إلى قاطعٍ عالمي (مُبرهَن حيّاً). هذا الرقم يوقف حشو بيانات الاعتماد
        # الآلي دون أن يمسّ صفّاً دراسياً يسجّل دخوله في آنٍ واحد.
        self.IP_LOCKOUT_THRESHOLD = 200
        # عتبة الإبطاء على العنوان — **٢٠ لا ٥**.
        #
        # كانت القيمة الضمنية ٥ (نفس عتبة الهوية عبر `max()`)، وهي معايَرة لعالمٍ
        # يكون فيه العنوان = مستخدماً واحداً. هذا الافتراض **خاطئ في نشرنا**:
        # بروكسي Next.js يجعل الجميع عنواناً واحداً، وcarrier-NAT الجزائري يجمع
        # آلاف الطلاب خلف عنوان واحد. المعايرة على افتراضٍ خاطئ هي أصل الانقطاع.
        #
        # ٢٠ تمرّ فوق ضجيج صفٍّ دراسي كامل يُخطئ الكتابة، وتصطدم بالتدوير الآلي
        # (مئات المحاولات) خلال ثوانٍ.
        self.IP_MAX_FREE_ATTEMPTS = 20
        self.MAX_DELAY = 5.0  # Maximum time dilation in seconds

        # Memory Management
        self.MAX_KEYS = 10000  # Max number of tracked keys before forced purge
        self.last_cleanup = time.time()
        self.CLEANUP_INTERVAL = 60.0  # Cleanup every minute

    def _manage_entropy(self) -> None:
        """
        Manages the entropy of the system (Memory Cleanup).
        Prevents the 'Grey Goo' scenario where memory grows infinitely.
        """
        now = time.time()

        # Periodic cleanup
        if now - self.last_cleanup > self.CLEANUP_INTERVAL:
            keys_to_delete = []
            for key, timestamps in self._failures.items():
                # Filter valid timestamps
                valid_timestamps = [t for t in timestamps if now - t < self.WINDOW]
                if not valid_timestamps:
                    keys_to_delete.append(key)
                else:
                    self._failures[key] = valid_timestamps

            for key in keys_to_delete:
                del self._failures[key]

            self.last_cleanup = now

        # Emergency purge if under attack (Too many keys)
        if len(self._failures) > self.MAX_KEYS:
            logger.warning("ChronoShield: ENTROPY LIMIT REACHED. Initiating Emergency Purge.")
            self._failures.clear()

    def _live_failures(self, key: str) -> int:
        """يعدّ الإخفاقات **داخل النافذة** لهذا المفتاح.

        D-236 · ISS-152: كانت القراءة `len(self._failures[key])` بلا ترشيح، والترشيح
        يحدث في `_manage_entropy` كل ٦٠ ثانية فقط — فإخفاقاتٌ عمرها ساعة كانت تُحتسَب
        تهديداً حاضراً حتى تمرّ دورة التنظيف. النافذة تعني النافذة.
        """
        now = time.time()
        recent = [stamp for stamp in self._failures.get(key, ()) if now - stamp < self.WINDOW]
        if recent:
            self._failures[key] = recent
        elif key in self._failures:
            del self._failures[key]
        return len(recent)

    async def check_allowance(self, request: Request, identifier: str) -> None:
        """
        Verifies if the request is allowed to proceed through the Chrono-Shield.
        Raises 429 if blocked, or sleeps if dilated.

        ⚠️ D-236 · ISS-152 — **القفل على الهوية، والعنوان إشارة ثانوية.**

        قِيس حيّاً قبل الإصلاح: ١٩ محاولة فاشلة بعناوين بريد **مختلفة وغير موجودة**
        جعلت الضحيّة تتلقّى **429 بكلمة سرّها الصحيحة**. السبب أن المفتاح `ip:` كان
        `127.0.0.1` لكل المستخدمين خلف بروكسي Next.js، فصار عدّاداً عالمياً: عشرون
        خطأً من أي أحد ⇒ المنصّة كلّها مقفلة.

        الآن: `ip:` يحمل العنوان الحقيقي (`client_identity`)، وسقفه **أعلى بكثير**
        لأن carrier-NAT الجزائري يجعل آلافاً يتقاسمون عنواناً واحداً — والقفل الحادّ
        على الهوية وحدها، فخطأ طالبٍ لا يمسّ جاره.
        """
        # Maintenance cycle
        self._manage_entropy()

        ip = client_ip_or_unknown(request)

        # Dual-Vector keys
        ip_key = f"ip:{ip}"
        target_key = f"target:{_target_key(identifier)}"

        ip_fails = self._live_failures(ip_key)
        target_fails = self._live_failures(target_key)

        # Phase 1: Event Horizon (Hard Lockout) — الهوية وحدها تُقفِل قفلاً حادّاً.
        if target_fails >= self.LOCKOUT_THRESHOLD:
            logger.warning("ChronoShield: EVENT HORIZON REACHED for target=%s", identifier)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Security protocol activated. Access suspended due to anomalous kinetic energy.",
                headers={"Retry-After": str(int(self.WINDOW))},
            )

        # العنوان يُقفِل فقط عند حجمٍ لا يفسّره استعمالٌ مشترك مشروع.
        if ip_fails >= self.IP_LOCKOUT_THRESHOLD:
            logger.warning("ChronoShield: EVENT HORIZON REACHED for ip=%s", ip)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Security protocol activated. Access suspended due to anomalous kinetic energy.",
                headers={"Retry-After": str(int(self.WINDOW))},
            )

        # Phase 2: Temporal Dilation (Exponential Backoff).
        #
        # ⚠️ يُحسَب على **المتّجهين** عمداً — الإبطاء المتدرّج هو مضادّ التدوير
        # (Anti-Rotation): مهاجمٌ يجرّب مئة بريد من عنوان واحد لا تُلام أيّ هوية
        # منفردة، فبلا متّجه العنوان يمرّ بلا أي مقاومة. حُذف هذا المتّجه في أول
        # صياغة للإصلاح فأسقط `test_chrono_shield_ip_persistence` — والاختبار كان
        # مُحقّاً: القصد الدفاعي حقيقي، والعطب كان في **القفل الصلب** لا في الإبطاء.
        #
        # الفرق الجوهري: الإبطاء يُكلِّف ثوانيَ ولا يمنع أحداً، والقفل الصلب (429)
        # يمنع الخدمة تماماً — لذلك بقي الإبطاء على العنوان، وانتقل القفل الصلب
        # إلى الهوية وحدها.
        delay = self._dilation_delay(target_fails=target_fails, ip_fails=ip_fails)
        if delay > 0:
            logger.info(
                "ChronoShield: Dilating time by %.2fs (target_fails=%d ip_fails=%d)",
                delay,
                target_fails,
                ip_fails,
            )
            await asyncio.sleep(delay)

    def _dilation_delay(self, *, target_fails: int, ip_fails: int) -> float:
        """يحسب زمن الإبطاء من أقوى المتّجهين، كلٌّ مقابل عتبته.

        العتبتان مختلفتان لأن الكمّيتين مختلفتان: هويةٌ واحدة تخفق خمس مرّات
        مؤشّرٌ قوي، وعنوانٌ واحد يخفق خمس مرّات لا يعني شيئاً حين يجلس خلفه صفٌّ
        دراسي كامل خلف carrier-NAT.
        """
        overages = [
            target_fails - self.MAX_FREE_ATTEMPTS,
            ip_fails - self.IP_MAX_FREE_ATTEMPTS,
        ]
        worst = max(overages)
        if worst <= 0:
            return 0.0
        return min(0.1 * (2**worst), self.MAX_DELAY)

    def record_failure(self, request: Request, identifier: str) -> None:
        """Records a failed authentication attempt (Kinetic Impact)."""
        ip = client_ip_or_unknown(request)
        now = time.time()
        self._failures[f"ip:{ip}"].append(now)
        self._failures[f"target:{_target_key(identifier)}"].append(now)

    def reset_target(self, identifier: str, request: Request | None = None) -> None:
        """
        Resets the threat level for a specific target upon success.

        D-236 · ISS-152: يُمرَّر ``request`` كي **يُخفَّض عدّاد العنوان أيضاً**. كان
        النجاح يمسح `target:` وحده ويترك `ip:` ينمو أبداً، فكان الدخول الناجح لا
        يشتري شيئاً: العدّاد الذي يقفل المنصّة لا ينخفض إلّا بانقضاء النافذة.

        ⛔ **لكنّ النجاح يخفض ولا يمحو.** أوّل إصلاحٍ لهذا مسح مفتاح العنوان
        كاملاً، ورصدت مراجعة CodeRabbit أنّ ذلك **يُبطِل مضادّ التدوير** الذي
        وُجد المتّجه من أجله: مهاجمٌ يملك بيانات حسابٍ واحد صحيحة يُدخِل نجاحاً
        بعد كل دفعة إخفاقات، فيُصفَّر `ip:` ولا يبلغ عتبةً أبداً — أي أنّ امتلاك
        حسابٍ واحد يشتري تجريب ما لا نهاية من الهويات من نفس العنوان.

        فالنجاح **دليلٌ على أن بعض حركة هذا العنوان مشروعة، لا كلّها**: يُخصَم
        منه ما يعادل الرصيد المجّاني (`IP_MAX_FREE_ATTEMPTS`) — يكفي لئلّا يُعاقَب
        صفٌّ خلف carrier-NAT بخطأ جارٍ، ولا يكفي لمحو أثر حملةٍ حقيقية.

        ⚠️ **وحدُّ هذا يُقال صراحةً**: الخصم يُقيِّد المهاجم ولا يمنعه — من يملك
        حساباً صحيحاً يستطيع إبقاء العدّاد مستوياً بـ`IP_MAX_FREE_ATTEMPTS`
        محاولةً لكل دخولٍ ناجح. أي أن السقف صار **معدّلاً** بدل أن يكون
        **لانهائياً** (وهو ما كان عليه المسح الكامل). والحماية الفعلية لكل حسابٍ
        مستهدَف تبقى في **القفل الصلب على الهوية** (`LOCKOUT_THRESHOLD`) الذي لا
        يمسّه هذا الخصم. ⛔ لا يُدَّعى أن متّجه العنوان يمنع التدوير — يُكلِّفه.
        **شرط الترقية:** اضمحلالٌ زمنيّ يقرأ توزيع الإخفاقات لا عددها فقط، بـADR.
        """
        self._failures.pop(f"target:{_target_key(identifier)}", None)
        if request is None:
            return
        ip_key = f"ip:{client_ip_or_unknown(request)}"
        # ⚠️ **الأقدم يُحذَف لا الأحدث.** `record_failure` يُلحِق، فالقائمة مرتّبة
        # من الأقدم إلى الأحدث، وشريحتي الأولى (`[:-N]`) كانت تُبقي **الأقدم**
        # وتُسقط **الأحدث** — أي عكس المقصود تماماً: تُرمى الأدلّة الطازجة ويُحتفَظ
        # بما يوشك أن ينتهي بانقضاء النافذة، فيهبط العدّاد أسرع مما صُمِّم له.
        # رصدته مراجعة CodeRabbit. والترشيح أوّلاً كي يُحسَب الخصم على **الحيّ**
        # لا على المنتهي (نفس قاعدة «النافذة تعني النافذة» في `_live_failures`).
        self._live_failures(ip_key)
        remaining = self._failures.get(ip_key, [])[self.IP_MAX_FREE_ATTEMPTS :]
        if remaining:
            self._failures[ip_key] = remaining
        else:
            self._failures.pop(ip_key, None)

    def phantom_verify(self, password: str) -> bool:
        """
        Performs a 'Phantom Verification' to protect against Timing Oracles.
        This consumes CPU cycles equivalent to a real password check.
        """
        # Verify against the dummy hash. Always returns False (hopefully),
        # but takes the same time as a real verify.
        return pwd_context.verify(password, DUMMY_HASH)


# Singleton Instance
chrono_shield = ChronoShield()
