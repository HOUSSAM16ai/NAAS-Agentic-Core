"""Text-streaming & sanitization mixin (D-164 Slice 2 — extracted verbatim from the God-file).

Single responsibility: user-facing text typography and safety — the markdown typing-effect
streamer (LaTeX-preserving, ISS-057/ISS-112), the conversation-history prompt formatter, the
internal retrieval-tag stripper, and the topology-leak sanitizer that every streamed chunk
passes through before it reaches the browser.

Mixed into `OrchestratorClient`; `cls._strip_retrieval_tags` etc. resolve through the MRO —
behaviour is byte-identical to the pre-extraction God-file.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator


class TextStreamingMixin:
    """Markdown typing-effect + history formatting + user-safe text sanitization (D-164)."""

    async def _stream_markdown_typing(self, full_response: str) -> AsyncGenerator[str, None]:
        """يبثّ نصاً ثابتاً (markdown) بإيقاع typing-effect مع حماية LaTeX.

        مُستخرَج من ``_stream_local_retrieval_response`` (ISS-112) ليُشارَك مع
        مسار «السؤال فقط» — السلوك مطابق حرفياً لما قبل الاستخراج.
        """
        import asyncio

        # ── استراتيجية البث الذكي (ISS-STREAM-002) ──────────────────────────
        # الهدف: typing-effect سلس يحاكي LLM streaming حقيقي.
        #
        # القواعد:
        # 1. الأسطر الفارغة والفواصل (---) → تُرسَل فوراً بدون تأخير
        # 2. عناوين Markdown (# ## ###) → تُرسَل كوحدة واحدة مع تأخير متوسط
        # 3. معادلات LaTeX ($$...$$) → تُرسَل كوحدة واحدة لا تُكسَر
        # 4. الأسطر العادية → تُقسَّم كلمة بكلمة مع تأخير 8-15ms
        # 5. الجداول → تُرسَل سطراً سطراً مع تأخير قصير
        import re as _re

        _LATEX_BLOCK_RE = _re.compile(r"\$\$[^$]*?\$\$", _re.DOTALL)  # noqa: N806
        # ISS-057 (D-051): يحفظ أربع صيغ من LaTeX inline كـ token واحد:
        #   $...$ | \(...\) | \\(...\\) | حتى عبر كلمات بدون فراغ
        # تطابق بالترتيب: $$ أولاً (في حالة عابر سطر)، ثم $، ثم \\(...\\)، ثم \(...\)
        _LATEX_INLINE_RE = _re.compile(  # noqa: N806
            r"\$\$[^$\n]+?\$\$"  # $$inline$$ نادر لكن ممكن
            r"|\$[^$\n]+?\$"  # $inline$
            r"|\\\\\([^\n]+?\\\\\)"  # \\(inline\\)  — الصيغة في knowledge_base
            r"|\\\([^\n]+?\\\)"  # \(inline\)
        )

        def _split_preserving_latex(line: str) -> list[str]:
            """يُقسِّم السطر إلى tokens مع الحفاظ على وحدة رموز LaTeX.

            ISS-057: يدعم كل صيغ inline math الموجودة في `knowledge_base/`:
            `$...$`, `\\(...\\)`, و `\\\\(...\\\\)` (double-backslash التاريخية).
            بهذا، الـ frontend يستقبل LaTeX block كـ chunk كامل ولا يُكشف نصف
            delimiter للطالب.
            """
            tokens: list[str] = []
            pos = 0
            for m in _LATEX_INLINE_RE.finditer(line):
                before = line[pos : m.start()]
                if before:
                    tokens.extend(w + " " for w in before.split() if w)
                tokens.append(m.group())
                pos = m.end()
            remainder = line[pos:]
            if remainder:
                tokens.extend(w + " " for w in remainder.split() if w)
            return tokens

        lines = full_response.splitlines(keepends=True)
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # سطر فارغ أو فاصل → فوري
            if not stripped or stripped == "---":
                yield line
                i += 1
                continue

            # معادلة LaTeX أحادية السطر $$...$$ — تُرسَل كوحدة واحدة لا تُكسَر
            if stripped.startswith("$$") and stripped.endswith("$$") and len(stripped) > 4:
                yield line
                await asyncio.sleep(0.025)
                i += 1
                continue

            # معادلة LaTeX متعددة الأسطر $$ ... $$
            if stripped.startswith("$$") and not stripped.endswith("$$"):
                block = line
                i += 1
                while i < len(lines) and "$$" not in lines[i]:
                    block += lines[i]
                    i += 1
                if i < len(lines):
                    block += lines[i]
                    i += 1
                yield block
                await asyncio.sleep(0.025)
                continue

            # عنوان Markdown
            if stripped.startswith("#"):
                yield line
                await asyncio.sleep(0.018)
                i += 1
                continue

            # سطر جدول
            if stripped.startswith("|"):
                yield line
                await asyncio.sleep(0.010)
                i += 1
                continue

            # سطر عادي — word-by-word مع الحفاظ على LaTeX
            tokens = _split_preserving_latex(stripped)
            for _j, token in enumerate(tokens):
                yield token
                # تأخير أقصر للكلمات القصيرة، أطول للرموز الرياضية
                if "$" in token:
                    await asyncio.sleep(0.020)
                elif len(token) <= 3:
                    await asyncio.sleep(0.006)
                else:
                    await asyncio.sleep(0.011)
            yield "\n"
            i += 1

    @staticmethod
    def _format_history_for_prompt(history_messages: list[dict[str, str]]) -> str:
        """يحوّل قائمة رسائل المحادثة إلى نص سياق منسّق للـ prompt."""
        lines: list[str] = []
        for msg in history_messages[-20:]:
            role = str(msg.get("role", "")).strip()
            content = str(msg.get("content", "")).replace("\x00", "").strip()
            if not content or role not in {"user", "assistant"}:
                continue
            label = "المستخدم" if role == "user" else "المساعد"
            lines.append(f"{label}: {content}")
        return "\n".join(lines)

    # vector DB / retriever ينتج chunks مع علامات داخلية مثل [ex: ex_1] / [sol: ex_1]
    # / [grading: ex_1] تُساعد في الفهرسة لكنها لا تنتمي لواجهة المستخدم. نُزيلها
    # قبل بثها للطالب — هذا يحدث في الـ orchestrator path قبل الـ preempt.
    _RETRIEVAL_TAG_RE = __import__("re").compile(
        r"\[(?:ex|sol|grading|chunk|src|source|meta|tag|id|doc):[^\]\n]{0,80}\]",
        __import__("re").IGNORECASE,
    )

    @classmethod
    def _strip_retrieval_tags(cls, content: str) -> str:
        """يحذف علامات chunks الداخلية من نص المستخدم.

        يحذف: [ex: ex_1] | [sol: ex_1] | [grading: ex_1] | [chunk: ...] | [src: ...]
        أي tag على شكل [key: value] حيث key ∈ {ex, sol, grading, chunk, src, source, meta, tag, id, doc}.
        """
        return cls._RETRIEVAL_TAG_RE.sub("", content)

    @classmethod
    def _sanitize_text_for_user(cls, content: str) -> str:
        """يعقّم نصًا موجّهًا للمستخدم النهائي من أي تلميحات طوبولوجيا داخلية."""
        lowered = content.lower()
        blocked_tokens = (
            "orchestrator-service",
            "localhost",
            "127.0.0.1",
            "host.docker.internal",
            "orchestrator_service_url",
            "diagnostic",
        )
        if any(token in lowered for token in blocked_tokens):
            return "تعذر إتمام طلبك حالياً بسبب ضغط أو عطل مؤقت في خدمة المحادثة. حاول مرة أخرى بعد لحظات."
        # ISS-058: حذف tags chunks الداخلية ([ex: ex_1], [sol: ex_1], [grading: ex_1])
        return cls._strip_retrieval_tags(content)
