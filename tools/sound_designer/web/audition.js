'use strict';
window.DesignAudition = (() => {
  let a = null, b = null, selected = 'b', notice;
  const player = () => document.getElementById('preview');
  function show(which) {
    const item = which === 'a' ? a : b;
    if (!item) return;
    const audio = player(), resume = !audio.paused;
    audio.pause();
    selected = which;
    audio.src = item.audio;
    document.getElementById('auditionLabel').textContent = which.toUpperCase() + ' · ' + item.label;
    for (const key of ['a', 'b']) document.getElementById('listen' + key.toUpperCase()).setAttribute('aria-pressed', String(key === which));
    if (resume) audio.play().catch(() => {});
  }
  function pin(value) {
    a = value;
    localStorage.setItem('vslSoundComparison', JSON.stringify(a));
    document.getElementById('listenA').disabled = false;
    notice('已保留对照 A；A/B共用一个播放器与音量，不做自动响度补偿。');
  }
  function setup(message) {
    notice = message;
    try {
      const saved = JSON.parse(localStorage.getItem('vslSoundComparison'));
      if (saved && new URL(saved.audio, location).origin === location.origin && saved.audio.startsWith('/files/')) a = saved;
    } catch {}
    document.getElementById('listenA').onclick = () => show('a');
    document.getElementById('listenB').onclick = () => show('b');
    document.getElementById('pinA').onclick = () => { if (b) pin({...b}); };
    for (const audio of [player(), document.getElementById('reference')]) {
      audio.addEventListener('play', () => {
        for (const other of document.querySelectorAll('audio')) if (other !== audio) other.pause();
      });
    }
    updateButtons(false);
  }
  function updateButtons(busy) {
    document.getElementById('listenA').disabled = busy || !a;
    document.getElementById('listenB').disabled = busy || !b;
    document.getElementById('pinA').disabled = busy || !b;
  }
  function update(project) {
    b = project.last_version ? {audio: `/files/${project.id}/${project.last_version}/preview.wav`,
      label: `${project.name} · ${project.last_version.slice(0, 6)}`} : null;
    if (b) show('b');
    else {
      selected = 'b';
      document.getElementById('auditionLabel').textContent = '先生成 B，再保留为 A 作比较';
      for (const key of ['a', 'b']) document.getElementById('listen' + key.toUpperCase()).setAttribute('aria-pressed', 'false');
    }
    updateButtons(false);
  }
  return {setup, update, updateButtons, pin};
})();
