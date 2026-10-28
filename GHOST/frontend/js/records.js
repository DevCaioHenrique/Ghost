// Tabela/cartões de registros: busca, filtros, ordenação, seleção em lote e edição.
import { api } from './api.js';
import { h, toast, modal, confirmDialog } from './ui.js';
import { buildForm } from './forms.js';

export function fmt(ctx, f, v) {
  if (v == null || v === '') return '';
  if (f.type === 'boolean') return v ? 'Sim' : 'Não';
  if (f.type === 'date') return String(v).split('-').reverse().join('/');
  if (f.type === 'datetime') return new Date(v).toLocaleString('pt-BR');
  if (f.type === 'file') return 'anexo';
  if (f.type === 'reference' || f.type === 'reference_list') {
    const recs = ctx.cache.get(f.options.target) || [];
    return [].concat(v).map(i => { const r = recs.find(x => x.id === i); return r ? ctx.label(f.options.target, r) : '(removido)'; }).join(', ');
  }
  return Array.isArray(v) ? v.join(', ') : String(v);
}

function describe(col, e) {
  const fs = e.data?.fields;
  if (!fs) return e.message;
  const names = Object.fromEntries(col.fields.map(f => [f.id, f.name]));
  return 'Corrija os campos: ' + Object.entries(fs).map(([k, m]) => `${names[k] || k} (${m})`).join('; ');
}

export async function editRecord(ctx, col, rec, onDone) {
  const form = await buildForm(col, rec?.values, ctx);
  const actions = [{ label: 'Cancelar', value: null }];
  if (rec) actions.push({
    label: 'Excluir', kind: 'danger',
    run: async () => {
      if (!(await confirmDialog('Excluir este registro? As referências a ele em outros registros serão removidas.', 'Excluir'))) return false;
      await api.deleteRecord(rec.id); ctx.cache.clear(); toast('Registro excluído'); onDone();
    },
  });
  actions.push({
    label: 'Salvar', kind: 'primary',
    run: async () => {
      try {
        const values = form.get();
        if (rec) await api.updateRecord(rec.id, { values }); else await api.createRecord(col.id, { values });
        ctx.cache.clear(); toast(rec ? 'Registro salvo' : 'Registro criado'); onDone();
      } catch (e) { toast(describe(col, e), 'error'); return false; }
    },
  });
  await modal(rec ? 'Editar registro' : 'Novo registro', form.node, { actions });
}

export async function renderRecords(ctx, col, root) {
  const st = (ctx.state[col.id] ??= { q: '', sort: null, desc: false, filters: {}, mode: 'table', sel: new Set() });
  const cols = col.fields.filter(f => !f.hidden), arrows = {};
  const count = h('span', { class: 'muted' }), body = h('tbody'), cards = h('div', { class: 'cards' });
  let timer;
  const debounce = fn => { clearTimeout(timer); timer = setTimeout(fn, 250); };

  const selAll = h('input', { type: 'checkbox', title: 'Selecionar todos', onchange: e => body.querySelectorAll('input.pick').forEach(c => { c.checked = e.target.checked; c.dispatchEvent(new Event('change')); }) });
  const delBtn = h('button', { class: 'danger', hidden: true, onclick: bulkDelete }, 'Excluir selecionados');
  const head = h('tr', {}, h('th', {}, selAll), cols.map(f => { arrows[f.id] = h('span'); return h('th', {}, h('button', { class: 'link', onclick: () => sortBy(f.id) }, f.name, arrows[f.id])); }));
  const filt = h('tr', { class: 'filters' }, h('th'), cols.map(f => h('th', {}, h('input', { type: 'search', placeholder: 'Filtrar', 'aria-label': 'Filtrar ' + f.name, value: st.filters[f.id] || '', oninput: e => { st.filters[f.id] = e.target.value; debounce(load); } }))));
  const table = h('div', { class: 'tablewrap' }, h('table', {}, h('thead', {}, head, filt), body));
  const modeBtn = (m, label) => h('button', { onclick: () => { st.mode = m; applyMode(); } }, label);

  function applyMode() { table.hidden = st.mode !== 'table'; cards.hidden = st.mode !== 'cards'; }
  function arrowsUpdate() { for (const f of cols) arrows[f.id].textContent = st.sort === f.id ? (st.desc ? ' ▼' : ' ▲') : ''; }
  function sortBy(id) { st.desc = st.sort === id ? !st.desc : false; st.sort = id; arrowsUpdate(); load(); }

  async function bulkDelete() {
    if (!(await confirmDialog(`Excluir ${st.sel.size} registro(s)? Esta ação não pode ser desfeita.`, 'Excluir'))) return;
    try { for (const id of st.sel) await api.deleteRecord(id); ctx.cache.clear(); toast('Registros excluídos'); } catch (e) { toast(e.message, 'error'); }
    load();
  }

  function draw({ items, total }) {
    st.sel.clear(); delBtn.hidden = true; selAll.checked = false;
    count.textContent = `${total} registro${total === 1 ? '' : 's'}`;
    body.replaceChildren(); cards.replaceChildren();
    if (!items.length) {
      const filtering = st.q || Object.values(st.filters).some(Boolean);
      const msg = filtering ? 'Nenhum registro corresponde à busca.' : `A coleção ${col.name} está vazia. Crie o primeiro registro.`;
      body.append(h('tr', {}, h('td', { colspan: cols.length + 1, class: 'empty' }, msg))); return;
    }
    for (const r of items) {
      const open = () => editRecord(ctx, col, r, load);
      const pick = h('input', { type: 'checkbox', class: 'pick', 'aria-label': 'Selecionar registro', onclick: e => e.stopPropagation(), onchange: e => { e.target.checked ? st.sel.add(r.id) : st.sel.delete(r.id); delBtn.hidden = !st.sel.size; } });
      body.append(h('tr', { tabindex: 0, onclick: open, onkeydown: e => e.key === 'Enter' && open() }, h('td', {}, pick), cols.map(f => h('td', {}, fmt(ctx, f, r.values[f.id])))));
      cards.append(h('article', { class: 'card', tabindex: 0, onclick: open, onkeydown: e => e.key === 'Enter' && open() },
        h('h3', {}, ctx.label(col.id, r)),
        cols.filter(f => !f.is_primary).slice(0, 4).map(f => { const t = fmt(ctx, f, r.values[f.id]); return t ? h('p', {}, h('span', { class: 'muted' }, f.name + ': '), t) : null; })));
    }
  }

  async function load() {
    try {
      const p = new URLSearchParams();
      if (st.q) p.set('q', st.q);
      if (st.sort) { p.set('sort', st.sort); p.set('order', st.desc ? 'desc' : 'asc'); }
      for (const [k, v] of Object.entries(st.filters)) if (v) p.set(`filter[${k}]`, v);
      const data = await api.records(col.id, p);
      await Promise.all(cols.filter(f => f.type.startsWith('reference')).map(f => ctx.recordsOf(f.options.target)));
      draw(data);
    } catch (e) {
      body.replaceChildren(h('tr', {}, h('td', { colspan: cols.length + 1 }, h('span', { class: 'error' }, e.message + ' '), h('button', { onclick: load }, 'Tentar novamente'))));
    }
  }

  root.replaceChildren(
    h('h1', {}, h('span', { class: 'ico', style: `color:${col.color}` }, col.icon), col.name),
    col.description ? h('p', { class: 'muted' }, col.description) : null,
    h('div', { class: 'toolbar' },
      h('input', { type: 'search', placeholder: `Buscar em ${col.name}`, 'aria-label': 'Buscar', value: st.q, oninput: e => { st.q = e.target.value; debounce(load); } }),
      h('button', { class: 'primary', onclick: () => editRecord(ctx, col, null, load) }, 'Novo registro'),
      delBtn, h('span', { class: 'grow' }), count, modeBtn('table', 'Tabela'), modeBtn('cards', 'Cartões')),
    table, cards);
  arrowsUpdate(); applyMode();
  await load();
  const id = ctx.pendingOpen; ctx.pendingOpen = null;
  if (id) { try { editRecord(ctx, col, await api.record(id), load); } catch (e) { toast(e.message, 'error'); } }
}
