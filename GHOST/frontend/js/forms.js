// Formulários gerados a partir dos metadados dos campos.
import { h } from './ui.js';

async function makeInput(f, v, ctx) {
  const t = f.type, wrap = (node, get) => ({ node, get });
  if (t === 'long_text') { const n = h('textarea', { rows: 4 }); n.value = v ?? ''; return wrap(n, () => n.value.trim() || null); }
  if (t === 'boolean') { const n = h('input', { type: 'checkbox' }); n.checked = !!v; return wrap(n, () => n.checked); }
  if (t === 'select') {
    const n = h('select', {}, h('option', { value: '' }, '—'), (f.options.choices || []).map(c => h('option', { value: c }, c)));
    n.value = v ?? ''; return wrap(n, () => n.value || null);
  }
  if (t === 'tags') {
    const n = h('input', { type: 'text', placeholder: 'Separe por vírgulas' }); n.value = (v || []).join(', ');
    return wrap(n, () => { const a = n.value.split(',').map(s => s.trim()).filter(Boolean); return a.length ? a : null; });
  }
  if (t === 'file') return wrap(h('em', { class: 'muted' }, 'Anexos ficam disponíveis na etapa de arquivos.'), () => v ?? null);
  if (t === 'reference' || t === 'reference_list') {
    const multi = t === 'reference_list', items = await ctx.recordsOf(f.options.target);
    const n = h('select', { multiple: multi, size: multi ? Math.min(6, Math.max(3, items.length)) : null },
      !multi && h('option', { value: '' }, '—'), items.map(r => h('option', { value: r.id }, ctx.label(f.options.target, r))));
    const chosen = multi ? (v || []) : [v];
    [...n.options].forEach(o => { o.selected = chosen.includes(o.value); });
    return wrap(n, () => { const vals = [...n.selectedOptions].map(o => o.value).filter(Boolean); return multi ? (vals.length ? vals : null) : (vals[0] ?? null); });
  }
  const type = { integer: 'number', decimal: 'number', date: 'date', datetime: 'datetime-local', email: 'email', url: 'url', phone: 'tel' }[t] || 'text';
  const n = h('input', { type, step: t === 'decimal' ? 'any' : null }); n.value = v ?? '';
  return wrap(n, () => (n.value === '' ? null : n.value));
}

export async function buildForm(col, values, ctx) {
  const inputs = {}, form = h('form', { class: 'form', onsubmit: e => e.preventDefault() });
  for (const f of col.fields) {
    inputs[f.id] = await makeInput(f, values?.[f.id], ctx);
    form.append(h('label', { class: 'row' }, h('span', {}, f.name + (f.required ? ' *' : '')), inputs[f.id].node, f.description ? h('small', {}, f.description) : null));
  }
  return { node: form, get: () => Object.fromEntries(Object.entries(inputs).map(([id, i]) => [id, i.get()])) };
}
