var API = 'http://localhost:9090/api/notes';

var editingId = null;

async function fetchNotes() {
    var res = await fetch(API);
    var notes = await res.json();
    var list = document.getElementById('notes-list');
    list.innerHTML = '';
    notes.forEach(function(note) {
        var card = document.createElement('div');
        card.className = 'note-card';
        card.innerHTML = '<h3>' + note.title + '</h3><p>' + note.content + '</p>';
        list.appendChild(card);
    });
}

document.getElementById('note-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    var title = document.getElementById('note-title').value;
    var content = document.getElementById('note-content').value;

    await fetch(API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title, content: content })
    });

    fetchNotes();
});

fetchNotes();
