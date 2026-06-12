const state = {
    bootstrap: null,
    selectedTemplate: null,
    currentView: "templates",
    selectedAdminId: null,
    adminCreating: false,
    language: localStorage.getItem("toolgrinder-language") === "en" ? "en" : "de",
};

const translations = {
    de: {
        language: "Sprache", subtitle: "Werkzeugdaten, Strategien und sichere G-Code-Erzeugung",
        mainNavigation: "Hauptnavigation", dashboard: "Übersicht", templates: "Fräser-Vorlagen",
        cutters: "Geschärfte Fräser", grindingTools: "Schleifwerkzeuge", strategies: "Strategien",
        jobs: "Aufträge", settings: "Einstellungen", templateHint: "Dynamische Stammdaten aus der Datenbank",
        searchTemplates: "Name, Typ oder Material suchen", database: "Datenbank", activeTemplates: "aktive Vorlagen",
        selectedTemplate: "Ausgewählte Vorlage", saveTemplate: "Vorlage speichern",
        prepareJob: "Auftrag vorbereiten", identity: "Identität", name: "Bezeichnung", type: "Fräsertyp",
        material: "Material", geometry: "Geometrie", nominalDiameter: "Nenndurchmesser",
        cuttingLength: "Schneidenlänge", targetDiameter: "Zieldurchmesser",
        cuttingData: "Schneiden und Drall", flutes: "Schneidenzahl", helix: "Drall Grad/mm",
        frontXEnd: "Stirn X Ende", jobSetup: "Auftragsvorbereitung", physicalCutter: "Konkreter Fräser",
        strategy: "Strategie", mode: "Modus", edgeFront: "Umfang + Stirn", edge: "Umfang",
        front: "Stirn", measure: "Vermessen", toolPreview: "Werkzeugdarstellung",
        validated: "Strukturell validiert", validationHint: "Generatorprüfung erfolgt vor Ausgabe",
        process: "Prozessablauf", templateStep: "Vorlage", cutterStep: "Fräser", measureStep: "Vermessen",
        strategyStep: "Strategie", gcodeStep: "G-Code", resultStep: "Ergebnis",
        recentJobs: "Letzte Aufträge", historyHint: "Unveränderliche Parameter-Snapshots je Generierung",
        jobNumber: "Auftrag", toolId: "Werkzeug-ID", template: "Vorlage", statusLabel: "Status",
        date: "Datum", newTemplate: "Neue Vorlage",
        newTemplateHint: "Die neue Vorlage übernimmt sichere Grundwerte der aktuell ausgewählten Vorlage.",
        cancel: "Abbrechen", create: "Anlegen", ready: "Bereit", loading: "Laden",
        saving: "Speichern", saved: "Gespeichert", generating: "Generiere", finished: "Fertig",
        noJobs: "Noch keine Aufträge erzeugt", noMatchingTemplates: "Keine passende Vorlage",
        noCutter: "Kein konkreter Fräser", templateCreated: "Vorlage wurde angelegt.",
        templateSaved: "Vorlage wurde gespeichert.", generated: "G-Code wurde erzeugt.",
        cutterIdentity: "Werkzeugidentität", currentState: "Aktueller Zustand",
        currentDiameter: "Ist-Durchmesser", currentLength: "Ist-Länge", location: "Lagerort",
        notes: "Notizen", save: "Speichern", grindingToolData: "Schleifwerkzeugdaten",
        toolType: "Werkzeugart", probe: "Taster", specification: "Spezifikation",
        diameter: "Durchmesser", maxRpm: "Max. Drehzahl",
        strategyVersionHint: "Änderungen erzeugen immer eine neue, nachvollziehbare Strategieversion.",
        strategyData: "Strategiedaten", draft: "Entwurf", released: "Freigegeben",
        retired: "Stillgelegt", requiresMeasurement: "Vermessung erforderlich",
        descriptionDe: "Beschreibung Deutsch", descriptionEn: "Beschreibung Englisch",
        createVersion: "Neue Version anlegen", jobHistory: "Auftragshistorie",
        newCutter: "Neuer konkreter Fräser", newGrindingTool: "Neues Schleifwerkzeug",
        newStrategy: "Neue Strategieversion", manageCutters: "Werkzeugbestand und Lebenslauf verwalten",
        manageWheels: "Schleifscheiben und Taster verwalten",
        manageStrategies: "Versionierte und freigegebene Bearbeitungsvorschriften",
        manageJobs: "Erzeugte Aufträge und unveränderliche Snapshots",
        recordSaved: "Datensatz wurde gespeichert.", versionCreated: "Strategieversion wurde angelegt.",
        search: "Suchen", newRecord: "Neu anlegen",
        standardGeometry: "Normnahe Werkzeugmerkmale", toolFamily: "Werkzeugfamilie",
        endMill: "Schaftfräser", ballNose: "Kugelkopffräser", radiusMill: "Torusfräser",
        drill: "Bohrer", reamer: "Reibahle", countersink: "Senker",
        cuttingDirection: "Schneidrichtung", rightHand: "Rechtsschneidend", leftHand: "Linksschneidend",
        helixDirection: "Drallrichtung", rightHelix: "Rechtsdrall", leftHelix: "Linksdrall",
        straightFlute: "Geradegenutet", helixAngle: "Drallwinkel", cornerStyle: "Eckenform",
        squareCorner: "Scharfkantig", cornerRadius: "Eckenradius", cornerChamfer: "Eckenfase",
        fullRadius: "Vollradius", cornerRadiusValue: "Eckenradius", coating: "Beschichtung",
        shankForm: "Schaftform", cylindrical: "Zylindrisch", weldon: "Weldon",
        whistleNotch: "Whistle-Notch", coolantSupply: "Kühlmittelzufuhr", none: "Keine",
        external: "Extern", internal: "Innenkühlung", centerCutting: "Zentrumschneidend",
        variablePitch: "Ungleiche Teilung",
        helixValueSource: "Quelle der Drallangabe", manufacturerValue: "Herstellerangabe",
        measuredValue: "An Maschine gemessen", unknownValue: "Noch unbekannt",
        angleToSlope: "Winkel → Grad/mm", slopeToAngle: "Grad/mm → Winkel",
        conversionDone: "Drallwert wurde aus Durchmesser und Zylinderhelix umgerechnet.",
        helixSeparationNote: "Drallwinkel (°) beschreibt die Werkzeuggeometrie. Grad/mm bleibt getrennt als kinematische A/X-Steigung des Generators gespeichert.",
    },
    en: {
        language: "Language", subtitle: "Tool data, strategies and safe G-code generation",
        mainNavigation: "Main navigation", dashboard: "Overview", templates: "Cutter templates",
        cutters: "Sharpened cutters", grindingTools: "Grinding tools", strategies: "Strategies",
        jobs: "Jobs", settings: "Settings", templateHint: "Dynamic master data from the database",
        searchTemplates: "Search name, type or material", database: "Database", activeTemplates: "active templates",
        selectedTemplate: "Selected template", saveTemplate: "Save template",
        prepareJob: "Prepare job", identity: "Identity", name: "Name", type: "Cutter type",
        material: "Material", geometry: "Geometry", nominalDiameter: "Nominal diameter",
        cuttingLength: "Cutting length", targetDiameter: "Target diameter",
        cuttingData: "Cutting edges and helix", flutes: "Number of flutes", helix: "Helix deg/mm",
        frontXEnd: "End-face X end", jobSetup: "Job preparation", physicalCutter: "Physical cutter",
        strategy: "Strategy", mode: "Mode", edgeFront: "Peripheral + end", edge: "Peripheral",
        front: "End", measure: "Measure", toolPreview: "Tool preview",
        validated: "Structurally validated", validationHint: "Generator validation runs before output",
        process: "Process", templateStep: "Template", cutterStep: "Cutter", measureStep: "Measure",
        strategyStep: "Strategy", gcodeStep: "G-code", resultStep: "Result",
        recentJobs: "Recent jobs", historyHint: "Immutable parameter snapshots for every generation",
        jobNumber: "Job", toolId: "Tool ID", template: "Template", statusLabel: "Status",
        date: "Date", newTemplate: "New template",
        newTemplateHint: "The new template inherits safe base values from the selected template.",
        cancel: "Cancel", create: "Create", ready: "Ready", loading: "Loading",
        saving: "Saving", saved: "Saved", generating: "Generating", finished: "Done",
        noJobs: "No jobs generated yet", noMatchingTemplates: "No matching template",
        noCutter: "No physical cutter", templateCreated: "Template created.",
        templateSaved: "Template saved.", generated: "G-code generated.",
        cutterIdentity: "Tool identity", currentState: "Current condition",
        currentDiameter: "Current diameter", currentLength: "Current length", location: "Location",
        notes: "Notes", save: "Save", grindingToolData: "Grinding tool data",
        toolType: "Tool type", probe: "Probe", specification: "Specification",
        diameter: "Diameter", maxRpm: "Max. speed",
        strategyVersionHint: "Changes always create a new traceable strategy version.",
        strategyData: "Strategy data", draft: "Draft", released: "Released",
        retired: "Retired", requiresMeasurement: "Measurement required",
        descriptionDe: "German description", descriptionEn: "English description",
        createVersion: "Create new version", jobHistory: "Job history",
        newCutter: "New physical cutter", newGrindingTool: "New grinding tool",
        newStrategy: "New strategy version", manageCutters: "Manage tool inventory and lifecycle",
        manageWheels: "Manage grinding wheels and probes",
        manageStrategies: "Versioned and released machining instructions",
        manageJobs: "Generated jobs and immutable snapshots",
        recordSaved: "Record saved.", versionCreated: "Strategy version created.",
        search: "Search", newRecord: "Create new",
        standardGeometry: "Standardized tool characteristics", toolFamily: "Tool family",
        endMill: "End mill", ballNose: "Ball nose", radiusMill: "Corner-radius mill",
        drill: "Drill", reamer: "Reamer", countersink: "Countersink",
        cuttingDirection: "Cutting direction", rightHand: "Right cutting", leftHand: "Left cutting",
        helixDirection: "Helix direction", rightHelix: "Right helix", leftHelix: "Left helix",
        straightFlute: "Straight flute", helixAngle: "Helix angle", cornerStyle: "Corner style",
        squareCorner: "Square", cornerRadius: "Corner radius", cornerChamfer: "Corner chamfer",
        fullRadius: "Full radius", cornerRadiusValue: "Corner radius", coating: "Coating",
        shankForm: "Shank form", cylindrical: "Cylindrical", weldon: "Weldon",
        whistleNotch: "Whistle notch", coolantSupply: "Coolant supply", none: "None",
        external: "External", internal: "Internal", centerCutting: "Center cutting",
        variablePitch: "Variable pitch",
        helixValueSource: "Source of helix value", manufacturerValue: "Manufacturer value",
        measuredValue: "Measured on machine", unknownValue: "Not known yet",
        angleToSlope: "Angle → deg/mm", slopeToAngle: "deg/mm → angle",
        conversionDone: "Helix value converted using diameter and cylindrical helix geometry.",
        helixSeparationNote: "Helix angle (°) describes tool geometry. Degrees/mm remains separate as the generator's kinematic A/X slope.",
    },
};

const $ = selector => document.querySelector(selector);
const t = key => translations[state.language][key] || translations.de[key] || key;

function applyLanguage(language) {
    state.language = language === "en" ? "en" : "de";
    localStorage.setItem("toolgrinder-language", state.language);
    document.documentElement.lang = state.language;
    $("#languageSelect").value = state.language;
    document.querySelectorAll("[data-i18n]").forEach(element => {
        element.textContent = t(element.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-aria-label]").forEach(element => {
        element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel));
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(element => {
        element.setAttribute("placeholder", t(element.dataset.i18nPlaceholder));
    });
    setStatus($("#status").dataset.statusKey || "ready");
    renderStrategies();
    renderJobs();
    if (state.currentView !== "templates") renderAdminView();
}

function setStatus(key) {
    $("#status").dataset.statusKey = key;
    $("#status").textContent = t(key);
}

async function api(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {"Content-Type": "application/json", ...(options.headers || {})},
    });
    const payload = await response.json();
    if (!response.ok || payload.ok === false) {
        throw new Error((payload.errors || ["Request failed"]).join("\n"));
    }
    return payload;
}

async function loadBootstrap(selectId = null) {
    setStatus("loading");
    state.bootstrap = await api("/api/bootstrap");
    renderTemplates();
    renderCutters();
    renderStrategies();
    renderGrindingTools();
    renderJobs();
    const id = selectId || state.selectedTemplate?.id || state.bootstrap.templates[0]?.id;
    if (id) await selectTemplate(id);
    setStatus("ready");
}

function renderTemplates() {
    const query = $("#templateSearch").value.trim().toLocaleLowerCase(state.language);
    const templates = (state.bootstrap?.templates || []).filter(item =>
        [item.name, item.type, item.material].join(" ").toLocaleLowerCase(state.language).includes(query)
    );
    $("#templateCount").textContent = state.bootstrap?.templates.length || 0;
    $("#templateList").innerHTML = templates.length ? templates.map(item => `
        <button class="entity-row ${state.selectedTemplate?.id === item.id ? "active" : ""}" data-template-id="${item.id}" type="button">
            <span class="tool-mini" aria-hidden="true"></span>
            <span><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.type)} · ${escapeHtml(item.material)} · Ø ${formatNumber(item.diameter)}</small></span>
            <span class="entity-arrow">›</span>
        </button>`).join("") : `<div class="empty-row">${t("noMatchingTemplates")}</div>`;
    document.querySelectorAll("[data-template-id]").forEach(button => {
        button.addEventListener("click", () => selectTemplate(Number(button.dataset.templateId)));
    });
}

async function selectTemplate(id) {
    state.selectedTemplate = await api(`/api/cutter-templates/${id}`);
    const item = state.selectedTemplate;
    const cfg = item.config || {};
    const cutter = cfg.fraeser || {};
    const actions = cfg.aktionen || {};
    const metadata = item.metadata || {};
    $("#templateTitle").textContent = item.name;
    $("#templateMeta").textContent = `${item.type}  |  ${item.material}  |  v${item.version}`;
    $("#fieldName").value = item.name || "";
    $("#fieldType").value = item.type || "";
    $("#fieldMaterial").value = item.material || "VHM";
    $("#fieldDiameter").value = cutter.durchmesser ?? "";
    $("#fieldCuttingLength").value = cutter.schneidenlaenge ?? "";
    $("#fieldFlutes").value = cutter.schneidenanzahl ?? "";
    $("#fieldHelix").value = cutter.drall_grad_pro_mm ?? "";
    $("#fieldTargetDiameter").value = actions.schneiden?.durchmesser_geschaerft ?? "";
    $("#fieldFrontXEnd").value = actions.front?.x_end ?? "";
    $("#fieldToolFamily").value = metadata.tool_family || "end_mill";
    $("#fieldCuttingDirection").value = metadata.cutting_direction || "right";
    $("#fieldHelixDirection").value = metadata.helix_direction || "right";
    $("#fieldHelixAngle").value = metadata.helix_angle_deg ?? "";
    $("#fieldHelixSource").value = metadata.helix_value_source || "unknown";
    $("#fieldCornerStyle").value = metadata.corner_style || "square";
    $("#fieldCornerRadius").value = metadata.corner_radius ?? "";
    $("#fieldCoating").value = metadata.coating || "";
    $("#fieldShankForm").value = metadata.shank_form || "cylindrical";
    $("#fieldCoolantSupply").value = metadata.coolant_supply || "none";
    $("#fieldCenterCutting").checked = metadata.center_cutting ?? true;
    $("#fieldVariablePitch").checked = Boolean(metadata.variable_pitch);
    $("#figureDiameter").textContent = `Ø ${formatNumber(cutter.durchmesser)}`;
    renderTemplates();
    renderCutters();
}

function formPayload() {
    return {
        name: $("#fieldName").value,
        type: $("#fieldType").value,
        material: $("#fieldMaterial").value,
        diameter: Number($("#fieldDiameter").value),
        cutting_length: Number($("#fieldCuttingLength").value),
        flutes: Number($("#fieldFlutes").value),
        helix: Number($("#fieldHelix").value),
        target_diameter: Number($("#fieldTargetDiameter").value),
        front_x_end: Number($("#fieldFrontXEnd").value),
        tool_family: $("#fieldToolFamily").value,
        cutting_direction: $("#fieldCuttingDirection").value,
        helix_direction: $("#fieldHelixDirection").value,
        helix_angle_deg: $("#fieldHelixAngle").value || null,
        helix_value_source: $("#fieldHelixSource").value,
        corner_style: $("#fieldCornerStyle").value,
        corner_radius: $("#fieldCornerRadius").value || null,
        coating: $("#fieldCoating").value,
        shank_form: $("#fieldShankForm").value,
        coolant_supply: $("#fieldCoolantSupply").value,
        center_cutting: $("#fieldCenterCutting").checked,
        variable_pitch: $("#fieldVariablePitch").checked,
    };
}

async function saveTemplate() {
    if (!state.selectedTemplate) return;
    setStatus("saving");
    const result = await api(`/api/cutter-templates/${state.selectedTemplate.id}`, {
        method: "PATCH", body: JSON.stringify(formPayload()),
    });
    state.selectedTemplate = result.template;
    await loadBootstrap(result.template.id);
    setStatus("saved");
    showToast(t("templateSaved"));
}

function renderCutters() {
    const select = $("#cutterSelect");
    const relevant = (state.bootstrap?.cutters || []).filter(
        cutter => !state.selectedTemplate || cutter.template_id === state.selectedTemplate.id
    );
    const fallback = state.bootstrap?.cutters || [];
    const cutters = relevant.length ? relevant : fallback;
    select.innerHTML = cutters.length
        ? cutters.map(item => `<option value="${item.id}">${escapeHtml(item.tool_uid)} · Ø ${formatNumber(item.current_diameter)}</option>`).join("")
        : `<option value="">${t("noCutter")}</option>`;
}

function renderStrategies() {
    if (!state.bootstrap) return;
    const mode = $("#modeSelect").value;
    const strategies = state.bootstrap.strategies.filter(item =>
        item.status === "released" && (item.parameters?.modes || []).includes(mode)
    );
    $("#strategySelect").innerHTML = strategies.map(item => {
        const description = state.language === "en" ? item.description_en : item.description_de;
        return `<option value="${item.id}" title="${escapeHtml(description)}">${escapeHtml(item.name)} · v${item.version}</option>`;
    }).join("") || `<option value="">-</option>`;
}

function renderGrindingTools() {
    $("#grindingToolList").innerHTML = (state.bootstrap?.grinding_tools || []).map(item => `
        <div class="compact-row"><span><strong>${escapeHtml(item.name)}</strong><br>${escapeHtml(item.tool_uid)}</span>
        <span>${escapeHtml(item.specification)}<br>Ø ${formatNumber(item.diameter)}</span></div>`).join("");
}

function renderJobs() {
    if (!state.bootstrap) return;
    const jobs = state.bootstrap.recent_jobs || [];
    $("#jobsTable").innerHTML = jobs.length ? jobs.map(job => `
        <tr><td>${escapeHtml(job.job_number)}</td><td>${escapeHtml(job.tool_uid)}</td>
        <td>${escapeHtml(job.template_name)}</td><td>${escapeHtml(job.mode)}</td>
        <td>${formatNumber(job.target_diameter)}</td><td class="status-generated">${escapeHtml(job.status)}</td>
        <td>${formatDate(job.created_at)}</td></tr>`).join("")
        : `<tr><td colspan="7" class="empty-row">${t("noJobs")}</td></tr>`;
}

const statusOptions = ["ready", "maintenance", "blocked", "retired"];

function showView(view) {
    state.currentView = view;
    state.selectedAdminId = null;
    state.adminCreating = false;
    document.querySelector(".workspace").hidden = view !== "templates";
    document.querySelector(".library-pane").hidden = view !== "templates";
    $("#adminWorkspace").hidden = view === "templates";
    document.querySelectorAll(".nav-item").forEach(button => {
        button.classList.toggle("active", button.dataset.view === view);
    });
    if (view !== "templates") renderAdminView();
}

function adminCollection() {
    if (state.currentView === "cutters") return state.bootstrap?.cutters || [];
    if (state.currentView === "wheels") return state.bootstrap?.grinding_tools || [];
    if (state.currentView === "strategies") return state.bootstrap?.strategies || [];
    if (state.currentView === "jobs") return state.bootstrap?.recent_jobs || [];
    return [];
}

function adminViewConfig() {
    return {
        cutters: {title: t("cutters"), hint: t("manageCutters"), newLabel: t("newCutter")},
        wheels: {title: t("grindingTools"), hint: t("manageWheels"), newLabel: t("newGrindingTool")},
        strategies: {title: t("strategies"), hint: t("manageStrategies"), newLabel: t("newStrategy")},
        jobs: {title: t("jobs"), hint: t("manageJobs"), newLabel: ""},
    }[state.currentView];
}

function renderAdminView() {
    const config = adminViewConfig();
    if (!config) {
        showToast(state.currentView === "dashboard" || state.currentView === "settings"
            ? t("manageJobs") : t("ready"));
        showView("templates");
        return;
    }
    $("#adminTitle").textContent = config.title;
    $("#adminEyeline").textContent = t("database");
    $("#adminHint").textContent = config.hint;
    $("#adminNew").textContent = config.newLabel;
    $("#adminNew").hidden = state.currentView === "jobs";
    $("#adminSearch").placeholder = t("search");
    hideAdminForms();
    if (state.currentView === "jobs") {
        $("#jobsAdminPanel").hidden = false;
        renderAllJobs();
    } else {
        renderAdminList();
        if (state.selectedAdminId) fillAdminForm(state.selectedAdminId);
        else startAdminCreate();
    }
}

function renderAdminList() {
    const query = $("#adminSearch").value.trim().toLocaleLowerCase(state.language);
    const rows = adminCollection().filter(item =>
        Object.values(item).join(" ").toLocaleLowerCase(state.language).includes(query)
    );
    $("#adminList").innerHTML = rows.map(item => {
        let title;
        let detail;
        if (state.currentView === "cutters") {
            title = item.tool_uid;
            detail = `${item.template_name} · Ø ${formatNumber(item.current_diameter)} · ${item.location || "-"}`;
        } else if (state.currentView === "wheels") {
            title = item.name;
            detail = `${item.tool_uid} · ${item.specification} · Ø ${formatNumber(item.diameter)}`;
        } else {
            title = `${item.name} · v${item.version}`;
            detail = state.language === "en" ? item.description_en : item.description_de;
        }
        return `<button class="admin-row ${state.selectedAdminId === item.id ? "active" : ""}" data-admin-id="${item.id}" type="button">
            <span><strong>${escapeHtml(title)}</strong><small>${escapeHtml(detail)}</small></span>
            <span class="status-mark">${escapeHtml(item.status)}</span></button>`;
    }).join("");
    document.querySelectorAll("[data-admin-id]").forEach(button => {
        button.addEventListener("click", () => {
            state.selectedAdminId = Number(button.dataset.adminId);
            state.adminCreating = false;
            renderAdminList();
            fillAdminForm(state.selectedAdminId);
        });
    });
}

function hideAdminForms() {
    ["cutterAdminForm", "wheelAdminForm", "strategyAdminForm", "jobsAdminPanel"].forEach(id => {
        $(`#${id}`).hidden = true;
    });
    $("#adminList").hidden = state.currentView === "jobs";
    $("#adminSearch").closest("label").hidden = state.currentView === "jobs";
}

function startAdminCreate() {
    state.selectedAdminId = null;
    state.adminCreating = true;
    renderAdminList();
    if (state.currentView === "cutters") fillCutterForm({});
    if (state.currentView === "wheels") fillWheelForm({});
    if (state.currentView === "strategies") fillStrategyForm({});
}

function fillAdminForm(id) {
    const item = adminCollection().find(entry => entry.id === id) || {};
    if (state.currentView === "cutters") fillCutterForm(item);
    if (state.currentView === "wheels") fillWheelForm(item);
    if (state.currentView === "strategies") fillStrategyForm(item);
}

function statusSelectOptions(selected = "ready") {
    return statusOptions.map(status =>
        `<option value="${status}" ${selected === status ? "selected" : ""}>${status}</option>`
    ).join("");
}

function fillCutterForm(item) {
    $("#cutterAdminForm").hidden = false;
    $("#adminCutterUid").value = item.tool_uid || nextToolUid();
    $("#adminCutterTemplate").innerHTML = state.bootstrap.templates.map(template =>
        `<option value="${template.id}" ${item.template_id === template.id ? "selected" : ""}>${escapeHtml(template.name)}</option>`
    ).join("");
    $("#adminCutterStatus").innerHTML = statusSelectOptions(item.status);
    $("#adminCutterDiameter").value = item.current_diameter ?? "";
    $("#adminCutterLength").value = item.current_length ?? "";
    $("#adminCutterLocation").value = item.location || "";
    $("#adminCutterNotes").value = item.notes || "";
}

function nextToolUid() {
    const year = new Date().getFullYear();
    const count = (state.bootstrap?.cutters.length || 0) + 1;
    return `TG-${year}-${String(count).padStart(3, "0")}`;
}

function fillWheelForm(item) {
    $("#wheelAdminForm").hidden = false;
    $("#adminWheelUid").value = item.tool_uid || "";
    $("#adminWheelName").value = item.name || "";
    $("#adminWheelType").value = item.tool_type || "edge";
    $("#adminWheelSpecification").value = item.specification || "";
    $("#adminWheelDiameter").value = item.diameter ?? "";
    $("#adminWheelRpm").value = item.max_rpm ?? "";
    $("#adminWheelStatus").innerHTML = statusSelectOptions(item.status);
}

function fillStrategyForm(item) {
    $("#strategyAdminForm").hidden = false;
    $("#adminStrategyName").value = item.name || "";
    $("#adminStrategyStatus").value = state.adminCreating ? "draft" : item.status || "draft";
    $("#adminStrategyDe").value = item.description_de || "";
    $("#adminStrategyEn").value = item.description_en || "";
    const parameters = item.parameters || {};
    $("#adminStrategyMeasure").checked = Boolean(parameters.requires_measurement);
    document.querySelectorAll("[name=strategyMode]").forEach(input => {
        input.checked = (parameters.modes || []).includes(input.value);
    });
}

function renderAllJobs() {
    const jobs = state.bootstrap?.recent_jobs || [];
    $("#allJobsTable").innerHTML = jobs.length ? jobs.map(job => `
        <tr><td>${escapeHtml(job.job_number)}</td><td>${escapeHtml(job.tool_uid)}</td>
        <td>${escapeHtml(job.template_name)}</td><td>${escapeHtml(job.mode)}</td>
        <td>${formatNumber(job.target_diameter)}</td><td>${escapeHtml(job.status)}</td>
        <td>${formatDate(job.created_at)}</td></tr>`).join("")
        : `<tr><td colspan="7" class="empty-row">${t("noJobs")}</td></tr>`;
}

async function saveAdminCutter(event) {
    event.preventDefault();
    const payload = {
        tool_uid: $("#adminCutterUid").value,
        template_id: Number($("#adminCutterTemplate").value),
        current_diameter: Number($("#adminCutterDiameter").value),
        current_length: $("#adminCutterLength").value || null,
        status: $("#adminCutterStatus").value,
        location: $("#adminCutterLocation").value,
        notes: $("#adminCutterNotes").value,
    };
    const url = state.adminCreating ? "/api/cutters" : `/api/cutters/${state.selectedAdminId}`;
    const result = await api(url, {method: state.adminCreating ? "POST" : "PATCH", body: JSON.stringify(payload)});
    await loadBootstrap(state.selectedTemplate?.id);
    state.selectedAdminId = result.cutter.id;
    state.adminCreating = false;
    renderAdminView();
    showToast(t("recordSaved"));
}

async function saveAdminWheel(event) {
    event.preventDefault();
    const payload = {
        tool_uid: $("#adminWheelUid").value,
        name: $("#adminWheelName").value,
        tool_type: $("#adminWheelType").value,
        specification: $("#adminWheelSpecification").value,
        diameter: Number($("#adminWheelDiameter").value),
        max_rpm: $("#adminWheelRpm").value || null,
        status: $("#adminWheelStatus").value,
    };
    const url = state.adminCreating ? "/api/grinding-tools" : `/api/grinding-tools/${state.selectedAdminId}`;
    const result = await api(url, {method: state.adminCreating ? "POST" : "PATCH", body: JSON.stringify(payload)});
    await loadBootstrap(state.selectedTemplate?.id);
    state.selectedAdminId = result.grinding_tool.id;
    state.adminCreating = false;
    renderAdminView();
    showToast(t("recordSaved"));
}

async function saveAdminStrategy(event) {
    event.preventDefault();
    const modes = Array.from(document.querySelectorAll("[name=strategyMode]:checked")).map(input => input.value);
    const result = await api("/api/strategies", {
        method: "POST",
        body: JSON.stringify({
            name: $("#adminStrategyName").value,
            status: $("#adminStrategyStatus").value,
            description_de: $("#adminStrategyDe").value,
            description_en: $("#adminStrategyEn").value,
            requires_measurement: $("#adminStrategyMeasure").checked,
            modes,
        }),
    });
    await loadBootstrap(state.selectedTemplate?.id);
    state.selectedAdminId = result.strategy.id;
    state.adminCreating = false;
    renderAdminView();
    showToast(t("versionCreated"));
}

async function prepareJob() {
    if (!state.selectedTemplate) return;
    await saveTemplate();
    setStatus("generating");
    const cutterId = $("#cutterSelect").value;
    const strategyId = $("#strategySelect").value;
    if (!strategyId) throw new Error("No released strategy supports the selected mode.");
    const result = await api("/api/generate", {
        method: "POST",
        body: JSON.stringify({
            template_id: state.selectedTemplate.id,
            cutter_id: cutterId ? Number(cutterId) : null,
            strategy_id: Number(strategyId),
            mode: $("#modeSelect").value,
        }),
    });
    await loadBootstrap(state.selectedTemplate.id);
    setStatus("finished");
    const links = result.files.map(file => `<a href="${file.download_url}">${escapeHtml(file.name)}</a>`).join(" · ");
    showToast(`${t("generated")} ${links}`, false, true);
}

function showToast(message, isError = false, html = false) {
    const toast = $("#toast");
    toast.classList.toggle("error", isError);
    if (html) toast.innerHTML = message;
    else toast.textContent = message;
    toast.hidden = false;
    window.setTimeout(() => { toast.hidden = true; }, 7000);
}

function formatNumber(value) {
    if (value === null || value === undefined || value === "") return "-";
    const number = Number(value);
    return Number.isFinite(number)
        ? number.toLocaleString(state.language === "en" ? "en-US" : "de-DE", {maximumFractionDigits: 3})
        : String(value);
}

function formatDate(value) {
    if (!value) return "-";
    return new Date(value).toLocaleString(state.language === "en" ? "en-US" : "de-DE", {
        dateStyle: "short", timeStyle: "short",
    });
}

function slopeFromHelixAngle(angleDeg, diameter) {
    if (!(diameter > 0)) throw new Error("Diameter must be greater than zero.");
    return 360 * Math.tan(angleDeg * Math.PI / 180) / (Math.PI * diameter);
}

function helixAngleFromSlope(slope, diameter) {
    if (!(diameter > 0)) throw new Error("Diameter must be greater than zero.");
    return Math.atan(slope * Math.PI * diameter / 360) * 180 / Math.PI;
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
    }[char]));
}

$("#languageSelect").addEventListener("change", event => applyLanguage(event.target.value));
$("#templateSearch").addEventListener("input", renderTemplates);
$("#saveTemplate").addEventListener("click", () => saveTemplate().catch(handleError));
$("#prepareJob").addEventListener("click", () => prepareJob().catch(handleError));
$("#modeSelect").addEventListener("change", renderStrategies);
$("#angleToSlope").addEventListener("click", () => {
    try {
        const value = slopeFromHelixAngle(
            Number($("#fieldHelixAngle").value),
            Number($("#fieldDiameter").value)
        );
        $("#fieldHelix").value = value.toFixed(6);
        $("#fieldHelixSource").value = "manufacturer";
        showToast(t("conversionDone"));
    } catch (error) {
        handleError(error);
    }
});
$("#slopeToAngle").addEventListener("click", () => {
    try {
        const value = helixAngleFromSlope(
            Number($("#fieldHelix").value),
            Number($("#fieldDiameter").value)
        );
        $("#fieldHelixAngle").value = value.toFixed(3);
        $("#fieldHelixSource").value = "measured";
        showToast(t("conversionDone"));
    } catch (error) {
        handleError(error);
    }
});
$("#newTemplate").addEventListener("click", () => {
    $("#newTemplateName").value = state.selectedTemplate ? `${state.selectedTemplate.name} Copy` : "";
    $("#templateDialog").showModal();
});
$("#newTemplateForm").addEventListener("submit", event => {
    if (event.submitter?.value === "cancel") return;
    event.preventDefault();
    api("/api/cutter-templates", {
        method: "POST",
        body: JSON.stringify({
            source_template_id: state.selectedTemplate.id,
            name: $("#newTemplateName").value,
        }),
    }).then(result => {
        $("#templateDialog").close();
        showToast(t("templateCreated"));
        return loadBootstrap(result.template.id);
    }).catch(handleError);
});
document.querySelectorAll(".nav-item").forEach(button => {
    button.addEventListener("click", () => {
        const view = button.dataset.view;
        if (view === "dashboard" || view === "settings") {
            showToast(view === "dashboard" ? t("manageJobs") : t("ready"));
            return;
        }
        showView(view);
    });
});
$("#adminNew").addEventListener("click", startAdminCreate);
$("#adminSearch").addEventListener("input", renderAdminList);
$("#cutterAdminForm").addEventListener("submit", event => saveAdminCutter(event).catch(handleError));
$("#wheelAdminForm").addEventListener("submit", event => saveAdminWheel(event).catch(handleError));
$("#strategyAdminForm").addEventListener("submit", event => saveAdminStrategy(event).catch(handleError));

function handleError(error) {
    setStatus("ready");
    showToast(error.message, true);
}

applyLanguage(state.language);
loadBootstrap().catch(handleError);
