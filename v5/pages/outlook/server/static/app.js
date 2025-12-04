/* outlook/server/static/app.js */

/* ======================= API ======================= */
const api = {
    list: (q) => fetch(`/accounts${q}`).then((r) => r.json()),
    get: (id) =>
        fetch(`/accounts/${id}`).then((r) => (r.ok ? r.json() : Promise.reject(r))),
    history: (id, page = 1, size = 200) =>
        fetch(`/accounts/${id}/history?page=${page}&size=${size}`).then((r) =>
            r.json()
        ),
    create: (item) =>
        fetch(`/accounts/batch`, {
            method: "POST",
            headers: {"Content-Type": "application/json; charset=utf-8"},
            body: JSON.stringify([item]),
        }).then((r) => r.json()),
    createBatch: (items) =>
        fetch(`/accounts/batch`, {
            method: "POST",
            headers: {"Content-Type": "application/json; charset=utf-8"},
            body: JSON.stringify(items),
        }).then((r) => r.json()),
    update: (item) =>
        fetch(`/accounts/batch`, {
            method: "PUT",
            headers: {"Content-Type": "application/json; charset=utf-8"},
            body: JSON.stringify([item]),
        }).then((r) => r.json()),
    updateBatch: (items) =>
        fetch(`/accounts/batch`, {
            method: "PUT",
            headers: {"Content-Type": "application/json; charset=utf-8"},
            body: JSON.stringify(items),
        }).then((r) => r.json()),
    restore: (id, body) =>
        fetch(`/accounts/${id}/restore`, {
            method: "POST",
            headers: {"Content-Type": "application/json; charset=utf-8"},
            body: JSON.stringify(body),
        }).then((r) => r.json()),
    del: (id) =>
        fetch(`/accounts/${id}`, {method: "DELETE"}).then((r) =>
            r.ok ? r.json() : Promise.reject(r)
        ),
    // 后端原有导出接口保留，但为支持字段选择，这里优先前端生成CSV
    export: (q) => fetch(`/accounts/export${q}`),
    mailsList: (accountId, {q, page, size, folder} = {}) => {
        const p = new URLSearchParams();
        if (q) p.set('q', q);
        if (folder) p.set('folder', folder);
        p.set('page', page || 1);
        p.set('size', size || 50);
        return fetch(`/accounts/${accountId}/mails?${p.toString()}`).then(r => r.json());
    },
    mailDetail: (messageId) => fetch(`/mail/${messageId}`).then(r => r.json())
};

/* ======================= State ======================= */
let state = {
    page: 1,
    size: 20,
    filters: {
        email_contains: "",
        status: "",
        rec_email_contains: "",
        rec_phone: "",
        note_contains: "",
    },
    currentId: null,
    listPages: 1,
    selected: new Set(), // 选中ID集合
    batchParsed: [],
    mails: {
        q: '',
        folder: '',
        page: 1,
        size: 50,
        pages: 1,
        total: 0,
        // 将列表行的数据缓存，便于右侧预览显示 folder/labels 而不必再次请求
        listMap: {}   // { messageId: {subject, from_addr, received_at, folder, labels_joined, attachments_count} }
    }
};

/* ======================= Utils ======================= */
function qs(id) {
    return document.getElementById(id);
}

// 多值通用：换行/逗号分隔
function parseList(s) {
    if (!s) return [];
    return [...new Set(s.split(/[\n,]/).map((x) => x.trim()).filter(Boolean))];
}

// 多值（用于 CSV 字段）：分号或竖线
function splitListField(s) {
    if (!s) return [];
    return [...new Set(s.split(/[;\|]/).map((x) => x.trim()).filter(Boolean))];
}

// 别名解析：换行/逗号/分号分隔，统一小写
function parseAliases(s) {
    if (!s) return [];
    return [...new Set(s.split(/[\n,;]+/).map((x) => x.trim().toLowerCase()).filter(Boolean))];
}

function toast(msg, isError = false) {
    const el = document.createElement("div");
    el.textContent = msg;
    el.style.position = "fixed";
    el.style.right = "12px";
    el.style.bottom = "12px";
    el.style.background = isError ? "#fee2e2" : "#dcfce7";
    el.style.color = isError ? "#991b1b" : "#166534";
    el.style.border = "1px solid #e5e7eb";
    el.style.padding = "10px 12px";
    el.style.borderRadius = "8px";
    el.style.zIndex = 2000;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2400);
}

function updateSelCount() {
    qs("sel-count").innerHTML = state.selected.size;
    qs("btn-batch-delete").disabled = state.selected.size === 0;
    qs("btn-batch-note").disabled =
        state.selected.size === 0 || !qs("bulk-note").value.trim();
}

/* ======================= List ======================= */
async function loadList() {
    const p = new URLSearchParams();
    p.set("page", state.page);
    p.set("size", state.size);
    const f = state.filters;
    if (f.email_contains) p.set("email_contains", f.email_contains);
    if (f.status) p.set("status", f.status);
    if (f.rec_email_contains)
        p.set("recovery_email_contains", f.rec_email_contains);
    if (f.rec_phone) p.set("recovery_phone", f.rec_phone);
    if (f.note_contains) p.set("note_contains", f.note_contains);

    qs("tbl-accounts").innerHTML = `<tr><td colspan="6" class="muted">加载中...</td></tr>`;
    try {
        const data = await api.list(`?${p.toString()}`);
        state.listPages = data.pages || 1;
        qs("pg-info").textContent = `第 ${data.page}/${state.listPages} 页（共 ${data.total} 条）`;

        const chkAll = qs("chk-all");
        chkAll.checked = false;

        if (!data.items.length) {
            qs("tbl-accounts").innerHTML = `<tr><td colspan="6" class="muted">暂无数据</td></tr>`;
            return;
        }
        qs("tbl-accounts").innerHTML = data.items
            .map((row) => {
                const statCls =
                    row.status === "未登录"
                        ? "status-normal"
                        : row.status === "登录成功"
                            ? "status-banned"
                            : "status-disabled";
                const checked = state.selected.has(row.id) ? "checked" : "";
                return `<tr>
          <td><input type="checkbox" class="chk-row" data-id="${row.id}" ${checked} /></td>
          <td>${row.id}</td>
          <td><span class="link" onclick="openDetail(${row.id})">${row.email}</span></td>
          <td><span class="muted">${row.updated_at}</span></td>
          <td><span class="pill ${statCls}">${row.status}</span></td>
          <td>
            <button class="secondary" onclick="openHistory(${row.id})">历史</button>
            <button class="xbtn" title="删除" onclick="openDelete(${row.id}, '${row.email.replace(/'/g, "\\'")}')">×</button>
          </td>
        </tr>`;
            })
            .join("");

        // 绑定行选择
        document.querySelectorAll(".chk-row").forEach((chk) => {
            chk.addEventListener("change", (e) => {
                const id = parseInt(e.target.getAttribute("data-id"), 10);
                if (e.target.checked) state.selected.add(id);
                else state.selected.delete(id);
                updateSelCount();

                const rows = [...document.querySelectorAll(".chk-row")];
                qs("chk-all").checked = rows.length > 0 && rows.every((r) => r.checked);
            });
        });

        const rows = [...document.querySelectorAll(".chk-row")];
        chkAll.checked = rows.length > 0 && rows.every((r) => r.checked);
    } catch (e) {
        qs("tbl-accounts").innerHTML = `<tr><td colspan="6" class="warn-text">加载失败</td></tr>`;
        toast("加载失败", true);
    }
}

/* ======================= Detail ======================= */
async function openDetail(id) {
    try {
        const r = await api.get(id);
        state.currentId = r.id;
        qs("detail-empty").classList.add("hidden");
        qs("detail-form").classList.remove("hidden");
        qs("d-id").textContent = r.id;
        qs("d-version").textContent = r.version;
        qs("d-email").value = r.email;
        qs("d-password").value = r.password || "";
        qs("d-status").value = r.status;
        qs("d-username").value = r.username || "";
        qs("d-birthday").value = r.birthday || "";
        qs("d-rec-emails").value = (r.recovery_emails || []).join("\n");
        qs("d-rec-phones").value = (r.recovery_phones || []).join("\n");
        qs("d-clear-emails").checked = false;
        qs("d-clear-phones").checked = false;

        // 别名
        if (qs("d-aliases")) {
            qs("d-aliases").value = (r.aliases || []).join("\n");
        }
        if (qs("d-clear-aliases")) {
            qs("d-clear-aliases").checked = false;
        }

        // 展示最近一次历史备注/操作者
        try {
            const h = await api.history(id, 1, 1);
            if (h.items && h.items.length) {
                const last = h.items[0];
                qs("d-note").value = last.note || "";
                qs("d-who").value = last.created_by || "";
            } else {
                qs("d-note").value = "";
                qs("d-who").value = "";
            }
        } catch {
            qs("d-note").value = "";
            qs("d-who").value = "";
        }
    } catch (e) {
        toast("获取详情失败", true);
    }
}

async function refreshDetail() {
    if (!state.currentId) return;
    openDetail(state.currentId);
}

async function saveUpdate() {
    if (!state.currentId) return;
    const obj = {
        id: state.currentId,
        email: qs("d-email").value.trim(),
        username: qs("d-username").value.trim(),
        birthday: qs("d-birthday").value.trim(),
        note: qs("d-note") ? qs("d-note").value.trim() || "更新" : "更新",
        created_by: qs("d-who")
            ? qs("d-who").value.trim() || undefined
            : undefined,
        status: qs("d-status").value,
    };
    const pwd = qs("d-password").value.trim();
    if (pwd) obj.password = pwd;

    const clearE = qs("d-clear-emails").checked;
    const eList = parseList(qs("d-rec-emails").value);
    if (clearE) obj.recovery_emails = [];
    else if (eList.length) obj.recovery_emails = eList;

    const clearP = qs("d-clear-phones").checked;
    const pList = parseList(qs("d-rec-phones").value);
    if (clearP) obj.recovery_phones = [];
    else if (pList.length) obj.recovery_phones = pList;

    // 别名
    if (qs("d-aliases")) {
        const clearA = qs("d-clear-aliases") ? qs("d-clear-aliases").checked : false;
        const aList = parseAliases(qs("d-aliases").value);
        if (clearA) obj.aliases = [];
        else if (aList.length) obj.aliases = aList;
        // 若未勾选清空且无输入，则不传 aliases 字段，后端视为“不修改”
    }

    try {
        const res = await api.update(obj);
        if (res.errors && res.errors.length) {
            toast("更新失败：" + res.errors[0].error, true);
            return;
        }
        const s = (res.success && res.success[0]) || {};
        toast(s.no_change ? "无变更，已跳过" : "更新成功");
        await openDetail(state.currentId);
        await loadList();
    } catch (e) {
        toast("更新失败", true);
    }
}

/* ======================= History ======================= */
async function openHistory(id) {
    qs("m-accid").textContent = id;
    // 历史表头已新增“别名”，占位 colspan 调整为 11
    qs("tbl-history").innerHTML = `<tr><td colspan="11" class="muted">加载中...</td></tr>`;
    toggleHistory(true);
    try {
        const data = await api.history(id, 1, 200);
        if (!data.items.length) {
            qs("tbl-history").innerHTML = `<tr><td colspan="11" class="muted">暂无历史</td></tr>`;
            return;
        }
        qs("tbl-history").innerHTML = data.items
            .map((h) => {
                const statCls =
                    h.status === "未登录"
                        ? "status-normal"
                        : h.status === "登录成功"
                            ? "status-banned"
                            : "status-disabled";
                const rem = (h.recovery_emails || []).slice(0, 2).join(", ");
                const rpm = (h.recovery_phones || []).slice(0, 2).join(", ");
                const als = (h.aliases || []).slice(0, 2).join(", ");
                const remMore = (h.recovery_emails || []).length > 2 ? " ..." : "";
                const rpmMore = (h.recovery_phones || []).length > 2 ? " ..." : "";
                const alsMore = (h.aliases || []).length > 2 ? " ..." : "";
                return `<tr>
          <td><span class="code">${h.version}</span></td>
          <td>${h.email}</td>
          <td class="mono">${h.password || ""}</td>
          <td><span class="pill ${statCls}">${h.status}</span></td>
          <td class="muted">${rem}${remMore}</td>
          <td class="muted">${rpm}${rpmMore}</td>
          <td class="muted">${als}${alsMore}</td>
          <td>${h.note ? h.note : ""}</td>
          <td>${h.created_by ? h.created_by : ""}</td>
          <td class="muted">${h.created_at}</td>
          <td><button onclick="doRestore(${id}, ${h.version})" class="warn">恢复</button></td>
        </tr>`;
            })
            .join("");
    } catch (e) {
        qs("tbl-history").innerHTML = `<tr><td colspan="11" class="warn-text">加载历史失败</td></tr>`;
    }
}

async function doRestore(id, ver) {
    const body = {
        version: ver,
        note: qs("m-note").value.trim() || `恢复自版本 ${ver}`,
        created_by: qs("m-who").value.trim() || undefined,
    };
    if (!confirm(`确定将账号 ${id} 恢复到版本 ${ver}？`)) return;
    try {
        const r = await api.restore(id, body);
        toast(
            r.no_change ? "与当前内容相同，未产生新版本" : `已恢复，当前版本：${r.version}`
        );
        await openDetail(id);
        await loadList();
    } catch (e) {
        toast("恢复失败", true);
    }
}

function toggleHistory(show) {
    qs("modal-history").style.display = show ? "flex" : "none";
}

/* ======================= Delete (single) ======================= */
function openDelete(id, email) {
    window._delCtx = {id, email};
    qs("del-id").textContent = id;
    qs("del-email").textContent = email;
    qs("del-confirm").value = "";
    qs("btn-delete-confirm").disabled = true;
    toggleDelete(true);
}

function toggleDelete(show) {
    qs("modal-delete").style.display = show ? "flex" : "none";
}

function bindSingleDeleteEvents() {
    qs("del-confirm").addEventListener("input", () => {
        qs("btn-delete-confirm").disabled =
            qs("del-confirm").value.trim() !== "delete";
    });
    qs("btn-delete-cancel").onclick = () => toggleDelete(false);
    qs("btn-delete-confirm").onclick = async () => {
        try {
            await api.del(window._delCtx.id);
            toast("删除成功");
            toggleDelete(false);
            if (state.currentId === window._delCtx.id) {
                state.currentId = null;
                qs("detail-empty").classList.remove("hidden");
                qs("detail-form").classList.add("hidden");
            }
            state.selected.delete(window._delCtx.id);
            updateSelCount();
            await loadList();
        } catch (e) {
            toast("删除失败", true);
        }
    };
}

/* ======================= Batch Delete ======================= */
function openBatchDelete() {
    if (state.selected.size === 0) {
        toast("请先选择记录", true);
        return;
    }
    qs("bd-count").textContent = state.selected.size;
    qs("bd-confirm").value = "";
    qs("btn-bd-confirm").disabled = true;
    toggleBatchDel(true);
}

function toggleBatchDel(show) {
    qs("modal-batch-del").style.display = show ? "flex" : "none";
}

function bindBatchDeleteEvents() {
    qs("bd-confirm").addEventListener("input", () => {
        qs("btn-bd-confirm").disabled = qs("bd-confirm").value.trim() !== "delete";
    });
    qs("btn-bd-cancel").onclick = () => toggleBatchDel(false);
    qs("btn-bd-confirm").onclick = async () => {
        const ids = Array.from(state.selected);
        let ok = 0,
            err = 0;
        qs("btn-bd-confirm").disabled = true;
        for (const id of ids) {
            try {
                await api.del(id);
                ok++;
                state.selected.delete(id);
            } catch {
                err++;
            }
        }
        toggleBatchDel(false);
        updateSelCount();
        toast(
            `批量删除完成：成功 ${ok}，失败 ${err}${err ? "（请稍后重试）" : ""}`
        );
        if (state.currentId && !state.selected.has(state.currentId)) {
            try {
                await api.get(state.currentId);
            } catch {
                state.currentId = null;
                qs("detail-empty").classList.remove("hidden");
                qs("detail-form").classList.add("hidden");
            }
        }
        await loadList();
    };
}

/* ======================= Batch Note Update ======================= */
async function batchUpdateNote() {
    const note = qs("bulk-note").value.trim();
    const who = qs("bulk-who").value.trim();
    if (state.selected.size === 0) {
        toast("请先选择记录", true);
        return;
    }
    if (!note) {
        toast("请填写备注（note）", true);
        return;
    }
    const items = Array.from(state.selected).map((id) => ({
        id,
        note,
        created_by: who || undefined,
    }));
    try {
        const res = await api.updateBatch(items);
        const ok = (res.success || []).length;
        const err = (res.errors || []).length;
        const skipped = (res.success || []).filter((x) => x.no_change).length;
        toast(
            `批量备注完成：成功 ${ok}，失败 ${err}${
                skipped ? `，其中 ${skipped} 项无变更被跳过` : ""
            }`
        );
        await loadList();
    } catch (e) {
        toast("批量备注失败", true);
    }
}

/* ======================= Create (single) ======================= */
async function createOne() {
    const item = {
        email: qs("c-email").value.trim(),
        password: qs("c-password").value.trim(),
        status: qs("c-status").value,
        username: qs("c-username").value.trim() || undefined,
        birthday: qs("c-birthday").value.trim() || undefined,
        recovery_emails: parseList(qs("c-rec-emails").value),
        recovery_phones: parseList(qs("c-rec-phones").value),
        aliases: qs("c-aliases") ? parseAliases(qs("c-aliases").value) : [],
        note: qs("c-note").value.trim() || "初始导入",
        created_by: qs("c-who").value.trim() || undefined,
    };
    if (!item.email || !item.password) {
        toast("请填写邮箱与密码", true);
        return;
    }
    try {
        const res = await api.create(item);
        if (res.errors && res.errors.length) {
            toast("创建失败：" + res.errors[0].error, true);
            return;
        }
        toast("创建成功");
        [
            "c-email",
            "c-password",
            "c-username",
            "c-birthday",
            "c-rec-emails",
            "c-rec-phones",
            "c-note",
            "c-who",
            "c-aliases",
        ].forEach((id) => qs(id) && (qs(id).value = ""));
        await loadList();
    } catch (e) {
        toast("创建失败", true);
    }
}

/* ======================= CSV 解码（修复上传中文乱码） ======================= */
function decodeAuto(uint8) {
    const candidates = ["utf-8", "gb18030", "gbk", "big5"].filter((enc) => {
        try {
            new TextDecoder(enc);
            return true;
        } catch {
            return false;
        }
    });
    let best = {s: "", score: -Infinity};
    const cjk = /[\u4E00-\u9FFF]/g;
    for (const enc of candidates) {
        try {
            const s = new TextDecoder(enc, {fatal: false}).decode(uint8);
            const hasReplacement = s.includes("\uFFFD");
            const cjkCount = (s.match(cjk) || []).length;
            const score = (hasReplacement ? -1000 : 0) + cjkCount;
            if (score > best.score) best = {s, score};
        } catch {
        }
    }
    if (best.score === -Infinity) {
        best = {s: new TextDecoder("utf-8").decode(uint8), score: 0};
    }
    return best.s;
}

async function readFileSmart(file) {
    const buf = await file.arrayBuffer();
    const s = decodeAuto(new Uint8Array(buf));
    return s;
}

/* ======================= Batch upload: Frontend parse ======================= */
function csvParse(text, delimiter = ",") {
    const rows = [];
    let row = [],
        cur = "",
        inQuotes = false,
        i = 0;
    while (i < text.length) {
        const ch = text[i];
        if (ch === '"') {
            if (inQuotes && text[i + 1] === '"') {
                cur += '"';
                i += 2;
                continue;
            }
            inQuotes = !inQuotes;
            i++;
            continue;
        }
        if (!inQuotes && ch === delimiter) {
            row.push(cur);
            cur = "";
            i++;
            continue;
        }
        if (!inQuotes && (ch === "\n" || ch === "\r")) {
            if (ch === "\r" && text[i + 1] === "\n") i++;
            row.push(cur);
            rows.push(row);
            row = [];
            cur = "";
            i++;
            continue;
        }
        cur += ch;
        i++;
    }
    if (cur.length || row.length) {
        row.push(cur);
        rows.push(row);
    }
    return rows.filter((r) => r.some((c) => (c || "").trim().length));
}

function mapCsvToObjects(rows) {
    if (!rows.length) return [];
    const header = rows[0].map((h) => (h || "").trim().toLowerCase());
    const idx = (name) => header.indexOf(name);
    const objects = [];
    for (let i = 1; i < rows.length; i++) {
        const r = rows[i];
        const email = idx("email") >= 0 && r[idx("email")] ? r[idx("email")].trim() : "";
        const password =
            idx("password") >= 0 && r[idx("password")] ? r[idx("password")].trim() : "";
        if (!email || !password) continue;
        const status =
            idx("status") >= 0 && r[idx("status")] ? r[idx("status")].trim().toLowerCase() : "未登录";
        const username =
            idx("username") >= 0 && r[idx("username")] ? r[idx("username")].trim() : "";
        const birthday =
            idx("birthday") >= 0 && r[idx("birthday")] ? r[idx("birthday")].trim() : "";
        const recEmails =
            idx("recovery_emails") >= 0
                ? splitListField(r[idx("recovery_emails")])
                : [];
        const recPhones =
            idx("recovery_phones") >= 0
                ? splitListField(r[idx("recovery_phones")])
                : [];
        // 新增：aliases 列（用分号分隔，统一小写）
        const aliases =
            idx("aliases") >= 0
                ? splitListField(r[idx("aliases")]).map(x => x.toLowerCase())
                : [];

        const note = idx("note") >= 0 ? (r[idx("note")] || "").trim() : "";
        const created_by =
            idx("created_by") >= 0 ? (r[idx("created_by")] || "").trim() : "";
        objects.push({
            email,
            password,
            status: ["未登录", "登录成功", "登录失败"].includes(status)
                ? status
                : "未登录",
            username: username || undefined,
            birthday: birthday || undefined,
            recovery_emails: recEmails,
            recovery_phones: recPhones,
            aliases, // 新增
            note: note || "批量导入",
            created_by: created_by || undefined,
        });
    }
    return objects;
}

function bindBatchUploadEvents() {
    let lastParsed = [];
    qs("btn-parse-file").onclick = async () => {
        const file = qs("u-file").files[0];
        if (!file) {
            toast("请选择文件", true);
            return;
        }
        const text = await readFileSmart(file);
        const rows = csvParse(text, ",");
        const objects = mapCsvToObjects(rows);
        state.batchParsed = objects;
        lastParsed = rows;
        const sample = objects.slice(0, 5);
        qs("u-summary").textContent = `解析完成：${objects.length} 条可导入（文件行数：${rows.length}）`;
        qs("u-preview").innerHTML = objects.length
            ? `<div class="muted">前 5 条预览：</div>
         <pre class="mono" style="white-space:pre-wrap;background:#f8fafc;border:1px solid #e5e7eb;padding:8px;border-radius:8px;">${sample
                .map((o) => JSON.stringify(o))
                .join("\n")}</pre>`
            : `<span class="warn-text">未解析到有效数据。请确认包含表头 email,password,...</span>`;
        qs("btn-import-file").disabled = objects.length === 0;
    };
    qs("btn-import-file").onclick = async () => {
        const items = state.batchParsed || [];
        if (!items.length) {
            toast("无数据可导入", true);
            return;
        }
        const chunkSize = 200;
        let ok = 0,
            err = 0,
            errMsgs = [];
        qs("btn-import-file").disabled = true;
        for (let i = 0; i < items.length; i += chunkSize) {
            const chunk = items.slice(i, i + chunkSize);
            try {
                const res = await api.createBatch(chunk);
                ok += (res.success || []).length;
                err += (res.errors || []).length;
                if (res.errors && res.errors.length) {
                    errMsgs.push(...res.errors.map((e) => e.error || "error"));
                }
                qs("u-summary").textContent = `导入进度：${Math.min(
                    i + chunk.length,
                    items.length
                )}/${items.length}，成功 ${ok}，失败 ${err}`;
            } catch (e) {
                err += chunk.length;
                errMsgs.push("网络或服务错误");
            }
        }
        toast(
            `导入完成：成功 ${ok}，失败 ${err}${err ? "（检查重复/格式）" : ""}`
        );
        if (errMsgs.length) {
            qs("u-preview").innerHTML += `<div class="mt warn-text mono">部分错误：\n- ${errMsgs
                .slice(0, 5)
                .join("\n- ")}</div>`;
        }
        qs("btn-import-file").disabled = false;
        await loadList();
    };
}

/* ======================= Export with selectable fields ======================= */

// CSV 工具
function csvEscape(val) {
    if (val === null || val === undefined) return '""';
    const s = String(val);
    return `"${s.replace(/"/g, '""')}"`;
}

function buildCsv(records, fields) {
    const header = fields.join(",");
    const lines = [header];
    for (const r of records) {
        const row = fields.map((f) => {
            let v = r[f];
            if (Array.isArray(v)) v = v.join(";");
            return csvEscape(v ?? "");
        });
        lines.push(row.join(","));
    }
    return "\ufeff" + lines.join("\n"); // BOM for Excel
}

function downloadCsv(text, base) {
    const blob = new Blob([text], {type: "text/csv;charset=utf-8"});
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${base}_${Date.now()}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
}

function getCheckedExportFields() {
    const boxes = [...document.querySelectorAll(".exp-field")];
    return boxes.filter((b) => b.checked).map((b) => b.getAttribute("data-field"));
}

async function fetchDetailsByIds(ids, concurrency = 10) {
    const results = new Array(ids.length);
    let i = 0;

    async function worker() {
        while (true) {
            const idx = i++;
            if (idx >= ids.length) break;
            const id = ids[idx];
            try {
                const r = await api.get(id);
                results[idx] = r;
            } catch {
                results[idx] = null;
            }
        }
    }

    const workers = new Array(Math.min(concurrency, ids.length))
        .fill(0)
        .map(() => worker());
    await Promise.all(workers);
    return results.filter(Boolean);
}

async function fetchAllUnderFilters(fields) {
    // 使用列表接口分页抓取所有结果
    const baseSize = 1000; // 尽量大，减少请求次数
    const p = new URLSearchParams();
    p.set("page", 1);
    p.set("size", baseSize);
    const f = state.filters;
    if (f.email_contains) p.set("email_contains", f.email_contains);
    if (f.status) p.set("status", f.status);
    if (f.rec_email_contains)
        p.set("recovery_email_contains", f.rec_email_contains);
    if (f.rec_phone) p.set("recovery_phone", f.rec_phone);
    if (f.note_contains) p.set("note_contains", f.note_contains);

    const first = await api.list(`?${p.toString()}`);
    let items = first.items || [];
    const pages = first.pages || 1;
    for (let page = 2; page <= pages; page++) {
        p.set("page", page);
        const data = await api.list(`?${p.toString()}`);
        items = items.concat(data.items || []);
    }
    return items;
}

function openExportModal() {
    toggleExportModal(true);
}

function toggleExportModal(show) {
    qs("modal-export").style.display = show ? "flex" : "none";
}

function bindExportModal() {
    // 全选/反选
    qs("exp-select-all").onclick = () => {
        document.querySelectorAll(".exp-field").forEach((el) => (el.checked = true));
    };
    qs("exp-invert").onclick = () => {
        document.querySelectorAll(".exp-field").forEach((el) => (el.checked = !el.checked));
    };
    qs("btn-export-cancel").onclick = () => toggleExportModal(false);

    // 确认导出
    qs("btn-export-confirm").onclick = async () => {
        const fields = getCheckedExportFields();
        if (!fields.length) {
            toast("请至少选择一个字段", true);
            return;
        }
        const btn = qs("btn-export-confirm");
        btn.disabled = true;
        btn.textContent = "导出准备中...";

        try {
            const selectedIds = Array.from(state.selected);
            if (selectedIds.length > 0) {
                // 优先导出选中项（逐条详情）
                const details = await fetchDetailsByIds(selectedIds, 10);
                const records = details.map((r) => mapRecordToFields(r));
                const csv = buildCsv(records, fields);
                downloadCsv(csv, "accounts_selected_export");
                toggleExportModal(false);
                btn.disabled = false;
                btn.textContent = "导出为 CSV";
                return;
            }
            // 否则导出搜索结果全部（抓全量列表）
            btn.textContent = "拉取数据...";
            const all = await fetchAllUnderFilters(fields);
            if (!all.length) {
                toast("没有可导出的数据", true);
                btn.disabled = false;
                btn.textContent = "导出为 CSV";
                return;
            }
            const records = all.map((r) => mapRecordToFields(r));
            const csv = buildCsv(records, fields);
            downloadCsv(csv, "accounts_export");
            toggleExportModal(false);
        } catch (e) {
            toast("导出失败", true);
        }
        btn.disabled = false;
        btn.textContent = "导出为 CSV";
    };
}

// 统一字段映射，确保字段名存在
function mapRecordToFields(r) {
    // r 可能来自 get 或 list，字段一致
    return {
        id: r.id,
        email: r.email || "",
        username: r.username || "",
        birthday: r.birthday || "",
        password: r.password || "",
        status: r.status || "",
        version: r.version || "",
        created_at: r.created_at || "",
        updated_at: r.updated_at || "",
        recovery_emails: r.recovery_emails || [],
        recovery_phones: r.recovery_phones || [],
        aliases: r.aliases || [], // 新增：导出支持
    };
}

/* ======================= Search & Paging ======================= */
function bindSearchAndPaging() {
    qs("btn-search").onclick = () => {
        state.filters.email_contains = qs("f-email-contains").value.trim();
        state.filters.status = qs("f-status").value;
        state.filters.rec_email_contains = qs("f-rec-email").value.trim();
        state.filters.rec_phone = qs("f-rec-phone").value.trim();
        state.filters.note_contains = qs("f-note").value.trim();
        state.page = 1;
        loadList();
    };
    qs("btn-reset").onclick = () => {
        ["f-email-contains", "f-rec-email", "f-rec-phone", "f-note"].forEach(
            (id) => (qs(id).value = "")
        );
        qs("f-status").value = "";
        state.filters = {
            email_contains: "",
            status: "",
            rec_email_contains: "",
            rec_phone: "",
            note_contains: "",
        };
        state.page = 1;
        loadList();
    };
    qs("btn-prev").onclick = () => {
        if (state.page > 1) {
            state.page--;
            loadList();
        }
    };
    qs("btn-next").onclick = () => {
        if (state.page < state.listPages) {
            state.page++;
            loadList();
        }
    };
    qs("pg-size").onchange = () => {
        state.size = parseInt(qs("pg-size").value, 10);
        state.page = 1;
        loadList();
    };
}

/* ======================= Create modal controls ======================= */
function bindCreateModal() {
    function toggleCreate(show) {
        qs("modal-create").style.display = show ? "flex" : "none";
    }

    qs("btn-open-create").onclick = () => toggleCreate(true);
    qs("btn-close-create").onclick = () => toggleCreate(false);
    qs("tab-single").onclick = () => {
        qs("tab-single").classList.add("active");
        qs("tab-batch").classList.remove("active");
        qs("panel-single").classList.remove("hidden");
        qs("panel-batch").classList.add("hidden");
    };
    qs("tab-batch").onclick = () => {
        qs("tab-batch").classList.add("active");
        qs("tab-single").classList.remove("active");
        qs("panel-batch").classList.remove("hidden");
        qs("panel-single").classList.add("hidden");
    };
}

/* ======================= Header checkbox (select all) ======================= */
function bindSelectAll() {
    qs("chk-all").addEventListener("change", (e) => {
        const rows = document.querySelectorAll(".chk-row");
        if (e.target.checked) {
            rows.forEach((chk) => {
                chk.checked = true;
                state.selected.add(parseInt(chk.getAttribute("data-id"), 10));
            });
        } else {
            rows.forEach((chk) => {
                chk.checked = false;
                state.selected.delete(parseInt(chk.getAttribute("data-id"), 10));
            });
        }
        updateSelCount();
    });
}

// ============ 查看邮件弹窗 ============

// 打开弹窗
function openMailsModal() {
    if (!state.currentId) {
        toast('请先选择一个账号', true);
        return;
    }
    // 重置查询条件
    state.mails.q = '';
    state.mails.folder = '';
    state.mails.page = 1;
    state.mails.size = parseInt(qs('mails-pg-size').value, 10) || 50;
    qs('mails-q').value = '';
    qs('mails-folder').value = '';
    qs('mails-view-subject').textContent = '（选择左侧一封邮件以预览）';
    qs('mails-view-from').textContent = '';
    qs('mails-view-time').textContent = '';
    qs('mails-view-folder').textContent = '';
    qs('mails-view-labels').textContent = '';
    qs('mails-view-attach').innerHTML = '';
    qs('mails-view-body-html').innerHTML = '';
    qs('mails-view-body-html').classList.add('hidden');
    qs('mails-view-body-plain').textContent = '';
    qs('mails-view-body-plain').classList.add('hidden');

    loadMailsList();
    toggleMailsModal(true);
}

// 关闭弹窗
function toggleMailsModal(show) {
    qs('modal-mails').style.display = show ? 'flex' : 'none';
}

// 加载账号下邮件列表
async function loadMailsList() {
    qs('mails-tbody').innerHTML = `<tr><td colspan="3" class="muted">加载中...</td></tr>`;
    try {
        const res = await api.mailsList(state.currentId, {
            q: state.mails.q,
            page: state.mails.page,
            size: state.mails.size,
            folder: state.mails.folder
        });
        state.mails.total = res.total || 0;
        state.mails.pages = res.pages || 1;

        qs('mails-pg-info').textContent = `第 ${res.page}/${state.mails.pages} 页（共 ${res.total} 封）`;

        if (!res.items || !res.items.length) {
            qs('mails-tbody').innerHTML = `<tr><td colspan="3" class="muted">暂无数据</td></tr>`;
            state.mails.listMap = {};
            return;
        }

        // 缓存
        const map = {};
        const rowsHtml = res.items.map(row => {
            map[row.id] = row;
            const subj = row.subject || '(无主题)';
            const from = row.from_addr || '';
            const time = row.received_at || '';
            // 点击事件：预览邮件
            return `<tr class="mail-row" data-id="${row.id}">
                <td style="max-width:360px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escapeHtml(subj)}</td>
                <td style="max-width:240px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escapeHtml(from)}</td>
                <td style="white-space:nowrap;">${escapeHtml(time)}</td>
              </tr>`;
        }).join('');

        state.mails.listMap = map;
        qs('mails-tbody').innerHTML = rowsHtml;

        // 绑定行点击
        document.querySelectorAll('.mail-row').forEach(tr => {
            tr.addEventListener('click', () => {
                const id = parseInt(tr.getAttribute('data-id'), 10);
                selectMail(id);
            });
        });

    } catch (e) {
        qs('mails-tbody').innerHTML = `<tr><td colspan="3" class="warn-text">加载失败</td></tr>`;
        toast('加载邮件失败', true);
    }
}

// 预览某封邮件
async function selectMail(messageId) {
    try {
        const detail = await api.mailDetail(messageId);
        // 优先使用列表缓存中的元数据（补足 folder/labels），detail.body 提供 html/plain/headers
        const meta = state.mails.listMap[messageId] || {};
        const subj = (detail.subject || meta.subject || '(无主题)');
        const from = (detail.from_addr || meta.from_addr || '');
        const time = (detail.received_at || meta.received_at || '');
        const folder = (detail.folder || meta.folder || '');
        const labels = (detail.labels_joined || meta.labels_joined || '');

        qs('mails-view-subject').textContent = subj;
        qs('mails-view-from').textContent = from ? `From: ${from}` : '';
        qs('mails-view-time').textContent = time ? `时间: ${time}` : '';
        qs('mails-view-folder').textContent = folder ? `文件夹: ${folder}` : '';
        qs('mails-view-labels').textContent = labels ? `标签: ${labels}` : '';

        // 附件
        const atts = detail.attachments || [];
        if (atts.length) {
            qs('mails-view-attach').innerHTML = atts.map(a => `<a href="${encodeURI(a.storage_url)}" target="_blank" rel="noopener">附件</a>`).join('');
        } else {
            qs('mails-view-attach').innerHTML = '';
        }

        // 显示正文（html 优先，退回到 plain）
        const html = detail.body && detail.body.body_html;
        const plain = detail.body && detail.body.body_plain;
        const htmlEl = qs('mails-view-body-html');
        const plainEl = qs('mails-view-body-plain');
        if (html && html.trim()) {
            htmlEl.innerHTML = html;   // 注意：如需更高安全性，可在服务端做清洗
            htmlEl.classList.remove('hidden');
            plainEl.classList.add('hidden');
            plainEl.textContent = '';
        } else {
            htmlEl.innerHTML = '';
            htmlEl.classList.add('hidden');
            plainEl.textContent = plain || '(无正文)';
            plainEl.classList.remove('hidden');
        }
    } catch (e) {
        toast('加载邮件详情失败', true);
    }
}

// 工具：简单 HTML 转义（用于列表列的安全显示）
function escapeHtml(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/[&<>"']/g, c => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[c]));
}

/* ======================= Expose for inline events ======================= */
window.openDetail = openDetail;
window.openHistory = openHistory;
window.openDelete = openDelete;
window.doRestore = doRestore;

/* ======================= Bind static buttons ======================= */
function bindStaticButtons() {
    qs("btn-save").onclick = saveUpdate;
    qs("btn-show-history").onclick = () =>
        state.currentId && openHistory(state.currentId);
    qs("btn-refresh-detail").onclick = refreshDetail;
    qs("btn-close-history").onclick = () => toggleHistory(false);
    qs("btn-create").onclick = createOne;

    // 导出：弹出字段选择框
    qs("btn-export").onclick = openExportModal;

    // 批量操作
    qs("btn-batch-delete").onclick = openBatchDelete;
    qs("bulk-note").addEventListener("input", updateSelCount);
    qs("btn-batch-note").onclick = batchUpdateNote;
    qs('btn-show-mails').onclick = openMailsModal;
    qs('btn-close-mails').onclick = () => toggleMailsModal(false);

    // 左侧列表查询与分页
    qs('mails-btn-search').onclick = () => {
        state.mails.q = qs('mails-q').value.trim();
        state.mails.folder = qs('mails-folder').value.trim();
        state.mails.page = 1;
        state.mails.size = parseInt(qs('mails-pg-size').value, 10) || 50;
        loadMailsList();
    };
    qs('mails-btn-reset').onclick = () => {
        qs('mails-q').value = '';
        qs('mails-folder').value = '';
        state.mails.q = '';
        state.mails.folder = '';
        state.mails.page = 1;
        state.mails.size = parseInt(qs('mails-pg-size').value, 10) || 50;
        loadMailsList();
    };
    qs('mails-btn-prev').onclick = () => {
        if (state.mails.page > 1) {
            state.mails.page--;
            loadMailsList();
        }
    };
    qs('mails-btn-next').onclick = () => {
        if (state.mails.page < state.mails.pages) {
            state.mails.page++;
            loadMailsList();
        }
    };
    qs('mails-pg-size').onchange = () => {
        state.mails.size = parseInt(qs('mails-pg-size').value, 10) || 50;
        state.mails.page = 1;
        loadMailsList();
    };
}

/* ======================= Init ======================= */
(function init() {
    qs("detail-empty").classList.remove("hidden");
    qs("detail-form").classList.add("hidden");

    updateSelCount();
    bindStaticButtons();
    bindSelectAll();
    bindSearchAndPaging();
    bindCreateModal();
    bindBatchUploadEvents();
    bindSingleDeleteEvents();
    bindBatchDeleteEvents();
    bindExportModal();
    loadList();
})();