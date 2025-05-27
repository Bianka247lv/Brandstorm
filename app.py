from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import sqlite3
import os
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'brandstorm-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")


# Initialize database
def init_db():
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        user TEXT NOT NULL,
        upvotes INTEGER DEFAULT 0,
        downvotes INTEGER DEFAULT 0
    )
    ''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        suggestion_id INTEGER,
        user TEXT NOT NULL,
        vote TEXT NOT NULL,
        FOREIGN KEY (suggestion_id) REFERENCES suggestions (id)
    )
    ''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT NOT NULL,
        message TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/suggestions', methods=['GET'])
def get_suggestions():
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    c.execute("SELECT id, name, user, upvotes, downvotes FROM suggestions ORDER BY id DESC")
    suggestions = [{'id': row[0], 'name': row[1], 'user': row[2], 'upvotes': row[3], 'downvotes': row[4]} for row in c.fetchall()]
    conn.close()
    return jsonify(suggestions)

@app.route('/api/suggestions', methods=['POST'])
def add_suggestion():
    data = request.json
    name = data.get('name')
    user = data.get('user')
    
    if not name or not user:
        return jsonify({'error': 'Name and user are required'}), 400
    
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    c.execute("INSERT INTO suggestions (name, user) VALUES (?, ?)", (name, user))
    suggestion_id = c.lastrowid
    conn.commit()
    conn.close()
    
    suggestion = {
        'id': suggestion_id,
        'name': name,
        'user': user,
        'upvotes': 0,
        'downvotes': 0
    }
    
    socketio.emit('new_suggestion', suggestion)
    return jsonify(suggestion)

@app.route('/api/suggestions/<int:suggestion_id>/vote', methods=['POST'])
def vote_suggestion(suggestion_id):
    data = request.json
    vote_type = data.get('vote')
    user = data.get('user')
    
    if not vote_type or not user:
        return jsonify({'error': 'Vote type and user are required'}), 400
    
    if vote_type not in ['up', 'down']:
        return jsonify({'error': 'Vote type must be "up" or "down"'}), 400
    
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    
    # Check if user has already voted
    c.execute("SELECT vote FROM votes WHERE suggestion_id = ? AND user = ?", (suggestion_id, user))
    existing_vote = c.fetchone()
    
    if existing_vote:
        existing_vote_type = existing_vote[0]
        if existing_vote_type == vote_type:
            # User is voting the same way, remove their vote
            c.execute("DELETE FROM votes WHERE suggestion_id = ? AND user = ?", (suggestion_id, user))
            vote_value = -1 if vote_type == 'up' else 1
            vote_column = 'upvotes' if vote_type == 'up' else 'downvotes'
            c.execute(f"UPDATE suggestions SET {vote_column} = {vote_column} - 1 WHERE id = ?", (suggestion_id,))
        else:
            # User is changing their vote
            c.execute("UPDATE votes SET vote = ? WHERE suggestion_id = ? AND user = ?", (vote_type, suggestion_id, user))
            if vote_type == 'up':
                c.execute("UPDATE suggestions SET upvotes = upvotes + 1, downvotes = downvotes - 1 WHERE id = ?", (suggestion_id,))
            else:
                c.execute("UPDATE suggestions SET upvotes = upvotes - 1, downvotes = downvotes + 1 WHERE id = ?", (suggestion_id,))
    else:
        # New vote
        c.execute("INSERT INTO votes (suggestion_id, user, vote) VALUES (?, ?, ?)", (suggestion_id, user, vote_type))
        vote_column = 'upvotes' if vote_type == 'up' else 'downvotes'
        c.execute(f"UPDATE suggestions SET {vote_column} = {vote_column} + 1 WHERE id = ?", (suggestion_id,))
    
    conn.commit()
    
    # Get updated suggestion
    c.execute("SELECT id, name, user, upvotes, downvotes FROM suggestions WHERE id = ?", (suggestion_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return jsonify({'error': 'Suggestion not found'}), 404
    
    suggestion = {
        'id': row[0],
        'name': row[1],
        'user': row[2],
        'upvotes': row[3],
        'downvotes': row[4]
    }
    
    socketio.emit('vote_update', suggestion)
    return jsonify(suggestion)

@app.route('/api/suggestions/<int:suggestion_id>', methods=['PUT'])
def edit_suggestion(suggestion_id):
    data = request.json
    name = data.get('name')
    user = data.get('user')
    
    if not name or not user:
        return jsonify({'error': 'Name and user are required'}), 400
    
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    
    # Check if suggestion exists and belongs to user
    c.execute("SELECT user FROM suggestions WHERE id = ?", (suggestion_id,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        return jsonify({'error': 'Suggestion not found'}), 404
    
    if row[0] != user:
        conn.close()
        return jsonify({'error': 'You can only edit your own suggestions'}), 403
    
    c.execute("UPDATE suggestions SET name = ? WHERE id = ?", (name, suggestion_id))
    conn.commit()
    
    # Get updated suggestion
    c.execute("SELECT id, name, user, upvotes, downvotes FROM suggestions WHERE id = ?", (suggestion_id,))
    row = c.fetchone()
    conn.close()
    
    suggestion = {
        'id': row[0],
        'name': row[1],
        'user': row[2],
        'upvotes': row[3],
        'downvotes': row[4]
    }
    
    socketio.emit('suggestion_edited', suggestion)
    return jsonify(suggestion)

@app.route('/api/suggestions/<int:suggestion_id>', methods=['DELETE'])
def delete_suggestion(suggestion_id):
    data = request.json
    user = data.get('user')
    
    if not user:
        return jsonify({'error': 'User is required'}), 400
    
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    
    # Check if suggestion exists and belongs to user
    c.execute("SELECT user FROM suggestions WHERE id = ?", (suggestion_id,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        return jsonify({'error': 'Suggestion not found'}), 404
    
    if row[0] != user:
        conn.close()
        return jsonify({'error': 'You can only delete your own suggestions'}), 403
    
    c.execute("DELETE FROM votes WHERE suggestion_id = ?", (suggestion_id,))
    c.execute("DELETE FROM suggestions WHERE id = ?", (suggestion_id,))
    conn.commit()
    conn.close()
    
    socketio.emit('suggestion_deleted', {'id': suggestion_id})
    return jsonify({'success': True})

@app.route('/api/chat', methods=['GET'])
def get_chat_messages():
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    c.execute("SELECT user, message FROM chat_messages ORDER BY id ASC")
    messages = [{'user': row[0], 'message': row[1]} for row in c.fetchall()]
    conn.close()
    return jsonify(messages)

@app.route('/api/chat/clear', methods=['POST'])
def clear_chat_messages():
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    c.execute("DELETE FROM chat_messages")
    conn.commit()
    conn.close()
    
    socketio.emit('chat_cleared')
    return jsonify({'success': True})

@socketio.on('chat_message')
def handle_chat_message(data):
    user = data.get('user')
    message = data.get('message')
    
    if not user or not message:
        return
    
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    c.execute("INSERT INTO chat_messages (user, message) VALUES (?, ?)", (user, message))
    conn.commit()
    conn.close()
    
    socketio.emit('new_chat_message', {'user': user, 'message': message})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)

