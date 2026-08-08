#!/usr/bin/env python3
"""لقطاتٌ حيّة للواجهة بمتصفّحٍ حقيقي — نهاراً وليلاً (D-232).

⛔ ليست اختبار انحدارٍ بصري: هي **دليلٌ يُرى**. الادّعاء «الواجهة تحسّنت» بلا صورةٍ
مأخوذةٍ من متصفّحٍ يشغّل الحزمة المبنيّة ادّعاءٌ غير قابل للتفنيد (D-227).

    python scripts/e2e/capture_ui.py --base http://localhost:5000 --out /tmp/ui
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

CHROMIUM = "/opt/pw-browsers/chromium"


async def main() -> int:
    from playwright.async_api import async_playwright

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://localhost:5000")
    parser.add_argument("--out", default="/tmp/ui")
    parser.add_argument("--email", default="e2e.student@example.dz")
    parser.add_argument("--password", default="Str0ng!Passw0rd")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])
        page = await (await browser.new_context(viewport={"width": 1280, "height": 900})).new_page()
        page.on(
            "console",
            lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
        )
        # ⚠️ نصّ الطرفية وحده يقول «فشل تحميل مورد» بلا تسمية المورد — وبلاغٌ بلا
        # عنوانٍ لا يُشخَّص. نلتقط الطلب الفاشل نفسه.
        failed: list[str] = []
        page.on("requestfailed", lambda r: failed.append(f"{r.failure} ← {r.url}"))
        page.on(
            "response",
            lambda r: failed.append(f"HTTP {r.status} ← {r.url}") if r.status >= 400 else None,
        )

        await page.goto(args.base, wait_until="networkidle", timeout=60_000)
        await page.screenshot(path=out / "01-login.png", full_page=False)
        print(f"✓ {out / '01-login.png'}")

        # تسجيل دخولٍ حقيقي — لا حقن توكِن في التخزين المحلّي.
        await page.fill('input[type="email"]', args.email)
        await page.fill('input[type="password"]', args.password)
        await page.click('form button')
        await page.wait_for_selector(".app-container", timeout=60_000)
        await page.wait_for_timeout(1200)

        for theme in ("dark", "light"):
            await page.evaluate(
                "t => { document.documentElement.setAttribute('data-theme', t);"
                " localStorage.setItem('theme', t); }",
                theme,
            )
            await page.wait_for_timeout(500)
            path = out / f"02-chat-{theme}.png"
            await page.screenshot(path=path, full_page=False)
            print(f"✓ {path}")

        # دورٌ حقيقي عبر الواجهة — الطالب يكتب ويرسل.
        box = page.locator("textarea, input[type='text']").first
        await box.fill("اعطني تمرين الاحتمالات 2024")
        await box.press("Enter")
        await page.wait_for_timeout(9000)
        await page.screenshot(path=out / "03-turn-light.png", full_page=False)
        print(f"✓ {out / '03-turn-light.png'}")

        await page.evaluate(
            "() => { document.documentElement.setAttribute('data-theme','dark');"
            " localStorage.setItem('theme','dark'); }"
        )
        await page.wait_for_timeout(500)
        await page.screenshot(path=out / "04-turn-dark.png", full_page=False)
        print(f"✓ {out / '04-turn-dark.png'}")

        await browser.close()

    # ⛔ أخطاء الطرفية ليست تفصيلاً: overlay الخطأ في Next يظهر للطالب نفسه (ISS-120).
    noisy = [e for e in console_errors if "favicon" not in e.lower()]
    if failed:
        print(f"\n⚠️ {len(failed)} طلبٌ فاشل — بعنوانه كي يُشخَّص لا كبلاغٍ مبهم:")
        for item in dict.fromkeys(failed):
            print(f"   • {item[:220]}")
    if noisy:
        print(f"\n❌ {len(noisy)} خطأ طرفية في المتصفّح.")
        return 1
    print("\n✅ صفر أخطاء طرفية في المتصفّح.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
