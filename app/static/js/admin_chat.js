/**
 * admin_chat.js — Legacy static admin chat client
 *
 * ملاحظة: هذا الملف legacy ولا يُستخدم في الـ Next.js frontend.
 * الـ frontend الحديث يستخدم useAgentSocket + useRealtimeConnection.
 *
 * الإصلاحات المُطبَّقة (D-WS-004):
 * - الـ endpoint الصحيح: /admin/api/chat/ws (وليس /ws/chat غير الموجود)
 * - token من localStorage يُرسَل عبر query param (وليس بدون auth)
 * - ws/wss يختار تلقائياً حسب protocol
 * - معالجة event types الحديثة (assistant_delta, assistant_final)
 */
document.addEventListener("DOMContentLoaded", function () {
    const chatBox = document.getElementById("chat-box");
    const chatInput = document.getElementById("chat-input");
    const sendBtn = document.getElementById("send-btn");

    if (!chatBox || !chatInput || !sendBtn) return;

    // D-WS-004: ws/wss ديناميكي — لا hardcoding
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";

    // D-WS-004: الـ endpoint الصحيح للأدمن
    const WS_ENDPOINT = "/admin/api/chat/ws";

    let socket = null;

    function _getToken() {
        return localStorage.getItem("token") || "";
    }

    function _buildWsUrl() {
        const token = _getToken();
        // D-WS-004: token عبر query param — يعمل عبر كل proxies (Codespaces/Gitpod/mobile)
        // sec-websocket-protocol يُحذف من proxies وشبكات الهاتف
        const base = wsProtocol + "//" + window.location.host + WS_ENDPOINT;
        return token ? base + "?token=" + encodeURIComponent(token) : base;
    }

    function connect() {
        const token = _getToken();
        if (!token) {
            chatBox.innerHTML += "<p style='color:red'><em>يجب تسجيل الدخول أولاً.</em></p>";
            return;
        }

        const url = _buildWsUrl();
        socket = new WebSocket(url);

        socket.onopen = function () {
            chatBox.innerHTML += "<p><em>متصل...</em></p>";
        };

        socket.onmessage = function (event) {
            try {
                const data = JSON.parse(event.data);

                if (data.type === "assistant_delta") {
                    const content = data?.payload?.content || "";
                    if (content) {
                        const lastP = chatBox.querySelector("p.assistant-streaming");
                        if (lastP) {
                            lastP.textContent += content;
                        } else {
                            const p = document.createElement("p");
                            p.className = "assistant-streaming";
                            p.textContent = content;
                            chatBox.appendChild(p);
                        }
                    }
                } else if (data.type === "assistant_final") {
                    const streaming = chatBox.querySelector("p.assistant-streaming");
                    if (streaming) {
                        streaming.classList.remove("assistant-streaming");
                        const extra = data?.payload?.content || "";
                        if (extra && !streaming.textContent.endsWith(extra)) {
                            streaming.textContent += extra;
                        }
                    }
                } else if (data.type === "error") {
                    const msg = data?.payload?.details || "خطأ غير معروف";
                    chatBox.innerHTML += "<p style='color:red'>" + msg + "</p>";
                } else if (data.delta) {
                    // Legacy format
                    chatBox.innerHTML += "<span>" + data.delta + "</span>";
                }
            } catch (_e) {
                // non-JSON — ignore
            }
            chatBox.scrollTop = chatBox.scrollHeight;
        };

        socket.onclose = function () {
            const s = chatBox.querySelector("p.assistant-streaming");
            if (s) s.classList.remove("assistant-streaming");
            chatBox.innerHTML += "<p><em>انقطع الاتصال.</em></p>";
            socket = null;
        };

        socket.onerror = function () {
            chatBox.innerHTML += "<p style='color:red'><em>خطأ في الاتصال.</em></p>";
        };
    }

    function _doSend(message) {
        chatBox.innerHTML += "<p><b>أنت:</b> " + message + "</p>";
        socket.send(JSON.stringify({ question: message }));
        chatInput.value = "";
    }

    function sendMessage() {
        const message = chatInput.value.trim();
        if (!message) return;

        if (!socket || socket.readyState !== WebSocket.OPEN) {
            connect();
            var attempts = 0;
            var waitAndSend = setInterval(function () {
                attempts++;
                if (socket && socket.readyState === WebSocket.OPEN) {
                    clearInterval(waitAndSend);
                    _doSend(message);
                } else if (attempts > 50) {
                    clearInterval(waitAndSend);
                }
            }, 100);
            return;
        }

        _doSend(message);
    }

    sendBtn.addEventListener("click", sendMessage);
    chatInput.addEventListener("keypress", function (event) {
        if (event.key === "Enter") sendMessage();
    });

    connect();
});
