/**
 * スマートホーム Web UI (index.html) 用 JavaScript
 * サーバーと非同期通信 (Fetch API) を行い、UIの更新とコマンド送信を行う
 */

// --- 1. グローバル変数 ---

// ステータス表示用のDOM要素をあらかじめ取得しておく
const statusMap = {
    // カーテン位置
    curtainVal: document.getElementById('curtain-pos-value'),
    curtainUnit: document.getElementById('curtain-pos-unit'),
    // プロジェクター状態
    proj: document.getElementById('projector-status'),
    // HDMI入力
    hdmi: document.getElementById('hdmi-status'),
    // ログ記録状態
    log: document.getElementById('logging-status'),
    // 制御モード
    mode: document.getElementById('control-mode'),
    // AIサーバー接続状態
    ai: document.getElementById('ai-status')
};

// タイマー制御用変数
let countdownSeconds = 0; // 残り秒数
const timerElement = document.getElementById('ai-timer'); // 表示場所

// --- 2. 非同期通信・UI更新関数 ---

/**
 * サーバーの /status エンドポイントにGETリクエストを送信し、
 * 最新のステータスを取得してUIの表示を更新する
 */
async function updateStatus() {
    try {
        // サーバーに状態を問い合わせ
        const response = await fetch('/status');
        const data = await response.json(); // 応答をJSONとしてパース

        // --- カーテン状態の更新 ---
        if (data.curtain_position === 'N/A') {
            statusMap.curtainVal.textContent = '不明';
            statusMap.curtainUnit.textContent = '';
            statusMap.curtainVal.style.color = 'var(--text-primary)';
        } else {
            statusMap.curtainVal.textContent = data.curtain_position;
            statusMap.curtainUnit.textContent = '%';
            statusMap.curtainVal.style.color = 'var(--color-green)';
        }

        // --- プロジェクター状態の更新 ---
        if (data.projector_status === 'Error' || data.projector_status === 'N/A') {
            statusMap.proj.textContent = '取得中...';
            statusMap.proj.style.color = 'var(--text-primary)';
        } else if (data.projector_status === 'ON') {
            statusMap.proj.textContent = 'ON';
            statusMap.proj.style.color = 'var(--color-green)';
        } else {
            statusMap.proj.textContent = 'OFF';
            statusMap.proj.style.color = 'var(--color-red)';
        }
        
        // --- HDMI入力の更新 ---
        statusMap.hdmi.textContent = data.hdmi_status;
        statusMap.hdmi.style.color = 'var(--text-primary)';
        
        // --- データ記録状態の更新 ---
        statusMap.log.textContent = data.logging_paused ? "OFF" : "ON";
        statusMap.log.style.color = data.logging_paused ? "var(--color-red)" : "var(--color-green)";
        
        // --- 制御モードの更新 ---
        statusMap.mode.textContent = data.auto_mode ? "自動(AI)" : "手動";
        statusMap.mode.style.color = data.auto_mode ? "var(--color-blue)" : "var(--color-orange)";
        
        // --- AIサーバー接続状態の更新 ---
        statusMap.ai.textContent = data.ai_connection_status ? "接続" : "切断";
        statusMap.ai.style.color = data.ai_connection_status ? "var(--color-green)" : "var(--color-red)";

        // カウントダウン変数の更新 (サーバーの時間に同期)
        if (data.time_remaining !== undefined) {
            countdownSeconds = data.time_remaining;
            updateTimerDisplay(); // 即時反映
        }

    } catch (e) {
        // 通信失敗時
        console.error("Status fetch failed:", e);
    }
}

/**
 * サーバーにシーン実行コマンドをPOST送信する (汎用)
 * @param {string} sceneName - 実行するシーン名 (例: "set0", "set100")
 */
async function sendCommand(sceneName) {
    try {
        await fetch(`/command/${sceneName}`, { method: "POST" });
    } catch (e) {
        console.error("Command failed:", e);
    } finally {
        // コマンド送信後、2秒待ってからステータスを更新 (デバイスの動作反映待ち)
        setTimeout(updateStatus, 2000);
    }
}

/**
 * サーバーにモード切替コマンドをPOST送信する
 * @param {string} mode - "auto" または "manual"
 */
async function setMode(mode) {
    try {
        await fetch(`/mode/${mode}`, { method: "POST" });
    } catch (e) {
        console.error("Mode set failed:", e);
    } finally {
        // モード切替は即時反映されるため、すぐにステータスを更新
        updateStatus();
    }
}

/**
 * サーバーにプロジェクター操作コマンドをPOST送信する
 * @param {string} action - "on" または "off"
 */
async function sendProjectorCommand(action) {
    try {
        await fetch(`/projector/${action}`, { method: "POST" });
    } catch (e) {
        console.error("Projector command failed:", e);
    } finally {
        // 1秒待ってからステータス更新
        setTimeout(updateStatus, 1000);
    }
}

/**
 * サーバーにHDMI切替コマンドをPOST送信する
 * @param {string} portName - "hdmi1" または "hdmi2"
 */
async function sendHdmiCommand(portName) {
    try {
        await fetch(`/hdmi/${portName}`, { method: "POST" });
    } catch (err) {
        console.error("HDMI command failed:", err);
    } finally {
        // 1秒待ってからステータス更新
        setTimeout(updateStatus, 1000);
    }
}

/**
 * サーバーにデータ記録モード切替コマンドをPOST送信する
 * @param {string} action - "on" または "off"
 */
async function setLogging(action) {
    try {
        await fetch(`/logging/${action}`, { method: "POST" });
    } catch (e) {
        console.error("Logging set failed:", e);
    } finally {
        // 即時反映
        updateStatus();
    }
}

// --- 3. イベントリスナーの登録 ---

// クラス名 '.scene-btn' を持つすべてのボタンにクリックイベントを登録
document.querySelectorAll('.scene-btn').forEach(button => {
    button.addEventListener('click', () => {
        // クリックされたボタンの 'data-scene' 属性の値を取得し、sendCommand に渡す
        sendCommand(button.getAttribute('data-scene'));
    });
});

// --- 4. 初回実行と定期実行 ---

// ページ読み込み完了時に、初回のステータス更新を実行
updateStatus();

// 5秒ごと (5000ミリ秒) にステータス更新を繰り返す
setInterval(updateStatus, 5000);

// 1秒ごとにカウントダウンを減らして表示を更新するタイマー
setInterval(() => {
    if (countdownSeconds > 0) {
        countdownSeconds--;
        updateTimerDisplay();
    }
}, 1000);

// 分・秒に変換して表示する関数
function updateTimerDisplay() {
    if (!timerElement) return;
    const m = Math.floor(countdownSeconds / 60);
    const s = countdownSeconds % 60;
    // ゼロ埋め (例: 4分05秒)
    const sStr = s.toString().padStart(2, '0');
    timerElement.textContent = `${m}分${sStr}秒後`;
}