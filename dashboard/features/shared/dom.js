// dashboard/features/shared/dom.js

/**
 * Define o texo de uma tag sem falhar silenciosamente se for nula.
 */
export function setText(element, text) {
    if (element) {
        element.textContent = String(text);
    }
}

/**
 * Formata números grandes adicionando vírgulas.
 */
export function formatNumber(value) {
    return new Intl.NumberFormat("en-US").format(Number(value || 0));
}

/**
 * Retorna uma string percentual com 1 casa decimal.
 */
export function formatPercent(value) {
    return `${Number(value || 0).toFixed(1)}%`;
}

/**
 * Garante que o valor venha como array.
 */
export function asArray(value) {
    return Array.isArray(value) ? value : [];
}

/**
 * Cria uma linha de tabela interativa (TR cheio de TD).
 */
export function createCellRow(values) {
    const row = document.createElement("tr");
    values.forEach((value) => {
        const cell = document.createElement("td");
        cell.textContent = String(value);
        row.appendChild(cell);
    });
    return row;
}

/**
 * Retorna o valor de referência salvo em `localStorage` com tratamento de erro.
 */
export function getStorageItem(key) {
    try {
        return String(window.localStorage.getItem(key) || "").trim();
    } catch (_error) {
        return "";
    }
}

/**
 * Salva dado em cache persistente local com resiliência.
 */
export function setStorageItem(key, value) {
    try {
        const safeValue = String(value || "");
        if (safeValue.trim()) {
            window.localStorage.setItem(key, safeValue);
        } else {
            window.localStorage.removeItem(key);
        }
    } catch (_error) {
        // block do browser (ex: iframe anonimo)
    }
}
