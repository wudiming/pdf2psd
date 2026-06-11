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
}

// ── 图层命名 ──────────────────────────────────────────────────────────────────
function getLayerName(index, total) {
    const scheme = document.getElementById("namingSelect").value;
    if (scheme === "zh")  return `第 ${index} 页`;
    if (scheme === "en")  return `Page ${index}`;
    if (scheme === "num") return String(index);
    return `Page ${index}`;
}

// ── 主转换流程 ────────────────────────────────────────────────────────────────
async function startConvert() {
    if (!selectedFileEntry || isConverting) return;

    const dpi = parseInt(document.getElementById("dpiSlider").value, 10);
    const scale = dpi / 72;    // PDF 默认 72 DPI

    isConverting = true;
    document.getElementById("convertBtn").disabled = true;
    document.getElementById("convertBtn").textContent = "转换中…";
    setProgress(0, 1, "正在加载 PDF.js…");
    setStatus("正在初始化…");

    try {
        // ── 1. 动态加载 PDF.js (CDN bundled as local copy) ──────────────────
        const pdfjsLib = await loadPDFJS();

        // ── 2. 读取 PDF 文件 ─────────────────────────────────────────────────
        setProgress(0, 1, "读取 PDF 文件…");
        const arrayBuffer = await selectedFileEntry.read({ format: uxpStorage.formats.binary });
        const pdfDoc = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
        const totalPages = pdfDoc.numPages;

        setStatus(`共 ${totalPages} 页，开始渲染…`);
        setProgress(0, totalPages, `准备渲染 ${totalPages} 页…`);

        // ── 3. 渲染每页为 ImageData ──────────────────────────────────────────
        const pageImages = [];  // Array of { width, height, data: Uint8Array (RGBA) }

        for (let i = 1; i <= totalPages; i++) {
            setProgress(i - 1, totalPages, `渲染第 ${i} / ${totalPages} 页…`);

            const page = await pdfDoc.getPage(i);
            const vp   = page.getViewport({ scale });

            // 用离屏 canvas 渲染
            const canvas  = document.createElement("canvas");
            canvas.width  = Math.round(vp.width);
            canvas.height = Math.round(vp.height);

            const ctx = canvas.getContext("2d");
            await page.render({ canvasContext: ctx, viewport: vp }).promise;

            const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
            pageImages.push({
                width:  canvas.width,
                height: canvas.height,
                data:   new Uint8Array(imgData.data.buffer),  // RGBA
            });
        }

        // ── 4. 确定画布尺寸（取最大页面） ────────────────────────────────────
        const canvasW = Math.max(...pageImages.map(p => p.width));
        const canvasH = Math.max(...pageImages.map(p => p.height));

        // ── 5. 在 Photoshop 中创建文档并写入图层 ─────────────────────────────
        setProgress(totalPages, totalPages, "正在创建 Photoshop 文档…");
        setStatus("正在写入 Photoshop…");

        await core.executeAsModal(async (executionContext) => {

            const docName = selectedFileEntry.name.replace(/\.pdf$/i, "");

            // 创建新文档
            const psDoc = await app.createDocument({
                width:      canvasW,
                height:     canvasH,
                resolution: dpi,
                mode:       constants.ColorMode.RGB,
                fill:       constants.DocumentFill.TRANSPARENT,
                name:       docName,
            });

            // 删除默认图层（Background）
            if (psDoc.layers.length > 0) {
                try { await psDoc.layers[0].delete(); } catch (_) {}
            }

            // 逐页创建像素图层
            for (let i = 0; i < pageImages.length; i++) {
                const pg = pageImages[i];
                setProgress(i + 1, pageImages.length, `写入图层 ${i + 1} / ${pageImages.length}…`);

                // 创建图层
                const layer = await psDoc.createLayer({
                    name: getLayerName(i + 1, totalPages),
                    type: constants.LayerType.LAYER,
                });

                // 将 RGBA 数据写入图层
                // 需要转换为 RGB（PS putPixels 接受 RGB 或 RGBA）
                const imageObj = {
                    imageData: pg.data,
                    width:     pg.width,
                    height:    pg.height,
                    components: 4,      // RGBA
                    chunky:    true,
                    colorProfile: "sRGB IEC61966-2.1",
                    colorSpace: constants.ColorSpace.RGB,
                };

                // 计算偏移（居中小于画布的页面）
                const offsetX = Math.floor((canvasW - pg.width)  / 2);
                const offsetY = Math.floor((canvasH - pg.height) / 2);

                await imaging.putPixels({
                    layerID:   layer.id,
                    imageData: await imaging.createImageDataFromBuffer(
                        pg.data,
                        { width: pg.width, height: pg.height, components: 4, chunky: true }
                    ),
                    targetBounds: {
                        left:   offsetX,
                        top:    offsetY,
                        right:  offsetX + pg.width,
                        bottom: offsetY + pg.height,
                    }
                });
            }

        }, { commandName: "PDF → PSD 转换" });

        // ── 6. 完成 ──────────────────────────────────────────────────────────
        setProgress(0, 0);
        setStatus(`✅ 转换完成！共 ${totalPages} 页图层`, "success");

    } catch (e) {
        setProgress(0, 0);
        setStatus("❌ 转换失败：" + e.message, "error");
        console.error("[PDF2PSD]", e);
    } finally {
        isConverting = false;
        document.getElementById("convertBtn").disabled  = false;
        document.getElementById("convertBtn").textContent = "开始转换";
    }
}

// ── 动态加载 PDF.js ───────────────────────────────────────────────────────────
let _pdfjsCache = null;

async function loadPDFJS() {
    if (_pdfjsCache) return _pdfjsCache;

    return new Promise((resolve, reject) => {
        // 使用本地打包的 PDF.js（lib/pdf.min.js）
        const script = document.createElement("script");
        script.src = "lib/pdf.min.js";
        script.onload = () => {
            if (typeof pdfjsLib === "undefined") {
                reject(new Error("PDF.js 加载失败，请检查 lib/pdf.min.js 是否存在"));
                return;
            }
            // 设置 worker 路径
            pdfjsLib.GlobalWorkerOptions.workerSrc = "lib/pdf.worker.min.js";
            _pdfjsCache = pdfjsLib;
            resolve(pdfjsLib);
        };
        script.onerror = () => reject(new Error("无法加载 PDF.js，请检查插件文件完整性"));
        document.head.appendChild(script);
    });
}

// ── 暴露全局函数（HTML onclick 使用）────────────────────────────────────────
window.selectFile  = selectFile;
window.startConvert = startConvert;
window.updateDpi   = updateDpi;
window.setDpi      = setDpi;
