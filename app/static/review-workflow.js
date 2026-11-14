/* Preserve comments and reading positions when switching review sections. */
(() => {
    const workspace = document.querySelector('[data-review-workflow]');
    if (!workspace) return;
    const panels = Array.from(workspace.querySelectorAll('[data-review-panel]'));
    const tabs = Array.from(workspace.querySelectorAll('[data-review-tab]'));
    function navigate(focus = true) {
        const requested = location.hash.slice(1);
        const selected = panels.find(panel => panel.dataset.reviewPanel === requested) || panels[0];
        panels.forEach(panel => { panel.hidden = panel !== selected; });
        tabs.forEach(tab => {
            if (tab.dataset.reviewTab === selected.dataset.reviewPanel) tab.setAttribute('aria-current', 'page');
            else tab.removeAttribute('aria-current');
        });
        if (focus) {
            const heading = requested === 'decision' ? workspace.querySelector('#decision-heading') : selected.querySelector('h2');
            heading.focus({preventScroll: true});
        }
    }
    const form = workspace.querySelector('[data-feedback-form]');
    const feedback = form.elements.feedback;
    const initial = feedback.value;
    const validate = workspace.querySelector('[data-validate-form]');
    let submitting = false;
    function update() {
        const dirty = feedback.value !== initial;
        workspace.querySelector('[data-feedback-dirty]').hidden = !dirty;
        validate.querySelector('button').disabled = dirty;
        form.querySelector('[value="return"]').disabled = !feedback.value.trim();
    }
    feedback.addEventListener('input', update);
    workspace.addEventListener('submit', event => {
        if (event.target === form && event.submitter?.value === 'return' && !feedback.value.trim()) {
            event.preventDefault();
            feedback.focus();
            return;
        }
        submitting = true;
    });
    window.addEventListener('beforeunload', event => {
        if (!submitting && feedback.value !== initial) {
            event.preventDefault();
            event.returnValue = '';
        }
    });
    window.addEventListener('pageshow', () => { submitting = false; update(); });
    window.addEventListener('hashchange', () => navigate());
    // The older feedback URL opens the same workspace with the comment field focused.
    navigate(false);
    if (location.pathname.endsWith('/feedback')) feedback.focus({preventScroll: true});
    update();
})();
