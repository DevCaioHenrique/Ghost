// Database Studio: administra coleções, campos e a visão geral do esquema.
import { api, ApiError } from './api.js';
import { h, toast, modal, confirmDialog } from './ui.js';

export const TYPE_LABELS = {
  short_text: 'Texto curto', long_text: 'Texto longo', integer: 'Número inteiro', decimal: 'Número decimal',
  date: 'Data', datetime: 'Data e hora', boolean: 'Sim/Não', select: 'Lista de opções', tags: 'Tags', url: 'URL',
  email: 'E-mail', phone: 'Telefone', file: 'Imagem ou arquivo', reference: 'Referência', reference_list: 'Lista de referências',
};

// Repete a operação com confirmação quando o servidor avisa que há dados afetados.
async function withConfirm(fn) {
  try { return await fn(false); } catch (e) {
    const d = e instanceof ApiError && e.status === 409 ? e.data?.details || {} : null;
    if (d && ('values' in d || 'records' in d || 'count' in d)) {
      if (await confirmDialog(e.message, 'Confirmar')) return fn(true);
      return undefined;
    }
    throw e;
  }
}

const row = (label, node) => h('label', { class: 'row' }, h('span', {}, label), node);
const check = (label, node) => h('label', { class: 'row check' }, node, h('span', {}, label));

export async function renderStudio(ctx, root, selId) {
  const cols = ctx.collections, sel = cols.find(c => c.id === selId);
  const done = async () => { await ctx.refresh(); ctx.render(); };
  const main = h('div', { class: 'studio-main' });
  root.replaceChildren(h('h1', {}, 'Database Studio'), h('div', { class: 'studio' },
    h('nav', { class: 'studio-list' },
      cols.map(c => h('a', { href: '#/studio/' + c.id, class: c.id === sel?.id ? 'on' : '' }, `${c.icon} ${c.name}${c.archived ? ' (arquivada)' : ''}`)),
      h('button', { class: 'primary', onclick: newCollection }, 'Nova coleção'),
      h('a', { href: '#/studio/schema', class: selId === 'schema' ? 'on' : '' }, 'Esquema do banco')),
    main));

  async function newCollection() {
    const name = h('input', { type: 'text' }), desc = h('input', { type: 'text' });
    await modal('Nova coleção', h('div', { class: 'form' }, row('Nome', name), row('Descrição (opcional)', desc)), {
      actions: [{ label: 'Cancelar' }, { label: 'Criar coleção', kind: 'primary', run: async () => {
        try {
          const c = await api.createCollection({ name: name.value, description: desc.value });
          await ctx.refresh(); toast('Coleção criada'); location.hash = '#/studio/' + c.id; ctx.render();
        } catch (e) { toast(e.message, 'error'); return false; }
      } }],
    });
  }

  if (selId === 'schema') {
    main.append(h('div', { class: 'blocks' }, cols.map(c => h('article', { class: 'block', style: `border-top-color:${c.color}` },
      h('h3', {}, `${c.icon} ${c.name}`),
      h('ul', {}, c.fields.map(f => h('li', {}, h('span', {}, f.name), h('span', { class: 'muted' },
        f.type.startsWith('reference') ? `${TYPE_LABELS[f.type]}: ${cols.find(x => x.id === f.options.target)?.name || '?'}` : TYPE_LABELS[f.type]))))))));
    return;
  }
  if (!sel) { main.append(h('p', { class: 'empty' }, 'Escolha uma coleção para configurar ou crie uma nova.')); return; }

  // Dados da coleção
  const name = h('input', { type: 'text', value: sel.name }), desc = h('input', { type: 'text', value: sel.description || '' });
  const icon = h('input', { type: 'text', value: sel.icon, maxlength: 4 }), color = h('input', { type: 'color', value: sel.color });
  const arch = h('input', { type: 'checkbox' }); arch.checked = sel.archived;
  main.append(h('section', { class: 'panel form' },
    h('h2', {}, 'Coleção'), row('Nome exibido', name), row('Descrição', desc), row('Ícone', icon), row('Cor de identificação', color), check('Arquivar (oculta da navegação)', arch),
    h('div', { class: 'inline' },
      h('button', { class: 'primary', onclick: async () => {
        try { await api.updateCollection(sel.id, { name: name.value, description: desc.value, icon: icon.value, color: color.value, archived: arch.checked }); toast('Coleção salva'); await done(); } catch (e) { toast(e.message, 'error'); }
      } }, 'Salvar coleção'),
      h('button', { class: 'danger', onclick: async () => {
        try {
          if (await withConfirm(c => api.deleteCollection(sel.id, c)) !== undefined) { toast('Coleção excluída'); location.hash = '#/studio'; await ctx.refresh(); ctx.render(); }
        } catch (e) { toast(e.message, 'error'); }
      } }, 'Excluir coleção'))));

  // Campos
  async function move(i, d) {
    const arr = [...sel.fields]; [arr[i], arr[i + d]] = [arr[i + d], arr[i]];
    try { for (const [idx, f] of arr.entries()) if (f.position !== idx) await api.updateField(f.id, { position: idx }); await done(); } catch (e) { toast(e.message, 'error'); }
  }

  function fieldRow(f, i) {
    const actions = h('div', { class: 'inline' },
      h('button', { onclick: () => fieldDialog(sel, f) }, 'Editar'),
      h('button', { disabled: i === 0, onclick: () => move(i, -1), 'aria-label': 'Mover para cima' }, 'Subir'),
      h('button', { disabled: i === sel.fields.length - 1, onclick: () => move(i, 1), 'aria-label': 'Mover para baixo' }, 'Descer'),
      h('button', { class: 'danger', onclick: async () => {
        try { if (await withConfirm(c => api.deleteField(f.id, c)) !== undefined) { toast('Campo excluído'); await done(); } } catch (e) { toast(e.message, 'error'); }
      } }, 'Excluir'));
    return h('tr', { style: 'cursor:default' },
      h('td', {}, f.name + (f.is_primary ? ' (principal)' : '')),
      h('td', {}, TYPE_LABELS[f.type]),
      h('td', {}, f.required ? 'Sim' : 'Não'),
      h('td', {}, f.hidden ? 'Não' : 'Sim'),
      h('td', {}, actions));
  }

  main.append(h('section', { class: 'panel' },
    h('div', { class: 'toolbar' }, h('h2', {}, 'Campos'), h('span', { class: 'grow' }), h('button', { class: 'primary', onclick: () => fieldDialog(sel, null) }, 'Adicionar campo')),
    h('div', { class: 'tablewrap' }, h('table', {}, h('thead', {}, h('tr', {}, ['Nome', 'Tipo', 'Obrigatório', 'Visível', ''].map(t => h('th', {}, t)))),
      h('tbody', {}, sel.fields.map(fieldRow))))));

  async function fieldDialog(c, f) {
    const name = h('input', { type: 'text', value: f?.name || '' }), desc = h('input', { type: 'text', value: f?.description || '' });
    const type = h('select', {}, Object.entries(TYPE_LABELS).map(([k, v]) => h('option', { value: k }, v)));
    type.value = f?.type || 'short_text';
    const req = h('input', { type: 'checkbox' }), hid = h('input', { type: 'checkbox' }), prim = h('input', { type: 'checkbox' });
    req.checked = !!f?.required; hid.checked = !!f?.hidden; prim.checked = !!f?.is_primary; prim.disabled = !!f?.is_primary;
    const choices = h('textarea', { rows: 4, placeholder: 'Uma opção por linha' }); choices.value = (f?.options.choices || []).join('\n');
    const target = h('select', {}, ctx.collections.map(x => h('option', { value: x.id }, x.name))); target.value = f?.options.target || ctx.collections[0].id;
    const rc = row('Opções', choices), rt = row('Coleção referenciada', target);
    const sync = () => { rc.hidden = type.value !== 'select'; rt.hidden = !type.value.startsWith('reference'); };
    type.onchange = sync; sync();
    await modal(f ? 'Editar campo' : 'Novo campo', h('div', { class: 'form' }, row('Nome', name), row('Descrição', desc), row('Tipo', type), rc, rt,
      check('Obrigatório', req), check('Ocultar nas tabelas', hid), check('Campo principal (identifica o registro)', prim)), {
      actions: [{ label: 'Cancelar' }, { label: 'Salvar campo', kind: 'primary', run: async () => {
        const options = type.value === 'select' ? { choices: choices.value.split('\n').map(s => s.trim()).filter(Boolean) } : type.value.startsWith('reference') ? { target: target.value } : {};
        const data = { name: name.value, description: desc.value, type: type.value, required: req.checked, hidden: hid.checked, options };
        try {
          if (f) {
            if (prim.checked && !f.is_primary) data.is_primary = true;
            if (await withConfirm(cf => api.updateField(f.id, { ...data, confirm: cf })) === undefined) return false;
          } else {
            const nf = await api.addField(c.id, data);
            if (prim.checked) await api.updateField(nf.id, { is_primary: true });
          }
          toast('Campo salvo'); await done();
        } catch (e) { toast(e.message, 'error'); return false; }
      } }],
    });
  }
}
