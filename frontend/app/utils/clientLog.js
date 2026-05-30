// ISS-101 (D-WS-KICK-DIAG): beacon تشخيصي — يُرسل أحداث حرجة (طرد/إعادة اتصال/
// نتيجة /me) إلى server.js الذي يطبعها في سجل الخادم. يتيح رؤية سبب الطرد على
// الجوال بلا devtools. غير قاتل: أي فشل يُتجاهَل.
import { BUILD_VERSION } from "../buildVersion";

export function clientLog(event, data = {}) {
  try {
    const body = JSON.stringify({
      event,
      ...data,
      build: BUILD_VERSION,
      t: new Date().toISOString(),
    });
    if (typeof navigator !== "undefined" && navigator.sendBeacon) {
      navigator.sendBeacon("/__clientlog", body);
    } else if (typeof fetch !== "undefined") {
      fetch("/__clientlog", { method: "POST", body, keepalive: true }).catch(() => {});
    }
  } catch (_e) {
    /* تشخيص فقط — لا يكسر شيئاً */
  }
}
