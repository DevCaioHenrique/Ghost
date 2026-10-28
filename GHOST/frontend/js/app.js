// Ponto de entrada: estado compartilhado, navegação por hash e barra lateral.
import { api } from './api.js';
import { h, toast, modal } from './ui.js';
import { renderRecords } from './records.js';
import { renderStudio } from './studio.js';

const ctx = {
  collections: [], state: {}, cache: new Map(), pendingOpen: null,
  async refresh() { this.collections = await api.collections(); this.cache.clear(); },
  col(id) { return this.collections.find(c => c.id === id); },
  label(cid, rec) {
    const c = this.col(cid), p = c?.fields.find(f => f.is_primary) || c?.fields[0];
    const v = p ? rec.values[p.id] : null;
    return v ? String(v) : '(sem nome)';
  },
  async recordsOf(cid) {
    if (!this.cache.has(cid)) this.cache.set(cid, (await api.records(cid, new URLSearchParams({ limit: 500 }))).items);
    return this.cache.get(cid);
  },
  render,
};

const LOGO = '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 2 29 9v14L16 30 3 23V9z" fill="none" stroke="currentColor" stroke-width="2"/><path d="M16 2v28M3 9l13 7 13-7" fill="none" stroke="currentColor" stroke-width="1" opacity=".5"/></svg>';

function renderSide() {
  const [view, id] = location.hash.replace(/^#\//, '').split('/');
  const search = h('input', { type: 'search', placeholder: 'Buscar em tudo', 'aria-label': 'Busca global', onkeydown: async e => {
    if (e.key !== 'Enter' || !e.target.value.trim()) return;
    try { showResults(await api.search(e.target.value.trim())); } catch (err) { toast(err.message, 'error'); }
  } });
  const brand = h('div', { class: 'brand' }, 'GHOST'); brand.insertAdjacentHTML('afterbegin', LOGO);
  document.getElementById('side').replaceChildren(brand, search, h('nav', {},
    ctx.collections.filter(c => !c.archived).map(c => h('a', { href: '#/c/' + c.id, class: view === 'c' && id === c.id ? 'on' : '' }, h('span', { style: `color:${c.color}` }, c.icon), c.name)),
    h('hr'), h('a', { href: '#/studio', class: view === 'studio' ? 'on' : '' }, h('span', {}, '⬢'), 'Database Studio')));
}

function showResults(items) {
  const list = items.length
    ? h('ul', { style: 'list-style:none;padding:0;margin:0;display:grid;gap:6px' }, items.map(r => h('li', {}, h('button', { class: 'link', onclick: () => { ctx.pendingOpen = r.id; document.querySelector('dialog')?.dispatchEvent(new Event('cancel')); location.hash = '#/c/' + r.collection_id; if (location.hash === '#/c/' + r.collection_id) render(); } },
      `${ctx.label(r.collection_id, r)} `, h('span', { class: 'muted' }, `em ${ctx.col(r.collection_id)?.name}`)))))
    : h('p', { class: 'muted' }, 'Nada encontrado.');
  modal('Resultados da busca', list, { actions: [{ label: 'Fechar' }] });
}

async function render() {
  renderSide();
  const [view, id] = location.hash.replace(/^#\//, '').split('/');
  const main = document.getElementById('main');
  if (view === 'studio') return renderStudio(ctx, main, id);
  const col = ctx.col(view === 'c' ? id : null) || ctx.collections.find(c => !c.archived);
  if (!col) { main.replaceChildren(h('p', { class: 'empty' }, 'Nenhuma coleção ativa. Abra o Database Studio para criar a primeira.')); return; }
  return renderRecords(ctx, col, main);
}

async function boot() {
  try { await ctx.refresh(); } catch (e) {
    document.getElementById('main').replaceChildren(h('p', { class: 'error' }, e.message + ' '), h('button', { onclick: boot }, 'Tentar novamente'));
    return;
  }
  render();
}
window.addEventListener('hashchange', render);
boot();
