# Artale EXP Tracker

macOS 專用的 MapleStory Worlds (Artale) 練功效率追蹤工具。懸浮在遊戲畫面上，自動辨識經驗值，即時顯示練功效率。

> 因為其他人做的都是 Windows 版，Mac 一直沒有好用的工具，所以做了這個。

![demo](https://img.shields.io/badge/platform-macOS-lightgrey) ![python](https://img.shields.io/badge/python-3.12+-blue)

## 功能

- **自動偵測遊戲** — 自動找到 MapleStory Worlds 視窗，不需手動設定
- **OCR 經驗值辨識** — 使用 macOS Vision Framework，100% 準確讀取狀態列
- **懸浮框顯示** — 浮在遊戲上方，即使遊戲有焦點也不會消失
- **即時統計**
  - EXP/分鐘 速率
  - 10 分鐘 / 60 分鐘 經驗預估（萬 W 顯示）
  - 距離升級剩餘經驗 + 預估時間
  - 累積時間 / 資料筆數
- **等級自動推算** — 內建 1~200 等經驗表，從 EXP + 百分比反推等級
- **技能冷卻提示** — 設定 4 個技能的快捷鍵和冷卻時間，按下後自動倒數，冷卻結束閃綠色提示
- **技能圖示截取** — 從遊戲畫面框選技能圖示，懸浮框上直接用圖示辨識
- **5 種顏色主題** — Dark / Ocean / Crimson / Forest / Glass
- **設定自動儲存** — 技能設定、圖示、主題、視窗位置下次開啟自動載入

## 下載安裝

### 方式一：直接下載 App（推薦）

1. 到 [Releases](../../releases) 頁面下載最新的 `Artale-EXP-Tracker-macOS-v1.0.0.zip`
2. 解壓縮
3. 將 `Artale EXP Tracker.app` 拖到「應用程式」資料夾
4. 雙擊啟動

### 方式二：從原始碼執行

需要 Python 3.12+ 和 [uv](https://docs.astral.sh/uv/)：

```bash
git clone https://github.com/guanrong1110/artale-exp-tracker.git
cd artale-exp-tracker
uv sync
uv run python main.py
```

## 首次使用：權限設定

App 需要兩個 macOS 權限才能正常運作，**首次啟動時會提示授權**：

### 1. 螢幕錄影權限（必要）

用於截取遊戲畫面讀取經驗值。

```
系統設定 → 隱私權與安全性 → 螢幕與系統錄音 → 開啟「Artale EXP Tracker」
```

> 如果從終端機執行，需要授權「終端機」。

### 2. 輔助使用權限（技能冷卻用）

用於全域鍵盤監聽，偵測你按下技能快捷鍵。

```
系統設定 → 隱私權與安全性 → 輔助使用 → 開啟「Artale EXP Tracker」
```

> 如果不需要技能冷卻功能，可以不開啟，其他功能不受影響。

### 權限設定圖解

| 步驟 | 說明 |
|------|------|
| 1 | 打開「系統設定」→「隱私權與安全性」 |
| 2 | 找到「螢幕與系統錄音」，點 + 號加入 App |
| 3 | 找到「輔助使用」，點 + 號加入 App |
| 4 | 重新啟動 App |

## 使用教學

### 基本使用

1. **開啟遊戲** — 啟動 MapleStory Worlds，進入 Artale
2. **啟動 Tracker** — 打開 Artale EXP Tracker
3. **確認偵測** — 主介面顯示「遊戲：已偵測 MapleStory Worlds」
4. **開始追蹤** — 點「開始追蹤」，懸浮框會出現在左上角
5. **開始打怪** — 懸浮框會即時顯示 EXP 速率和升級預估

> 懸浮框可以拖曳到任意位置。

### 技能冷卻設定

1. 在主介面的「技能冷卻設定」區域
2. 點 📷 按鈕 → 從遊戲畫面框選技能圖示
3. 填入按鍵（例：`v`、`a`、`shift`、`f1`）
4. 填入冷卻秒數
5. 點「開始追蹤」後，在遊戲中按下技能鍵就會開始倒數

支援的按鍵：`a-z`、`0-9`、`f1-f12`、`shift`、`ctrl`、`alt`、`space`、`tab` 等。

### 顏色主題

主介面有「懸浮框主題」下拉選單，提供 5 種配色：

| 主題 | 風格 |
|------|------|
| Dark | 深色底 + 金色重點（預設）|
| Ocean | 深藍底 + 天藍重點 |
| Crimson | 暗紅底 + 紅色重點 |
| Forest | 暗綠底 + 綠色重點 |
| Glass | 高透明 + 白色重點 |

## 經驗值顯示格式

大數字使用「萬（W）」格式方便閱讀：

| 顯示 | 實際數值 |
|------|----------|
| `4,898` | 4,898 |
| `4.9W` | 49,000 |
| `29.4W` | 294,000 |
| `200.0W` | 2,000,000 |
| `5,432.1W` | 54,321,000 |

## 注意事項

- 遊戲需要使用**視窗模式**（非 macOS 原生全螢幕），懸浮框才能正確顯示
- 開啟遊戲內選單 / 商店時，狀態列會被遮住，OCR 會暫停並自動恢復
- 等級是透過經驗表反推（內建 1~200 等），非直接 OCR 辨識
- 首次啟動 App 可能因安全性限制被阻擋，到「系統設定 → 安全性」點「仍然開啟」

## 技術細節

- **OCR 引擎**：macOS Vision Framework（不需要 Tesseract）
- **UI 框架**：PyQt6
- **鍵盤監聽**：macOS Quartz Event Tap
- **遊戲偵測**：Quartz CGWindowListCopyWindowInfo
- **螢幕擷取**：macOS screencapture 命令列工具

## 授權

MIT License
