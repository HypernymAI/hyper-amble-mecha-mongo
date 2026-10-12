document.getElementById('back').addEventListener('click', () => {
  if (window.parent !== window) {
    window.parent.postMessage({type: 'presents:leave-terminal'}, location.origin);
  } else {
    location.href = '/hypernym/presents/#now';
  }
});
