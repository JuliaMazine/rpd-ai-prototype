/* Progressive enhancement: without JS all courses and form fields stay available. */
(() => {
    const workflow = document.querySelector('[data-course-workflow]');
    if (workflow) {
        const screens = Array.from(workflow.querySelectorAll('[data-screen]'));
        const steps = ['details', 'materials', 'competencies', 'drafts'];
        function navigate(focus = true) {
            const [screenName, requestedStep] = location.hash.slice(1).split('/');
            const screen = screens.find(item => item.dataset.screen === screenName) || screens[0];
            const step = steps.includes(requestedStep) ? requestedStep : 'details';
            screens.forEach(item => { item.hidden = item !== screen; });
            screen.querySelectorAll('[data-panel]').forEach(panel => {
                panel.hidden = panel.dataset.panel !== step;
            });
            screen.querySelectorAll('[data-step]').forEach(link => {
                if (link.dataset.step === step) link.setAttribute('aria-current', 'step');
                else link.removeAttribute('aria-current');
            });
            if (focus) {
                const heading = screen.querySelector(`[data-panel="${step}"] h3`) || screen.querySelector('h2');
                heading?.focus({preventScroll: true});
                workflow.scrollIntoView({block: 'start'});
            }
            // Competency retrieval can take minutes: start only for the opened step.
            screen.querySelector('[data-panel="competencies"]:not([hidden]) .generation-form')
                ?.dispatchEvent(new Event('generation:activate'));
        }
        window.addEventListener('hashchange', () => navigate());
        navigate(false);
    }

    const editor = document.querySelector('[data-editor-workflow]');
    if (editor) {
        const panels = Array.from(editor.querySelectorAll('[data-editor-panel]'));
        function navigateEditor(focus = true) {
            const selected = panels.find(panel => panel.dataset.editorPanel === location.hash.slice(1)) || panels[0];
            panels.forEach(panel => { panel.hidden = panel !== selected; });
            editor.querySelectorAll('[data-editor-step]').forEach(link => {
                if (link.dataset.editorStep === selected.dataset.editorPanel) link.setAttribute('aria-current', 'step');
                else link.removeAttribute('aria-current');
            });
            if (focus) {
                selected.querySelector('h2').focus({preventScroll: true});
                editor.scrollIntoView({block: 'start'});
            }
        }
        // Switching panels keeps unsaved form values in the DOM. Block review until saved.
        const editForms = Array.from(editor.querySelectorAll('[data-draft-text-form], [data-draft-selection-form]'));
        const initialValues = editForms.map(form => new URLSearchParams(new FormData(form)).toString());
        function updateDirty() {
            const dirty = editForms.some((form, i) => new URLSearchParams(new FormData(form)).toString() !== initialValues[i]);
            editor.querySelector('[data-unsaved-warning]').hidden = !dirty;
            editor.querySelectorAll('[data-review-form] button').forEach(button => { button.disabled = dirty; });
        }
        // Saving one form can discard edits in another panel; warn only for actual edits.
        let savingForm = null;
        editor.addEventListener('submit', event => { savingForm = event.target; });
        window.addEventListener('beforeunload', event => {
            const unsaved = editForms.some((form, i) => form !== savingForm &&
                new URLSearchParams(new FormData(form)).toString() !== initialValues[i]);
            savingForm = null;
            if (unsaved) {
                event.preventDefault();
                event.returnValue = '';
            }
        });
        editor.addEventListener('input', updateDirty);
        editor.addEventListener('change', updateDirty);
        window.addEventListener('pageshow', updateDirty);
        window.addEventListener('hashchange', () => navigateEditor());
        navigateEditor(false);
    }

    document.querySelectorAll('[data-form-steps]').forEach(container => {
        const form = container.closest('form');
        const fields = Array.from(container.querySelectorAll('[data-form-step]'));
        const submit = form.querySelector('[type="submit"]');
        if (!submit) return;
        let current = 0;
        const progress = document.createElement('p');
        progress.className = 'form-progress small';
        progress.setAttribute('aria-live', 'polite');
        const controls = document.createElement('div');
        controls.className = 'step-actions';
        const back = document.createElement('button');
        back.type = 'button';
        back.className = 'secondary';
        back.textContent = '← Назад';
        const next = document.createElement('button');
        next.type = 'button';
        next.textContent = 'Далее →';
        controls.append(back, next);
        container.prepend(progress);
        container.append(controls);
        function show(index, focus = true) {
            current = index;
            fields.forEach((field, i) => { field.hidden = i !== current; });
            progress.textContent = `Шаг ${current + 1} из ${fields.length}`;
            back.hidden = current === 0;
            next.hidden = current === fields.length - 1;
            submit.hidden = current !== fields.length - 1;
            if (focus) {
                const legend = fields[current].querySelector('legend');
                legend.tabIndex = -1;
                legend.focus();
            }
        }
        function advance() {
            const invalid = Array.from(fields[current].querySelectorAll('input, select, textarea'))
                .find(input => !input.checkValidity());
            if (invalid) { invalid.reportValidity(); return; }
            show(current + 1);
        }
        next.addEventListener('click', advance);
        back.addEventListener('click', () => show(current - 1));
        // Native validation must reveal invalid fields before the browser focuses them.
        form.addEventListener('invalid', event => {
            const index = fields.findIndex(field => field.contains(event.target));
            if (index >= 0 && fields[index].hidden) show(index, false);
        }, true);
        form.addEventListener('submit', event => {
            if (current < fields.length - 1) { event.preventDefault(); advance(); }
        });
        show(0, false);
    });
})();
