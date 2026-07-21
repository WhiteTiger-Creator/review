var API = '/api/notes';
var editingId = null;
var API_KEY = 'tb3_notes_api_secret_2026';

function authHeaders() {
    return { 'Content-Type': 'application/json', 'X-API-Key': API_KEY };
}

async function fetchNotes() {
    var res = await fetch(API);
    var notes = await res.json();
    var list = document.getElementById('notes-list');
    list.innerHTML = '';
    notes.forEach(function(note) {
        var card = document.createElement('div');
        card.className = 'note-card';
        card.setAttribute('data-id', note.id);

        var h3 = document.createElement('h3');
        h3.textContent = note.title;
        var p = document.createElement('p');
        p.textContent = note.content;

        var actions = document.createElement('div');
        actions.className = 'note-actions';

        var editBtn = document.createElement('button');
        editBtn.className = 'edit-btn';
        editBtn.textContent = 'Edit';
        editBtn.addEventListener('click', function() { startEdit(note); });

        var deleteBtn = document.createElement('button');
        deleteBtn.className = 'delete-btn';
        deleteBtn.textContent = 'Delete';
        deleteBtn.addEventListener('click', function() { deleteNote(note.id); });

        actions.appendChild(editBtn);
        actions.appendChild(deleteBtn);
        card.appendChild(h3);
        card.appendChild(p);
        card.appendChild(actions);
        list.appendChild(card);
    });
}

function startEdit(note) {
    editingId = note.id;
    document.getElementById('note-title').value = note.title;
    document.getElementById('note-content').value = note.content;
    document.getElementById('btn-submit').textContent = 'Update';
}

function clearForm() {
    document.getElementById('note-title').value = '';
    document.getElementById('note-content').value = '';
    editingId = null;
    document.getElementById('btn-submit').textContent = 'Save';
}

async function deleteNote(id) {
    await fetch(API + '/' + id, {
        method: 'DELETE',
        headers: authHeaders()
    });
    fetchNotes();
}

document.getElementById('note-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    var title = document.getElementById('note-title').value;
    var content = document.getElementById('note-content').value;

    if (editingId) {
        await fetch(API + '/' + editingId, {
            method: 'PUT',
            headers: authHeaders(),
            body: JSON.stringify({ title: title, content: content })
        });
    } else {
        await fetch(API, {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({ title: title, content: content })
        });
    }

    clearForm();
    fetchNotes();
});

fetchNotes();
