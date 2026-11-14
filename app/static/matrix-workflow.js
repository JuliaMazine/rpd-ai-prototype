/* Optional local search; programme and assignment filters also work without JS. */
(() => {
    const search = document.querySelector('[data-matrix-search]');
    if (!search) return;
    const input = search.querySelector('input');
    const rows = Array.from(document.querySelectorAll('#matrix-table tbody tr'));
    const labels = rows.map(row => row.querySelector('th').textContent.toLocaleLowerCase('ru'));
    const count = search.querySelector('[data-matrix-count]');
    const empty = document.querySelector('[data-matrix-empty]');
    function filter() {
        const query = input.value.trim().toLocaleLowerCase('ru');
        let visible = 0;
        rows.forEach((row, i) => {
            row.hidden = !labels[i].includes(query);
            if (!row.hidden) visible++;
        });
        count.textContent = `Показано: ${visible} из ${rows.length}`;
        empty.hidden = visible !== 0;
    }
    search.hidden = false;
    input.addEventListener('input', filter);
    window.addEventListener('pageshow', filter);
    filter();
})();
