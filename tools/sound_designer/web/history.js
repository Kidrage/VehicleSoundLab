'use strict';
window.DesignHistory = (() => {
  let api, revisions = [], generation = 0;
  const select = () => document.getElementById('historyList');
  function setup(callbacks) {
    api = callbacks;
    document.getElementById('restoreHistory').onclick = () => api.guarded(async () => {
      const revision = select().value;
      if (!revision) throw Error('请先选择历史版本');
      const id = api.getProject().id;
      await api.savePending();
      api.load(await api.task('/api/restore', {id, revision}, '恢复参数、模型与参考选区…'));
      api.notice('历史版本已恢复；恢复前的调参也保存在历史里。');
    });
    document.getElementById('historyAsA').onclick = () => api.guarded(async () => {
      const item = revisions.find(r => r.id === select().value);
      if (!item?.preview_version) throw Error('该版本没有对应试听，请选择“生成试听”的版本');
      window.DesignAudition.pin({audio: `/files/${api.getProject().id}/${item.preview_version}/preview.wav`,
        label: `${item.name} · ${item.preview_version.slice(0, 6)}`});
    });
  }
  async function refresh(project) {
    const requestGeneration = ++generation;
    const values = await api.request('/api/history/' + project.id);
    if (api.getProject()?.id !== project.id || requestGeneration !== generation) return;
    const chosen = select().value;
    revisions = values;
    select().replaceChildren();
    for (const value of values) {
      const option = document.createElement('option');
      option.value = value.id;
      option.textContent = `${new Date(value.created).toLocaleString()} · ${value.action}${value.preview_version ? ' · 有试听' : ''}`;
      select().append(option);
    }
    if (values.some(value => value.id === chosen)) select().value = chosen;
    document.getElementById('historyCount').textContent = values.length + ' 个版本';
  }
  return {setup, refresh};
})();
