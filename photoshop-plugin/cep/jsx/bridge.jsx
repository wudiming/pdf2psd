/**
 * bridge.jsx  ──  CEP 面板与 Photoshop 之间的 ExtendScript 桥接层
 * 由 CEP 面板通过 CSInterface.evalScript() 调用这里的函数。
 * 
 * 注意：ExtendScript (ES3) 环境中没有原生的 JSON 对象！
 * 必须手动拼接 JSON 字符串返回。
 */

/**
 * 快速读取 PDF 文件的总页数
 * 原理：直接解析 PDF 二进制文件的 /Count 字段，完全不需要用 PS 打开文档。
 * 解析失败时才回退到传统的二分法（打开 PS 文档）。
 * @param {string} pdfPathEncoded  URI 编码的文件路径
 * @returns {string} JSON 字符串
 */
function getPageCount(pdfPathEncoded) {
    try {
        var pdfPath = decodeURI(pdfPathEncoded);
        var pdfFile = new File(pdfPath);
        if (!pdfFile.exists) {
            return '{ "ok": false, "error": "文件不存在" }';
        }

        // ── 方法一：直接读取 PDF 二进制，匹配 /Count 字段 ──────────────────
        // PDF 规范：页面树的根节点 /Type /Pages 下有 /Count N 记录总页数
        // 读取文件尾部即可，目录表（xref）和根字典一般在文件末尾
        try {
            pdfFile.open("r");
            pdfFile.encoding = "BINARY";
            
            // 读取文件尾部 32KB，足够覆盖大多数 PDF 的结构
            var fileLen  = pdfFile.length;
            var tailSize = Math.min(fileLen, 32768);
            pdfFile.seek(fileLen - tailSize, 0); // 0 = SEEK_SET
            var tail = pdfFile.read(tailSize);
            pdfFile.close();
            
            // 找出所有 /Count 后跟数字的匹配，取其中最大的一个
            // 这是因为 PDF 内部各子节点也有 /Count，最大值才是总页数
            var maxCount = 0;
            var re = /\/Count\s+(\d+)/g;
            var m;
            while ((m = re.exec(tail)) !== null) {
                var n = parseInt(m[1], 10);
                if (n > maxCount) maxCount = n;
            }

            if (maxCount > 0) {
                return '{ "ok": true, "count": ' + maxCount + ', "method": "binary" }';
            }
            // 如果尾部没找到，尝试头部（少见的 PDF 结构）
            pdfFile.open("r");
            pdfFile.encoding = "BINARY";
            var headSize = Math.min(fileLen, 32768);
            pdfFile.seek(0, 0);
            var head = pdfFile.read(headSize);
            pdfFile.close();
            
            while ((m = re.exec(head)) !== null) {
                var n2 = parseInt(m[1], 10);
                if (n2 > maxCount) maxCount = n2;
            }
            if (maxCount > 0) {
                return '{ "ok": true, "count": ' + maxCount + ', "method": "binary_head" }';
            }
        } catch(readErr) {
            // 文件读取失败，忽略，继续用 PS 打开方式
        }

        // ── 方法二：回退 - 用 PS 打开文档（指数+二分法）───────────────────
        var opts = new PDFOpenOptions();
        opts.suppressWarnings = true;
        opts.bitsPerChannel   = BitsPerChannelType.EIGHT;
        opts.colorMode        = OpenDocumentMode.RGB;
        opts.resolution       = 72;
        opts.usePageNumber    = true;

        var originalDisplayDialogs = app.displayDialogs;
        app.displayDialogs = DialogModes.NO;

        function canOpenPage(p) {
            opts.page = p;
            try {
                var d = app.open(pdfFile, opts);
                d.close(SaveOptions.DONOTSAVECHANGES);
                return true;
            } catch(e) {
                return false;
            }
        }

        if (!canOpenPage(1)) {
            app.displayDialogs = originalDisplayDialogs;
            return '{ "ok": false, "error": "无法作为 PDF 打开此文件" }';
        }

        var lo = 1;
        var hi = 2;
        while (canOpenPage(hi)) {
            lo = hi;
            hi = hi * 2;
            if (hi > 2000) { hi = 2000; break; }
        }

        var ans = lo;
        var low = lo + 1;
        var high = hi - 1;
        while (low <= high) {
            var mid = Math.floor((low + high) / 2);
            if (canOpenPage(mid)) { ans = mid; low = mid + 1; }
            else { high = mid - 1; }
        }

        app.displayDialogs = originalDisplayDialogs;
        return '{ "ok": true, "count": ' + ans + ', "method": "ps_open" }';

    } catch (e) {
        var errStr = String(e.message || e).replace(/"/g, '\\"');
        return '{ "ok": false, "error": "' + errStr + '" }';
    }
}

/**
 * 打开文件选择对话框，返回所选 PDF 路径
 * @returns {string} URI 编码路径，或 "" 表示取消
 */
function selectPDFFile() {
    var f = File.openDialog("选择 PDF 文件", "PDF 文件:*.pdf,所有文件:*.*");
    if (f) return encodeURI(f.fsName);
    return "";
}

/**
 * 主转换函数：逐页将 PDF 导入为 PS 图层
 * 修复：导入结束后执行「显示全部」(Reveal All)，防止大页面溢出画布
 * @param {string} pdfPathEncoded  URI 编码的 PDF 路径
 * @param {number} totalPages      总页数
 * @param {number} dpi             渲染 DPI
 * @returns {string} JSON 字符串
 */
function importPDFAsLayers(pdfPathEncoded, totalPages, dpi) {
    try {
        var pdfPath = decodeURI(pdfPathEncoded);
        var pdfFile = new File(pdfPath);
        if (!pdfFile.exists) {
            return '{ "ok": false, "error": "文件不存在" }';
        }

        var docName = decodeURI(pdfFile.name).replace(/\.pdf$/i, "");

        var importOpts = new PDFOpenOptions();
        importOpts.antiAlias        = true;
        importOpts.bitsPerChannel   = BitsPerChannelType.EIGHT;
        importOpts.colorMode        = OpenDocumentMode.RGB;
        importOpts.resolution       = dpi;
        importOpts.suppressWarnings = true;
        importOpts.cropPage         = CropToType.MEDIABOX;
        importOpts.usePageNumber    = true;

        var masterDoc  = null;
        var succeeded  = 0;

        var originalDisplayDialogs = app.displayDialogs;
        app.displayDialogs = DialogModes.NO;

        for (var i = 1; i <= totalPages; i++) {
            importOpts.page = i;

            var pageDoc;
            try {
                pageDoc = app.open(pdfFile, importOpts);
            } catch (e) {
                if (i === 1) {
                    app.displayDialogs = originalDisplayDialogs;
                    return '{ "ok": false, "error": "无法打开 PDF 第1页" }';
                }
                break; // 页数已超出实际页数
            }

            if (i === 1) {
                var w = pageDoc.width.as("px");
                var h = pageDoc.height.as("px");
                masterDoc = app.documents.add(
                    w, h, dpi, docName,
                    NewDocumentMode.RGB,
                    DocumentFill.TRANSPARENT
                );
            }

            app.activeDocument = pageDoc;
            var pdfLayer = pageDoc.activeLayer;
            pdfLayer.name = "第 " + i + " 页";
            
            // 直接复制图层到主文档，完美保留透明通道
            pdfLayer.duplicate(masterDoc, ElementPlacement.PLACEATBEGINNING);

            pageDoc.close(SaveOptions.DONOTSAVECHANGES);

            succeeded++;
        }

        app.displayDialogs = originalDisplayDialogs;

        if (!masterDoc || succeeded === 0) {
            return '{ "ok": false, "error": "没有成功导入任何页面" }';
        }

        // 清理初始空白背景图层
        app.activeDocument = masterDoc;
        if (masterDoc.layers.length > succeeded) {
            try {
                var last = masterDoc.layers[masterDoc.layers.length - 1];
                if (last.kind === LayerKind.NORMAL && (last.name === "图层 1" || last.name === "Layer 1")) {
                    last.remove();
                }
            } catch (e) { /* 忽略 */ }
        }

        // ── 关键修复：执行「图像 → 显示全部」(Reveal All) ──────────────────
        // 防止 A2 等超大页面的图层内容超出以 A3 为基准创建的画布，导致显示不全
        try {
            app.activeDocument = masterDoc;
            var idrevealAll = stringIDToTypeID("revealAll");
            executeAction(idrevealAll, undefined, DialogModes.NO);
        } catch (revealErr) { /* 旧版 PS 可能不支持，忽略 */ }

        var safeDocName = docName.replace(/"/g, '\\"');
        return '{ "ok": true, "imported": ' + succeeded + ', "docName": "' + safeDocName + '" }';

    } catch (e) {
        var errStr = String(e.message || e).replace(/"/g, '\\"');
        return '{ "ok": false, "error": "' + errStr + '" }';
    }
}
