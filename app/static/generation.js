/* Show candidates inside each course's generation form; submit accepts checked items. */
document.querySelectorAll('.generation-form').forEach((form) => {
    const token = form.querySelector('[name="competency_token"]');
    const options = form.querySelector('.competency-options');
    const status = form.querySelector('.competency-status');
    const retry = form.querySelector('.retry-competencies');
    const skipLabel = form.querySelector('.skip-competencies');
    const skip = skipLabel.querySelector('input');
    const submit = form.querySelector('[type="submit"]');
    let controller;
    let ready = false;
    let generating = false;

    function updateButton() {
        submit.disabled = generating || (!ready && !skip.checked);
    }

    async function load(refresh = false) {
        const selected = Array.from(options.querySelectorAll('input:checked')).map(input => input.value);
        const previousToken = token.value;
        if (refresh && previousToken && selected.length === 5) {
            status.textContent = 'Все пять компетенций выбраны. Снимите отметки с тех, которые хотите заменить.';
            return;
        }
        const body = refresh && previousToken ? {token: previousToken, selected_ids: selected} : {};
        if (controller) controller.abort();
        const current = new AbortController();
        controller = current;
        ready = false;
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
            options.replaceChildren();
            result.results.forEach((entry) => {
                const label = document.createElement('label');
                label.style.display = 'block';
                label.style.margin = '12px 0';
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.name = 'competency_ids';
                checkbox.value = entry.id;
                checkbox.checked = true;
                label.append(checkbox, document.createTextNode(' ' + entry.codes.join(' / ') + ' — ' + entry.description));
                options.append(label);
            });
            ready = true;
            status.textContent = 'Предложено компетенций: ' + result.results.length + (result.material_sources?.length ? ' по загруженным материалам (' + result.material_sources.length + ' файлов).' : ' по описанию и темам дисциплины.') + ' Снимите отметки с неподходящих.';
            if (result.exhausted) status.textContent += ' Других подходящих компетенций в каталоге больше нет; выбранные сохранены.';
            retry.textContent = 'Заменить невыбранные';
            retry.hidden = false;
        } catch (error) {
            if (current.signal.aborted || controller !== current) return;
            status.textContent = error.message || 'Не удалось подобрать компетенции. Повторите подбор.';
            retry.hidden = false;
            ready = Boolean(previousToken);
            skipLabel.hidden = ready;
            if (!ready) retry.textContent = 'Повторить подбор';
        }
        retry.disabled = false;
        options.querySelectorAll('input').forEach(input => { input.disabled = false; });
        updateButton();
    }
    retry.addEventListener('click', () => load(true));
    skip.addEventListener('change', updateButton);
    form.addEventListener('submit', (event) => {
        if (generating || (!ready && !skip.checked)) {
            event.preventDefault();
            return;
        }
        generating = true;
        updateButton();
        status.textContent = 'Создаем черновик… ' + (ready ? 'Используем отмеченные компетенции.' : 'Компетенции потребуется заполнить вручную.');
    });
    // Refresh after navigating Back, where browsers may preserve disabled buttons.
    window.addEventListener('pageshow', (event) => {
        if (event.persisted) { generating = false; updateButton(); }
    });
    load();
});
