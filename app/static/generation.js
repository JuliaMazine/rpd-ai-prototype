/* Show candidates inside each course's generation form; submit accepts checked items. */
document.querySelectorAll('.generation-form').forEach((form) => {
    const token = form.querySelector('[name="competency_token"]');
    const options = form.querySelector('.competency-options');
    const status = form.querySelector('.competency-status');
    const retry = form.querySelector('.retry-competencies');
    const skipLabel = form.querySelector('.skip-competencies');
    const skip = skipLabel.querySelector('input');
    const submit = form.querySelector('[type="submit"]');
    const catalogueOptions = form.querySelector('.catalogue-options');
    const catalogueStatus = form.querySelector('.catalogue-status');
    const catalogueToken = form.querySelector('[name="catalogue_token"]');
    let catalogueReady = false;
    let controller;
    let ready = false;
    let generating = false;
    let loading = false;

    function updateButton() {
        submit.disabled = loading || generating || (!ready && !catalogueReady && !skip.checked);
    }

    async function load(refresh = false) {
        const selected = Array.from(options.querySelectorAll('input:checked')).map(input => input.value);
        const previousToken = token.value;
        if (refresh && previousToken && selected.length >= 5) {
            status.textContent = 'Все пять компетенций выбраны. Снимите отметки с тех, которые хотите заменить.';
            return;
        }
        const body = refresh && previousToken ? {token: previousToken, selected_ids: selected} : {};
        if (controller) controller.abort();
        const current = new AbortController();
        controller = current;
        loading = true;
        ready = false;
        catalogueOptions.querySelectorAll("input").forEach(input => { input.disabled = true; });
        skip.checked = false;
        skipLabel.hidden = true;
        retry.disabled = true;
        options.querySelectorAll('input').forEach(input => { input.disabled = true; });
        updateButton();
        status.textContent = 'Подбираем пять компетенций по загруженным материалам… Первый подбор может занять несколько минут.';
        try {
            const response = await fetch(form.dataset.previewUrl, {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body), signal: current.signal,
            });
            const result = await response.json();
            if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Не удалось подобрать компетенции.');
            // Ignore an older response after the teacher has selected another program.
            if (controller !== current) return;
            token.value = result.token;
            const manualCodes = new Set(Array.from(catalogueOptions.querySelectorAll('input:checked')).map(input => input.value));
            options.replaceChildren();
            result.results.forEach((entry) => {
                const label = document.createElement('label');
                label.style.display = 'block';
                label.style.margin = '12px 0';
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.name = 'competency_ids';
                checkbox.value = entry.id;
                checkbox.checked = !entry.codes.some(code => manualCodes.has(code));
                checkbox.dataset.codes = JSON.stringify(entry.codes);
                label.append(checkbox, document.createTextNode(' ' + entry.codes.join(' / ') + ' — ' + entry.description));
                options.append(label);
            });
            ready = Boolean(form.dataset.programId);
            syncCatalogue();
            status.textContent = 'Предложено компетенций: ' + result.results.length + (result.material_sources?.length ? ' по загруженным материалам (' + result.material_sources.length + ' файлов).' : ' по описанию и темам дисциплины.') + ' Снимите отметки с неподходящих.';
            if (result.exhausted) status.textContent += ' Других подходящих компетенций в каталоге больше нет; выбранные сохранены.';
            retry.textContent = 'Заменить невыбранные';
            retry.hidden = false;
        } catch (error) {
            if (current.signal.aborted || controller !== current) return;
            status.textContent = error.message || 'Не удалось подобрать компетенции. Повторите подбор.';
            retry.hidden = false;
            ready = Boolean(previousToken) && Boolean(form.dataset.programId);
            skipLabel.hidden = ready;
            if (!ready) retry.textContent = 'Повторить подбор';
        }
        loading = false;
        skipLabel.hidden = ready || catalogueReady;
        retry.disabled = false;
        syncCatalogue();
        options.querySelectorAll('input').forEach(input => { input.disabled = !form.dataset.programId; });
        updateButton();
    }
    function syncCatalogue() {
        const selectedCodes = new Set(Array.from(options.querySelectorAll('input:checked')).flatMap(input => JSON.parse(input.dataset.codes)));
        catalogueOptions.querySelectorAll('input').forEach(input => {
            input.disabled = selectedCodes.has(input.value);
            if (input.disabled) input.checked = false;
        });
    }
    options.addEventListener('change', syncCatalogue);
    async function loadCatalogue() {
        if (!form.dataset.programId) {
            catalogueStatus.textContent = 'Выберите программу из каталога в сведениях о дисциплине для подтверждения выбора. Можно создать черновик без компетенций.';
            skipLabel.hidden = false;
            return;
        }
        try {
            const response = await fetch(form.dataset.catalogueUrl);
            const result = await response.json();
            if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Каталог недоступен.');
            catalogueToken.value = result.token;
            result.entries.forEach(entry => {
                const label = document.createElement('label');
                label.style.display = 'block';
                label.style.margin = '12px 0';
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.name = 'manual_codes';
                checkbox.value = entry.codes[0];
                label.append(checkbox, document.createTextNode(' ' + entry.codes[0] + ' — ' + entry.description));
                catalogueOptions.append(label);
            });
            catalogueReady = true;
            catalogueStatus.textContent = 'Можно выбрать любое количество компетенций или оставить выбор пустым. Отмеченные предложения уже включены в выбор.';
            syncCatalogue();
        } catch (error) {
            catalogueStatus.textContent = error.message || 'Каталог недоступен.';
        }
        updateButton();
    }
    retry.addEventListener('click', () => load(true));
    skip.addEventListener('change', updateButton);
    form.addEventListener('submit', (event) => {
        if (loading || generating || (!ready && !catalogueReady && !skip.checked)) {
            event.preventDefault();
            return;
        }
        if (!form.dataset.programId) {
            token.value = '';
            skip.checked = true;
        }
        generating = true;
        updateButton();
        status.textContent = 'Создаем черновик… ' + (ready ? 'Используем отмеченные компетенции.' : 'Компетенции потребуется заполнить вручную.');
    });
    // Refresh after navigating Back, where browsers may preserve disabled buttons.
    window.addEventListener('pageshow', (event) => {
        if (event.persisted) { generating = false; updateButton(); }
    });
    loadCatalogue();
    load();
});
