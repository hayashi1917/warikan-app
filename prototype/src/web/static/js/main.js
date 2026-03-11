const timeEl = document.getElementById("clock-time");
const dateEl = document.getElementById("clock-date");
const zoneEl = document.getElementById("clock-zone");
const statusEl = document.getElementById("clock-status");

const setStatus = (text, isError = false) => {
    if (!statusEl) return;
    statusEl.textContent = text;
    statusEl.classList.toggle("error", isError);
};

const renderCurrentTime = async () => {
    try {
        const response = await fetch("/api/current-time", { cache: "no-store" });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const payload = await response.json();
        if (timeEl) timeEl.textContent = payload.time ?? "--:--:--";
        if (dateEl) dateEl.textContent = payload.date ?? "----/--/--";
        if (zoneEl) zoneEl.textContent = `${payload.timezone ?? ""} (UTC${(payload.utc_offset || "+0000").replace(/(\\+|\\-)(\\d{2})(\\d{2})/, "$1$2:$3")})`;
        setStatus("最新の時刻を表示しています。");
    } catch (error) {
        setStatus("時刻の取得に失敗しました。", true);
    }
};

renderCurrentTime();
setInterval(renderCurrentTime, 1000);
