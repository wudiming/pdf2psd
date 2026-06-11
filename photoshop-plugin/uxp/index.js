/**
 * PDF → PSD UXP 插件逻辑
 * 使用 PDF.js 渲染 PDF 页面，通过 PS UXP DOM API 创建图层
 * 适用于 Adobe Photoshop 2021+ (UXP)
 */

"use strict";

// ── UXP & Photoshop APIs ──────────────────────────────────────────────────────
const { app, core, imaging, constants } = require("photoshop");
const { entrypoints } = require("uxp");
const uxpStorage = require("uxp").storage;
const localFS = uxpStorage.localFileSystem;

// ── 状态 ──────────────────────────────────────────────────────────────────────
let selectedFileEntry = null;   // UXP FileEntry
let isConverting      = false;

// ── Panel 入口 ────────────────────────────────────────────────────────────────
entrypoints.setup({
    panels: {
        mainPanel: {
            show() {},
            hide() {},
        }
    }
});

// ── UI 辅助函数 ───────────────────────────────────────────────────────────────
function setStatus(msg, type = "") {
    const el = document.getElementById("statusMsg");
    el.textContent = msg;
    el.className = "status " + type;
}

function setProgress(current, total, label = "") {
    const card = document.getElementById("progressCard");
    const fill = document.getElementById("progressFill");
    const lbl  = document.getElementById("progressLabel");

    if (total <= 0) { card.style.display = "none"; return; }
    card.style.display = "block";
    fill.style.width = ((current / total) * 100).toFixed(1) + "%";
    lbl.textContent = label || `第 ${current} / ${total} 页`;
}

// ── DPI 控件 ──────────────────────────────────────────────────────────────────
function updateDpi(value) {
    document.getElementById("dpiLabel").textContent = value;
}

function setDpi(value) {
    document.getElementById("dpiSlider").value = value;
    updateDpi(value);

    // 更新 preset 按钮高亮
    document.querySelectorAll(".dpi-presets button").forEach(btn => {
        btn.classList.toggle("active", parseInt(btn.textContent) === value ||
                                       btn.textContent.includes(String(value)));
    });
}

// ── 文件选择 ──────────────────────────────────────────────────────────────────
async function selectFile() {
    if (isConverting) return;
    try {
        const entry = await localFS.getFileForOpening({
            allowMultiple: false,
            types: ["pdf"]
        });
        if (!entry) return;

        selectedFileEntry = entry;

        document.getElementById("dropIcon").textContent  = "✅";
        document.getElementById("dropTitle").textContent = entry.name;
        document.getElementById("dropTitle").style.color = "#4a9eff";
        document.getElementById("dropSub").textContent   = "已选择，点击更换";
        document.getElementById("dropZone").classList.add("has-file");
        document.getElementById("convertBtn").disabled   = false;
        setStatus("文件已选择，点击「开始转换」");

    } catch (e) {
        setStatus("选择文件失败：" + e.message, "error");
    }

    // 自动探测页数 (需要 executeAsModal)
    try {
        setStatus("正在自动识别页数…");
        document.getElementById("pageInput").value = "识别中...";
        await core.executeAsModal(async () => {
            const count = await getPdfPageCount(selectedFileEntry);
            if (count > 0) {
                document.getElementById("pageInput").value = count;
                setStatus(`已选择文件，共识别出 ${count} 页`);
            } else {
                document.getElementById("pageInput").value = "1";
                setStatus("无法自动识别页数，请手动输入", "error");
            }
        }, { commandName: "探测 PDF 页数" });
    } catch (e) {
        document.getElementById("pageInput").value = "1";
        setStatus("页数探测出错：" + e.message, "error");
    }
}

// ── 图层命名 ──────────────────────────────────────────────────────────────────
function getLayerName(index, total) {
    const scheme = document.getElementById("namingSelect").value;
    if (scheme === "zh")  return `第 ${index} 页`;
    if (scheme === "en")  return `Page ${index}`;
    if (scheme === "num") return String(index);
    return `Page ${index}`;
}

// ── PDF 核心功能：使用 Photoshop 原生 PDF 引擎 ────────────────────────────────
const { batchPlay } = require("photoshop").action;

async function canOpenPage(entry, pageNum) {
    try {
        const token = await localFS.createSessionToken(entry);
        await batchPlay([{
            _obj: "open",
            "null": { _path: token, _kind: "local" },
            "as": {
                _class: "PDFGenericFormat",
                pageNumber: pageNum,
                mode: { _class: "RGBColorMode" },
                resolution: { _unit: "densityUnit", _value: 72 },
                suppressWarnings: true
            }
        }], {});

        // 成功打开的话，关闭它
        if (app.activeDocument) {
            await app.activeDocument.closeWithoutSaving();
        }
        return true;
    } catch (e) {
        return false;
    }
}

async function getPdfPageCount(entry) {
    if (!(await canOpenPage(entry, 1))) return 0;

    let lo = 1;
    let hi = 2;
    while (await canOpenPage(entry, hi)) {
        lo = hi;
        hi = hi * 2;
        if (hi > 2000) { hi = 2000; break; }
    }

    let ans = lo;
    let low = lo + 1;
    let high = hi - 1;

    while (low <= high) {
        let mid = Math.floor((low + high) / 2);
        if (await canOpenPage(entry, mid)) {
            ans = mid;
            low = mid + 1;
        } else {
            high = mid - 1;
        }
    }
    return ans;
}

// ── 主转换流程 ────────────────────────────────────────────────────────────────
async function startConvert() {
    if (!selectedFileEntry || isConverting) return;

    const dpi = parseInt(document.getElementById("dpiSlider").value, 10);

    isConverting = true;
    document.getElementById("convertBtn").disabled = true;
    document.getElementById("convertBtn").textContent = "转换中…";
    
    try {
        await core.executeAsModal(async (executionContext) => {
            
            
            const totalPages = parseInt(document.getElementById("pageInput").value, 10);
            if (isNaN(totalPages) || totalPages < 1) {
                throw new Error("请输入有效的页数（大于0）");
            }
            
            setStatus(`开始导入 ${totalPages} 页…`);
            setProgress(0, totalPages, `准备导入 ${totalPages} 页…`);

            const docName = selectedFileEntry.name.replace(/\.pdf$/i, "");
            let masterDoc = null;
            let succeeded = 0;

            for (let i = 1; i <= totalPages; i++) {
                setProgress(i - 1, totalPages, `正在导入第 ${i} / ${totalPages} 页…`);

                const token = await localFS.createSessionToken(selectedFileEntry);
                
                // 打开该页
                try {
                    await batchPlay([{
                        _obj: "open",
                        "null": { _path: token, _kind: "local" },
                        "as": {
                            _class: "PDFGenericFormat",
                            pageNumber: i,
                            mode: { _class: "RGBColorMode" },
                            resolution: { _unit: "densityUnit", _value: dpi },
                            antiAlias: true,
                            suppressWarnings: true,
                            cropPage: { _enum: "cropTo", _value: "mediaBox" }
                        }
                    }], {});
                } catch (e) {
                    if (i === 1) throw new Error("无法打开第一页");
                    break; 
                }

                const pageDoc = app.activeDocument;
                if (!pageDoc) break;

                // 创建主文档
                if (i === 1) {
                    masterDoc = await app.createDocument({
                        width: pageDoc.width,
                        height: pageDoc.height,
                        resolution: dpi,
                        mode: constants.ColorMode.RGB,
                        fill: constants.DocumentFill.TRANSPARENT,
                        name: docName,
                    });
                }

                // 激活回单页文档
                app.activeDocument = pageDoc;
                
                // 获取活动图层并改名
                const pdfLayer = pageDoc.activeLayers[0];
                if (pdfLayer) {
                    pdfLayer.name = getLayerName(i, totalPages);
                    // 复制图层到主文档（完美保留透明度）
                    await pdfLayer.duplicate(masterDoc);
                }

                await pageDoc.closeWithoutSaving();
                succeeded++;
            }

            if (!masterDoc || succeeded === 0) {
                throw new Error("没有任何页面被成功导入");
            }

            // 激活主文档并清理默认的空背景层
            app.activeDocument = masterDoc;
            if (masterDoc.layers.length > succeeded) {
                try {
                    const lastLayer = masterDoc.layers[masterDoc.layers.length - 1];
                    if (lastLayer.name === "Layer 1" || lastLayer.name === "图层 1") {
                        await lastLayer.delete();
                    }
                } catch (_) {}
            }

            setProgress(totalPages, totalPages, "完成");
            setStatus(`✅ 转换完成！共 ${succeeded} 页图层`, "success");

        }, { commandName: "PDF → PSD 导入" });

    } catch (e) {
        setProgress(0, 0);
        setStatus("❌ 导入失败：" + e.message, "error");
        console.error("[PDF2PSD]", e);
    } finally {
        isConverting = false;
        document.getElementById("convertBtn").disabled  = false;
        document.getElementById("convertBtn").textContent = "开始导入";
    }
}

// ── 暴露全局函数（HTML onclick 使用）────────────────────────────────────────
window.selectFile  = selectFile;
window.startConvert = startConvert;
window.updateDpi   = updateDpi;
window.setDpi      = setDpi;
