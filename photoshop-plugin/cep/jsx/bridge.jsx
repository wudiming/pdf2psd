/**
 * bridge.jsx  ──  CEP 面板与 Photoshop 之间的 ExtendScript 桥接层
 * 由 CEP 面板通过 CSInterface.evalScript() 调用这里的函数。
 * 
 * 注意：ExtendScript (ES3) 环境中没有原生的 JSON 对象！
 * 必须手动拼接 JSON 字符串返回。
 */

/**
 * 自动探测 PDF 文件的总页数
 * 原理：尝试逐页打开直到失败，或通过 PDF 字典中的 /Count 值读取
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

        // 方法1：读取 PDF 二进制，找 /Count 字典条目（快速但不100%可靠）
        pdfFile.encoding = 'BINARY';
        pdfFile.open('r');
        var raw = pdfFile.read(65536); // 读前64KB通常足以找到页数
        pdfFile.close();

        // 查找 /Type /Pages ... /Count N 模式
        var countMatch = raw.match(/\/Type\s*\/Pages[\s\S]{0,200}?\/Count\s+(\d+)/);
        if (countMatch && countMatch[1]) {
            var n = parseInt(countMatch[1], 10);
            if (n > 0 && n < 10000) {
                return '{ "ok": true, "count": ' + n + ' }';
            }
        }

        // 方法2：数 /Type /Page 出现次数（备用）
        var pageMatches = raw.match(/\/Type\s*\/Page[^s]/g);
        if (pageMatches && pageMatches.length > 0) {
            return '{ "ok": true, "count": ' + pageMatches.length + ' }';
        }

        // 方法3：尝试打开获取页数（最慢但最准确）
        var opts = new PDFOpenOptions();
        opts.suppressWarnings = true;
        opts.bitsPerChannel   = BitsPerChannelType.EIGHT;
        opts.colorMode        = OpenDocumentMode.RGB;
        opts.resolution       = 72;
        opts.page             = 1;
        opts.usePageNumber    = true;

        var originalDisplayDialogs = app.displayDialogs;
        app.displayDialogs = DialogModes.NO;

        try {
            var testDoc = app.open(pdfFile, opts);
            testDoc.close(SaveOptions.DONOTSAVECHANGES);
        } catch (e) {
            app.displayDialogs = originalDisplayDialogs;
            return '{ "ok": false, "error": "无法作为 PDF 打开此文件" }';
        }

        // 二分探测或顺序探测，这里顺序探测
        var hi = 1;
        while (true) {
            try {
                opts.page = hi + 1;
                var d = app.open(pdfFile, opts);
                d.close(SaveOptions.DONOTSAVECHANGES);
                hi = hi + 1;
                if (hi > 500) break; // 防止超大 PDF 无限循环
            } catch(e) { break; }
        }

        app.displayDialogs = originalDisplayDialogs;
        return '{ "ok": true, "count": ' + hi + ' }';

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

        var safeDocName = docName.replace(/"/g, '\\"');
        return '{ "ok": true, "imported": ' + succeeded + ', "docName": "' + safeDocName + '" }';

    } catch (e) {
        var errStr = String(e.message || e).replace(/"/g, '\\"');
        return '{ "ok": false, "error": "' + errStr + '" }';
    }
}
