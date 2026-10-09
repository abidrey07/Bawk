let supervisor = null, registering = false, profilePhoto = '', photoLoading = false;
function greetingFor(date) {
  const hour = date.getHours();
  return hour >= 5 && hour < 12 ? 'Good morning' : hour >= 12 && hour < 17 ? 'Good afternoon' : 'Good evening';
}
function fullName(person) {
  return [person.first_name, person.last_name].filter(Boolean).join(' ');
}
function profileFormName() {
  return fullName({ first_name: $('supervisor-first-name').value.trim(), last_name: $('supervisor-last-name').value.trim() });
}
function updateGreeting() {
  $('greeting').textContent = supervisor ? `${greetingFor(new Date())}, ${supervisor.first_name}` : 'Welcome to Bawk';
}
function showAvatar(container, name, photo) {
  container.replaceChildren();
  if (photo) {
    const image = document.createElement('img'); image.src = photo; image.alt = ''; container.append(image);
  } else container.textContent = name.trim().split(/\s+/).slice(0, 2).map(word => word[0] || '').join('').toUpperCase() || '🙂';
}
function closeAccountMenu() { $('account-menu').hidden = true; $('account-toggle').setAttribute('aria-expanded', 'false'); }
function showSupervisor(value) {
  supervisor = value;
  $('account-access').hidden = Boolean(value);
  $('supervisor-workspace').hidden = !value;
  $('supervisor-account').hidden = !value;
  closeAccountMenu(); updateGreeting();
  if (value) {
    $('supervisor-name').textContent = fullName(value);
    showAvatar($('supervisor-avatar'), fullName(value), value.photo);
  } else {
    workspace = { clients: [], goals: [], sets: [], responses: [] };
    clientId = null; selectedGoalId = null; profileDirty = false; detailsOpen = false;
    resetEditor(); render();
    $('supervisor-name').textContent = ''; $('supervisor-avatar').replaceChildren();
  }
}
$('access-switch').onclick = () => {
  registering = !registering;
  $('register-name-row').hidden = !registering; $('register-first-name').required = registering;
  $('register-note').hidden = !registering;
  $('access-title').textContent = registering ? 'Create your supervisor account' : 'Sign in to your supervisor account';
  $('access-submit').textContent = registering ? 'Create account' : 'Sign in';
  $('access-switch').textContent = registering ? 'Already have an account? Sign in' : 'Create an account';
  $('account-password').autocomplete = registering ? 'new-password' : 'current-password';
  $('access-status').textContent = '';
};
$('account-form').onsubmit = async e => {
  e.preventDefault(); $('access-submit').disabled = true; $('access-switch').disabled = true;
  $('access-status').textContent = '';
  try {
    const result = await api(`account/${registering ? 'register' : 'login'}`, {
      first_name: $('register-first-name').value.trim(), last_name: $('register-last-name').value.trim(), email: $('account-email').value.trim(), password: $('account-password').value
    });
    $('account-password').value = ''; showSupervisor(result.supervisor); await refresh(); status('');
  } catch (error) { $('access-status').textContent = error.message; }
  finally { $('access-submit').disabled = false; $('access-switch').disabled = false; }
};
$('account-toggle').onclick = () => {
  const open = $('account-menu').hidden; $('account-menu').hidden = !open;
  $('account-toggle').setAttribute('aria-expanded', String(open));
};
document.addEventListener('click', e => { if (!$('supervisor-account').contains(e.target)) closeAccountMenu(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeAccountMenu(); });
$('edit-supervisor').onclick = () => {
  closeAccountMenu(); profilePhoto = supervisor.photo;
  $('supervisor-first-name').value = supervisor.first_name; $('supervisor-last-name').value = supervisor.last_name; $('supervisor-email').value = supervisor.email;
  $('current-password').value = ''; $('new-password').value = ''; $('supervisor-photo').value = '';
  $('supervisor-profile-status').textContent = ''; showAvatar($('profile-photo-preview'), fullName(supervisor), profilePhoto);
  $('supervisor-settings').showModal();
};
$('close-supervisor-settings').onclick = () => $('supervisor-settings').close();
$('remove-supervisor-photo').onclick = () => {
  profilePhoto = ''; $('supervisor-photo').value = '';
  showAvatar($('profile-photo-preview'), profileFormName(), profilePhoto);
};
$('supervisor-photo').onchange = async e => {
  const file = e.target.files[0]; if (!file) return;
  $('supervisor-profile-status').textContent = ''; photoLoading = true;
  try {
    if (!['image/jpeg', 'image/png'].includes(file.type) || file.size > 10 * 1024 * 1024) throw new Error('Choose a JPEG or PNG photo under 10 MB.');
    const bitmap = await createImageBitmap(file);
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = 256;
    const context = canvas.getContext('2d'); context.fillStyle = '#fff8e8'; context.fillRect(0, 0, 256, 256);
    const side = Math.min(bitmap.width, bitmap.height);
    context.drawImage(bitmap, (bitmap.width - side) / 2, (bitmap.height - side) / 2, side, side, 0, 0, 256, 256);
    bitmap.close(); profilePhoto = canvas.toDataURL('image/jpeg', 0.85);
    showAvatar($('profile-photo-preview'), profileFormName(), profilePhoto);
  } catch (error) { $('supervisor-profile-status').textContent = error.message; }
  finally { photoLoading = false; }
};
$('supervisor-profile-form').onsubmit = async e => {
  e.preventDefault(); if (photoLoading) { $('supervisor-profile-status').textContent = 'Please wait for the photo to finish loading.'; return; }
  const submit = e.submitter; if (submit) submit.disabled = true;
  try {
    const result = await api('account/profile', { first_name: $('supervisor-first-name').value.trim(), last_name: $('supervisor-last-name').value.trim(), photo: profilePhoto,
      current_password: $('current-password').value, new_password: $('new-password').value });
    showSupervisor(result.supervisor); $('supervisor-settings').close(); status('Profile updated.');
  } catch (error) { $('supervisor-profile-status').textContent = error.message; }
  finally { if (submit) submit.disabled = false; }
};
$('sign-out').onclick = async () => {
  if ((dirty || profileDirty) && !confirm('Sign out and discard unsaved changes?')) return;
  try { await api('account/logout', {}); showSupervisor(null); status('Signed out.'); }
  catch (error) { status(error.message, true); }
};
window.addEventListener('bawk-session-expired', () => {
  $('supervisor-settings').close(); showSupervisor(null); status('Your session expired. Please sign in again.');
});
window.setInterval(updateGreeting, 60000);
document.addEventListener('visibilitychange', updateGreeting);
api('session').then(async result => { showSupervisor(result.supervisor); if (result.supervisor) await refresh(); })
  .catch(error => { showSupervisor(null); status(error.message, true); });
