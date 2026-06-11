/**
 * PDF → PSD 图层导入脚本
 * 适用于：Adobe Photoshop (所有版本)
 *
 * 安装方法：
 *   将此文件拷贝到 Photoshop 的 Scripts 文件夹：
 *     Windows: C:\Program Files\Adobe\Adobe Photoshop XXXX\Presets\Scripts\
 *     macOS:   /Applications/Adobe Photoshop XXXX/Presets/Scripts/
 *   重启 PS 后可在「文件 → 脚本」菜单找到此脚本。
 *   也可随时通过「文件 → 脚本 → 浏览」直接运行。
 */
#target photoshop
#script "PDF 导入为图层"

// ── 入口 ─────────────────────────────────────────────────────────────────────
(function () {
    app.bringToFront();

    // ── 1. 显示设置对话框 ────────────────────────────────────────────────────
    var settings = showSettingsDialog();
    if (!settings) return;  // 用户取消

    var pdfFile    = settings.file;
    var dpi        = settings.dpi;
    var pageCount  = settings.pages;
    var docName    = decodeURI(pdfFile.name).replace(/\.pdf$/i, "");

    // ── 2. 进度窗口 ──────────────────────────────────────────────────────────
    var prog = new Window("palette", "PDF → PSD 转换中…");
    prog.progBar  = prog.add("progressbar", [0,0,360,16], 0, pageCount);
    prog.stLabel  = prog.add("statictext",  [0,0,360,20], "正在准备…");
    prog.stLabel.justify = "center";
    prog.center(); prog.show();

    // ── 3. 逐页打开 PDF ──────────────────────────────────────────────────────
    var importOpts = new PDFOpenOptions();
    importOpts.antiAlias       = true;
    importOpts.bitsPerChannel  = BitsPerChannelType.EIGHT;
    importOpts.colorMode       = OpenDocumentMode.RGB;
    importOpts.resolution      = dpi;
    importOpts.suppressWarnings = true;
    importOpts.cropPage        = CropToType.MEDIABOX;

    var masterDoc = null;
    var succeeded = 0;

    for (var i = 1; i <= pageCount; i++) {
        prog.stLabel.text = "正在处理第 " + i + " / " + pageCount + " 页…";
        prog.progBar.value = i - 1;
        prog.update();

        importOpts.pageNumber = i;

        var pageDoc;
        try {
            pageDoc = app.open(pdfFile, importOpts);
        } catch (e) {
            // 页码超出实际页数
            if (i === 1) {
                prog.close();
                alert("无法打开 PDF 文件，请确认文件有效。\n" + e.message);
                return;
            }
            break;  // 页面已经遍历完
        }

        // 将页面展平并全选
        pageDoc.flatten();
        pageDoc.selection.selectAll();
        pageDoc.selection.copy();

        if (i === 1) {
            // 第一页：建立主文档
            var w = pageDoc.width.as("px");
            var h = pageDoc.height.as("px");
            pageDoc.close(SaveOptions.DONOTSAVECHANGES);

            masterDoc = app.documents.add(
                w, h, dpi,
                docName,
                NewDocumentMode.RGB,
                DocumentFill.TRANSPARENT
            );
        } else {
            pageDoc.close(SaveOptions.DONOTSAVECHANGES);
        }

        // 粘贴为新图层
        app.activeDocument = masterDoc;
        masterDoc.paste();  // 旧版 PS：创建浮动选区；新版 PS：直接创建像素图层

        // 将浮动选区合并为图层（旧版 PS 需要；新版 PS paste 已直接创建图层，此步骤会报错，忽略即可）
        try {
            executeAction(
                charIDToTypeID("Mrg2"),
                new ActionDescriptor(),
                DialogModes.NO
            );
        } catch (mergeErr) {
            // 新版 Photoshop (CC 2020+)：paste() 已直接创建像素图层，无需合并浮动选区
        }

        masterDoc.activeLayer.name = "第 " + i + " 页";
        succeeded++;
    }

    prog.close();

    if (!masterDoc || succeeded === 0) {
        alert("没有成功导入任何页面，请检查文件。");
        return;
    }

    // ── 4. 清理：删除初始空白背景图层（如果存在）────────────────────────────
    if (masterDoc.layers.length > succeeded) {
        try {
            var lastLayer = masterDoc.layers[masterDoc.layers.length - 1];
            if (lastLayer.kind === LayerKind.NORMAL && lastLayer.name === "图层 1") {
                lastLayer.remove();
            }
        } catch (e) { /* 忽略 */ }
    }

    // ── 5. 完成提示 ──────────────────────────────────────────────────────────
    alert(
        "✅ 转换完成！\n\n" +
        "文件名：" + docName + "\n" +
        "共导入 " + succeeded + " 页，每页为独立图层。\n\n" +
        "提示：使用「文件 → 存储为」保存为 .psd 格式。"
    );

})();


// ── 设置对话框 ───────────────────────────────────────────────────────────────
function showSettingsDialog() {
    var dlg = new Window("dialog", "PDF → PSD 图层导入");
    dlg.orientation = "column";
    dlg.alignChildren = "fill";
    dlg.margins = 20;
    dlg.spacing = 12;

    // 标题
    var titleGroup = dlg.add("group");
    titleGroup.alignment = "center";
    var titleText = titleGroup.add("statictext", undefined, "PDF → PSD 图层导入工具");
    titleText.graphics.font = ScriptUI.newFont("dialog", "BOLD", 14);

    dlg.add("panel"); // 分割线

    // ── PDF 文件选择 ──────────────────────────────────────────────────────────
    var fileGroup = dlg.add("group");
    fileGroup.orientation = "column";
    fileGroup.alignChildren = "fill";
    fileGroup.add("statictext", undefined, "PDF 文件：");

    var fileRow = fileGroup.add("group");
    fileRow.orientation = "row";
    fileRow.alignChildren = "center";

    var fileEdit = fileRow.add("edittext", [0, 0, 290, 24], "");
    fileEdit.enabled = false;

    var browseBtn = fileRow.add("button", undefined, "浏览…");

    var selectedFile = null;
    browseBtn.onClick = function () {
        var f = File.openDialog(
            "选择 PDF 文件",
            "PDF 文件:*.pdf,所有文件:*.*"
        );
        if (f) {
            selectedFile = f;
            fileEdit.text = decodeURI(f.name);
        }
    };

    // ── 页数输入 ──────────────────────────────────────────────────────────────
    var pageGroup = dlg.add("group");
    pageGroup.orientation = "row";
    pageGroup.add("statictext", [0,0,120,20], "PDF 总页数：");
    var pageInput = pageGroup.add("edittext", [0,0,60,22], "10");
    pageGroup.add("statictext", undefined, "（在 PDF 阅读器中查看）");

    // ── DPI ───────────────────────────────────────────────────────────────────
    var dpiGroup = dlg.add("group");
    dpiGroup.orientation = "row";
    dpiGroup.add("statictext", [0,0,120,20], "渲染 DPI：");
    var dpiDropdown = dpiGroup.add("dropdownlist", [0,0,100,24],
        ["72（屏幕）", "96", "150（标准）", "200", "300（印刷）"]
    );
    dpiDropdown.selection = 2;  // 默认 150

    dlg.add("panel"); // 分割线

    // ── 按钮 ─────────────────────────────────────────────────────────────────
    var btnGroup = dlg.add("group");
    btnGroup.alignment = "right";
    var cancelBtn = btnGroup.add("button", undefined, "取消", { name: "cancel" });
    var okBtn     = btnGroup.add("button", undefined, "开始转换", { name: "ok" });

    okBtn.onClick = function () {
        if (!selectedFile) {
            alert("请先选择 PDF 文件！");
            return;
        }
        var pages = parseInt(pageInput.text, 10);
        if (isNaN(pages) || pages < 1) {
            alert("请输入有效的页数（大于 0 的整数）！");
            return;
        }
        dlg.close(1);
    };
    cancelBtn.onClick = function () { dlg.close(0); };

    var dpiValues = [72, 96, 150, 200, 300];

    var result = dlg.show();
    if (result !== 1) return null;

    return {
        file:  selectedFile,
        pages: parseInt(pageInput.text, 10),
        dpi:   dpiValues[dpiDropdown.selection.index]
    };
}
